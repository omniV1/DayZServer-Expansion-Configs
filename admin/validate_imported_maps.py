#!/usr/bin/env python3
"""Validate imported community maps are in the stable/sanitized state."""
from __future__ import annotations

import json
import sys
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

RISKY_DIRS = [
    "expansion/missions",
    "expansion/objects",
    "expansion/p2pmarket",
    "expansion/personalstorage",
    "expansion/traders",
    "expansion/traderzones",
]


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def is_disabled_setting(path: Path) -> bool:
    data = read_json(path)
    if not data:
        return False
    if path.name == "MarketSettings.json":
        return data.get("MarketSystemEnabled") == 0 and data.get("ATMSystemEnabled") == 0
    return data.get("Enabled") == 0


def validate_map(label: str, mission: str) -> list[str]:
    errors: list[str] = []
    root = ROOT / "mpmissions" / mission
    if not root.exists():
        return [f"{label}: missing mission folder {mission}"]

    for rel in RISKY_DIRS:
        path = root / rel
        if path.exists():
            errors.append(f"{label}: risky generated folder exists: {rel}")

    for storage in root.glob("storage_*"):
        errors.append(f"{label}: storage folder exists after cleanup: {storage.name}")

    for name in ("MarketSettings.json", "P2PMarketSettings.json", "PersonalStorageSettings.json", "SafeZoneSettings.json"):
        path = root / "expansion" / "settings" / name
        if not is_disabled_setting(path):
            errors.append(f"{label}: setting is missing or enabled: expansion/settings/{name}")

    economy = root / "cfgeconomycore.xml"
    if not economy.exists():
        errors.append(f"{label}: missing cfgeconomycore.xml")
    elif "mod_ce" in economy.read_text(encoding="utf-8", errors="replace"):
        errors.append(f"{label}: imported map still wires generated mod_ce")

    spawns = root / "cfgplayerspawnpoints.xml"
    if not spawns.exists():
        errors.append(f"{label}: missing cfgplayerspawnpoints.xml")
    else:
        try:
            ET.parse(spawns)
        except ET.ParseError as exc:
            errors.append(f"{label}: cfgplayerspawnpoints.xml parse failed: {exc}")

    return errors


def main() -> int:
    errors: list[str] = []
    for label, mission in MISSIONS.items():
        errors.extend(validate_map(label, mission))

    if errors:
        print("Imported map validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Imported map validation OK ({len(MISSIONS)} maps).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
