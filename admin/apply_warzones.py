#!/usr/bin/env python3
"""
Activate AI War Zones for a specific map (copies profiles/AIWarZones/maps/<map>.json
to AIWarZones_Settings.json).

The mod uses ONE settings file — run this for whichever map your server is starting.

Usage:
  python admin/apply_warzones.py chernarus
  python admin/apply_warzones.py enoch
  python admin/apply_warzones.py sakhal
  python admin/apply_warzones.py takistan
  python admin/apply_warzones.py namalsk
  python admin/apply_warzones.py --list
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
MAPS_DIR = SERVER / "profiles" / "AIWarZones" / "maps"
ACTIVE = SERVER / "profiles" / "AIWarZones" / "AIWarZones_Settings.json"

ALIASES = {
    "chernarus": "chernarus",
    "chernarusplus": "chernarus",
    "livonia": "enoch",
    "enoch": "enoch",
    "sakhal": "sakhal",
    "takistan": "takistan",
    "namalsk": "namalsk",
    "regular.namalsk": "namalsk",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("map", nargs="?", help="Map id (chernarus, enoch, sakhal, takistan, namalsk)")
    ap.add_argument("--list", action="store_true", help="List available map packs")
    ap.add_argument("--build", action="store_true", help="Regenerate map JSON from build_warzones.py")
    args = ap.parse_args()

    if args.build:
        import build_warzones

        build_warzones.write_all()
        print()

    if args.list or not args.map:
        print("War zone map packs in profiles/AIWarZones/maps/:")
        for p in sorted(MAPS_DIR.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            print(f"  {p.stem}: {len(d.get('WarZones', []))} zones")
        if not args.map:
            print("\nUsage: python admin/apply_warzones.py <map>")
        return 0

    key = ALIASES.get(args.map.lower())
    if not key:
        print(f"Unknown map '{args.map}'. Use --list")
        return 1

    src = MAPS_DIR / f"{key}.json"
    if not src.exists():
        print(f"Missing {src} — run: python admin/build_warzones.py")
        return 1

    data = json.loads(src.read_text(encoding="utf-8"))
    data.pop("_map", None)
    ACTIVE.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    d = data
    print(f"Active war zones: {key} -> {ACTIVE.relative_to(SERVER)}")
    print(f"  Zones: {len(d['WarZones'])} | maxConcurrentZones: {d['maxConcurrentZones']}")
    for z in d["WarZones"]:
        print(f"    - {z['zoneName']}")
    print("\nRestart the server so the mod reloads this file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
