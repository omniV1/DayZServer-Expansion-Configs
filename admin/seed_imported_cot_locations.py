#!/usr/bin/env python3
"""Seed COT-style location files for imported maps from mission mapgrouppos.xml."""
from __future__ import annotations

import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADMIN = ROOT / "admin"
if str(ADMIN) not in sys.path:
    sys.path.insert(0, str(ADMIN))

from build_map_expansion import MAP_CONFIGS, mission_paths  # noqa: E402

IMPORTED_MAPS = ["deerisle", "banov", "esseker", "rostow", "iztek", "alteria"]
TYPES = ["ALL", "Airfield", "Camp", "Capital", "City", "Hill", "Local", "Marine", "Military Base", "Ruin", "Village"]

SKIP_KEYWORDS = (
    "wreck",
    "container",
    "misc",
    "sign",
    "rail",
    "wall",
    "fence",
    "light",
    "pole",
    "tree",
    "rock",
)
MILITARY_KEYWORDS = ("mil", "army", "barrack", "prison", "guardhouse", "tenthangar")
AIRFIELD_KEYWORDS = ("airport", "airfield", "hangar", "runway")
CAMP_KEYWORDS = ("camp", "tent")
RUIN_KEYWORDS = ("ruin", "castle")
LOCAL_KEYWORDS = ("police", "hospital", "office", "factory", "industrial", "school", "church", "ship")


def parse_pos(value: str) -> tuple[float, float, float] | None:
    parts = value.split()
    if len(parts) < 3:
        return None
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None


def classify_name(name: str) -> str:
    lower = name.lower()
    if any(k in lower for k in AIRFIELD_KEYWORDS):
        return "Airfield"
    if any(k in lower for k in MILITARY_KEYWORDS):
        return "Military Base"
    if any(k in lower for k in CAMP_KEYWORDS):
        return "Camp"
    if any(k in lower for k in RUIN_KEYWORDS):
        return "Ruin"
    if any(k in lower for k in LOCAL_KEYWORDS):
        return "Local"
    return "Village"


def type_priority(t: str) -> int:
    return {
        "Airfield": 0,
        "Military Base": 1,
        "Camp": 2,
        "Ruin": 3,
        "City": 4,
        "Village": 5,
        "Local": 6,
    }.get(t, 9)


def location_type(items: list[tuple[str, float, float, float]]) -> str:
    scores: dict[str, int] = defaultdict(int)
    for name, *_ in items:
        scores[classify_name(name)] += 1
    if scores["Airfield"] >= 2:
        return "Airfield"
    if scores["Military Base"] >= 2:
        return "Military Base"
    if scores["Camp"] >= 3:
        return "Camp"
    if scores["Ruin"] >= 3:
        return "Ruin"
    if scores["Local"] >= 4:
        return "Local"
    return "Village"


def wanted_group(name: str) -> bool:
    lower = name.lower()
    if any(k in lower for k in SKIP_KEYWORDS):
        return any(k in lower for k in AIRFIELD_KEYWORDS + MILITARY_KEYWORDS + CAMP_KEYWORDS + RUIN_KEYWORDS + LOCAL_KEYWORDS)
    return lower.startswith("land_")


def load_groups(mission: str) -> list[tuple[str, float, float, float]]:
    path = ROOT / "mpmissions" / mission / "mapgrouppos.xml"
    root = ET.parse(path).getroot()
    groups = []
    for group in root.findall("group"):
        name = group.get("name", "")
        pos = parse_pos(group.get("pos", ""))
        if not name or not pos or not wanted_group(name):
            continue
        x, y, z = pos
        groups.append((name, x, y, z))
    return groups


def build_grid_clusters(groups: list[tuple[str, float, float, float]], cell_size: float = 650.0) -> list[dict]:
    cells: dict[tuple[int, int], list[tuple[str, float, float, float]]] = defaultdict(list)
    for item in groups:
        _, x, _, z = item
        cells[(math.floor(x / cell_size), math.floor(z / cell_size))].append(item)

    clusters = []
    for (cx, cz), items in cells.items():
        if len(items) < 7:
            continue
        xs = [i[1] for i in items]
        ys = [i[2] for i in items]
        zs = [i[3] for i in items]
        t = location_type(items)
        clusters.append(
            {
                "type": t,
                "count": len(items),
                "x": sum(xs) / len(xs),
                "y": sum(ys) / len(ys),
                "z": sum(zs) / len(zs),
                "cell": (cx, cz),
            }
        )
    clusters.sort(key=lambda c: (type_priority(c["type"]), -c["count"], c["cell"]))
    return clusters


def select_locations(key: str, clusters: list[dict]) -> list[dict]:
    caps = {
        "Airfield": 4,
        "Military Base": 8,
        "Camp": 5,
        "Ruin": 5,
        "Local": 8,
        "Village": 24,
    }
    used = {k: 0 for k in caps}
    selected = []
    for cluster in clusters:
        t = cluster["type"]
        if used.get(t, 0) >= caps.get(t, 0):
            continue
        used[t] += 1
        selected.append(
            {
                "Type": t,
                "Name": f"{key.title()} {t} {used[t]:02d}",
                "Position": [round(cluster["x"], 2), round(cluster["y"], 2), round(cluster["z"], 2)],
                "Radius": 4.0,
            }
        )
        if len(selected) >= 42:
            break
    selected.sort(key=lambda loc: (type_priority(loc["Type"]), loc["Name"]))
    return selected


def write_locations(key: str, *, profile: bool, cache: bool) -> int:
    cfg = MAP_CONFIGS[key]
    groups = load_groups(cfg.mission)
    clusters = build_grid_clusters(groups)
    locations = select_locations(key, clusters)
    data = {"Types": TYPES, "Locations": locations}

    _, _, teleports = mission_paths(cfg)
    outputs = []
    if profile:
        outputs.append(teleports)
    if cache:
        outputs.append(ADMIN / cfg.cache_file)
    for path in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    print(f"{key}: {len(locations)} locations from {len(groups)} map groups")
    return len(locations)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed imported map COT teleport files from mapgrouppos.xml.")
    parser.add_argument("maps", nargs="*", choices=IMPORTED_MAPS, help="Defaults to all imported maps.")
    parser.add_argument("--profile-only", action="store_true", help="Only write profiles_*/CommunityOnlineTools files.")
    parser.add_argument("--cache-only", action="store_true", help="Only write admin/*_locations.json files.")
    args = parser.parse_args()

    maps = args.maps or IMPORTED_MAPS
    profile = not args.cache_only
    cache = not args.profile_only
    if not profile and not cache:
        parser.error("Choose at least one output.")
    failed = []
    for key in maps:
        try:
            if write_locations(key, profile=profile, cache=cache) == 0:
                failed.append(key)
        except Exception as exc:  # noqa: BLE001 - report all maps in one run.
            failed.append(key)
            print(f"{key}: FAILED {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
