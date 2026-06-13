#!/usr/bin/env python3
"""Tune Chernarus event counts for a richer PvE economy."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
EVENTS = SERVER / "mpmissions" / "dayzOffline.chernarusplus" / "db" / "events.xml"

# Higher huntable wildlife without turning Chernarus into a constant wolf/bear fight.
EVENT_COUNTS = {
    "AmbientFox": {"nominal": 6, "min": 2, "max": 30},
    "AmbientHare": {"nominal": 14, "min": 4, "max": 55},
    "AmbientHen": {"nominal": 10, "min": 4, "max": 60},
    "AnimalBear": {"nominal": 2, "min": 1, "max": 3},
    "AnimalCow": {"nominal": 12, "min": 4, "max": 5},
    "AnimalDeer": {"nominal": 15, "min": 4, "max": 6},
    "AnimalGoat": {"nominal": 12, "min": 3, "max": 5},
    "AnimalPig": {"nominal": 10, "min": 3, "max": 4},
    "AnimalRoeDeer": {"nominal": 16, "min": 5, "max": 6},
    "AnimalSheep": {"nominal": 10, "min": 5, "max": 7},
    "AnimalWildBoar": {"nominal": 10, "min": 3, "max": 5},
    "AnimalWolf": {"nominal": 8, "min": 3, "max": 5},
    "VehicleBoat": {"nominal": 28, "min": 22, "max": 32},
    "VehicleCivilianSedan": {"nominal": 12, "min": 8, "max": 16},
    "VehicleHatchback02": {"nominal": 12, "min": 8, "max": 16},
    "VehicleOffroad02": {"nominal": 5, "min": 3, "max": 6},
    "VehicleOffroadHatchback": {"nominal": 12, "min": 8, "max": 16},
    "VehicleSedan02": {"nominal": 12, "min": 8, "max": 16},
    "VehicleTruck01": {"nominal": 10, "min": 7, "max": 14},
}


def set_text(event: ET.Element, tag: str, value: int) -> bool:
    node = event.find(tag)
    if node is None:
        raise ValueError(f"{event.get('name')} is missing <{tag}>")
    new = str(value)
    if node.text == new:
        return False
    node.text = new
    return True


def main() -> int:
    tree = ET.parse(EVENTS)
    root = tree.getroot()
    updated: list[str] = []
    seen: set[str] = set()

    for event in root.findall("event"):
        name = event.get("name", "")
        counts = EVENT_COUNTS.get(name)
        if not counts:
            continue
        seen.add(name)
        changed = False
        for tag, value in counts.items():
            changed = set_text(event, tag, value) or changed
        if changed:
            updated.append(name)

    missing = sorted(set(EVENT_COUNTS) - seen)
    if missing:
        raise RuntimeError(f"Missing events in {EVENTS}: {', '.join(missing)}")

    tree.write(EVENTS, encoding="UTF-8", xml_declaration=True)
    print(f"Tuned {len(EVENT_COUNTS)} Chernarus events ({len(updated)} changed).")
    for name in updated:
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
