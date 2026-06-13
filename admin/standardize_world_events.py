#!/usr/bin/env python3
"""Standardize rare airdrops and richer static events across active maps."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
MISSIONS = {
    "chernarus": "dayzOffline.chernarusplus",
    "enoch": "dayzOffline.enoch",
    "sakhal": "dayzOffline.sakhal",
    "namalsk": "regular.namalsk",
    "takistan": "dayzOffline.TakistanPlus",
}

ENABLED_AIRDROPS = {
    "chernarus": {"Airdrop_Random_NEAF.json", "Airdrop_Random_NWAF.json", "Airdrop_Random_Zelenogorsk.json"},
    "enoch": {"Airdrop_Random_Brena.json", "Airdrop_Random_Nadbor.json", "Airdrop_Random_Radunin.json"},
    "sakhal": {"Airdrop_Random_Settlement_Capital.json", "Airdrop_Random_Settlement_CityAirfield.json", "Airdrop_Random_Shantar.json"},
    "namalsk": {"Airdrop_Random_Airstrip.json", "Airdrop_Random_Tara-Harbor.json", "Airdrop_Random_Vorkuta.json"},
    "takistan": {"Airdrop_Random_NEAF.json", "Airdrop_Random_NWAF.json", "Airdrop_Random_Zelenogorsk.json"},
}

MISSION_SETTINGS = {
    "Enabled": 1,
    "InitialMissionStartDelay": 1800000,
    "TimeBetweenMissions": 21600000,
    "MinMissions": 0,
    "MaxMissions": 1,
    "MinPlayersToStartMissions": 0,
}

STATIC_EVENTS = {
    "StaticHeliCrash": {"nominal": 6, "min": 3, "lifetime": 2700, "active": 1},
    "StaticMilitaryConvoy": {"nominal": 8, "min": 3, "lifetime": 2700, "active": 1},
    "StaticPoliceCar": {"nominal": 8, "min": 3, "lifetime": 2700, "active": 1},
    "StaticPoliceSituation": {"nominal": 8, "min": 3, "lifetime": 2700, "active": 1},
    "StaticTrain": {"nominal": 5, "min": 2, "lifetime": 5400, "active": 1},
}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")


def tune_profile_missions() -> bool:
    path = SERVER / "profiles" / "ExpansionMod" / "Settings" / "MissionSettings.json"
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    changed = False
    for key, value in MISSION_SETTINGS.items():
        if data.get(key) != value:
            data[key] = value
            changed = True
    if changed:
        write_json(path, data)
    return changed


def tune_airdrops(map_key: str, mission: str) -> tuple[int, int]:
    folder = SERVER / "mpmissions" / mission / "expansion" / "missions"
    enabled = ENABLED_AIRDROPS[map_key]
    changed = 0
    total = 0
    for path in sorted(folder.glob("Airdrop_*.json")):
        total += 1
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        desired = 1 if path.name in enabled else 0
        if data.get("Enabled") != desired:
            data["Enabled"] = desired
            write_json(path, data)
            changed += 1
    return total, changed


def set_text(event: ET.Element, tag: str, value: int) -> bool:
    node = event.find(tag)
    if node is None:
        return False
    new = str(value)
    if node.text == new:
        return False
    node.text = new
    return True


def tune_static_events(mission: str) -> tuple[int, int]:
    path = SERVER / "mpmissions" / mission / "db" / "events.xml"
    tree = ET.parse(path)
    root = tree.getroot()
    seen = 0
    changed = 0
    for event in root.findall("event"):
        counts = STATIC_EVENTS.get(event.get("name", ""))
        if not counts:
            continue
        seen += 1
        event_changed = False
        for tag, value in counts.items():
            event_changed = set_text(event, tag, value) or event_changed
        if event_changed:
            changed += 1
    if changed:
        tree.write(path, encoding="UTF-8", xml_declaration=True)
    return seen, changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Tune rare airdrops and static world events.")
    parser.add_argument("maps", nargs="*", choices=sorted(MISSIONS), help="Maps to tune. Defaults to all active maps.")
    args = parser.parse_args()
    maps = args.maps or list(MISSIONS)

    profile_changed = tune_profile_missions()
    print(f"profile MissionSettings: {'changed' if profile_changed else 'already rare'}")
    for key in maps:
        mission = MISSIONS[key]
        air_total, air_changed = tune_airdrops(key, mission)
        static_seen, static_changed = tune_static_events(mission)
        print(f"{key}: airdrops {air_changed}/{air_total} changed; static events {static_changed}/{static_seen} changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
