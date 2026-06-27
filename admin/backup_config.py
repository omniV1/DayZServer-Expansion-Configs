#!/usr/bin/env python3
"""Back up disk-only / gitignored server CONFIG to a rotated local zip.

This fills the gap between the two existing tools:
  - snapshot_configs.py only zips git-TRACKED files, so the gitignored stock
    mission CE (mod_ce, expansion_ce, cfgeconomycore, cfgeventspawns, globals,
    mapgroupproto) and the profiles_* settings are NOT captured by it.
  - backup_storage.py only covers player persistence (storage_*).

A DayZ/Steam update or a Workshop re-download can silently wipe those config
artifacts, undoing hand-tuning. This makes a self-contained archive of them.

Captured: per-map mission config (cfg*.xml, db/*.xml, mapgroup*.xml, init.c,
mod_ce/, expansion_ce/, expansion/settings/), profile settings (ExpansionMod,
PermissionsFramework, CommunityOnlineTools, CodeLock, configs), mod signing
keys (keys/*.bikey), server cfgs (serverDZ_*.cfg), and admin config (*.json,
*.txt). NOT captured: @mod PBO folders (re-downloadable from Workshop) or
storage_* (use backup_storage.py for that).

  python backup_config.py                    # create a backup
  python backup_config.py --list
  python backup_config.py --retention 20
  python backup_config.py --restore <zip>    # dry list of what would restore
  python backup_config.py --restore <zip> --yes
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
BACKUP_ROOT = ROOT / "local_backups" / "config"
SIZE_CAP = 30 * 1024 * 1024  # never pull a PBO/bin into a "config" backup

CONFIG_SUFFIXES = {".xml", ".json", ".c", ".txt", ".cfg"}
# directories pruned wherever they appear (huge / re-downloadable / regenerated)
PRUNE_DIR_EXACT = {"battleye", "BattlEye", ".git"}


def _prune_dirs(dirs: list[str]) -> list[str]:
    keep = []
    for d in dirs:
        if d.startswith("@") or d.startswith("storage_") or d in PRUNE_DIR_EXACT:
            continue
        keep.append(d)
    return keep


def _walk(base: Path, suffixes: set[str]) -> list[Path]:
    out: list[Path] = []
    if not base.exists():
        return out
    for root, dirs, files in os.walk(base):
        dirs[:] = _prune_dirs(dirs)
        for fname in files:
            p = Path(root) / fname
            if p.suffix.lower() not in suffixes:
                continue
            try:
                if p.stat().st_size > SIZE_CAP:
                    continue
            except OSError:
                continue
            out.append(p)
    return out


def collect_files() -> list[Path]:
    files: set[Path] = set()

    # Per-map mission config (everything config-shaped under each mission,
    # minus storage_*/@mods which _walk prunes).
    missions = ROOT / "mpmissions"
    if missions.exists():
        for mission in missions.iterdir():
            if mission.is_dir():
                files.update(_walk(mission, CONFIG_SUFFIXES))

    # Profile settings that carry real config (not logs).
    for prof in sorted(ROOT.glob("profiles*")):
        if not prof.is_dir():
            continue
        for sub in ("ExpansionMod", "PermissionsFramework", "CommunityOnlineTools", "CodeLock", "configs"):
            files.update(_walk(prof / sub, CONFIG_SUFFIXES))

    # Mod signing keys (tiny; re-deriving needs re-downloading every mod).
    for key in (ROOT / "keys").glob("*.bikey"):
        files.add(key)

    # Server configs at the root + admin config files.
    for cfg in ROOT.glob("serverDZ*.cfg"):
        if not cfg.name.lower().endswith(".example.cfg"):
            files.add(cfg)
    admin = ROOT / "admin"
    for pattern in ("*.json", "*.txt"):
        files.update(p for p in admin.glob(pattern) if p.is_file())

    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def create_backup(label: str | None) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(ch for ch in (label or "config") if ch.isalnum() or ch in ("-", "_")).strip("-_") or "config"
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    target = BACKUP_ROOT / f"{stamp}-{safe}.zip"
    files = collect_files()
    total = 0
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("CONFIG_BACKUP.txt", f"DayZ server config backup\nCreated: {stamp}\nFiles: {len(files)}\n")
        for path in files:
            arc = path.relative_to(ROOT).as_posix()
            zf.write(path, arc)
            total += path.stat().st_size
    print(f"Created {target}")
    print(f"Files: {len(files)} | uncompressed {total // 1024} KB | archive {target.stat().st_size // 1024} KB")
    return target


def prune(retention: int) -> list[str]:
    zips = sorted(BACKUP_ROOT.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed: list[str] = []
    for old in zips[max(1, retention):]:
        old.unlink()
        removed.append(old.name)
    return removed


def list_backups() -> int:
    if not BACKUP_ROOT.exists():
        print("No config backups yet.")
        return 0
    zips = sorted(BACKUP_ROOT.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not zips:
        print("No config backups yet.")
        return 0
    for z in zips:
        size = z.stat().st_size // 1024
        when = dt.datetime.fromtimestamp(z.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {z.name}  ({size} KB, {when})")
    return 0


def _safe_member(name: str) -> bool:
    posix = PurePosixPath(name)
    return not (posix.is_absolute() or ".." in posix.parts or name.startswith("@"))


def restore_backup(zip_arg: Path, yes: bool) -> int:
    full = zip_arg if zip_arg.is_absolute() else (BACKUP_ROOT / zip_arg)
    if not full.exists():
        print(f"Backup not found: {full}")
        return 2
    with zipfile.ZipFile(full, "r") as zf:
        members = [m for m in zf.namelist() if m != "CONFIG_BACKUP.txt" and not m.endswith("/")]
        unsafe = [m for m in members if not _safe_member(m)]
        if unsafe:
            print(f"Refusing to restore: unsafe paths in archive ({unsafe[:3]} ...)")
            return 2
        if not yes:
            print(f"Would restore {len(members)} files from {full.name} into {ROOT} (pass --yes to apply):")
            for m in members[:25]:
                print(f"  {m}")
            if len(members) > 25:
                print(f"  ... and {len(members) - 25} more")
            return 0
        for m in members:
            zf.extract(m, ROOT)
        print(f"Restored {len(members)} files from {full.name} into {ROOT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", help="Optional label in the archive name.")
    parser.add_argument("--retention", type=int, default=14, help="Backups to keep (default 14).")
    parser.add_argument("--list", action="store_true", help="List existing config backups.")
    parser.add_argument("--restore", type=Path, help="Restore a backup zip (dry run unless --yes).")
    parser.add_argument("--yes", action="store_true", help="Apply the restore.")
    args = parser.parse_args()

    if args.list:
        return list_backups()
    if args.restore:
        return restore_backup(args.restore, args.yes)

    create_backup(args.label)
    removed = prune(max(1, args.retention))
    if removed:
        print(f"Pruned {len(removed)} old backup(s): {', '.join(removed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
