#!/usr/bin/env python3
"""Print a compact balance/status summary for every active map."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MAPS = {
    "chernarus": "dayzOffline.chernarusplus",
    "enoch": "dayzOffline.enoch",
    "sakhal": "dayzOffline.sakhal",
    "namalsk": "regular.namalsk",
    "takistan": "dayzOffline.TakistanPlus",
    "deerisle": "empty.deerisle",
    "banov": "dayzOffline.banov",
    "esseker": "dayzOffline.Esseker",
    "rostow": "Offline.rostow",
    "iztek": "empty.Iztek",
    "alteria": "empty.alteria",
}


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_event_counts(path: Path) -> dict[str, int]:
    counts = {
        "animals": 0,
        "vehicles": 0,
        "heli": 0,
        "police": 0,
        "train": 0,
    }
    if not path.exists():
        return counts
    root = ET.parse(path).getroot()
    for event in root.findall("event"):
        name = event.get("name", "")
        active = event.findtext("active", "1")
        if active == "0":
            continue
        lower = name.lower()
        if lower.startswith("animal"):
            counts["animals"] += 1
        if lower.startswith("vehicle"):
            counts["vehicles"] += 1
        if "helicrash" in lower or "helicopter" in lower:
            counts["heli"] += 1
        if "police" in lower:
            counts["police"] += 1
        if "train" in lower:
            counts["train"] += 1
    return counts


def read_globals(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    root = ET.parse(path).getroot()
    for var in root.findall("var"):
        name = var.get("name")
        value = var.get("value")
        if name and value and name in {"SpawnInitial", "InitialSpawn", "ZombieMaxCount"}:
            values[name] = value
    return values


def mission_settings() -> str:
    data = read_json(ROOT / "profiles" / "ExpansionMod" / "Settings" / "MissionSettings.json")
    between_ms = int(data.get("TimeBetweenMissions", 0) or 0)
    hours = between_ms / 1000 / 60 / 60 if between_ms else 0
    return f"airdrops/events interval {hours:g}h, max {data.get('MaxMissions', '?')}"


def summarize_map(label: str, mission: str) -> str:
    base = ROOT / "mpmissions" / mission
    ai = read_json(base / "expansion" / "settings" / "AIPatrolSettings.json")
    patrols = ai.get("Patrols", [])
    ai_ranges = sorted({(p.get("NumberOfAI"), p.get("NumberOfAIMax")) for p in patrols})
    ai_text = "missing"
    if patrols:
        ranges = ", ".join(f"{lo}-{hi}" for lo, hi in ai_ranges if lo is not None and hi is not None)
        caps = ai.get("LoadBalancingCategories", {})
        patrol_cap = next((entry.get("MaxPatrols") for entry in caps.get("Patrol", []) if "MaxPatrols" in entry), "?")
        global_cap = next((entry.get("MaxPatrols") for entry in caps.get("Global", []) if "MaxPatrols" in entry), "?")
        ai_text = (
            f"{len(patrols)} patrols, active {patrol_cap}/global {global_cap}, "
            f"AI {ranges or 'varied'}, acc {ai.get('AccuracyMin', '?')}-{ai.get('AccuracyMax', '?')}"
        )

    economy = base / "cfgeconomycore.xml"
    economy_text = "mod_ce yes" if economy.exists() and "mod_ce" in economy.read_text(encoding="utf-8", errors="replace") else "mod_ce no"
    globals_text = ", ".join(f"{k}={v}" for k, v in read_globals(base / "db" / "globals.xml").items()) or "globals missing"
    events = read_event_counts(base / "db" / "events.xml")
    event_text = ", ".join(f"{k} {v}" for k, v in events.items())
    airdrops = sum(1 for p in (base / "expansion" / "missions").glob("Airdrop_*.json") if read_json(p).get("Enabled", 0))

    return f"{label:9} {mission:28} | {ai_text} | {economy_text}, {globals_text} | events: {event_text} | airdrops enabled {airdrops}"


def main() -> int:
    loot = read_json(ROOT / "admin" / "loot_config.json")
    print(f"Active loot preset: {loot.get('active_preset', 'unknown')}")
    print(f"Global Expansion mission pacing: {mission_settings()}")
    for label, mission in MAPS.items():
        print(summarize_map(label, mission))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
