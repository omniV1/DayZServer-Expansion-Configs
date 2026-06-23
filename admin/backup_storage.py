#!/usr/bin/env python3
"""Back up a map's CE persistence (storage_*) to a rotated local zip.

Best effort by design: a missing mission or storage folder is a warning, not a
failure (exit 0), so this is safe to run as a pre-restart step without aborting
the restart. Backups land in local_backups/storage/<map>/ and are pruned to the
newest --retention per map.

Usage:
  python backup_storage.py --map chernarus
  python backup_storage.py --all --retention 14
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
    data = json.loads(read_text(ROOT / "admin" / "map_launch.json"))
    return data.get("maps", {})


def mission_for(cfg_name: str) -> str:
    """Resolve the mission template from a server .cfg (same field the engine reads)."""
    if not cfg_name:
        return ""
    path = ROOT / cfg_name
    if not path.exists():
        return ""
    match = re.search(r'(?im)^\s*template\s*=\s*"?([^";\r\n]+)', read_text(path))
    return match.group(1).strip() if match else ""


def storage_dirs(mission: str) -> list[Path]:
    base = ROOT / "mpmissions" / mission
    if not mission or not base.exists():
        return []
    return sorted(path for path in base.glob("storage_*") if path.is_dir())


def prune(folder: Path, retention: int) -> list[str]:
    """Keep the newest `retention` zips in folder; return names removed."""
    zips = sorted(folder.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed: list[str] = []
    for old in zips[max(1, retention):]:
        old.unlink()
        removed.append(old.name)
    return removed


def backup_map(map_name: str, cfg: dict, retention: int, stamp: str) -> bool:
    mission = mission_for(str(cfg.get("config", "")))
    dirs = storage_dirs(mission)
    if not dirs:
        print(f"{map_name}: no storage_* found (mission '{mission}'); skipped.")
        return False
    folder = BACKUP_ROOT / map_name
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{map_name}_{stamp}.zip"
    mission_root = ROOT / "mpmissions" / mission
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for sdir in dirs:
            for path in sdir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(mission_root).as_posix())
                    count += 1
    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"{map_name}: archived {count} files ({size_mb:.1f} MB) -> {target.relative_to(ROOT).as_posix()}")
    removed = prune(folder, retention)
    if removed:
        print(f"{map_name}: pruned {len(removed)} old backup(s) (retention {retention}).")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", help="Map key from admin/map_launch.json.")
    parser.add_argument("--all", action="store_true", help="Back up every map.")
    parser.add_argument("--retention", type=int, default=10, help="Backups to keep per map.")
    args = parser.parse_args()

    maps = launch_maps()
    if args.all:
        selected = maps
    elif args.map and args.map in maps:
        selected = {args.map: maps[args.map]}
    else:
        print(f"Unknown or missing map: {args.map}. Use --map <key> or --all.")
        return 2

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    retention = max(1, args.retention)
    for name, cfg in selected.items():
        try:
            backup_map(name, cfg, retention, stamp)
        except Exception as exc:  # noqa: BLE001 - best effort; never block a restart.
            print(f"{name}: backup failed: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
