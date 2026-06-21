"""Expansion AI combat tuning + PvPLoadout deployment for all maps."""
from __future__ import annotations

import json
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
SERVER = ADMIN.parent

PVP_LOADOUT = "PvPLoadout"

# PvP AI — capable but not hyper-aggressive
AI_ACCURACY_MIN = 0.42
AI_ACCURACY_MAX = 0.68
AI_THREAT_DISTANCE = 450.0
AI_NOISE_INVESTIGATE = 250.0
AI_MAX_FLANK = 120.0
AI_SNIPER_PRONE_DIST = 140.0
AI_DAMAGE_DEALT = 1.0
AI_DAMAGE_RECEIVED = 1.0
AI_HEADSHOT_RESIST = 0.2
AI_HUNT_MODE = 3
AI_AGGRESSION_TIMEOUT = 180.0
AI_GUARD_AGGRESSION_TIMEOUT = 240.0

PROFILE_DIRS = [
    "profiles",
    "profiles_namalsk",
    "profiles_enoch",
    "profiles_sakhal",
    "profiles_takistan",
    "profiles_deerisle",
    "profiles_banov",
    "profiles_esseker",
    "profiles_rostow",
    "profiles_iztek",
    "profiles_alteria",
    "profiles_winterchernarus",
    "profiles_bitterroot",
    "profiles_deadfall",
]

MISSIONS = [
    "dayzOffline.chernarusplus",
    "regular.namalsk",
    "dayzOffline.enoch",
    "dayzOffline.sakhal",
    "dayzOffline.TakistanPlus",
    "empty.deerisle",
    "dayzOffline.banov",
    "dayzOffline.Esseker",
    "Offline.rostow",
    "empty.Iztek",
    "empty.alteria",
    "RegularWinter.chernarusplus",
    "empty.Bitterroot",
    "dayz.Deadfall",
]

# Expansion reads AI loadouts from the active -profiles folder, not mpmissions.
MISSION_PROFILE: dict[str, str] = {
    "dayzOffline.chernarusplus": "profiles",
    "regular.namalsk": "profiles_namalsk",
    "dayzOffline.enoch": "profiles_enoch",
    "dayzOffline.sakhal": "profiles_sakhal",
    "dayzOffline.TakistanPlus": "profiles_takistan",
    "empty.deerisle": "profiles_deerisle",
    "dayzOffline.banov": "profiles_banov",
    "dayzOffline.Esseker": "profiles_esseker",
    "Offline.rostow": "profiles_rostow",
    "empty.Iztek": "profiles_iztek",
    "empty.alteria": "profiles_alteria",
    "RegularWinter.chernarusplus": "profiles_winterchernarus",
    "empty.Bitterroot": "profiles_bitterroot",
    "dayz.Deadfall": "profiles_deadfall",
}


def _health(min_h: float = 0.92, max_h: float = 1.0) -> list[dict]:
    return [{"Min": min_h, "Max": max_h, "Zone": ""}]


def _item(
    class_name: str,
    *,
    chance: float = 1.0,
    attachments: list | None = None,
    cargo: list | None = None,
) -> dict:
    return {
        "ClassName": class_name,
        "Chance": chance,
        "Quantity": {"Min": 0.0, "Max": 0.0},
        "Health": _health(),
        "InventoryAttachments": attachments or [],
        "InventoryCargo": cargo or [],
        "ConstructionPartsBuilt": [],
    }


def _slot(slot_name: str, items: list[dict]) -> dict:
    return {"SlotName": slot_name, "Items": items}


def _mag(class_name: str) -> dict:
    return _item(class_name)


def build_m4() -> dict:
    return _item(
        "M4A1",
        attachments=[
            _slot(
                "",
                [
                    _mag("Mag_STANAG_30Rnd"),
                    _item("M4_Suppressor"),
                    _item("M4_T3NRDSOptic"),
                ],
            )
        ],
        cargo=[
            _mag("Mag_STANAG_30Rnd"),
            _mag("Mag_STANAG_30Rnd"),
            _mag("Mag_STANAG_30Rnd"),
            _item("BandageDressing"),
            _item("Morphine"),
            _item("RGD5Grenade"),
        ],
    )


def build_akm() -> dict:
    return _item(
        "AKM",
        attachments=[
            _slot(
                "",
                [
                    _mag("Mag_AKM_30Rnd"),
                    _item("AK_Suppressor"),
                    _item("KobraOptic"),
                ],
            )
        ],
        cargo=[
            _mag("Mag_AKM_30Rnd"),
            _mag("Mag_AKM_30Rnd"),
            _mag("Mag_AKM_30Rnd"),
            _item("BandageDressing"),
        ],
    )


def build_svd() -> dict:
    return _item(
        "SVD",
        attachments=[
            _slot(
                "",
                [
                    _mag("Mag_SVD_10Rnd"),
                    _item("PSO1Optic"),
                    _item("AK_Suppressor"),
                ],
            )
        ],
        cargo=[
            _mag("Mag_SVD_10Rnd"),
            _mag("Mag_SVD_10Rnd"),
            _item("Morphine"),
        ],
    )


def build_fal() -> dict:
    return _item(
        "FAL",
        attachments=[
            _slot(
                "",
                [
                    _mag("Mag_FAL_20Rnd"),
                    _item("ACOGOptic"),
                ],
            )
        ],
        cargo=[
            _mag("Mag_FAL_20Rnd"),
            _mag("Mag_FAL_20Rnd"),
            _item("BandageDressing"),
        ],
    )


def build_pvp_loadout(*, gear_theme: str = "temperate") -> dict:
    """gear_theme: winter | temperate | desert — vanilla class names only."""
    vest = _item(
        "PlateCarrierVest",
        attachments=[
            _slot(
                "",
                [
                    _item("PlateCarrierPouches"),
                    _item("PlateCarrierHolster", chance=0.85),
                ],
            )
        ],
    )
    helmet = _item(
        "BallisticHelmet_Black",
        attachments=[_slot("", [_item("NVGoggles", chance=0.85)])],
    )
    if gear_theme == "winter":
        clothing = [
            _slot("Body", [_item("GorkaEJacket_Winter")]),
            _slot("Legs", [_item("GorkaPants_Winter")]),
            _slot("Gloves", [_item("WoolGloves_Black")]),
        ]
    elif gear_theme == "desert":
        clothing = [
            _slot("Body", [_item("USMCJacket_Desert"), _item("TacticalShirt_Olive")]),
            _slot("Legs", [_item("USMCPants_Desert"), _item("CargoPants_Beige")]),
        ]
    else:
        clothing = [
            _slot("Body", [_item("GorkaEJacket_Autumn"), _item("TacticalShirt_Grey")]),
            _slot("Legs", [_item("GorkaPants_Autumn"), _item("CargoPants_Green")]),
        ]

    # One weapon picked at random (same pattern as WestLoadout)
    weapons = [
        build_m4(),
        build_akm(),
        build_svd(),
        build_fal(),
    ]

    return {
        "ClassName": "",
        "Chance": 1.0,
        "Quantity": {"Min": 0.0, "Max": 0.0},
        "Health": [],
        "InventoryAttachments": [
            *clothing,
            _slot("Vest", [vest]),
            _slot("Headgear", [helmet]),
            _slot("Feet", [_item("CombatBoots_Black"), _item("CombatBoots_Green")]),
            _slot("Back", [_item("AssaultBag_Black"), _item("CoyoteBag_Brown")]),
            _slot("Hips", [_item("MilitaryBelt")]),
            _slot("Hands", weapons),
        ],
        "InventoryCargo": [
            _item("TacticalBaconCan"),
            _item("WaterBottle"),
            _item("BandageDressing"),
            _item("Morphine"),
            _item("Epinephrine"),
        ],
        "ConstructionPartsBuilt": [],
    }


def _write_loadout_file(path: Path, *, gear_theme: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_pvp_loadout(gear_theme=gear_theme), indent=4) + "\n",
        encoding="utf-8",
    )


def write_pvp_loadout(
    mission: Path,
    *,
    gear_theme: str = "temperate",
    profile_name: str | None = None,
) -> list[Path]:
    """Write PvPLoadout.json to mission pack and the active profiles folder."""
    written: list[Path] = []
    mission_path = mission / "expansion" / "Loadouts" / f"{PVP_LOADOUT}.json"
    _write_loadout_file(mission_path, gear_theme=gear_theme)
    written.append(mission_path)

    prof = profile_name or MISSION_PROFILE.get(mission.name)
    if prof:
        profile_path = SERVER / prof / "ExpansionMod" / "Loadouts" / f"{PVP_LOADOUT}.json"
        _write_loadout_file(profile_path, gear_theme=gear_theme)
        written.append(profile_path)
    return written


def tune_patrol_dict(patrol: dict) -> None:
    patrol["AccuracyMin"] = AI_ACCURACY_MIN
    patrol["AccuracyMax"] = AI_ACCURACY_MAX
    patrol["ThreatDistanceLimit"] = AI_THREAT_DISTANCE
    patrol["NoiseInvestigationDistanceLimit"] = AI_NOISE_INVESTIGATE
    patrol["MaxFlankingDistance"] = AI_MAX_FLANK
    patrol["EnableFlankingOutsideCombat"] = 0
    patrol["SniperProneDistanceThreshold"] = AI_SNIPER_PRONE_DIST
    patrol["DamageMultiplier"] = AI_DAMAGE_DEALT
    patrol["DamageReceivedMultiplier"] = AI_DAMAGE_RECEIVED
    patrol["HeadshotResistance"] = AI_HEADSHOT_RESIST
    patrol["Speed"] = "WALK"
    patrol["UnderThreatSpeed"] = "JOG"
    patrol["DefaultStance"] = "STANDING"
    patrol["UnlimitedReload"] = 1
    patrol["CanBeTriggeredByAI"] = 0
    patrol["Formation"] = "RANDOM"
    patrol["FormationLooseness"] = 0.0
    if not patrol.get("Loadout"):
        patrol["Loadout"] = PVP_LOADOUT


def tune_patrol_settings_global(patrol_settings: dict) -> None:
    patrol_settings["AccuracyMin"] = AI_ACCURACY_MIN
    patrol_settings["AccuracyMax"] = AI_ACCURACY_MAX
    patrol_settings["ThreatDistanceLimit"] = AI_THREAT_DISTANCE
    patrol_settings["NoiseInvestigationDistanceLimit"] = AI_NOISE_INVESTIGATE
    patrol_settings["MaxFlankingDistance"] = AI_MAX_FLANK
    patrol_settings["EnableFlankingOutsideCombat"] = 0
    patrol_settings["SniperProneDistanceThreshold"] = AI_SNIPER_PRONE_DIST
    patrol_settings["DamageReceivedMultiplier"] = AI_DAMAGE_RECEIVED
    for p in patrol_settings.get("Patrols", []):
        tune_patrol_dict(p)


def tune_spatial_dict(spatial: dict) -> None:
    spatial["MinimumPlayerDistance"] = 80
    spatial["MinDistance"] = 150
    spatial["MaxDistance"] = 300
    for loc in spatial.get("Location", []):
        loc["Spatial_MinAccuracy"] = AI_ACCURACY_MIN
        loc["Spatial_MaxAccuracy"] = AI_ACCURACY_MAX
        loc["Spatial_HuntMode"] = AI_HUNT_MODE
        loc["Spatial_Timer"] = 35.0
        loc["Spatial_Chance"] = min(float(loc.get("Spatial_Chance", 0.65)), 0.65)
        if loc.get("Spatial_ZoneLoadout") in ("", "WestLoadout.json", "EastLoadout.json"):
            loc["Spatial_ZoneLoadout"] = f"{PVP_LOADOUT}.json"
        elif isinstance(loc.get("Spatial_ZoneLoadout"), list):
            loc["Spatial_ZoneLoadout"] = [f"{PVP_LOADOUT}.json"]
    for group in spatial.get("Group", []):
        group["Spatial_MinCount"] = 1
        group["Spatial_MaxCount"] = 3
        group["Spatial_Chance"] = 0.45


def patch_ai_settings(profile_dir: Path) -> bool:
    path = profile_dir / "ExpansionMod" / "Settings" / "AISettings.json"
    if not path.exists():
        template = SERVER / "profiles" / "ExpansionMod" / "Settings" / "AISettings.json"
        if template.exists():
            data = json.loads(template.read_text(encoding="utf-8"))
        else:
            data = {}
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
    data["AccuracyMin"] = AI_ACCURACY_MIN
    data["AccuracyMax"] = AI_ACCURACY_MAX
    data["ThreatDistanceLimit"] = AI_THREAT_DISTANCE
    data["NoiseInvestigationDistanceLimit"] = AI_NOISE_INVESTIGATE
    data["MaxFlankingDistance"] = AI_MAX_FLANK
    data["EnableFlankingOutsideCombat"] = 0
    data["SniperProneDistanceThreshold"] = AI_SNIPER_PRONE_DIST
    data["DamageMultiplier"] = AI_DAMAGE_DEALT
    data["DamageReceivedMultiplier"] = AI_DAMAGE_RECEIVED
    data["Vaulting"] = 1
    data["MemeLevel"] = 0
    data["AggressionTimeout"] = AI_AGGRESSION_TIMEOUT
    data["GuardAggressionTimeout"] = AI_GUARD_AGGRESSION_TIMEOUT
    data["OverrideClientWeaponFiring"] = 1
    data["RecreateWeaponNetworkRepresentation"] = 1
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    return True


def deploy_for_mission(
    mission_name: str,
    *,
    gear_theme: str = "temperate",
    profile_name: str | None = None,
) -> list[str]:
    mission = SERVER / "mpmissions" / mission_name
    if not mission.exists():
        return [f"  SKIP {mission_name} (missing)"]
    lines = []
    profile_name = profile_name or MISSION_PROFILE.get(mission_name)
    for path in write_pvp_loadout(
        mission, gear_theme=gear_theme, profile_name=profile_name
    ):
        rel = path.relative_to(SERVER)
        lines.append(f"  OK   {rel}")
    patrol_path = mission / "expansion" / "settings" / "AIPatrolSettings.json"
    if patrol_path.exists():
        patrol = json.loads(patrol_path.read_text(encoding="utf-8"))
        tune_patrol_settings_global(patrol)
        patrol_path.write_text(json.dumps(patrol, indent=4) + "\n", encoding="utf-8")
        lines.append(f"  OK   {mission_name}/AIPatrolSettings.json (combat tune)")
    spatial_path = mission / "expansion" / "settings" / "SpatialSettings.json"
    if spatial_path.exists():
        spatial = json.loads(spatial_path.read_text(encoding="utf-8"))
        tune_spatial_dict(spatial)
        spatial_path.write_text(json.dumps(spatial, indent=4) + "\n", encoding="utf-8")
        lines.append(f"  OK   {mission_name}/SpatialSettings.json")
    return lines


MISSION_GEAR: dict[str, str] = {
    "dayzOffline.chernarusplus": "temperate",
    "regular.namalsk": "winter",
    "dayzOffline.enoch": "temperate",
    "dayzOffline.sakhal": "winter",
    "dayzOffline.TakistanPlus": "desert",
}


def deploy_all() -> int:
    print("Deploying PvP AI loadouts + combat tuning:")
    for name in MISSIONS:
        theme = MISSION_GEAR.get(name, "temperate")
        for line in deploy_for_mission(name, gear_theme=theme):
            print(line)
    print("Patching Expansion AISettings in profiles:")
    for prof in PROFILE_DIRS:
        p = SERVER / prof
        if patch_ai_settings(p):
            print(f"  OK   {prof}/ExpansionMod/Settings/AISettings.json")
        else:
            print(f"  SKIP {prof}")
    return 0


if __name__ == "__main__":
    raise SystemExit(deploy_all())
