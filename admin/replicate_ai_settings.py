#!/usr/bin/env python3
"""
Sync Expansion AI patrol + spatial tuning from Chernarus to other missions.

- Patrols: global caps, radii, UnlimitedReload; keeps each map's existing routes/waypoints.
- Spatial: copies Group + global timers/MaxAI; skips Chernarus-only map coordinates unless enabled in ai_config.json.
- Namalsk: creates expansion/settings if missing (patrol enabled, object patrols only).

Usage:
  python admin/replicate_ai_settings.py
  python admin/replicate_ai_settings.py --status
"""
from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
ADMIN = Path(__file__).resolve().parent
CONFIG_PATH = ADMIN / "ai_config.json"
MISSIONS = SERVER / "mpmissions"

# Top-level AIPatrol fields copied from source (not Patrols array)
PATROL_GLOBAL_KEYS = [
    "Enabled",
    "FormationScale",
    "DespawnTime",
    "RespawnTime",
    "MinDistRadius",
    "MaxDistRadius",
    "DespawnRadius",
    "AccuracyMin",
    "AccuracyMax",
    "ThreatDistanceLimit",
    "NoiseInvestigationDistanceLimit",
    "MaxFlankingDistance",
    "EnableFlankingOutsideCombat",
    "DamageMultiplier",
    "DamageReceivedMultiplier",
    "ShoryukenChance",
    "ShoryukenDamageMultiplier",
    "LoadBalancingCategories",
]

# Spatial keys copied; Point/Location cleared when sync_spatial_fixed_locations is false
SPATIAL_GLOBAL_KEYS = [
    "Version",
    "Spatial_MinTimer",
    "Spatial_MaxTimer",
    "MinDistance",
    "MaxDistance",
    "HuntMode",
    "Points_Enabled",
    "Locations_Enabled",
    "Audio_Enabled",
    "EngageTimer",
    "CleanupTimer",
    "PlayerChecks",
    "MaxAI",
    "GroupDifficulty",
    "MinimumPlayerDistance",
    "MaxSoloPlayers",
    "MinimumAge",
    "ActiveHoursEnabled",
    "ActiveStartTime",
    "ActiveStopTime",
    "TargetBone",
    "MessageType",
    "MessageTitle",
    "MessageText",
    "LootWhitelist",
    "Spatial_InVehicle",
    "Spatial_IsBleeding",
    "Spatial_IsRestrained",
    "Spatial_IsUnconscious",
    "Spatial_IsInSafeZone",
    "Spatial_TPSafeZone",
    "Spatial_InOwnTerritory",
    "Group",
]


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def mission_path(name: str) -> Path:
    return MISSIONS / name


def sync_patrol_file(source: dict, target_path: Path) -> bool:
    if not target_path.exists():
        return False
    target = json.loads(target_path.read_text(encoding="utf-8"))
    changed = False
    for key in PATROL_GLOBAL_KEYS:
        if key in source and target.get(key) != source[key]:
            target[key] = deepcopy(source[key])
            changed = True
    for patrol in target.get("Patrols", []):
        if patrol.get("UnlimitedReload") != 1:
            patrol["UnlimitedReload"] = 1
            changed = True
    if changed:
        target_path.write_text(json.dumps(target, indent=4) + "\n", encoding="utf-8")
    return changed


def build_namalsk_patrols(source: dict) -> dict:
    """Patrol shell for Namalsk: global tuning + object/heli patrols only (no Chernarus waypoints)."""
    out = {k: deepcopy(source[k]) for k in PATROL_GLOBAL_KEYS if k in source}
    out["m_Version"] = source.get("m_Version", 32)
    object_patrols = []
    for p in source.get("Patrols", []):
        if p.get("ObjectClassName") or p.get("LoadBalancingCategory") in (
            "HelicopterWreck",
            "ObjectPatrol",
            "ContaminatedArea",
        ):
            cp = deepcopy(p)
            cp["UnlimitedReload"] = 1
            cp["Waypoints"] = []
            object_patrols.append(cp)
    out["Patrols"] = object_patrols
    return out


def sync_spatial_file(source: dict, target_path: Path, fixed_locations: bool) -> bool:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target = {}
    if target_path.exists():
        target = json.loads(target_path.read_text(encoding="utf-8"))
    out = {}
    for key in SPATIAL_GLOBAL_KEYS:
        if key in source:
            out[key] = deepcopy(source[key])
    if fixed_locations:
        for key in ("Point", "Location"):
            if key in source:
                out[key] = deepcopy(source[key])
    else:
        out["Point"] = []
        out["Location"] = []
        if not fixed_locations:
            out["Points_Enabled"] = 0
    # Ensure unlimited reload on groups/points/locations
    for group in out.get("Group", []):
        if group.get("Spatial_UnlimitedReload") != 1:
            group["Spatial_UnlimitedReload"] = 1
    for section in ("Point", "Location"):
        for entry in out.get(section, []):
            if entry.get("Spatial_UnlimitedReload") != 1:
                entry["Spatial_UnlimitedReload"] = 1
    changed = target != out
    target_path.write_text(json.dumps(out, indent=4) + "\n", encoding="utf-8")
    return changed or not target


def copy_loadouts(source_mission: str, target_mission: str) -> int:
    src = mission_path(source_mission) / "expansion" / "Loadouts"
    dst = mission_path(target_mission) / "expansion" / "Loadouts"
    if not src.exists():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in src.glob("*.json"):
        dest = dst / f.name
        if not dest.exists() or f.stat().st_mtime > dest.stat().st_mtime:
            shutil.copy2(f, dest)
            n += 1
    return n


def cmd_status(cfg: dict) -> None:
    src = cfg["source_mission"]
    sp = mission_path(src) / "expansion/settings/AIPatrolSettings.json"
    print(f"Source: {src}")
    if sp.exists():
        d = json.loads(sp.read_text(encoding="utf-8"))
        print(f"  Patrols: {len(d.get('Patrols', []))}, Enabled={d.get('Enabled')}")
        print(f"  Patrol MaxPatrols: {d['LoadBalancingCategories']['Patrol'][0]['MaxPatrols']}")
    for name in cfg["patrol_targets"]:
        p = mission_path(name) / "expansion/settings/AIPatrolSettings.json"
        ss = mission_path(name) / "expansion/settings/SpatialSettings.json"
        print(f"{name}: AIPatrol={'yes' if p.exists() else 'NO'} Spatial={'yes' if ss.exists() else 'no'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--copy-loadouts", action="store_true", help="Copy mission Loadouts JSON from Chernarus")
    args = ap.parse_args()
    cfg = load_config()
    if args.status:
        cmd_status(cfg)
        return 0

    src_name = cfg["source_mission"]
    src_patrol_path = mission_path(src_name) / "expansion/settings/AIPatrolSettings.json"
    src_spatial_path = mission_path(src_name) / "expansion/settings/SpatialSettings.json"
    if not src_patrol_path.exists():
        print("Missing source AIPatrolSettings.json")
        return 1

    source_patrol = json.loads(src_patrol_path.read_text(encoding="utf-8"))
    source_spatial = {}
    if src_spatial_path.exists():
        source_spatial = json.loads(src_spatial_path.read_text(encoding="utf-8"))

    print(f"Syncing AI settings from {src_name}...\n")

    for name in cfg["patrol_targets"]:
        settings_dir = mission_path(name) / "expansion/settings"
        settings_dir.mkdir(parents=True, exist_ok=True)
        patrol_file = settings_dir / "AIPatrolSettings.json"

        if name == "regular.namalsk" and not patrol_file.exists():
            built = build_namalsk_patrols(source_patrol)
            patrol_file.write_text(json.dumps(built, indent=4) + "\n", encoding="utf-8")
            print(f"  OK   {name}: created AIPatrolSettings ({len(built['Patrols'])} object patrols)")
        elif patrol_file.exists():
            if sync_patrol_file(source_patrol, patrol_file):
                print(f"  OK   {name}: synced patrol globals + UnlimitedReload")
            else:
                print(f"  --   {name}: patrol already up to date")
        else:
            print(f"  WARN {name}: no AIPatrolSettings.json (skipped)")

        if args.copy_loadouts:
            n = copy_loadouts(src_name, name)
            if n:
                print(f"  OK   {name}: copied {n} loadout file(s)")

    fixed = cfg.get("sync_spatial_fixed_locations", False)
    if source_spatial:
        for name in cfg.get("spatial_targets", []):
            spatial_file = mission_path(name) / "expansion/settings/SpatialSettings.json"
            if sync_spatial_file(source_spatial, spatial_file, fixed):
                mode = "with coords" if fixed else "groups only (no Chernarus coords)"
                print(f"  OK   {name}: SpatialSettings ({mode})")

    print("\nRun: python admin/apply_ai_ammo.py  (ammo/reload on all maps)")
    print("Restart DayZ server for changes to load.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
