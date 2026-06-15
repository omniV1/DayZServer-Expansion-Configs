#!/usr/bin/env python3
"""Validate imported community maps are in the stable/sanitized state."""
from __future__ import annotations

import json
import re
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

PROFILES = {
    "deerisle": "profiles_deerisle",
    "banov": "profiles_banov",
    "esseker": "profiles_esseker",
    "rostow": "profiles_rostow",
    "iztek": "profiles_iztek",
    "alteria": "profiles_alteria",
}

RISKY_DIRS = [
    "expansion/missions",
    "expansion/objects",
    "expansion/p2pmarket",
    "expansion/personalstorage",
    "expansion/traders",
    "expansion/traderzones",
]

CATEGORY_ALIASES = {
    "bags": "containers",
    "rifles": "weapons",
    "vehicleparts": "vehiclesparts",
}

INVALID_USAGE_OR_VALUE = {"Historical", "Lunapark", "SeasonalEvent", "Unique"}
SEARCH_OVERTIME_RE = re.compile(r'causing search overtime:\s*"([^"]+)"', re.I)


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


def child_text(element: ET.Element, name: str) -> str:
    child = element.find(name)
    return child.text if child is not None and child.text is not None else ""


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

    for name in ("MarketSettings.json", "MissionSettings.json", "P2PMarketSettings.json", "PersonalStorageSettings.json", "SafeZoneSettings.json"):
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

    types = root / "db" / "types.xml"
    if types.exists():
        try:
            types_root = ET.parse(types).getroot()
            overtime_names = collect_search_overtime_types(label)
            for item_type in types_root.findall("type"):
                name = item_type.get("name", "")
                for child in item_type:
                    child_name = child.get("name")
                    if child.tag == "category" and child_name in CATEGORY_ALIASES:
                        errors.append(f"{label}: db/types.xml {name} has unnormalized category {child_name}")
                    if child.tag in {"usage", "value"} and child_name in INVALID_USAGE_OR_VALUE:
                        errors.append(f"{label}: db/types.xml {name} has unsupported {child.tag} {child_name}")
                if name.lower() in overtime_names and (child_text(item_type, "nominal") != "0" or child_text(item_type, "min") != "0"):
                    errors.append(f"{label}: latest RPT search-overtime type still enabled: {name}")
        except ET.ParseError as exc:
            errors.append(f"{label}: db/types.xml parse failed: {exc}")

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
