#!/usr/bin/env python3
"""Summarize recent DayZ server logs and highlight likely startup blockers."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FATAL_PATTERNS = [
    ("termination", re.compile(r"\btermination in:|\[ERROR\]\[Server config\]|server config.*invalid", re.I)),
    ("no-spawns", re.compile(r"NO VALID SPAWNS|no valid regular player spawn points", re.I)),
    ("missing-file", re.compile(r"cannot open file|cannot load file|missing .*pbo|file .* not found", re.I)),
    ("mod-load", re.compile(r"mod .* failed|unable to load mod|dependency .* missing|wrong signature", re.I)),
    ("port-bind", re.compile(r"bind failed|address already in use|steamgameserver_init.*failed|port .* already", re.I)),
    ("script-error", re.compile(r"\bSCRIPT\s+ERROR\b|\bNULL pointer\b|\bClass .* not found\b", re.I)),
]

WARNING_PATTERNS = [
    ("inputs", re.compile(r"Cannot Register .* input|Fix Preset", re.I)),
    ("ce-warning", re.compile(r"\[CE\].*warning|cfgignorelist", re.I)),
    ("config-noise", re.compile(r"Warning Message: No entry", re.I)),
    ("generic", re.compile(r"\bwarning\b|!!!", re.I)),
]


@dataclass
class Finding:
    label: str
    line: str


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def launch_maps() -> dict:
    return read_json(ROOT / "admin" / "map_launch.json").get("maps", {})


def newest_log(profile_dir: Path) -> Path | None:
    if not profile_dir.exists():
        return None
    for patterns in (("*.RPT",), ("*.log", "*.adm")):
        candidates = [
            path
            for pattern in patterns
            for path in profile_dir.rglob(pattern)
            if path.is_file()
        ]
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime)
    return None


def tail_lines(path: Path, limit: int) -> list[str]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return text.splitlines()[-limit:]


def collect_findings(lines: list[str], patterns: list[tuple[str, re.Pattern[str]]], max_per_label: int) -> list[Finding]:
    counts: dict[str, int] = {}
    findings: list[Finding] = []
    for line in lines:
        for label, pattern in patterns:
            if pattern.search(line):
                if counts.get(label, 0) < max_per_label:
                    findings.append(Finding(label, line.strip()))
                    counts[label] = counts.get(label, 0) + 1
                break
    return findings


def summarize_map(map_name: str, config: dict, tail: int, max_per_label: int) -> int:
    profile = ROOT / config.get("profiles_dir", "")
    log = newest_log(profile)
    if not log:
        print(f"{map_name:9} no logs found in {profile.name}")
        return 0

    lines = tail_lines(log, tail)
    fatals = collect_findings(lines, FATAL_PATTERNS, max_per_label)
    warnings = collect_findings(lines, WARNING_PATTERNS, max_per_label)
    connect_ready = any("Player connect enabled" in line for line in lines)
    status = "BLOCKER" if fatals else ("READY" if connect_ready else "CHECK")
    rel_log = log.relative_to(ROOT) if log.is_relative_to(ROOT) else log
    print(f"{map_name:9} {status:7} {rel_log}")
    if fatals:
        for finding in fatals[:8]:
            print(f"  fatal/{finding.label}: {finding.line[:180]}")
    elif warnings:
        labels = ", ".join(sorted({finding.label for finding in warnings}))
        print(f"  warnings: {labels}")
    if not fatals and not connect_ready:
        print("  hint: no recent 'Player connect enabled' line in scanned tail")
    return 1 if fatals else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", default="all", help="Map key from admin/map_launch.json, or all.")
    parser.add_argument("--tail", type=int, default=800, help="Lines to scan from the newest log.")
    parser.add_argument("--max-per-label", type=int, default=2, help="Repeated finding limit per category.")
    args = parser.parse_args()

    maps = launch_maps()
    selected = maps if args.map == "all" else {args.map: maps[args.map]} if args.map in maps else {}
    if not selected:
        print(f"Unknown map: {args.map}")
        return 2

    blockers = 0
    for name, config in selected.items():
        blockers += summarize_map(name, config, args.tail, args.max_per_label)
    if blockers:
        print(f"\nBlockers found: {blockers}. Use admin\\recover_imported_map.ps1 for imported-map recovery.")
        return 1
    print("\nNo fatal startup blockers found in scanned log tails.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
