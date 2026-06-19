#!/usr/bin/env python3
"""Validate that the public DayZ config repo is safe and parseable."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_SUFFIXES = {
    ".exe",
    ".dll",
    ".pbo",
    ".bisign",
    ".bikey",
    ".rpt",
    ".log",
    ".mdmp",
    ".adm",
    ".core",
    ".storage",
}

FORBIDDEN_PARTS = {
    "storage_1",
    "storage_2",
    "storage_3",
    "storage_4",
    "storage_5",
    "battleye",
    "keys",
    "logs",
    "backup",
    "backups",
    "__pycache__",
}

SECRET_PATTERNS = [
    re.compile(r'passwordAdmin\s*=\s*"(?!CHANGE_ME|CHANGEME|REPLACE_ME)[^"]+"', re.I),
    re.compile(r'password\s*=\s*"(?!")[^"]+"', re.I),
    re.compile(r"gho_[A-Za-z0-9_]+"),
    re.compile(r"steam_appid\.txt", re.I),
]

SHARD_ID_PATTERN = re.compile(r'shardId\s*=\s*"([^"]+)"', re.I)
VALID_SHARD_ID = re.compile(r"^[A-Za-z0-9]{4,6}$")

STEAMID_PATTERN = re.compile(r"\b7656\d{13}\b")
STEAMID_ALLOWLIST_NAME = "public_steamid_allowlist.txt"


def load_steamid_allowlist() -> set[str]:
    path = ROOT / "admin" / STEAMID_ALLOWLIST_NAME
    if not path.exists():
        return set()
    allowed: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        allowed.add(entry)
    return allowed


STEAMID_ALLOWLIST = load_steamid_allowlist()

MOD_LIST_NAMES = {"chernarus_mods.txt", "namalsk_mods.txt", "takistan_mods.txt"}
COT_MOD_PATTERNS = ["@Community-Online-Tools", "1564026768"]


def git_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [Path(line.strip()) for line in out.splitlines() if line.strip()]


def read_text(path: Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig", errors="replace")


def is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in {
        ".bat",
        ".cmd",
        ".cfg",
        ".json",
        ".md",
        ".ps1",
        ".py",
        ".txt",
        ".xml",
    } or path.name in {".gitignore", "README.md"}


def validate_path(path: Path, errors: list[str]) -> None:
    if not (ROOT / path).exists():
        errors.append(f"Tracked file missing from working tree: {path}")
        return
    parts = {p.lower() for p in path.parts}
    if path.parts and path.parts[0].startswith("@"):
        errors.append(f"Workshop mod folder tracked: {path}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        errors.append(f"Forbidden file type tracked: {path}")
    if parts & FORBIDDEN_PARTS:
        errors.append(f"Forbidden generated/private path tracked: {path}")
    if path.name.lower().startswith("serverdz") and path.suffix.lower() == ".cfg":
        if not path.name.lower().endswith(".example.cfg"):
            errors.append(f"Real server config tracked: {path}")


def validate_content(path: Path, errors: list[str]) -> None:
    if not is_text_candidate(path):
        return
    text = read_text(path)
    if path.name != ".gitignore":
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"Secret-like content in {path}: {pattern.pattern}")
    if path.name != STEAMID_ALLOWLIST_NAME:
        for steamid in sorted(set(STEAMID_PATTERN.findall(text))):
            if steamid not in STEAMID_ALLOWLIST:
                errors.append(
                    f"SteamID64 in {path}: {steamid} "
                    f"(add it to admin/{STEAMID_ALLOWLIST_NAME} to allow, or remove it)"
                )
    if path.name in MOD_LIST_NAMES:
        if "@VPPAdminTools" not in text:
            errors.append(f"VPP admin tool missing from mod list: {path}")
        for needle in COT_MOD_PATTERNS:
            if needle in text:
                errors.append(f"COT admin tool is active in mod list: {path}")
    if path.name.lower().startswith("serverdz") and path.suffix.lower() == ".cfg":
        match = SHARD_ID_PATTERN.search(text)
        if match and not VALID_SHARD_ID.fullmatch(match.group(1)):
            errors.append(f"Invalid shardId in {path}: {match.group(1)!r} (use 4-6 letters/numbers)")
    if "install_" in path.name:
        for needle in COT_MOD_PATTERNS:
            if needle in text:
                errors.append(f"Stale COT reference in {path}: {needle}")


def validate_parse(path: Path, errors: list[str]) -> None:
    full = ROOT / path
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            json.loads(full.read_text(encoding="utf-8-sig"))
        elif suffix == ".xml":
            ET.parse(full)
    except Exception as exc:  # noqa: BLE001 - report parse failures without hiding detail.
        errors.append(f"Parse failed for {path}: {exc}")


def main() -> int:
    errors: list[str] = []
    files = git_files()
    for path in files:
        validate_path(path, errors)
        validate_content(path, errors)
        validate_parse(path, errors)

    if errors:
        print("Public repo validation FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"Public repo validation OK ({len(files)} tracked files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
