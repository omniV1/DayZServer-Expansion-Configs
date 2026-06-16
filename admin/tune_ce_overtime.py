#!/usr/bin/env python3
"""Reduce CE loot placement overtime learned from recent DayZ RPT logs."""
from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent

OVERTIME_RE = re.compile(r'causing search overtime:\s*"([^"]+)"', re.I)
HARD_RE = re.compile(r'hard to place, performance drops:\s*"([^"]+)"', re.I)
TEMPLATE_RE = re.compile(r'template\s*=\s*"([^"]+)"', re.I)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def latest_rpt(profile_dir: Path) -> Path | None:
    if not profile_dir.exists():
        return None
    rpts = sorted(profile_dir.glob("DayZServer_x64_*.RPT"), key=lambda path: path.stat().st_mtime, reverse=True)
    return rpts[0] if rpts else None


def mission_from_config(config: str) -> str | None:
    path = ROOT / config
    if not path.exists():
        return None
    match = TEMPLATE_RE.search(path.read_text(encoding="utf-8-sig", errors="replace"))
    return match.group(1) if match else None


def collect_log_counts(rpt: Path) -> tuple[Counter[str], Counter[str]]:
    overtime: Counter[str] = Counter()
    hard: Counter[str] = Counter()
    for line in rpt.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        overtime_match = OVERTIME_RE.search(line)
        if overtime_match:
            overtime[overtime_match.group(1)] += 1
        hard_match = HARD_RE.search(line)
        if hard_match:
            hard[hard_match.group(1)] += 1
    return overtime, hard


def set_child_text(element: ET.Element, name: str, value: str) -> bool:
    child = element.find(name)
    if child is None:
        return False
    if child.text == value:
        return False
    child.text = value
    return True


def int_child(element: ET.Element, name: str) -> int | None:
    child = element.find(name)
    if child is None or child.text is None:
        return None
    try:
        return int(child.text)
    except ValueError:
        return None


def cap_child(element: ET.Element, name: str, maximum: int) -> bool:
    value = int_child(element, name)
    if value is None or value <= maximum:
        return False
    return set_child_text(element, name, str(maximum))


def write_tree(tree: ET.ElementTree, path: Path) -> None:
    ET.indent(tree, space="    ")
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def mission_loads_mod_ce(mission_dir: Path) -> bool:
    economy = mission_dir / "cfgeconomycore.xml"
    if not economy.exists():
        return False
    return "mod_ce" in economy.read_text(encoding="utf-8-sig", errors="replace")


def type_files(mission_dir: Path) -> list[Path]:
    files: list[Path] = []
    main_types = mission_dir / "db" / "types.xml"
    if main_types.exists():
        files.append(main_types)
    if not mission_loads_mod_ce(mission_dir):
        return files
    mod_ce = mission_dir / "mod_ce"
    if mod_ce.exists():
        files.extend(sorted(path for path in mod_ce.glob("*.xml") if path.name.endswith("_types.xml") or path.name == "types.xml"))
    return files


def backup_once(path: Path, backup_root: Path, copied: set[Path]) -> None:
    if path in copied:
        return
    dest = backup_root / path.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    copied.add(path)


def tune_types_file(
    path: Path,
    overtime_names: set[str],
    hard_names: set[str],
    backup_root: Path,
    copied: set[Path],
    dry_run: bool,
    disable_overtime: bool,
    overtime_nominal: int,
    hard_nominal: int,
) -> list[str]:
    tree = ET.parse(path)
    root = tree.getroot()
    changed: list[str] = []
    for item_type in root.findall("type"):
        name = item_type.get("name", "")
        key = name.lower()
        if key in overtime_names:
            edits = []
            if disable_overtime:
                for tag in ("nominal", "min"):
                    if set_child_text(item_type, tag, "0"):
                        edits.append(tag)
            else:
                if cap_child(item_type, "nominal", overtime_nominal):
                    edits.append(f"nominal<={overtime_nominal}")
                if cap_child(item_type, "min", 0):
                    edits.append("min=0")
            if edits:
                action = "disable overtime" if disable_overtime else "reduce overtime"
                changed.append(f"{name}:{action}")
            continue
        if key in hard_names:
            edits = []
            if cap_child(item_type, "nominal", hard_nominal):
                edits.append(f"nominal<={hard_nominal}")
            if cap_child(item_type, "min", 0):
                edits.append("min=0")
            if edits:
                changed.append(f"{name}:reduce hard")
    if changed and not dry_run:
        backup_once(path, backup_root, copied)
        write_tree(tree, path)
    return changed


def selected_maps(all_maps: dict, selection: str) -> dict:
    if selection == "all":
        return all_maps
    names = [name.strip().lower() for name in selection.split(",") if name.strip()]
    missing = [name for name in names if name not in all_maps]
    if missing:
        raise SystemExit(f"Unknown map(s): {', '.join(missing)}. Known maps: {', '.join(all_maps)}")
    return {name: all_maps[name] for name in names}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", default="all", help="Map key, comma-separated map keys, or all.")
    parser.add_argument("--min-overtime-count", type=int, default=1, help="Tune types with this many search-overtime hits.")
    parser.add_argument("--min-hard-count", type=int, default=5, help="Reduce hard-to-place-only types with this many hits.")
    parser.add_argument("--disable-overtime", action="store_true", help="Set overtime types to nominal/min 0 instead of capping them.")
    parser.add_argument("--overtime-nominal", type=int, default=1, help="Nominal cap for overtime types unless --disable-overtime is set.")
    parser.add_argument("--hard-nominal", type=int, default=1, help="Nominal cap for hard-to-place-only types.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned edits without writing files.")
    args = parser.parse_args()

    launch = read_json(ROOT / "admin" / "map_launch.json").get("maps", {})
    maps = selected_maps(launch, args.map)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = ROOT / "local_backups" / "ce_overtime" / stamp
    copied: set[Path] = set()
    report: dict[str, object] = {"generated_at": stamp, "maps": {}}

    total_edits = 0
    for label, cfg in maps.items():
        mission = mission_from_config(cfg["config"])
        if not mission:
            print(f"{label}: missing mission template in {cfg['config']}")
            continue
        mission_dir = ROOT / "mpmissions" / mission
        rpt = latest_rpt(ROOT / cfg.get("profiles_dir", f"profiles_{label}"))
        if not rpt:
            print(f"{label}: no RPT found")
            continue
        overtime_counts, hard_counts = collect_log_counts(rpt)
        overtime_names = {
            name.lower()
            for name, count in overtime_counts.items()
            if count >= args.min_overtime_count
        }
        hard_names = {
            name.lower()
            for name, count in hard_counts.items()
            if count >= args.min_hard_count and name.lower() not in overtime_names
        }

        edits: list[str] = []
        for path in type_files(mission_dir):
            edits.extend(
                f"{path.relative_to(ROOT)}:{change}"
                for change in tune_types_file(
                    path,
                    overtime_names,
                    hard_names,
                    backup_root,
                    copied,
                    args.dry_run,
                    args.disable_overtime,
                    args.overtime_nominal,
                    args.hard_nominal,
                )
            )
        total_edits += len(edits)
        report["maps"][label] = {
            "mission": mission,
            "rpt": str(rpt.relative_to(ROOT)),
            "overtime_types": overtime_counts.most_common(50),
            "hard_types": hard_counts.most_common(50),
            "edits": edits,
        }
        print(
            f"{label}: {len(overtime_names)} overtime types, {len(hard_names)} hard-only types, "
            f"{len(edits)} edits from {rpt.name}"
        )
        for change in edits[:12]:
            print(f"  {change}")
        if len(edits) > 12:
            print(f"  ... {len(edits) - 12} more")

    report_dir = ROOT / "local_runtime"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "ce_overtime_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if total_edits and not args.dry_run:
        print(f"Backups written under {backup_root}")
    print(f"CE overtime tuning {'would make' if args.dry_run else 'made'} {total_edits} edits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
