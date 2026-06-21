#!/usr/bin/env python3
"""Make imported-map player spawn bubbles less brittle."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MISSIONS = {
    "deerisle": "empty.deerisle",
    "banov": "dayzOffline.banov",
    "esseker": "dayzOffline.Esseker",
    "rostow": "Offline.rostow",
    "iztek": "empty.Iztek",
    "alteria": "empty.alteria",
    "bitterroot": "empty.Bitterroot",
    "deadfall": "dayz.Deadfall",
}

REPLACE_FROM_MAPGROUPPOS = {"iztek", "bitterroot"}
SIMPLE_SPAWN_HANDLER = {"iztek", "bitterroot"}
# Maps whose <hop> section is empty in the shipped mission — CE validates hop
# separately as "regular player spawn points" and aborts with NO VALID SPAWNS
# when it is empty. Fix by mirroring the fresh bubbles into hop.
MIRROR_FRESH_TO_HOP = {"deadfall"}

# Per-map spatial filter (x_min, x_max, z_min, z_max) for read_mapgroup_positions.
# Needed to exclude coastal/edge positions where the CE generator can't place spawns.
MAP_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "iztek": (900.0, 7300.0, 3000.0, 7600.0),
    # Bitterroot is ~12 km × 12 km; keep 2 km inland from each edge.
    "bitterroot": (2000.0, 10500.0, 2000.0, 10500.0),
}

MAP_OVERRIDES = {
    "iztek": {
        "spawn_params": {
            "min_dist_infected": "0.0",
            "max_dist_infected": "300.0",
            "min_dist_player": "0.0",
            "max_dist_player": "300.0",
            "min_dist_static": "0.0",
            "max_dist_static": "120.0",
        },
        "generator_params": {
            "grid_density": "12",
            "grid_width": "500.0",
            "grid_height": "500.0",
            "min_dist_static": "0.0",
            "max_dist_static": "120.0",
            "min_steepness": "-90",
            "max_steepness": "90",
        },
    },
    # Bitterroot ships with max_dist_static=2 which requires spawns to be within
    # 2m of a static object — almost impossible for its rural bubble positions.
    "bitterroot": {
        "spawn_params": {
            "min_dist_infected": "20.0",
            "max_dist_infected": "150.0",
            "min_dist_player": "25.0",
            "max_dist_player": "300.0",
            "min_dist_static": "0.0",
            "max_dist_static": "300.0",
        },
        "generator_params": {
            "grid_density": "6",
            "grid_width": "300.0",
            "grid_height": "300.0",
            "min_dist_static": "0.0",
            "max_dist_static": "300.0",
            "min_steepness": "-45",
            "max_steepness": "45",
        },
    },
    # Deadfall: same default issue, relax static-object constraint.
    "deadfall": {
        "spawn_params": {
            "min_dist_infected": "20.0",
            "max_dist_infected": "150.0",
            "min_dist_player": "25.0",
            "max_dist_player": "300.0",
            "min_dist_static": "0.0",
            "max_dist_static": "300.0",
        },
        "generator_params": {
            "grid_density": "6",
            "grid_width": "300.0",
            "grid_height": "300.0",
            "min_dist_static": "0.0",
            "max_dist_static": "300.0",
            "min_steepness": "-45",
            "max_steepness": "45",
        },
    },
}


def child(parent: ET.Element, name: str) -> ET.Element:
    found = parent.find(name)
    if found is None:
        found = ET.SubElement(parent, name)
    return found


def set_text(parent: ET.Element, name: str, value: str) -> bool:
    elem = child(parent, name)
    if elem.text != value:
        elem.text = value
        return True
    return False


def tune_file(path: Path, overrides: dict | None = None) -> bool:
    tree = ET.parse(path)
    root = tree.getroot()
    changed = False

    fresh = child(root, "fresh")
    spawn_params = child(fresh, "spawn_params")
    generator_params = child(fresh, "generator_params")

    spawn_defaults = {
        "min_dist_infected": "20.0",
        "max_dist_infected": "90.0",
        "min_dist_player": "25.0",
        "max_dist_player": "120.0",
        "min_dist_static": "0.0",
        "max_dist_static": "12.0",
    }
    generator_defaults = {
        "grid_density": "6",
        "grid_width": "180.0",
        "grid_height": "180.0",
        "min_dist_static": "0.0",
        "max_dist_static": "12.0",
        "min_steepness": "-45",
        "max_steepness": "45",
    }
    if overrides:
        spawn_defaults.update(overrides.get("spawn_params", {}))
        generator_defaults.update(overrides.get("generator_params", {}))

    # Imported maps often ship spawn bubbles that are technically present but
    # too small or too close to static objects for DayZ's generator to accept.
    for name, value in spawn_defaults.items():
        changed |= set_text(spawn_params, name, value)

    for name, value in generator_defaults.items():
        changed |= set_text(generator_params, name, value)

    bubbles = fresh.find("generator_posbubbles")
    if bubbles is None or not list(bubbles):
        raise ValueError(f"{path} has no fresh generator_posbubbles")

    if changed:
        ET.indent(tree, space="    ")
        tree.write(path, encoding="utf-8", xml_declaration=True)
    return changed


def read_mapgroup_positions(
    path: Path,
    bounds: tuple[float, float, float, float] | None = None,
) -> list[tuple[float, float]]:
    root = ET.parse(path).getroot()
    x_min, x_max, z_min, z_max = bounds if bounds else (0.0, float("inf"), 0.0, float("inf"))
    positions: list[tuple[float, float]] = []
    for elem in root.iter():
        raw = elem.get("pos")
        if not raw:
            continue
        parts = raw.split()
        if len(parts) < 3:
            continue
        try:
            x = float(parts[0])
            z = float(parts[2])
        except ValueError:
            continue
        if x_min <= x <= x_max and z_min <= z <= z_max:
            positions.append((x, z))
    return positions


def spread_positions(positions: list[tuple[float, float]], limit: int = 36, cell: float = 650.0) -> list[tuple[float, float]]:
    cells: dict[tuple[int, int], tuple[float, float]] = {}
    for x, z in positions:
        key = (int(x // cell), int(z // cell))
        if key not in cells:
            cells[key] = (x, z)
    selected = sorted(cells.values(), key=lambda p: (p[1], p[0]))
    if len(selected) <= limit:
        return selected
    step = len(selected) / limit
    return [selected[int(i * step)] for i in range(limit)]


def replace_fresh_bubbles(path: Path, positions: list[tuple[float, float]]) -> bool:
    tree = ET.parse(path)
    root = tree.getroot()
    fresh = child(root, "fresh")
    bubbles = child(fresh, "generator_posbubbles")
    old = [(float(p.get("x", "0")), float(p.get("z", "0"))) for p in bubbles.findall("pos")]
    if old == positions:
        return False
    for elem in list(bubbles):
        bubbles.remove(elem)
    for x, z in positions:
        ET.SubElement(bubbles, "pos", {"x": f"{x:.3f}", "z": f"{z:.3f}"})
    ET.indent(tree, space="    ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return True


def mirror_fresh_to_hop(path: Path) -> bool:
    """Copy <fresh> generator_posbubbles into <hop> when hop is empty.

    Some community maps ship with an empty <hop> section. DayZ CE validates
    <hop> separately as 'regular player spawn points' and prints NO VALID SPAWNS
    (which our smoke test treats as fatal) when it is empty.
    """
    tree = ET.parse(path)
    root = tree.getroot()
    fresh = root.find("fresh")
    if fresh is None:
        return False
    fresh_bubbles = fresh.find("generator_posbubbles")
    if fresh_bubbles is None:
        return False
    fresh_positions = [(float(p.get("x", "0")), float(p.get("z", "0"))) for p in fresh_bubbles.findall("pos")]
    if not fresh_positions:
        return False

    hop = child(root, "hop")
    hop_bubbles = child(hop, "generator_posbubbles")
    existing = [p for p in hop_bubbles.findall("pos")]
    if existing:
        return False  # already populated, leave it alone

    for x, z in fresh_positions:
        ET.SubElement(hop_bubbles, "pos", {"x": f"{x:.3f}", "z": f"{z:.3f}"})
    ET.indent(tree, space="    ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return True


def write_simple_spawn_handler(path: Path, positions: list[tuple[float, float]]) -> bool:
    root = ET.Element("playerspawnpoints")
    generator = ET.SubElement(root, "generator", {"type": "PlayerSpawnHandler"})
    for idx, (x, z) in enumerate(positions):
        spawn = ET.SubElement(generator, "spawn", {"id": str(idx)})
        ET.SubElement(spawn, "pos", {"x": f"{x:.3f}", "z": f"{z:.3f}"})
    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    new_text_path = path.with_suffix(".tmp.xml")
    tree.write(new_text_path, encoding="utf-8", xml_declaration=True)
    new_text = new_text_path.read_text(encoding="utf-8")
    new_text_path.unlink()
    old_text = path.read_text(encoding="utf-8") if path.exists() else ""
    if old_text == new_text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    changed = []
    for key, mission in MISSIONS.items():
        path = ROOT / "mpmissions" / mission / "cfgplayerspawnpoints.xml"
        if not path.exists():
            print(f"{key}: missing {path}")
            continue
        if key in REPLACE_FROM_MAPGROUPPOS:
            mapgroups = ROOT / "mpmissions" / mission / "mapgrouppos.xml"
            positions = spread_positions(read_mapgroup_positions(mapgroups, MAP_BOUNDS.get(key)))
            if len(positions) < 10:
                raise ValueError(f"{key}: only found {len(positions)} usable map-group positions")
            if key in SIMPLE_SPAWN_HANDLER:
                if write_simple_spawn_handler(path, positions):
                    changed.append(key)
                    print(f"{key}: wrote simple PlayerSpawnHandler spawns ({len(positions)} points)")
                else:
                    print(f"{key}: simple PlayerSpawnHandler spawns already tuned")
                continue
            if replace_fresh_bubbles(path, positions):
                changed.append(key)
                print(f"{key}: replaced player spawn bubbles from mapgrouppos ({len(positions)} points)")
        if key in MIRROR_FRESH_TO_HOP:
            if mirror_fresh_to_hop(path):
                changed.append(key)
                print(f"{key}: mirrored fresh bubbles into empty hop section")
            else:
                print(f"{key}: hop section already populated")
        if tune_file(path, MAP_OVERRIDES.get(key)):
            changed.append(key)
            print(f"{key}: tuned player spawn generator")
        else:
            print(f"{key}: already tuned")
    print(f"Changed {len(changed)} map(s). Restart affected servers to reload spawns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
