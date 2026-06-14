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


def tune_file(path: Path) -> bool:
    tree = ET.parse(path)
    root = tree.getroot()
    changed = False

    fresh = child(root, "fresh")
    spawn_params = child(fresh, "spawn_params")
    generator_params = child(fresh, "generator_params")

    # Imported maps often ship spawn bubbles that are technically present but
    # too small or too close to static objects for DayZ's generator to accept.
    changed |= set_text(spawn_params, "min_dist_infected", "20.0")
    changed |= set_text(spawn_params, "max_dist_infected", "90.0")
    changed |= set_text(spawn_params, "min_dist_player", "25.0")
    changed |= set_text(spawn_params, "max_dist_player", "120.0")
    changed |= set_text(spawn_params, "min_dist_static", "0.0")
    changed |= set_text(spawn_params, "max_dist_static", "12.0")

    changed |= set_text(generator_params, "grid_density", "6")
    changed |= set_text(generator_params, "grid_width", "180.0")
    changed |= set_text(generator_params, "grid_height", "180.0")
    changed |= set_text(generator_params, "min_dist_static", "0.0")
    changed |= set_text(generator_params, "max_dist_static", "12.0")
    changed |= set_text(generator_params, "min_steepness", "-45")
    changed |= set_text(generator_params, "max_steepness", "45")

    bubbles = fresh.find("generator_posbubbles")
    if bubbles is None or not list(bubbles):
        raise ValueError(f"{path} has no fresh generator_posbubbles")

    if changed:
        ET.indent(tree, space="    ")
        tree.write(path, encoding="utf-8", xml_declaration=True)
    return changed


def main() -> int:
    changed = []
    for key, mission in MISSIONS.items():
        path = ROOT / "mpmissions" / mission / "cfgplayerspawnpoints.xml"
        if not path.exists():
            print(f"{key}: missing {path}")
            continue
        if tune_file(path):
            changed.append(key)
            print(f"{key}: tuned player spawn generator")
        else:
            print(f"{key}: already tuned")
    print(f"Changed {len(changed)} map(s). Restart affected servers to reload spawns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
