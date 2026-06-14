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

VPP_ACTIVE_PATTERNS = [
    "@VPPAdminTools",
    "VPPAdminTools",
]


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
    if path.name in {"chernarus_mods.txt", "namalsk_mods.txt", "takistan_mods.txt"}:
        if "@VPPAdminTools" in text:
            errors.append(f"VPP is active in mod list: {path}")
    if path.name.endswith("preset_User.xml") or path.name.endswith("core.xml") or "install_" in path.name:
        for needle in VPP_ACTIVE_PATTERNS:
            if needle in text:
                errors.append(f"Stale VPP reference in {path}: {needle}")


def validate_parse(path: Path, errors: list[str]) -> None:
    full = ROOT / path
    suffix = path.suffix.lower()
    parts = set(path.parts)
    if suffix == ".json" and {"profiles", "ExpansionMod"} <= parts and ("Market" in parts or "Traders" in parts):
        return
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
