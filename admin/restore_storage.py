#!/usr/bin/env python3
"""Restore a map's CE persistence from a local storage backup zip.

DESTRUCTIVE: overwrites the live storage_* with the chosen backup, rolling
player progress back to that point. The current storage is archived first
(labeled prerestore) so the restore itself is reversible.

Stop the server for this map before running -- restoring under a live server
corrupts persistence.

Usage:
  python restore_storage.py --map chernarus            # preview (newest backup)
  python restore_storage.py --map chernarus --yes      # restore newest
  python restore_storage.py --map chernarus --backup chernarus_20260623-112231.zip --yes
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = ROOT / "local_backups" / "storage"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def launch_maps() -> dict:
    return json.loads(read_text(ROOT / "admin" / "map_launch.json")).get("maps", {})


def mission_for(cfg_name: str) -> str:
    if not cfg_name:
        return ""
    path = ROOT / cfg_name
    if not path.exists():
        return ""
    match = re.search(r'(?im)^\s*template\s*=\s*"?([^";\r\n]+)', read_text(path))
    return match.group(1).strip() if match else ""


def pick_backup(map_name: str, name: str | None) -> Path | None:
    folder = BACKUP_ROOT / map_name
    if not folder.exists():
        return None
    if name:
        # Guard against path tricks in the requested name.
        if name != Path(name).name or not name.lower().endswith(".zip"):
            return None
        candidate = folder / name
        return candidate if candidate.exists() else None
    zips = sorted(folder.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return zips[0] if zips else None


def archive_current(mission_root: Path, map_name: str, stamp: str) -> tuple[Path, int]:
    target = BACKUP_ROOT / map_name / f"{map_name}_prerestore_{stamp}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for sdir in sorted(mission_root.glob("storage_*")):
            if sdir.is_dir():
                for path in sdir.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(mission_root).as_posix())
                        count += 1
    return target, count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True)
    parser.add_argument("--backup", help="Backup zip filename (default: newest for the map).")
    parser.add_argument("--yes", action="store_true", help="Confirm the destructive restore.")
    args = parser.parse_args()

    maps = launch_maps()
    if args.map not in maps:
        print(f"Unknown map: {args.map}")
        return 2
    mission = mission_for(str(maps[args.map].get("config", "")))
    mission_root = ROOT / "mpmissions" / mission
    if not mission or not mission_root.exists():
        print(f"Could not resolve mission folder for {args.map} (mission '{mission}').")
        return 2

    backup = pick_backup(args.map, args.backup)
    if not backup:
        suffix = f" named {args.backup}" if args.backup else ""
        print(f"No storage backup found for {args.map}{suffix}.")
        return 2

    if not args.yes:
        print(
            f"Would restore {backup.name} into {mission_root.relative_to(ROOT).as_posix()} "
            f"(overwrites live storage). Stop the map, then re-run with --yes."
        )
        return 1

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safety, count = archive_current(mission_root, args.map, stamp)
    print(f"Pre-restore safety backup: {safety.relative_to(ROOT).as_posix()} ({count} files)")

    with zipfile.ZipFile(backup) as archive:
        root_resolved = str(mission_root.resolve())
        for member in archive.namelist():
            dest = (mission_root / member).resolve()
            if not str(dest).startswith(root_resolved):
                print(f"Refusing unsafe path in backup zip: {member}")
                return 2
        archive.extractall(mission_root)
        restored = len(archive.namelist())

    print(f"Restored {restored} files from {backup.name} into {mission_root.relative_to(ROOT).as_posix()}")
    print("Done. Start the map and confirm storage health (0 failed) on the next boot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
