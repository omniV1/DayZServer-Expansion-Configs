#!/usr/bin/env python3
"""
Give Expansion AI more staying power in fights.

1. UnlimitedReload on all AIPatrolSettings patrols
2. Spatial_UnlimitedReload on all SpatialSettings entries
3. Higher Weapon*MagCount on simple-format loadouts
4. Extra spare mags in backpack cargo on complex patrol loadouts

Usage:
  python admin/apply_ai_ammo.py
  python admin/apply_ai_ammo.py --status
"""
from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
MISSIONS = SERVER / "mpmissions"
PROFILES = SERVER / "profiles" / "ExpansionMod"

# Simple loadouts: [min, max] mag counts per weapon slot
RIFLE_MAG = [4, 10]
HANDGUN_MAG = [3, 8]

SIMPLE_LOADOUTS = [
    "SoldierCDFLoadout.json",
    "SoldierMOTRSLoadout.json",
    "HumanLoadout.json",
    "CivilianLoadout.json",
    "RaiderLoadout.json",
]

# Complex Expansion loadouts used by patrols / war zones — extra mags in backpack cargo
EXTRA_BACKPACK_MAGS: dict[str, list[str]] = {
    "WestLoadout.json": [
        "Mag_STANAG_30Rnd",
        "Mag_STANAG_30Rnd",
        "Mag_STANAG_30Rnd",
        "Mag_STANAG_60Rnd",
        "Mag_STANAG_60Rnd",
    ],
    "EastLoadout.json": [
        "Mag_AKM_30Rnd",
        "Mag_AKM_30Rnd",
        "Mag_AKM_30Rnd",
        "Mag_AKM_30Rnd",
        "Ammo_762x39",
        "Ammo_762x39",
    ],
    "GorkaLoadout.json": [
        "Mag_AKM_30Rnd",
        "Mag_AKM_30Rnd",
        "Mag_AKM_30Rnd",
        "Ammo_762x39",
        "Ammo_762x39",
    ],
    "BanditLoadout.json": [
        "Mag_AKM_30Rnd",
        "Mag_AKM_30Rnd",
        "Mag_STANAG_30Rnd",
        "Mag_STANAG_30Rnd",
        "Ammo_762x39",
        "Ammo_762x54",
    ],
    "PoliceLoadout.json": [
        "Mag_12gaSlug",
        "Mag_12gaSlug",
        "Mag_12gaSlug",
        "Mag_CZ75_15Rnd",
        "Mag_CZ75_15Rnd",
    ],
    "NBCLoadout.json": [
        "Mag_AKM_30Rnd",
        "Mag_AKM_30Rnd",
        "Mag_AKM_30Rnd",
        "Mag_SVD_10Rnd",
        "Mag_SVD_10Rnd",
        "Ammo_762x39",
    ],
}

MAG_ITEM_TEMPLATE = {
    "ClassName": "",
    "Chance": 1.0,
    "Quantity": {"Min": 0.0, "Max": 0.0},
    "Health": [],
    "InventoryAttachments": [],
    "InventoryCargo": [],
    "ConstructionPartsBuilt": [],
}

BACKPACK_CLASSES = {
    "CoyoteBag_Brown",
    "CoyoteBag_Green",
    "CoyoteBag_Black",
    "TortillaBag",
    "TaloonBag_Blue",
    "TaloonBag_Green",
    "TaloonBag_Orange",
    "TaloonBag_Violet",
    "AssaultBag_Black",
    "AssaultBag_Green",
    "AssaultBag_Ttsko",
    "MountainBag_Green",
    "DryBag_Green",
    "HuntingBag",
    "SmershBag",
    "AliceBag_Green",
    "AliceBag_Black",
    "AliceBag_Camo",
}


def mag_item(class_name: str) -> dict:
    item = deepcopy(MAG_ITEM_TEMPLATE)
    item["ClassName"] = class_name
    return item


def patch_unlimited_reload_patrols(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(r'"UnlimitedReload"\s*:\s*0\b', '"UnlimitedReload": 1', text)
    if n == 0:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def patch_spatial_unlimited(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(
        r'"Spatial_UnlimitedReload"\s*:\s*0\b',
        '"Spatial_UnlimitedReload": 1',
        text,
    )
    if n == 0:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def patch_simple_loadout(path: Path) -> bool:
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    if "WeaponRifleMagCount" in data and data["WeaponRifleMagCount"] != RIFLE_MAG:
        data["WeaponRifleMagCount"] = RIFLE_MAG
        changed = True
    if "WeaponHandgunMagCount" in data and data["WeaponHandgunMagCount"] != HANDGUN_MAG:
        data["WeaponHandgunMagCount"] = HANDGUN_MAG
        changed = True
    if changed:
        path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    return changed


def inject_backpack_mags(node: dict, extra_mags: list[str]) -> bool:
    """Add spare mags to backpack cargo once per loadout tree walk."""
    changed = False
    if node.get("ClassName") in BACKPACK_CLASSES:
        cargo = node.setdefault("InventoryCargo", [])
        existing = {i.get("ClassName") for i in cargo if isinstance(i, dict)}
        for mag in extra_mags:
            if mag in existing:
                continue
            cargo.append(mag_item(mag))
            existing.add(mag)
            changed = True
    for key in ("InventoryAttachments", "Items", "InventoryCargo"):
        val = node.get(key)
        if isinstance(val, list):
            for child in val:
                if isinstance(child, dict):
                    changed |= inject_backpack_mags(child, extra_mags)
    return changed


def patch_complex_loadout(path: Path, extra_mags: list[str]) -> bool:
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False
    if not inject_backpack_mags(data, extra_mags):
        return False
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    return True


def loadout_paths(name: str) -> list[Path]:
    paths = [PROFILES / "Loadouts" / name]
    for mission in MISSIONS.iterdir():
        p = mission / "expansion" / "Loadouts" / name
        if p.exists():
            paths.append(p)
    return paths


def find_files(pattern: str) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for base in (MISSIONS, PROFILES, SERVER / "profiles" / "ExpansionMod"):
        for path in base.glob(pattern):
            if path not in seen:
                seen.add(path)
                out.append(path)
    return sorted(out)


def cmd_status() -> None:
    patrol = find_files("**/AIPatrolSettings.json")
    spatial = find_files("**/SpatialSettings.json")
    if patrol:
        t = patrol[0].read_text(encoding="utf-8")
        off = len(re.findall(r'"UnlimitedReload":\s*0', t))
        on = len(re.findall(r'"UnlimitedReload":\s*1', t))
        print(f"Patrol sample ({patrol[0].parent.parent.name}): UnlimitedReload on={on} off={off}")
    if spatial:
        t = spatial[0].read_text(encoding="utf-8")
        off = len(re.findall(r'"Spatial_UnlimitedReload":\s*0', t))
        on = len(re.findall(r'"Spatial_UnlimitedReload":\s*1', t))
        print(f"Spatial sample: UnlimitedReload on={on} off={off}")
    p = PROFILES / "Loadouts" / "HumanLoadout.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        print(f"HumanLoadout rifle mags: {d.get('WeaponRifleMagCount')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.status:
        cmd_status()
        return 0

    print("Patching AI ammo / reload settings...\n")

    for path in find_files("**/AIPatrolSettings.json"):
        if patch_unlimited_reload_patrols(path):
            print(f"  OK   patrol UnlimitedReload: {path.relative_to(SERVER)}")

    for path in find_files("**/SpatialSettings.json"):
        if patch_spatial_unlimited(path):
            print(f"  OK   spatial UnlimitedReload: {path.relative_to(SERVER)}")

    for name in SIMPLE_LOADOUTS:
        for path in loadout_paths(name):
            if patch_simple_loadout(path):
                print(f"  OK   mag counts: {path.relative_to(SERVER)}")

    for name, mags in EXTRA_BACKPACK_MAGS.items():
        for path in loadout_paths(name):
            if patch_complex_loadout(path, mags):
                print(f"  OK   backpack mags: {path.relative_to(SERVER)}")

    print("\nDone. Restart server (or respawn AI) for changes to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
