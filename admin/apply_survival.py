#!/usr/bin/env python3
"""Fix hunger/thirst metabolism: Namalsk event system + normal spawn food/water values."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
SERVER = ADMIN.parent
MISSIONS = SERVER / "mpmissions"

SPAWN_ENERGY = 500.0
SPAWN_WATER = 500.0

SERVER_CFGS = [
    "serverDZChernarus.cfg",
    "serverDZEnoch.cfg",
    "serverDZSakhal.cfg",
    "serverDZ_Takistan.cfg",
    "serverDZ_Namalsk.cfg",
]


def patch_spawn_settings(path: Path) -> bool:
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    sg = data.get("StartingGear", {})
    sg["ApplyEnergySources"] = 0
    data["StartingGear"] = sg
    data["SpawnEnergyValue"] = SPAWN_ENERGY
    data["SpawnWaterValue"] = SPAWN_WATER
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    return True


def patch_server_cfg(path: Path) -> str:
    if not path.exists():
        return f"SKIP {path.name} (missing)"
    text = path.read_text(encoding="utf-8")
    if "enableCfgGameplayFile" in text:
        return f"OK   {path.name} (already has enableCfgGameplayFile)"
    text = text.replace(
        "disableCrosshair=0;",
        "disableCrosshair=0;\nenableCfgGameplayFile = 1;",
        1,
    )
    path.write_text(text, encoding="utf-8")
    return f"OK   {path.name} (enableCfgGameplayFile=1)"


def main() -> int:
    print("Survival fix: SpawnEnergy/Water=500, ApplyEnergySources=0, enableCfgGameplayFile on cfgs")
    for mission in MISSIONS_ROOT.iterdir() if (MISSIONS_ROOT := MISSIONS).exists() else []:
        sp = mission / "expansion" / "settings" / "SpawnSettings.json"
        if patch_spawn_settings(sp):
            print(f"  OK   {mission.name}/SpawnSettings.json")

    for name in SERVER_CFGS:
        try:
            print(f"  {patch_server_cfg(SERVER / name)}")
        except OSError as e:
            print(f"  WARN {name}: {e}")

    print("\nNamalsk init.c must use OnInitServer(true,...) — already patched in mission.")
    print("Restart the server after applying.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
