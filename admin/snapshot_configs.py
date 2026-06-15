#!/usr/bin/env python3
"""Snapshot and restore public-safe DayZ config files.

Backups are written under admin/backups/, which is intentionally ignored.
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "admin" / "backups"

ALLOWED_PREFIXES = ("admin/", "mpmissions/", "profiles/")
ALLOWED_ROOT_SUFFIXES = (".bat", ".cmd", ".ps1", ".example.cfg", ".md", ".txt")
LOCAL_CONFIG_GLOB = "serverDZ*.cfg"
TEXT_SUFFIXES = {".bat", ".cfg", ".cmd", ".json", ".md", ".ps1", ".py", ".txt", ".xml"}
FORBIDDEN_PARTS = {
    "storage_1",
    "storage_2",
    "storage_3",
    "storage_4",
    "storage_5",
    "storage_6",
    "storage_7",
    "storage_8",
    "storage_9",
    "storage_10",
    "battleye",
    "keys",
    "logs",
    "backup",
    "backups",
    "__pycache__",
}
FORBIDDEN_SUFFIXES = {".exe", ".dll", ".pbo", ".bisign", ".bikey", ".rpt", ".log", ".mdmp", ".adm", ".core", ".storage"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def git_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / line.strip() for line in out.splitlines() if line.strip()]


def is_safe_relative(name: str) -> bool:
    posix = PurePosixPath(name)
    if posix.is_absolute() or ".." in posix.parts:
        return False
    lower_parts = {part.lower() for part in posix.parts}
    if lower_parts & FORBIDDEN_PARTS:
        return False
    if posix.suffix.lower() in FORBIDDEN_SUFFIXES:
        return False
    if name.startswith("@"):
        return False
    return True


def include_tracked(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    name = rel(path)
    if not is_safe_relative(name):
        return False
    if name.startswith(ALLOWED_PREFIXES):
        return path.suffix.lower() in TEXT_SUFFIXES or path.name in {".gitignore"}
    if "/" not in name:
        return path.name.endswith(ALLOWED_ROOT_SUFFIXES) or path.suffix.lower() in {".bat", ".cmd", ".ps1"}
    return False


def collect_files() -> list[Path]:
    files = {path for path in git_files() if include_tracked(path)}
    for path in ROOT.glob(LOCAL_CONFIG_GLOB):
        if path.name.lower().endswith(".example.cfg"):
            continue
        if path.is_file() and is_safe_relative(path.name):
            files.add(path)
    return sorted(files, key=rel)


def create_snapshot(label: str | None) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_label = "".join(ch for ch in (label or "config") if ch.isalnum() or ch in ("-", "_")).strip("-_") or "config"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"{stamp}-{safe_label}.zip"
    files = collect_files()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SNAPSHOT.txt", f"DayZ config snapshot\nCreated: {stamp}\nFiles: {len(files)}\n")
        for path in files:
            zf.write(path, rel(path))
    print(f"Created {target}")
    print(f"Files included: {len(files)}")
    return target


def list_snapshots() -> int:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    snapshots = sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not snapshots:
        print("No snapshots found.")
        return 0
    for path in snapshots:
        size_kb = path.stat().st_size / 1024
        print(f"{path.name:36} {size_kb:8.1f} KB")
    return 0


def restore_snapshot(path: Path, yes: bool) -> int:
    full = path if path.is_absolute() else ROOT / path
    if not full.exists():
        print(f"Snapshot not found: {full}", file=sys.stderr)
        return 1
    if not yes:
        print("Restore requires --yes because it overwrites local files.")
        print(f"Preview target: {full}")
        return 2
    with zipfile.ZipFile(full, "r") as zf:
        names = [name for name in zf.namelist() if name != "SNAPSHOT.txt"]
        unsafe = [name for name in names if not is_safe_relative(name)]
        if unsafe:
            print("Refusing to restore unsafe paths:", file=sys.stderr)
            for name in unsafe:
                print(f"  - {name}", file=sys.stderr)
            return 1
        for name in names:
            target = ROOT / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
    print(f"Restored {len(names)} files from {full}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", help="Short label for a new snapshot name.")
    parser.add_argument("--list", action="store_true", help="List existing local snapshots.")
    parser.add_argument("--restore", type=Path, help="Restore this snapshot zip.")
    parser.add_argument("--yes", action="store_true", help="Required with --restore to overwrite files.")
    args = parser.parse_args()

    if args.list:
        return list_snapshots()
    if args.restore:
        return restore_snapshot(args.restore, args.yes)
    create_snapshot(args.label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
