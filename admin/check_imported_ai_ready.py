#!/usr/bin/env python3
"""Report whether imported maps have COT teleport exports for AI generation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADMIN = ROOT / "admin"
if str(ADMIN) not in sys.path:
    sys.path.insert(0, str(ADMIN))

from build_map_expansion import MAP_CONFIGS, mission_paths  # noqa: E402

IMPORTED_MAPS = ["deerisle", "banov", "esseker", "rostow", "iztek", "alteria"]


def count_locations(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return -1
    return len(data.get("Locations", []))


def main() -> int:
    missing = []
    print("Imported map AI readiness:")
    for key in IMPORTED_MAPS:
        cfg = MAP_CONFIGS[key]
        mission, _, teleports = mission_paths(cfg)
        cache = ADMIN / cfg.cache_file
        source = cache if cache.exists() else teleports
        locations = count_locations(source)
        mission_ok = "yes" if mission.exists() else "NO"
        if locations > 0:
            print(f"  OK   {key:8} mission={mission_ok} locations={locations} source={source.relative_to(ROOT)}")
        elif locations == -1:
            missing.append(key)
            print(f"  BAD  {key:8} mission={mission_ok} unreadable JSON: {source.relative_to(ROOT)}")
        else:
            missing.append(key)
            print(f"  MISS {key:8} mission={mission_ok} expected {teleports.relative_to(ROOT)}")

    if missing:
        print("\nCapture COT teleport/location exports in-game for:")
        print("  " + ", ".join(missing))
        print("Then run:")
        print("  python admin\\check_imported_ai_ready.py")
        print("  python admin\\build_map_expansion.py --imported")
        print("  python admin\\apply_ai_ammo.py")
        return 1

    print("\nReady. Run: python admin\\build_map_expansion.py --imported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
