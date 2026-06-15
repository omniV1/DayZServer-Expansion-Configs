#!/usr/bin/env python3
"""Reduce Central Economy placement pressure on imported community maps."""
from __future__ import annotations

import re
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

PROFILES = {
    "deerisle": "profiles_deerisle",
    "banov": "profiles_banov",
    "esseker": "profiles_esseker",
    "rostow": "profiles_rostow",
    "iztek": "profiles_iztek",
    "alteria": "profiles_alteria",
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
ALWAYS_DISABLE_EVENTS = {"ItemPlanks"}
SEARCH_OVERTIME_RE = re.compile(r'causing search overtime:\s*"([^"]+)"', re.I)
IGNORED_TYPE_RE = re.compile(r"Type '([^']+)' will be ignored", re.I)


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


def latest_rpt(profile_dir: Path) -> Path | None:
    if not profile_dir.exists():
        return None
    rpts = sorted(profile_dir.glob("DayZServer_x64_*.RPT"), key=lambda path: path.stat().st_mtime, reverse=True)
    return rpts[0] if rpts else None


def collect_search_overtime_types(label: str) -> set[str]:
    rpt = latest_rpt(ROOT / PROFILES[label])
    if not rpt:
        return set()
    found: set[str] = set()
    for line in rpt.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        match = SEARCH_OVERTIME_RE.search(line)
        if match:
            found.add(match.group(1).lower())
    return found


def collect_ignored_types(label: str) -> set[str]:
    rpt = latest_rpt(ROOT / PROFILES[label])
    if not rpt:
        return set()
    found: set[str] = set()
    for line in rpt.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        match = IGNORED_TYPE_RE.search(line)
        if match:
            found.add(match.group(1).lower())
    return found


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


def tune_types(path: Path, search_overtime_types: set[str], ignored_types: set[str]) -> list[str]:
    if not path.exists():
        return []
    tree = ET.parse(path)
    root = tree.getroot()
    changed: list[str] = []
    for item_type in list(root.findall("type")):
        name = item_type.get("name", "")
        if name.lower() in ignored_types:
            root.remove(item_type)
            changed.append(f"{name}:removed ignored type")
            continue
        should_disable = (
            name in SEARCH_OVERTIME_TYPES
            or name.lower() in search_overtime_types
            or is_bulky_vehicle_part(item_type, name)
        )
        if should_disable:
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


def event_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {event.get("name", "") for event in ET.parse(path).getroot().findall("event") if event.get("name")}


def disable_event(event: ET.Element) -> bool:
    changed = False
    for tag in ("nominal", "min", "max"):
        changed = set_child_text(event, tag, "0") or changed
    changed = set_child_text(event, "active", "0") or changed
    for child in event.findall("./children/child"):
        for attr in ("lootmax", "lootmin", "max", "min"):
            if child.get(attr) != "0":
                child.set(attr, "0")
                changed = True
    return changed


def tune_event_spawns(path: Path, valid_events: set[str]) -> list[str]:
    if not path.exists():
        return []
    tree = ET.parse(path)
    root = tree.getroot()
    changed: list[str] = []
    for event in list(root.findall("event")):
        name = event.get("name", "")
        if name and name not in valid_events:
            root.remove(event)
            changed.append(f"{name}:removed orphan spawn")
    if changed:
        write_tree(tree, path)
    return changed


def tune_invalid_fixed_events(events_path: Path, spawns_path: Path) -> list[str]:
    if not events_path.exists() or not spawns_path.exists():
        return []
    spawn_root = ET.parse(spawns_path).getroot()
    spawn_counts = {
        event.get("name", ""): len(event.findall("pos")) + len(event.findall("zone"))
        for event in spawn_root.findall("event")
    }
    tree = ET.parse(events_path)
    root = tree.getroot()
    changed: list[str] = []
    for event in root.findall("event"):
        name = event.get("name", "")
        position = child_text(event, "position")
        active = child_text(event, "active")
        has_spawn_entry = name in spawn_counts
        if name in ALWAYS_DISABLE_EVENTS or (
            has_spawn_entry
            and name.startswith("Vehicle")
            and active != "0"
            and position in {"fixed", "custom"}
            and spawn_counts.get(name, 0) == 0
        ):
            if disable_event(event):
                changed.append(name)
    if changed:
        write_tree(tree, events_path)
    return changed


def ensure_event_groups(path: Path) -> list[str]:
    if path.exists():
        return []
    path.write_text('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<eventgroupdef />\n', encoding="utf-8")
    return ["created cfgeventgroups.xml"]


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

        valid_events = event_names(base / "db" / "events.xml")

        spawn_changes = tune_event_spawns(base / "cfgeventspawns.xml", valid_events)
        if spawn_changes:
            changes.append(f"eventspawns {len(spawn_changes)} edits")

        fixed_event_changes = tune_invalid_fixed_events(base / "db" / "events.xml", base / "cfgeventspawns.xml")
        if fixed_event_changes:
            changes.append(f"events disabled invalid fixed {', '.join(fixed_event_changes[:8])}")

        group_changes = ensure_event_groups(base / "cfgeventgroups.xml")
        if group_changes:
            changes.append("eventgroups " + ", ".join(group_changes))

        log_overtime_types = collect_search_overtime_types(label)
        log_ignored_types = collect_ignored_types(label)
        type_changes = tune_types(base / "db" / "types.xml", log_overtime_types, log_ignored_types)
        if type_changes:
            learned = f", {len(log_overtime_types)} from latest RPT" if log_overtime_types else ""
            ignored = f", {len(log_ignored_types)} ignored types from latest RPT" if log_ignored_types else ""
            changes.append(f"types {len(type_changes)} edits{learned}{ignored}")

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
