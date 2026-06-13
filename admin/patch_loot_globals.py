"""Patch db/globals.xml on all missions from loot_config preset.

Prefer:  python admin/apply_loot.py globals [--preset high]
"""
import argparse
import sys
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
sys.path.insert(0, str(ADMIN))

import apply_loot
import loot_settings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=list(loot_settings.load_config()["presets"].keys()))
    ns = ap.parse_args()
    preset = ns.preset or loot_settings.load_config().get("active_preset", "medium")
    print(f"Preset: {preset}")
    for line in apply_loot.patch_globals_all(preset):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
