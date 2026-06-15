#!/usr/bin/env python3
"""Reduce Central Economy placement pressure on imported community maps."""
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

GLOBAL_LIMITS = {
    "InitialSpawn": "120",
    "SpawnInitial": "1400",
    "ZombieMaxCount": "1100",
}

DISABLE_EVENTS = {
    "StaticAirplaneCrate",
    "StaticContaminatedArea",
    "VehicleBoat",
    "VehicleBoatSTAG",
}

SEARCH_OVERTIME_TYPES = {
    "FireworksLauncher",
    "Headtorch_Black",
    "HikingJacket_Blue",
    "Hatchback_02_Trunk_RedRust",
    "Hook",
    "MetalPlate",
    "PartyTent_Lunapark",
}

BULKY_VEHICLE_PART_PREFIXES = (
    "CivSedanDoors_",
    "CivSedanHood",
    "CivSedanTrunk",
    "CivSedanWheel",
    "Expansion_Landrover_",
    "ExpansionTractor",
    "ExpansionUAZDoor",
    "ExpansionUAZWheel",
    "Hatchback_02_Door_",
    "Hatchback_02_Hood",
    "Hatchback_02_Trunk",
    "Hatchback_02_Wheel",
    "HatchbackDoors_",
    "HatchbackHood",
    "HatchbackTrunk",
    "Offroad_02_Door_",
    "Offroad_02_Trunk",
    "Sedan_02_Door_",
    "Sedan_02_Hood",
    "Sedan_02_Trunk",
    "Truck_01_Door_",
    "Truck_01_Hood",
    "Truck_01_Wheel",
)

CATEGORY_ALIASES = {
    "bags": "containers",
    "rifles": "weapons",
    "vehicleparts": "vehiclesparts",
}

INVALID_NAMES = {"Historical", "Lunapark", "SeasonalEvent", "Unique"}


def indent(tree: ET.ElementTree) -> None:
    ET.indent(tree, space="    ")


def write_tree(tree: ET.ElementTree, path: Path) -> None:
    indent(tree)
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def child_text(element: ET.Element, name: str) -> str | None:
    child = element.find(name)
    return child.text if child is not None else None


def set_child_text(element: ET.Element, name: str, value: str) -> bool:
    child = element.find(name)
    if child is None:
        return False
    if child.text == value:
        return False
    child.text = value
    return True


def has_category(element: ET.Element, name: str) -> bool:
    return any(child.tag == "category" and child.get("name") == name for child in element)


def is_bulky_vehicle_part(element: ET.Element, type_name: str) -> bool:
    if not has_category(element, "vehiclesparts"):
        return False
    return type_name.startswith(BULKY_VEHICLE_PART_PREFIXES)


def tune_globals(path: Path) -> list[str]:
    tree = ET.parse(path)
    root = tree.getroot()
    changed: list[str] = []
    for var in root.findall("var"):
        name = var.get("name")
        if name not in GLOBAL_LIMITS:
            continue
        value = GLOBAL_LIMITS[name]
        if var.get("value") != value:
            var.set("value", value)
            changed.append(f"{name}={value}")
    if changed:
        write_tree(tree, path)
    return changed


def tune_events(path: Path) -> list[str]:
    tree = ET.parse(path)
    root = tree.getroot()
    changed: list[str] = []
    for event in root.findall("event"):
        name = event.get("name", "")
        if name not in DISABLE_EVENTS:
            continue
        edits = []
        for tag in ("nominal", "min", "max"):
            if set_child_text(event, tag, "0"):
                edits.append(tag)
        if set_child_text(event, "active", "0"):
            edits.append("active")
        if name == "StaticAirplaneCrate":
            for child in event.findall("./children/child"):
                for attr in ("lootmax", "lootmin"):
                    if child.get(attr) != "0":
                        child.set(attr, "0")
                        edits.append(attr)
        if edits:
            changed.append(name)
    if changed:
        write_tree(tree, path)
    return changed


def tune_types(path: Path) -> list[str]:
    if not path.exists():
        return []
    tree = ET.parse(path)
    root = tree.getroot()
    changed: list[str] = []
    for item_type in root.findall("type"):
        name = item_type.get("name", "")
        if name in SEARCH_OVERTIME_TYPES or is_bulky_vehicle_part(item_type, name):
            edits = []
            for tag in ("nominal", "min"):
                if child_text(item_type, tag) != "0" and set_child_text(item_type, tag, "0"):
                    edits.append(tag)
            if edits:
                changed.append(name)
        for child in list(item_type):
            child_name = child.get("name")
            if child.tag == "category" and child_name in CATEGORY_ALIASES:
                new_name = CATEGORY_ALIASES[child_name]
                child.set("name", new_name)
                changed.append(f"{name}:category:{child_name}->{new_name}")
                continue
            if child.tag in {"usage", "value"} and child_name in INVALID_NAMES:
                item_type.remove(child)
                changed.append(f"{name}:{child.tag}:{child_name}")
    if changed:
        write_tree(tree, path)
    return changed


def tune_economy_core(path: Path) -> list[str]:
    if not path.exists():
        return []
    tree = ET.parse(path)
    root = tree.getroot()
    changed: list[str] = []
    for ce in list(root.findall("ce")):
        if ce.get("folder") == "mod_ce":
            root.remove(ce)
            changed.append("removed mod_ce")
    if changed:
        write_tree(tree, path)
    return changed


def main() -> int:
    for label, mission in MISSIONS.items():
        base = ROOT / "mpmissions" / mission
        if not base.exists():
            print(f"{label}: missing {mission}")
            continue

        changes = []
        globals_changes = tune_globals(base / "db" / "globals.xml")
        if globals_changes:
            changes.append("globals " + ", ".join(globals_changes))

        event_changes = tune_events(base / "db" / "events.xml")
        if event_changes:
            changes.append("events " + ", ".join(event_changes))

        type_changes = tune_types(base / "db" / "types.xml")
        if type_changes:
            changes.append(f"types {len(type_changes)} edits")

        economy_changes = tune_economy_core(base / "cfgeconomycore.xml")
        if economy_changes:
            changes.append("economycore " + ", ".join(economy_changes))

        if changes:
            print(f"{label}: " + " | ".join(changes))
        else:
            print(f"{label}: already safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
