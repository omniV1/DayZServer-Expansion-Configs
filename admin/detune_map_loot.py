#!/usr/bin/env python3
"""Revert sparse maps to vanilla loot density.

Some small/custom maps have too few (or buggy) loot points to absorb the
mod_ce loot boost without LootRespawner "search overtime" / "hard to place"
spam (Deadfall is the known case). For each mission listed in
loot_config.json -> "vanilla_loot_maps", this removes the mod_ce and
expansion_ce <ce> registrations from its cfgeconomycore.xml so it falls back
to the map's own vanilla nominals. The mod_ce/expansion_ce folders are left on
disk (just unregistered), so re-enabling is a matter of re-running the
loot/vehicle pipelines after dropping the map from vanilla_loot_maps.

Usage:
  python admin/detune_map_loot.py            # apply all vanilla_loot_maps
  python admin/detune_map_loot.py --map dayz.Deadfall
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
if str(ADMIN) not in sys.path:
    sys.path.insert(0, str(ADMIN))

import loot_settings

MISSIONS = loot_settings.SERVER / "mpmissions"
# Strip a whole "<ce folder="NAME"> ... </ce>" block plus trailing blank line.
CE_BLOCK = r'[ \t]*<ce folder="{name}">.*?</ce>\s*?\n'


def detune(mission: str) -> str:
    eco = MISSIONS / mission / "cfgeconomycore.xml"
    if not eco.exists():
        return f"SKIP {mission}: no cfgeconomycore.xml"
    text = eco.read_text(encoding="utf-8")
    original = text
    removed = []
    for folder in ("mod_ce", "expansion_ce"):
        new = re.sub(CE_BLOCK.format(name=folder), "", text, count=1, flags=re.DOTALL)
        if new != text:
            removed.append(folder)
            text = new
    if text == original:
        return f"noop {mission}: already vanilla (no mod_ce/expansion_ce registered)"
    ET.fromstring(text)  # validate before writing
    eco.write_text(text, encoding="utf-8", newline="\n")
    return f"OK   {mission}: de-registered {', '.join(removed)} -> vanilla loot"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--map", help="Single mission dir (default: all vanilla_loot_maps)")
    args = ap.parse_args()
    targets = [args.map] if args.map else loot_settings.vanilla_loot_maps()
    if not targets:
        print("No vanilla_loot_maps configured and no --map given.")
        return 0
    for m in targets:
        print(detune(m))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
