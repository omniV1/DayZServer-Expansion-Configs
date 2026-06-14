#!/usr/bin/env python3
"""
Build Expansion SpawnSettings, AILocationSettings, AIPatrolSettings, and SpatialSettings
for Namalsk, Livonia (Enoch), Sakhal, and Takistan from COT teleports + mission spawn bubbles.

Usage:
  python admin/build_map_expansion.py namalsk enoch sakhal
  python admin/build_map_expansion.py --all
  python admin/build_map_expansion.py takistan
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

SERVER = Path(__file__).resolve().parent.parent
ADMIN = Path(__file__).resolve().parent
if str(ADMIN) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ADMIN))

from ai_combat import (
    AI_ACCURACY_MAX,
    AI_ACCURACY_MIN,
    AI_HUNT_MODE,
    PVP_LOADOUT,
    deploy_for_mission,
    tune_patrol_dict,
    tune_patrol_settings_global,
    tune_spatial_dict,
)

# PvP squads: 4–6 AI per site (reduced from 6–8)
TOWN_MIN_AI = 2
TOWN_MAX_AI = 4
HUB_MIN_AI = 2
HUB_MAX_AI = 4
PATROL_CATEGORY_MIN = 24
PATROL_CATEGORY_CAP = 32
OBJECT_PATROL_MAX = 12
HELICOPTER_WRECK_MAX = 18
SPATIAL_MAX_AI_CAP = 60
SPATIAL_MAX_AI_FLOOR = 30

CHERNARUS_AI_KEEP_TERMS = [
    "Airfield",
    "Military",
    "Chernogorsk",
    "Elektrozavodsk",
    "Berezino",
    "Severograd",
    "Svetloyarsk",
    "Zelenogorsk",
    "Vybor",
    "Stary Sobor",
    "Gorka",
    "Solnechny",
    "Krasnostav",
    "Balota",
]

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


@dataclass
class MapConfig:
    key: str
    mission: str
    profile: str
    teleports_file: str
    cache_file: str
    patrol_prefix: str
    town_types: list[str]
    roaming_types: list[str]
    spatial_types: list[str]
    type_radius: dict[str, float]
    type_category: dict[str, str]
    extra_town_names: list[str] = field(default_factory=list)
    patrol_hubs: list[tuple] = field(default_factory=list)
    spawn_from_settlements: bool = False
    settlement_spawn_types: list[str] = field(default_factory=lambda: ["Capital", "City", "Village"])
    max_spawn_regions: int = 8
    estimate_y: Callable[[float, float], float] | None = None
    gear_theme: str = "temperate"
    spawn_energy: float = 500.0
    spawn_water: float = 500.0
    military_patrol_types: list[str] = field(default_factory=list)
    armed_town_types: list[str] = field(default_factory=lambda: ["City", "Capital"])
    structure_poi_file: str = ""
    poi_patrol_keywords: list[str] = field(default_factory=list)
    poi_patrol_exclude_substrings: list[str] = field(default_factory=list)
    spatial_poi_keywords: list[str] = field(default_factory=list)
    merge_structure_spawn_regions: bool = False
    max_structure_spawn_regions: int = 12
    structure_roaming_radius: float = 320.0
    ai_winter_gear: bool = False


def _y_namalsk(x: float, z: float) -> float:
    return 8.0


def _y_enoch(x: float, z: float) -> float:
    return 275.0


def _y_sakhal(x: float, z: float) -> float:
    return 45.0 if z < 9000 else 25.0


def _y_chernarus(x: float, z: float) -> float:
    if z > 12000:
        return 55.0
    if x < 3000 and z < 3000:
        return 12.0
    if x > 11000 and z > 11000:
        return 140.0
    return 120.0


def _y_takistan(x: float, z: float) -> float:
    if x < 2800 and z < 4200:
        return 385.0
    if z > 9500 or x > 9000:
        return 55.0
    if x > 7500 and z < 3500:
        return 95.0
    return 115.0


GENERIC_TYPE_RADIUS = {
    "Capital": 650.0,
    "City": 500.0,
    "Village": 350.0,
    "Local": 220.0,
    "Hill": 250.0,
    "Marine": 220.0,
    "Camp": 280.0,
    "Ruin": 240.0,
    "Airfield": 450.0,
    "Military Base": 400.0,
}

GENERIC_TYPE_CATEGORY = {
    "Capital": "Capital",
    "City": "City",
    "Village": "Village",
    "Local": "Local",
    "Hill": "Local",
    "Marine": "Local",
    "Camp": "Local",
    "Ruin": "Local",
    "Airfield": "Local",
    "Military Base": "Local",
}

GENERIC_POI_KEYWORDS = [
    "airfield",
    "army",
    "base",
    "bunker",
    "camp",
    "castle",
    "factory",
    "harbor",
    "industrial",
    "military",
    "mine",
    "police",
    "port",
    "prison",
    "quarry",
    "radio",
]


MAP_CONFIGS: dict[str, MapConfig] = {
    "namalsk": MapConfig(
        key="namalsk",
        mission="regular.namalsk",
        profile="profiles_namalsk",
        teleports_file="Teleports_namalsk.json",
        cache_file="namalsk_locations.json",
        patrol_prefix="NamalskPatrol",
        town_types=["City", "Village"],
        roaming_types=["City", "Village", "Local", "Hill", "Marine"],
        spatial_types=["Camp", "City", "Village"],
        type_radius={
            "City": 500.0,
            "Village": 350.0,
            "Local": 200.0,
            "Hill": 250.0,
            "Marine": 200.0,
            "Camp": 280.0,
        },
        type_category={
            "City": "City",
            "Village": "Village",
            "Local": "Local",
            "Hill": "Local",
            "Marine": "Local",
            "Camp": "Local",
        },
        extra_town_names=["Tara harbor"],
        patrol_hubs=[
            ("TaraHarbor", 7823.86, 7513.78, "Civilian", "", "ALTERNATE", 2),
            ("Brensk", 4396.13, 4727.53, "West", "WestLoadout", "ALTERNATE", 2),
            ("Sebjan", 5284.94, 8624.85, "East", "EastLoadout", "ALTERNATE", 2),
        ],
        structure_poi_file="namalsk_structure_pois.json",
        poi_patrol_keywords=[
            "athena",
            "bk-",
            "airfield",
            "factory",
            "hospital",
            "refugee",
            "outpost",
            "phoenix",
            "skat",
            "uranium",
            "research",
            "c-130",
            "mohawk",
            "warehouse",
            "sawmill",
            "dam",
            "bering",
            "sibirskiy",
            "alakit",
            "warehouses",
        ],
        poi_patrol_exclude_substrings=["bay", "marsh", "strait", "iceberg", " pass", "valley"],
        spatial_poi_keywords=[],
        merge_structure_spawn_regions=True,
        max_structure_spawn_regions=14,
        structure_roaming_radius=340.0,
        spawn_from_settlements=False,
        estimate_y=_y_namalsk,
        gear_theme="winter",
        spawn_energy=500.0,
        spawn_water=500.0,
        ai_winter_gear=True,
    ),
    "enoch": MapConfig(
        key="enoch",
        mission="dayzOffline.enoch",
        profile="profiles_enoch",
        teleports_file="Teleports_enoch.json",
        cache_file="enoch_locations.json",
        patrol_prefix="EnochPatrol",
        town_types=["City", "Village"],
        roaming_types=["City", "Village", "Local", "Hill", "Marine", "Camp", "Ruin"],
        spatial_types=["Camp", "Ruin", "City"],
        military_patrol_types=["Ruin"],
        type_radius={
            "City": 500.0,
            "Village": 350.0,
            "Local": 200.0,
            "Hill": 250.0,
            "Marine": 200.0,
            "Camp": 280.0,
            "Ruin": 220.0,
        },
        type_category={
            "City": "City",
            "Village": "Village",
            "Local": "Local",
            "Hill": "Local",
            "Marine": "Local",
            "Camp": "Local",
            "Ruin": "Local",
        },
        patrol_hubs=[
            ("Bielawa", 1573.45, 9677.45, "Civilian", "", "ALTERNATE", 2),
            ("Lukow", 3529.65, 11966.53, "Civilian", "", "ALTERNATE", 2),
            ("Brena", 6617.63, 11211.03, "West", "WestLoadout", "ALTERNATE", 2),
            ("Radunin", 7298.38, 6491.90, "Raiders", "", "ALTERNATE", 2),
        ],
        spawn_from_settlements=False,
        estimate_y=_y_enoch,
        gear_theme="temperate",
    ),
    "sakhal": MapConfig(
        key="sakhal",
        mission="dayzOffline.sakhal",
        profile="profiles_sakhal",
        teleports_file="Teleports_sakhal.json",
        cache_file="sakhal_locations.json",
        patrol_prefix="SakhalPatrol",
        town_types=["Capital", "City", "Village"],
        roaming_types=["Capital", "City", "Village", "Local", "Hill", "Marine"],
        spatial_types=["Capital", "City"],
        armed_town_types=["Capital", "City"],
        type_radius={
            "Capital": 800.0,
            "City": 500.0,
            "Village": 350.0,
            "Local": 200.0,
            "Hill": 250.0,
            "Marine": 200.0,
        },
        type_category={
            "Capital": "Capital",
            "City": "City",
            "Village": "Village",
            "Local": "Local",
            "Hill": "Local",
            "Marine": "Local",
        },
        patrol_hubs=[
            ("Petropavlovsk", 4749.0, 10695.0, "Civilian", "", "ALTERNATE", 2),
            ("Severomorsk", 9544.0, 13656.0, "East", "EastLoadout", "ALTERNATE", 2),
            ("Aniva", 12895.0, 7273.0, "Civilian", "", "ALTERNATE", 2),
            ("Nogovo", 7814.0, 7949.0, "West", "WestLoadout", "ALTERNATE", 2),
        ],
        spawn_from_settlements=True,
        settlement_spawn_types=["Capital", "City", "Village"],
        max_spawn_regions=10,
        estimate_y=_y_sakhal,
        gear_theme="winter",
        spawn_energy=500.0,
        spawn_water=500.0,
        ai_winter_gear=True,
    ),
    "takistan": MapConfig(
        key="takistan",
        mission="dayzOffline.TakistanPlus",
        profile="profiles_takistan",
        teleports_file="Teleports_TakistanPlus.json",
        cache_file="takistan_locations.json",
        patrol_prefix="TakistanPatrol",
        town_types=["City", "Local"],
        roaming_types=["City", "StrongpointArea", "Hill", "Local"],
        spatial_types=["StrongpointArea", "City"],
        military_patrol_types=["StrongpointArea"],
        type_radius={
            "City": 500.0,
            "StrongpointArea": 350.0,
            "Hill": 250.0,
            "Local": 200.0,
        },
        type_category={
            "City": "City",
            "StrongpointArea": "Local",
            "Hill": "Local",
            "Local": "Local",
        },
        patrol_hubs=[
            ("Chaman", 876.04, 3099.05, "Civilian", "", "ALTERNATE", 2),
            ("FeeruzAbad", 5364.53, 6197.93, "West", "WestLoadout", "ALTERNATE", 2),
            ("Rasman", 6244.28, 11217.34, "East", "EastLoadout", "ALTERNATE", 2),
            ("Hachaman", 9152.49, 9741.92, "Civilian", "", "ALTERNATE", 2),
        ],
        spawn_from_settlements=False,
        estimate_y=_y_takistan,
        gear_theme="desert",
    ),
    "chernarus": MapConfig(
        key="chernarus",
        mission="dayzOffline.chernarusplus",
        profile="profiles",
        teleports_file="Teleports_chernarusplus.json",
        cache_file="chernarus_locations.json",
        patrol_prefix="ChernarusPatrol",
        town_types=["City", "Village", "Capital"],
        roaming_types=["City", "Village", "Capital", "Local", "Hill", "Marine", "Airfield", "Military Base", "Camp"],
        spatial_types=["Airfield", "Military Base", "City", "Capital"],
        military_patrol_types=["Airfield", "Military Base"],
        armed_town_types=["City", "Capital"],
        type_radius={
            "City": 500.0,
            "Capital": 650.0,
            "Village": 350.0,
            "Airfield": 450.0,
            "Military Base": 400.0,
            "Local": 200.0,
            "Hill": 250.0,
            "Marine": 200.0,
            "Camp": 280.0,
        },
        type_category={
            "City": "City",
            "Capital": "Capital",
            "Village": "Village",
            "Airfield": "Local",
            "Military Base": "Local",
            "Local": "Local",
            "Hill": "Local",
            "Marine": "Local",
            "Camp": "Local",
        },
        patrol_hubs=[],
        estimate_y=_y_chernarus,
        gear_theme="temperate",
    ),
    "deerisle": MapConfig(
        key="deerisle",
        mission="empty.deerisle",
        profile="profiles_deerisle",
        teleports_file="Teleports_deerisle.json",
        cache_file="deerisle_locations.json",
        patrol_prefix="DeerIslePatrol",
        town_types=["Capital", "City", "Village"],
        roaming_types=list(GENERIC_TYPE_RADIUS),
        spatial_types=["Capital", "City", "Airfield", "Military Base", "Camp"],
        military_patrol_types=["Airfield", "Military Base"],
        armed_town_types=["Capital", "City"],
        type_radius=GENERIC_TYPE_RADIUS,
        type_category=GENERIC_TYPE_CATEGORY,
        poi_patrol_keywords=GENERIC_POI_KEYWORDS,
        spawn_from_settlements=True,
        max_spawn_regions=10,
        gear_theme="temperate",
    ),
    "banov": MapConfig(
        key="banov",
        mission="dayzOffline.banov",
        profile="profiles_banov",
        teleports_file="Teleports_banov.json",
        cache_file="banov_locations.json",
        patrol_prefix="BanovPatrol",
        town_types=["Capital", "City", "Village"],
        roaming_types=list(GENERIC_TYPE_RADIUS),
        spatial_types=["Capital", "City", "Airfield", "Military Base", "Camp"],
        military_patrol_types=["Airfield", "Military Base"],
        armed_town_types=["Capital", "City"],
        type_radius=GENERIC_TYPE_RADIUS,
        type_category=GENERIC_TYPE_CATEGORY,
        poi_patrol_keywords=GENERIC_POI_KEYWORDS,
        spawn_from_settlements=True,
        max_spawn_regions=10,
        gear_theme="temperate",
    ),
    "esseker": MapConfig(
        key="esseker",
        mission="dayzOffline.Esseker",
        profile="profiles_esseker",
        teleports_file="Teleports_esseker.json",
        cache_file="esseker_locations.json",
        patrol_prefix="EssekerPatrol",
        town_types=["Capital", "City", "Village"],
        roaming_types=list(GENERIC_TYPE_RADIUS),
        spatial_types=["Capital", "City", "Airfield", "Military Base", "Camp"],
        military_patrol_types=["Airfield", "Military Base"],
        armed_town_types=["Capital", "City"],
        type_radius=GENERIC_TYPE_RADIUS,
        type_category=GENERIC_TYPE_CATEGORY,
        poi_patrol_keywords=GENERIC_POI_KEYWORDS,
        spawn_from_settlements=True,
        max_spawn_regions=8,
        gear_theme="temperate",
    ),
    "rostow": MapConfig(
        key="rostow",
        mission="Offline.rostow",
        profile="profiles_rostow",
        teleports_file="Teleports_rostow.json",
        cache_file="rostow_locations.json",
        patrol_prefix="RostowPatrol",
        town_types=["Capital", "City", "Village"],
        roaming_types=list(GENERIC_TYPE_RADIUS),
        spatial_types=["Capital", "City", "Airfield", "Military Base", "Camp"],
        military_patrol_types=["Airfield", "Military Base"],
        armed_town_types=["Capital", "City"],
        type_radius=GENERIC_TYPE_RADIUS,
        type_category=GENERIC_TYPE_CATEGORY,
        poi_patrol_keywords=GENERIC_POI_KEYWORDS,
        spawn_from_settlements=True,
        max_spawn_regions=10,
        gear_theme="temperate",
    ),
    "iztek": MapConfig(
        key="iztek",
        mission="empty.Iztek",
        profile="profiles_iztek",
        teleports_file="Teleports_iztek.json",
        cache_file="iztek_locations.json",
        patrol_prefix="IztekPatrol",
        town_types=["Capital", "City", "Village"],
        roaming_types=list(GENERIC_TYPE_RADIUS),
        spatial_types=["Capital", "City", "Airfield", "Military Base", "Camp"],
        military_patrol_types=["Airfield", "Military Base"],
        armed_town_types=["Capital", "City"],
        type_radius=GENERIC_TYPE_RADIUS,
        type_category=GENERIC_TYPE_CATEGORY,
        poi_patrol_keywords=GENERIC_POI_KEYWORDS,
        spawn_from_settlements=True,
        max_spawn_regions=8,
        gear_theme="desert",
    ),
    "alteria": MapConfig(
        key="alteria",
        mission="empty.alteria",
        profile="profiles_alteria",
        teleports_file="Teleports_alteria.json",
        cache_file="alteria_locations.json",
        patrol_prefix="AlteriaPatrol",
        town_types=["Capital", "City", "Village"],
        roaming_types=list(GENERIC_TYPE_RADIUS),
        spatial_types=["Capital", "City", "Airfield", "Military Base", "Camp"],
        military_patrol_types=["Airfield", "Military Base"],
        armed_town_types=["Capital", "City"],
        type_radius=GENERIC_TYPE_RADIUS,
        type_category=GENERIC_TYPE_CATEGORY,
        poi_patrol_keywords=GENERIC_POI_KEYWORDS,
        spawn_from_settlements=True,
        max_spawn_regions=8,
        gear_theme="temperate",
    ),
}


def _gear_item(class_name: str, quantity: int = -1, attachments: list[str] | None = None) -> dict:
    return {"ClassName": class_name, "Quantity": quantity, "Attachments": attachments or []}


PRIMARY_RIFLE = {
    "ClassName": "AKM",
    "Quantity": 1,
    "Attachments": ["AK_PlasticBttstck", "AK_PlasticHndgrd", "Mag_AKM_30Rnd"],
}

SPAWN_GEAR_THEMES: dict[str, dict] = {
    "temperate": {
        "StartingClothing": {
            "EnableCustomClothing": 1,
            "SetRandomHealth": 1,
            "Headgear": ["BaseballCap_Black", "BeanieHat_Green", ""],
            "Glasses": [],
            "Masks": [],
            "Tops": ["HunterJacket_Brown", "HunterJacket_Autumn", "Shirt_BlueCheckBright", "Sweater_Gray"],
            "Vests": [],
            "Gloves": [],
            "Pants": ["CargoPants_Green", "CargoPants_Beige", "CargoPants_Black"],
            "Belts": [],
            "Shoes": ["CombatBoots_Black", "CombatBoots_Brown", "CombatBoots_Green"],
            "Armbands": [],
            "Backpacks": ["TaloonBag_Green", "DryBag_Green", "AssaultBag_Green"],
        },
        "StartingGear": {
            "UpperGear": [
                _gear_item("Rag", 4),
                _gear_item("BandageDressing"),
                _gear_item("Compass"),
                _gear_item("SteakKnife"),
                _gear_item("Chemlight_Green"),
            ],
            "PantsGear": [_gear_item("Canteen")],
            "BackpackGear": [
                _gear_item("Mag_AKM_30Rnd"),
                _gear_item("Mag_AKM_30Rnd"),
                _gear_item("TacticalBaconCan"),
                _gear_item("PeachesCan"),
            ],
        },
    },
    "winter": {
        "StartingClothing": {
            "EnableCustomClothing": 1,
            "SetRandomHealth": 1,
            "Headgear": ["Ushanka_Black", "Ushanka_Blue", "BeanieHat_Black"],
            "Glasses": [],
            "Masks": ["Balaclava3Holes_Black", "Balaclava3Holes_Green"],
            "Tops": ["GorkaEJacket_Winter", "GorkaEJacket_Autumn"],
            "Vests": [],
            "Gloves": ["WoolGloves_Black", "WoolGloves_Green", "WorkingGloves_Black"],
            "Pants": ["GorkaPants_Winter", "GorkaPants_Autumn", "CargoPants_Black"],
            "Belts": [],
            "Shoes": ["CombatBoots_Black", "CombatBoots_Brown", "MilitaryBoots_Black"],
            "Armbands": [],
            "Backpacks": ["TaloonBag_Green", "TaloonBag_Blue", "DryBag_Green"],
        },
        "StartingGear": {
            "UpperGear": [
                _gear_item("Rag", 4),
                _gear_item("BandageDressing"),
                _gear_item("Compass"),
                _gear_item("SteakKnife"),
                _gear_item("RoadFlare"),
                _gear_item("RoadFlare"),
            ],
            "PantsGear": [
                _gear_item("Heatpack"),
                _gear_item("Heatpack"),
                _gear_item("Canteen"),
            ],
            "BackpackGear": [
                _gear_item("Mag_AKM_30Rnd"),
                _gear_item("Mag_AKM_30Rnd"),
                _gear_item("TacticalBaconCan"),
            ],
        },
    },
    "desert": {
        "StartingClothing": {
            "EnableCustomClothing": 1,
            "SetRandomHealth": 1,
            "Headgear": ["BaseballCap_Tan", "BaseballCap_Olive", "BeanieHat_Brown"],
            "Glasses": ["Sunglasses", "AviatorGlasses"],
            "Masks": ["Balaclava3Holes_Beige"],
            "Tops": ["GorkaEJacket_Autumn", "TShirt_Beige", "TShirt_OrangeWhiteStripes", "FieldJacket_Green"],
            "Vests": [],
            "Gloves": [],
            "Pants": ["CargoPants_Beige", "GorkaPants_Autumn", "CargoPants_Green"],
            "Belts": [],
            "Shoes": ["CombatBoots_Beige", "CombatBoots_Brown", "CombatBoots_Green"],
            "Armbands": [],
            "Backpacks": ["TortillaBag", "TaloonBag_Green", "DryBag_Yellow"],
        },
        "StartingGear": {
            "UpperGear": [
                _gear_item("Rag", 4),
                _gear_item("BandageDressing"),
                _gear_item("Compass"),
                _gear_item("SteakKnife"),
                _gear_item("Chemlight_White"),
                _gear_item("SodaCan_Pipsi"),
            ],
            "PantsGear": [_gear_item("Canteen"), _gear_item("WaterBottle")],
            "BackpackGear": [
                _gear_item("Mag_AKM_30Rnd"),
                _gear_item("Mag_AKM_30Rnd"),
                _gear_item("TunaCan"),
                _gear_item("PeachesCan"),
            ],
        },
    },
}


def apply_starting_gear(settings: dict, cfg: MapConfig) -> None:
    """Always spawn with AKM + map-themed clothing/supplies (Expansion StartingGear)."""
    theme = SPAWN_GEAR_THEMES.get(cfg.gear_theme, SPAWN_GEAR_THEMES["temperate"])
    settings["StartingClothing"] = deepcopy(theme["StartingClothing"])
    sg = deepcopy(theme["StartingGear"])
    settings["StartingGear"] = {
        "EnableStartingGear": 1,
        "ApplyEnergySources": 0,
        "SetRandomHealth": 1,
        "UseUpperGear": 1,
        "UsePantsGear": 1,
        "UseBackpackGear": 1,
        "UseVestGear": 0,
        "UsePrimaryWeapon": 1,
        "UseSecondaryWeapon": 0,
        "UpperGear": sg["UpperGear"],
        "PantsGear": sg["PantsGear"],
        "BackpackGear": sg["BackpackGear"],
        "VestGear": [],
        "PrimaryWeapon": deepcopy(PRIMARY_RIFLE),
        "SecondaryWeapon": {},
    }
    settings["SpawnHealthValue"] = 100.0
    settings["SpawnEnergyValue"] = cfg.spawn_energy
    settings["SpawnWaterValue"] = cfg.spawn_water
    settings["UseLoadouts"] = 0


def sanitize_name(name: str) -> str:
    s = re.sub(r"[^\w]+", "_", name.strip())
    return s.strip("_") or "Unknown"


def mission_paths(cfg: MapConfig) -> tuple[Path, Path, Path]:
    mission = SERVER / "mpmissions" / cfg.mission
    settings = mission / "expansion" / "settings"
    teleports = SERVER / cfg.profile / "CommunityOnlineTools" / cfg.teleports_file
    cache = ADMIN / cfg.cache_file
    return mission, settings, teleports


def location_key(loc: dict) -> tuple[str, int, int]:
    pos = loc["Position"]
    name = loc.get("Name", "").strip().lower()
    return (name, round(float(pos[0])), round(float(pos[2])))


def dedupe_locations(locations: list[dict]) -> list[dict]:
    seen: set[tuple[str, int, int]] = set()
    out: list[dict] = []
    for loc in locations:
        key = location_key(loc)
        if key in seen or not key[0]:
            continue
        seen.add(key)
        out.append(loc)
    return out


def merge_structure_poi_file(cfg: MapConfig, teleports: dict) -> dict:
    if not cfg.structure_poi_file:
        return teleports
    path = ADMIN / cfg.structure_poi_file
    if not path.exists():
        return teleports
    extra = json.loads(path.read_text(encoding="utf-8"))
    merged = list(teleports.get("Locations", []))
    for loc in extra.get("locations", []):
        merged.append(
            {
                "Type": loc.get("type", loc.get("Type", "Local")),
                "Name": loc["name"] if "name" in loc else loc["Name"],
                "Position": loc.get("position", loc.get("Position")),
                "Radius": loc.get("radius", loc.get("Radius", 4.0)),
            }
        )
    teleports = dict(teleports)
    teleports["Locations"] = dedupe_locations(merged)
    return teleports


def load_teleports(cfg: MapConfig) -> dict:
    _, _, teleports_path = mission_paths(cfg)
    cache = ADMIN / cfg.cache_file
    src = cache if cache.exists() else teleports_path
    if not src.exists():
        raise FileNotFoundError(f"Missing {teleports_path} (join {cfg.key} once to generate COT teleports)")
    data = json.loads(src.read_text(encoding="utf-8"))
    if not cache.exists() and teleports_path.exists():
        shutil.copy2(teleports_path, cache)
    data["Locations"] = dedupe_locations(data.get("Locations", []))
    return merge_structure_poi_file(cfg, data)


def poi_keywords(cfg: MapConfig) -> list[str]:
    return [k.lower() for k in (cfg.spatial_poi_keywords or cfg.poi_patrol_keywords)]


def is_structure_poi(cfg: MapConfig, loc: dict) -> bool:
    keywords = poi_keywords(cfg)
    if not keywords:
        return False
    if loc.get("Type") in ("Marine", "Hill"):
        return False
    name = f" {loc.get('Name', '').strip().lower()} "
    if any(ex in name for ex in cfg.poi_patrol_exclude_substrings):
        return False
    return any(kw in name for kw in keywords)


def load_bubbles(mission: Path) -> list[tuple[float, float]]:
    xml = mission / "cfgplayerspawnpoints.xml"
    if not xml.exists():
        return []
    text = xml.read_text(encoding="utf-8")
    return [(float(x), float(z)) for x, z in re.findall(r'x="([^"]+)" z="([^"]+)"', text)]


def dist2(ax: float, az: float, bx: float, bz: float) -> float:
    dx, dz = ax - bx, az - bz
    return dx * dx + dz * dz


def estimate_y(cfg: MapConfig, x: float, z: float) -> float:
    if cfg.estimate_y:
        return cfg.estimate_y(x, z)
    return 0.0


def location_y(cfg: MapConfig, loc: dict) -> float:
    pos = loc["Position"]
    x, z = float(pos[0]), float(pos[2])
    if len(pos) > 1:
        py = float(pos[1])
        if py > 0.5:
            return py
    return estimate_y(cfg, x, z)


def ring_waypoints(
    cfg: MapConfig, x: float, z: float, radius: float = 120.0, points: int = 4, y: float | None = None
) -> list[list[float]]:
    yv = y if y is not None else estimate_y(cfg, x, z)
    wps: list[list[float]] = []
    for i in range(points):
        a = (2.0 * math.pi * i) / points
        wps.append([round(x + radius * math.cos(a), 2), yv, round(z + radius * math.sin(a), 2)])
    return wps


def build_roaming_locations(cfg: MapConfig, teleports: dict) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for loc in teleports.get("Locations", []):
        name = loc.get("Name", "").strip()
        if not name or name in seen:
            continue
        t = loc.get("Type", "Local")
        if t not in cfg.roaming_types:
            continue
        seen.add(name)
        pos = loc["Position"]
        radius = cfg.type_radius.get(t, 200.0)
        if is_structure_poi(cfg, loc):
            radius = max(radius, cfg.structure_roaming_radius)
        enabled = 1 if is_chernarus_major_ai_location(cfg, loc) else 0
        out.append(
            {
                "Name": f"Settlement_{sanitize_name(name)}",
                "Position": [float(pos[0]), 0.0, float(pos[2])],
                "Radius": radius,
                "Type": cfg.type_category.get(t, "Local"),
                "Enabled": enabled,
            }
        )
    out.sort(key=lambda e: e["Name"])
    return out


def make_route_patrol(
    cfg: MapConfig,
    idx: int,
    hub_name: str,
    x: float,
    z: float,
    faction: str,
    loadout: str,
    behaviour: str,
    number_of_ai: int,
) -> dict:
    p = {
        "Name": f"{cfg.patrol_prefix}_{idx}_{hub_name}",
        "Persist": 0,
        "Faction": faction,
        "Formation": "RANDOM",
        "FormationScale": -1.0,
        "FormationLooseness": 0.0,
        "Loadout": loadout,
        "Units": [],
        "NumberOfAI": number_of_ai,
        "NumberOfAIMax": 0,
        "Behaviour": behaviour,
        "LootingBehaviour": "DEFAULT",
        "Speed": "WALK",
        "UnderThreatSpeed": "SPRINT",
        "DefaultStance": "STANDING",
        "DefaultLookAngle": 0.0,
        "CanBeLooted": 1,
        "LootDropOnDeath": "",
        "UnlimitedReload": 1,
        "SniperProneDistanceThreshold": 0.0,
        "AccuracyMin": -1.0,
        "AccuracyMax": -1.0,
        "ThreatDistanceLimit": -1.0,
        "NoiseInvestigationDistanceLimit": -1.0,
        "MaxFlankingDistance": -1.0,
        "EnableFlankingOutsideCombat": -1,
        "DamageMultiplier": -1.0,
        "DamageReceivedMultiplier": -1.0,
        "HeadshotResistance": 0.0,
        "ShoryukenChance": -1.0,
        "ShoryukenDamageMultiplier": -1.0,
        "CanSpawnInContaminatedArea": 0,
        "CanBeTriggeredByAI": 0,
        "MinDistRadius": -1.0,
        "MaxDistRadius": -1.0,
        "DespawnRadius": -2.0,
        "MinSpreadRadius": 1.0,
        "MaxSpreadRadius": 100.0,
        "Chance": 1.0,
        "DespawnTime": -1.0,
        "RespawnTime": -2.0,
        "LoadBalancingCategory": "Patrol",
        "ObjectClassName": "",
        "WaypointInterpolation": "",
        "UseRandomWaypointAsStartPoint": 1,
        "Waypoints": ring_waypoints(cfg, x, z),
    }
    tune_patrol_dict(p)
    return p


def is_object_patrol(p: dict) -> bool:
    if p.get("ObjectClassName"):
        return True
    return (p.get("LoadBalancingCategory") or "") in ("HelicopterWreck", "ObjectPatrol")


def is_town_location(cfg: MapConfig, loc: dict) -> bool:
    name = loc.get("Name", "").strip()
    if loc.get("Type") in cfg.town_types:
        return True
    return name in cfg.extra_town_names


def is_military_location(cfg: MapConfig, loc: dict) -> bool:
    t = loc.get("Type", "")
    if t in cfg.military_patrol_types:
        return True
    name = loc.get("Name", "").strip().lower()
    return "military" in name or "airfield" in name or "strongpoint" in name


def is_chernarus_major_ai_location(cfg: MapConfig, loc: dict) -> bool:
    if cfg.key != "chernarus":
        return True
    name = loc.get("Name", "").strip()
    if loc.get("Type", "") in ("Capital", "City"):
        return True
    return any(term in name for term in CHERNARUS_AI_KEEP_TERMS)


def patrol_faction_for_location(cfg: MapConfig, loc: dict, *, military: bool = False) -> tuple[str, str]:
    # Raiders/East heavy — hostile military feel even at villages
    name = loc.get("Name", "")
    roll = sum(name.encode("utf-8")) % 10
    if roll < 5:
        return "Raiders", PVP_LOADOUT
    if roll < 8:
        return "East", PVP_LOADOUT
    return "West", PVP_LOADOUT


def build_town_patrols(cfg: MapConfig, teleports: dict, start_idx: int) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    idx = start_idx
    for loc in teleports.get("Locations", []):
        if not is_town_location(cfg, loc):
            continue
        if not is_chernarus_major_ai_location(cfg, loc):
            continue
        name = loc.get("Name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        pos = loc["Position"]
        x, z = float(pos[0]), float(pos[2])
        y = location_y(cfg, loc)
        faction, loadout = patrol_faction_for_location(cfg, loc)
        p = make_route_patrol(
            cfg, idx, sanitize_name(name), x, z, faction, loadout, "HALT_OR_ALTERNATE", TOWN_MIN_AI
        )
        p["NumberOfAIMax"] = TOWN_MAX_AI
        p["MinSpreadRadius"] = 14.0
        p["MaxSpreadRadius"] = 90.0
        p["Waypoints"] = ring_waypoints(cfg, x, z, radius=110.0, points=5, y=y)
        out.append(p)
        idx += 1
    return out


def build_structure_patrols(cfg: MapConfig, teleports: dict, start_idx: int) -> list[dict]:
    if not cfg.poi_patrol_keywords:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    idx = start_idx
    for loc in teleports.get("Locations", []):
        if not is_structure_poi(cfg, loc) or is_town_location(cfg, loc):
            continue
        name = loc.get("Name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        pos = loc["Position"]
        x, z = float(pos[0]), float(pos[2])
        y = location_y(cfg, loc)
        faction, loadout = patrol_faction_for_location(cfg, loc, military=True)
        p = make_route_patrol(
            cfg, idx, sanitize_name(name), x, z, faction, loadout, "HALT_OR_ALTERNATE", TOWN_MIN_AI
        )
        p["NumberOfAIMax"] = TOWN_MAX_AI
        p["MinSpreadRadius"] = 12.0
        p["MaxSpreadRadius"] = 85.0
        p["Waypoints"] = ring_waypoints(cfg, x, z, radius=105.0, points=4, y=y)
        out.append(p)
        idx += 1
    return out


def build_military_patrols(cfg: MapConfig, teleports: dict, start_idx: int) -> list[dict]:
    if not cfg.military_patrol_types:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    idx = start_idx
    for loc in teleports.get("Locations", []):
        if not is_military_location(cfg, loc):
            continue
        if not is_chernarus_major_ai_location(cfg, loc):
            continue
        name = loc.get("Name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        pos = loc["Position"]
        x, z = float(pos[0]), float(pos[2])
        y = location_y(cfg, loc)
        faction, loadout = patrol_faction_for_location(cfg, loc, military=True)
        label = sanitize_name(name)
        p = make_route_patrol(
            cfg, idx, label, x, z, faction, loadout, "HALT_OR_ALTERNATE", TOWN_MIN_AI
        )
        p["NumberOfAIMax"] = TOWN_MAX_AI
        p["MinSpreadRadius"] = 14.0
        p["MaxSpreadRadius"] = 100.0
        p["Waypoints"] = ring_waypoints(cfg, x, z, radius=125.0, points=5, y=y)
        out.append(p)
        idx += 1
    return out


def build_patrols(cfg: MapConfig, existing: dict, teleports: dict) -> list[dict]:
    object_patrols = []
    for p in existing.get("Patrols", []):
        if not is_object_patrol(p):
            continue
        if p.get("LoadBalancingCategory") == "ContaminatedArea":
            continue
        if "ContaminatedArea" in (p.get("ObjectClassName") or ""):
            continue
        cp = deepcopy(p)
        cp["UnlimitedReload"] = 1
        cp["Waypoints"] = []
        cp["NumberOfAI"] = TOWN_MIN_AI
        cp["NumberOfAIMax"] = TOWN_MAX_AI
        cp["Loadout"] = cp.get("Loadout") or PVP_LOADOUT
        tune_patrol_dict(cp)
        object_patrols.append(cp)

    routes: list[dict] = []
    for i, hub in enumerate(cfg.patrol_hubs):
        hub_args = list(hub)
        hub_args[-1] = HUB_MIN_AI
        route = make_route_patrol(cfg, i, *hub_args)
        route["NumberOfAIMax"] = HUB_MAX_AI
        route["MinSpreadRadius"] = 10.0
        route["MaxSpreadRadius"] = 80.0
        routes.append(route)
    base = len(routes)
    military = build_military_patrols(cfg, teleports, start_idx=base)
    base += len(military)
    structure = build_structure_patrols(cfg, teleports, start_idx=base)
    base += len(structure)
    towns = build_town_patrols(cfg, teleports, start_idx=base)
    return object_patrols + routes + military + structure + towns


def make_spatial_zone(
    cfg: MapConfig, x: float, z: float, label: str, *, faction: str = "West", loadout: str = "WestLoadout.json"
) -> dict:
    y = estimate_y(cfg, x, z)
    return {
        "Spatial_Name": f"Site_{label}",
        "Spatial_TriggerRadius": 340.0,
        "Spatial_ZoneLoadout": loadout,
        "Spatial_MinCount": TOWN_MIN_AI,
        "Spatial_MaxCount": TOWN_MAX_AI,
        "Spatial_HuntMode": AI_HUNT_MODE,
        "Spatial_Faction": faction if faction != "West" else "Raiders",
        "Spatial_Lootable": 1,
        "Spatial_Chance": 0.92,
        "Spatial_MinAccuracy": AI_ACCURACY_MIN,
        "Spatial_MaxAccuracy": AI_ACCURACY_MAX,
        "Spatial_Timer": 28.0,
        "Spatial_SpawnMode": 1,
        "Spatial_UnlimitedReload": 1,
        "Spatial_TriggerPosition": [round(x, 2), y, round(z, 2)],
        "Spatial_SpawnPosition": [
            [round(x + 15, 2), y, round(z + 15, 2)],
            [round(x - 12, 2), y, round(z - 10, 2)],
        ],
    }


def build_spatial_locations(cfg: MapConfig, teleports: dict) -> list[dict]:
    if not cfg.spatial_types and not cfg.poi_patrol_keywords:
        return []
    locations: list[dict] = []
    seen: set[str] = set()
    for loc in teleports.get("Locations", []):
        name = loc.get("Name", "").strip()
        if not name or name in seen:
            continue
        t = loc.get("Type", "Local")
        if t not in cfg.spatial_types and not is_structure_poi(cfg, loc):
            continue
        seen.add(name)
        pos = loc["Position"]
        x, z = float(pos[0]), float(pos[2])
        armed = (
            t in cfg.armed_town_types
            or t in cfg.military_patrol_types
            or is_structure_poi(cfg, loc)
        )
        fac = "Raiders" if armed else "East"
        loadout = f"{PVP_LOADOUT}.json"
        locations.append(make_spatial_zone(cfg, x, z, sanitize_name(name), faction=fac, loadout=loadout))
    locations.sort(key=lambda e: e["Spatial_Name"])
    return locations


def find_location_by_match(teleports: dict, match: str) -> dict | None:
    needle = match.strip().lower()
    for loc in teleports.get("Locations", []):
        name = loc.get("Name", "").strip().lower()
        if name == needle or needle in name:
            return loc
    return None


def build_structure_spawn_regions(
    cfg: MapConfig, teleports: dict, bubbles: list[tuple[float, float]], existing_names: set[str]
) -> list[dict]:
    if not cfg.merge_structure_spawn_regions:
        return []
    wanted: list[tuple[str, str]] = []
    if cfg.structure_poi_file:
        path = ADMIN / cfg.structure_poi_file
        if path.exists():
            for entry in json.loads(path.read_text(encoding="utf-8")).get("spawn_regions", []):
                wanted.append((entry["name"], entry.get("match", entry["name"])))

    for loc in teleports.get("Locations", []):
        if not is_structure_poi(cfg, loc):
            continue
        name = loc.get("Name", "").strip()
        if name.lower() in existing_names:
            continue
        wanted.append((name, name))

    regions: list[dict] = []
    seen_names: set[str] = set()
    for region_name, match in wanted:
        key = region_name.strip().lower()
        if key in seen_names or key in existing_names:
            continue
        loc = find_location_by_match(teleports, match)
        if not loc:
            continue
        pos = loc["Position"]
        x, z = float(pos[0]), float(pos[2])
        positions = spawn_positions_near(cfg, x, z, bubbles, limit=6)
        if len(positions) < 2:
            continue
        regions.append({"Name": region_name, "Positions": positions, "UseCooldown": 1})
        seen_names.add(key)
        if len(regions) >= cfg.max_structure_spawn_regions:
            break
    return regions


def tune_spatial_globals(spatial: dict, zone_count: int, town_patrol_count: int) -> None:
    budget = max(zone_count, 1) * TOWN_MAX_AI + town_patrol_count
    spatial["MaxAI"] = min(SPATIAL_MAX_AI_CAP, max(SPATIAL_MAX_AI_FLOOR, budget // 2))
    spatial["Locations_Enabled"] = 2 if spatial.get("Location") else 0
    spatial["Points_Enabled"] = 0
    spatial["MinimumPlayerDistance"] = 50
    spatial["MinDistance"] = 85
    spatial["MaxDistance"] = 165
    for group in spatial.get("Group", []):
        group["Spatial_MinCount"] = 1
        group["Spatial_MaxCount"] = 3
        group["Spatial_Chance"] = 0.45


def sync_patrol_globals_from_chernarus(patrol: dict) -> None:
    src = SERVER / "mpmissions" / "dayzOffline.chernarusplus" / "expansion" / "settings" / "AIPatrolSettings.json"
    if not src.exists():
        return
    source = json.loads(src.read_text(encoding="utf-8"))
    for key in PATROL_GLOBAL_KEYS:
        if key in source:
            patrol[key] = deepcopy(source[key])


def apply_pvp_patrol_globals(patrol: dict) -> None:
    patrol["DespawnTime"] = 500.0
    patrol["MinDistRadius"] = 175.0
    patrol["MaxDistRadius"] = 850.0
    patrol["DespawnRadius"] = 950.0


def tune_patrol_load_balance(patrol: dict, town_count: int, hub_count: int) -> None:
    cap = min(PATROL_CATEGORY_CAP, max(PATROL_CATEGORY_MIN, town_count + hub_count + 8))
    cats = patrol.get("LoadBalancingCategories", {})
    for entry in cats.get("Patrol", []):
        entry["MaxPatrols"] = cap
    for entry in cats.get("ObjectPatrol", []):
        entry["MaxPatrols"] = max(int(entry.get("MaxPatrols", 5)), OBJECT_PATROL_MAX)
    for entry in cats.get("HelicopterWreck", []):
        entry["MaxPatrols"] = max(int(entry.get("MaxPatrols", 3)), HELICOPTER_WRECK_MAX)
    for entry in cats.get("Global", []):
        mp = entry.get("MaxPatrols", 0)
        if 0 < mp < 255:
            entry["MaxPatrols"] = min(max(mp, 18), 20)


def count_active_town_patrols(patrol: dict) -> int:
    return sum(
        1
        for p in patrol.get("Patrols", [])
        if p.get("Behaviour") in ("HALT_OR_ALTERNATE", "ALTERNATE") and p.get("Waypoints")
    )


def boost_existing_patrols(patrol: dict) -> int:
    """Raise AI counts on patrols already defined in mission JSON (Chernarus, etc.)."""
    n = 0
    for p in patrol.get("Patrols", []):
        if not p.get("Waypoints") and not p.get("ObjectClassName"):
            continue
        base = int(p.get("NumberOfAI", 1))
        if p.get("Behaviour") in ("HALT_OR_ALTERNATE", "ALTERNATE", "LOOP_OR_ALTERNATE") or (
            p.get("LoadBalancingCategory") == "Patrol" and p.get("Waypoints")
        ):
            p["NumberOfAI"] = TOWN_MIN_AI
            p["NumberOfAIMax"] = TOWN_MAX_AI
            p["UnlimitedReload"] = 1
            n += 1
    return n


def boost_spatial_settings(spatial: dict) -> None:
    spatial["MaxAI"] = min(SPATIAL_MAX_AI_CAP, max(SPATIAL_MAX_AI_FLOOR, int(spatial.get("MaxAI", 28))))
    spatial["MinimumPlayerDistance"] = 80
    spatial["MinDistance"] = 150
    spatial["MaxDistance"] = 300
    for loc in spatial.get("Location", []):
        loc["Spatial_MinCount"] = max(int(loc.get("Spatial_MinCount", 0)), TOWN_MIN_AI)
        loc["Spatial_MaxCount"] = max(int(loc.get("Spatial_MaxCount", 1)), TOWN_MAX_AI)
        loc["Spatial_Chance"] = min(float(loc.get("Spatial_Chance", 0.65)), 0.65)
        loc["Spatial_UnlimitedReload"] = 1
    for group in spatial.get("Group", []):
        group["Spatial_MinCount"] = max(int(group.get("Spatial_MinCount", 0)), 1)
        group["Spatial_MaxCount"] = max(int(group.get("Spatial_MaxCount", 1)), 3)
        group["Spatial_Chance"] = max(float(group.get("Spatial_Chance", 0.1)), 0.4)


def normalize_spawn_y_zero(settings: dict) -> int:
    n = 0
    for loc in settings.get("SpawnLocations", []):
        for pos in loc.get("Positions", []):
            if len(pos) >= 3 and pos[1] != 0.0:
                pos[1] = 0.0
                n += 1
    return n


def spawn_positions_near(
    cfg: MapConfig, x: float, z: float, bubbles: list[tuple[float, float]], limit: int = 6
) -> list[list[float]]:
    if bubbles:
        ranked = sorted(bubbles, key=lambda b: dist2(x, z, b[0], b[1]))
        seen: set[tuple[float, float]] = set()
        out: list[list[float]] = []
        for bx, bz in ranked:
            key = (round(bx, 1), round(bz, 1))
            if key in seen:
                continue
            seen.add(key)
            out.append([bx, 0.0, bz])
            if len(out) >= limit:
                break
        if len(out) >= 2:
            return out
    y = 0.0
    return [
        [x, y, z],
        [x + 40, y, z + 30],
        [x - 35, y, z + 25],
        [x + 25, y, z - 40],
    ]


def build_spawns_from_settlements(cfg: MapConfig, teleports: dict, bubbles: list[tuple[float, float]]) -> list[dict]:
    seen: set[str] = set()
    settlements: list[dict] = []
    for loc in teleports.get("Locations", []):
        if loc.get("Type") not in cfg.settlement_spawn_types:
            continue
        name = loc.get("Name", "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        settlements.append(loc)
    settlements.sort(key=lambda l: (0 if l["Type"] == "Capital" else 1 if l["Type"] == "City" else 2, l["Name"]))
    settlements = settlements[: cfg.max_spawn_regions]

    locations = []
    for loc in settlements:
        pos = loc["Position"]
        x, z = float(pos[0]), float(pos[2])
        positions = spawn_positions_near(cfg, x, z, bubbles)
        if len(positions) < 2:
            continue
        locations.append({"Name": loc["Name"], "Positions": positions, "UseCooldown": 1})
    return locations


def cluster_spawn_regions(
    cfg: MapConfig, bubbles: list[tuple[float, float]], teleports: dict, n_regions: int = 4
) -> list[dict]:
    if len(bubbles) < n_regions * 2:
        return build_spawns_from_settlements(cfg, teleports, bubbles)

    xs = [b[0] for b in bubbles]
    zs = [b[1] for b in bubbles]
    x_mid = sorted(xs)[len(xs) // 2]
    z_mid = sorted(zs)[len(zs) // 2]

    quadrants = {
        "NW": lambda x, z: x < x_mid and z >= z_mid,
        "NE": lambda x, z: x >= x_mid and z >= z_mid,
        "SW": lambda x, z: x < x_mid and z < z_mid,
        "SE": lambda x, z: x >= x_mid and z < z_mid,
    }
    locations = []
    for qname, pred in quadrants.items():
        pts = [b for b in bubbles if pred(b[0], b[1])]
        if len(pts) < 2:
            continue
        positions = [[x, 0.0, z] for x, z in pts[:6]]
        locations.append({"Name": qname, "Positions": positions, "UseCooldown": 1})
    if locations:
        return locations
    return build_spawns_from_settlements(cfg, teleports, bubbles)


def update_spawn_settings(cfg: MapConfig, mission: Path, teleports: dict) -> str:
    spawn_path = mission / "expansion" / "settings" / "SpawnSettings.json"
    if not spawn_path.exists():
        template = SERVER / "mpmissions" / "dayzOffline.chernarusplus" / "expansion" / "settings" / "SpawnSettings.json"
        if not template.exists():
            raise FileNotFoundError(f"Missing {spawn_path} and template {template}")
        spawn_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, spawn_path)
    settings = json.loads(spawn_path.read_text(encoding="utf-8"))
    bubbles = load_bubbles(mission)

    if cfg.spawn_from_settlements or not settings.get("SpawnLocations"):
        settings["SpawnLocations"] = build_spawns_from_settlements(cfg, teleports, bubbles)
        mode = "built from settlements (Y=0)"
    else:
        changed = normalize_spawn_y_zero(settings)
        kept = len(settings.get("SpawnLocations", []))
        mode = f"kept {kept} regions, set Y=0 on {changed} coords"

    if cfg.merge_structure_spawn_regions:
        existing = settings.get("SpawnLocations", [])
        existing_names = {r.get("Name", "").strip().lower() for r in existing}
        added = build_structure_spawn_regions(cfg, teleports, bubbles, existing_names)
        if added:
            settings["SpawnLocations"] = existing + added
            mode += f", +{len(added)} structure spawn regions"

    settings["EnableSpawnSelection"] = 1
    apply_starting_gear(settings, cfg)
    spawn_path.write_text(json.dumps(settings, indent=4) + "\n", encoding="utf-8")
    return mode


def copy_loadouts(mission: Path) -> int:
    src = SERVER / "mpmissions" / "dayzOffline.chernarusplus" / "expansion" / "Loadouts"
    dst = mission / "expansion" / "Loadouts"
    if not src.exists():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in src.glob("*.json"):
        dest = dst / f.name
        if not dest.exists():
            shutil.copy2(f, dest)
            n += 1
    return n


def build_map(cfg: MapConfig) -> None:
    mission, settings_dir, _ = mission_paths(cfg)
    teleports = load_teleports(cfg)
    settings_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== {cfg.key.upper()} ({cfg.mission}) ===")

    roaming = build_roaming_locations(cfg, teleports)
    (settings_dir / "AILocationSettings.json").write_text(
        json.dumps({"m_Version": 4, "RoamingLocations": roaming}, indent=4) + "\n",
        encoding="utf-8",
    )
    print(f"  AILocationSettings: {len(roaming)} locations")

    patrol_path = settings_dir / "AIPatrolSettings.json"
    patrol = json.loads(patrol_path.read_text(encoding="utf-8")) if patrol_path.exists() else {"Patrols": []}
    sync_patrol_globals_from_chernarus(patrol)
    apply_pvp_patrol_globals(patrol)
    patrol["Patrols"] = build_patrols(cfg, patrol, teleports)
    town_count = sum(1 for loc in teleports.get("Locations", []) if is_town_location(cfg, loc))
    mil_count = sum(1 for loc in teleports.get("Locations", []) if is_military_location(cfg, loc))
    struct_count = sum(
        1
        for loc in teleports.get("Locations", [])
        if is_structure_poi(cfg, loc) and not is_town_location(cfg, loc)
    )
    hub_count = len(cfg.patrol_hubs)
    tune_patrol_load_balance(patrol, town_count + mil_count + struct_count, hub_count)
    tune_patrol_settings_global(patrol)
    patrol_path.write_text(json.dumps(patrol, indent=4) + "\n", encoding="utf-8")
    halt = sum(
        1
        for p in patrol["Patrols"]
        if p.get("Behaviour") == "HALT_OR_ALTERNATE" and p.get("Waypoints")
    )
    struct_msg = f", {struct_count} structure POIs" if struct_count else ""
    print(
        f"  AIPatrolSettings: {len(patrol['Patrols'])} patrols "
        f"({halt} sites @ {TOWN_MIN_AI}-{TOWN_MAX_AI} AI){struct_msg}"
    )

    spatial_path = settings_dir / "SpatialSettings.json"
    spatial = json.loads(spatial_path.read_text(encoding="utf-8")) if spatial_path.exists() else {"Group": []}
    spatial["Location"] = build_spatial_locations(cfg, teleports)
    tune_spatial_dict(spatial)
    tune_spatial_globals(spatial, len(spatial["Location"]), halt)
    spatial["Point"] = []
    for group in spatial.get("Group", []):
        group["Spatial_UnlimitedReload"] = 1
    spatial_path.parent.mkdir(parents=True, exist_ok=True)
    spatial_path.write_text(json.dumps(spatial, indent=4) + "\n", encoding="utf-8")
    print(f"  SpatialSettings: {len(spatial['Location'])} site zones, MaxAI={spatial.get('MaxAI')}")

    spawn_msg = update_spawn_settings(cfg, mission, teleports)
    print(f"  SpawnSettings: {spawn_msg} | gear={cfg.gear_theme} + AKM rifle")

    copied = copy_loadouts(mission)
    if copied:
        print(f"  Loadouts: copied {copied} file(s)")
    gear = cfg.gear_theme if cfg.gear_theme in ("winter", "desert") else "temperate"
    for line in deploy_for_mission(
        cfg.mission, gear_theme=gear, profile_name=cfg.profile
    ):
        if "PvPLoadout" in line or "combat" in line:
            print(line.replace("  OK   ", "  AI: "))


def apply_ai_boost_only(cfg: MapConfig) -> None:
    _, settings_dir, _ = mission_paths(cfg)
    patrol_path = settings_dir / "AIPatrolSettings.json"
    spatial_path = settings_dir / "SpatialSettings.json"
    if not patrol_path.exists():
        raise FileNotFoundError(f"Missing {patrol_path}")
    patrol = json.loads(patrol_path.read_text(encoding="utf-8"))
    apply_pvp_patrol_globals(patrol)
    boosted = boost_existing_patrols(patrol)
    towns = count_active_town_patrols(patrol)
    tune_patrol_load_balance(patrol, towns, len(cfg.patrol_hubs))
    patrol_path.write_text(json.dumps(patrol, indent=4) + "\n", encoding="utf-8")
    spatial_msg = ""
    if spatial_path.exists():
        spatial = json.loads(spatial_path.read_text(encoding="utf-8"))
        boost_spatial_settings(spatial)
        spatial_path.write_text(json.dumps(spatial, indent=4) + "\n", encoding="utf-8")
        spatial_msg = f", spatial MaxAI={spatial.get('MaxAI')}"
    print(
        f"  AI density: {boosted} patrols -> {TOWN_MIN_AI}-{TOWN_MAX_AI} AI"
        f", Patrol MaxPatrols up to {min(PATROL_CATEGORY_CAP, max(PATROL_CATEGORY_MIN, towns + len(cfg.patrol_hubs) + 8))}"
        f"{spatial_msg}"
    )


def apply_gear_only(cfg: MapConfig) -> None:
    mission, settings_dir, _ = mission_paths(cfg)
    spawn_path = settings_dir / "SpawnSettings.json"
    if not spawn_path.exists():
        raise FileNotFoundError(f"Missing {spawn_path}")
    settings = json.loads(spawn_path.read_text(encoding="utf-8"))
    apply_starting_gear(settings, cfg)
    spawn_path.write_text(json.dumps(settings, indent=4) + "\n", encoding="utf-8")
    print(f"  SpawnSettings: applied {cfg.gear_theme} clothing + AKM (UsePrimaryWeapon=1)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Expansion spawn + AI for custom maps")
    ap.add_argument("maps", nargs="*", help="namalsk enoch sakhal takistan chernarus deerisle banov esseker rostow iztek alteria")
    ap.add_argument("--all", action="store_true", help="Build all configured maps")
    ap.add_argument("--imported", action="store_true", help="Build imported Workshop maps only after COT teleports have been exported")
    ap.add_argument("--gear-only", action="store_true", help="Only update StartingClothing/StartingGear")
    ap.add_argument("--ai-only", action="store_true", help="Boost AI on existing patrols (Chernarus); custom maps use full build")
    args = ap.parse_args()

    all_maps = ["namalsk", "enoch", "sakhal", "takistan", "chernarus"]
    imported_maps = ["deerisle", "banov", "esseker", "rostow", "iztek", "alteria"]
    if args.all:
        keys = list(MAP_CONFIGS.keys()) if args.gear_only else all_maps
    elif args.imported:
        keys = imported_maps
    else:
        keys = args.maps
    if not keys:
        ap.print_help()
        return 1

    for key in keys:
        if key not in MAP_CONFIGS:
            print(f"Unknown map: {key} (choose from {', '.join(MAP_CONFIGS)})")
            return 1
        cfg = MAP_CONFIGS[key]
        if args.gear_only:
            print(f"\n=== {cfg.key.upper()} ({cfg.mission}) ===")
            apply_gear_only(cfg)
        elif args.ai_only:
            print(f"\n=== {cfg.key.upper()} ({cfg.mission}) ===")
            apply_ai_boost_only(cfg)
        else:
            build_map(cfg)

    print("\nRestart each map's server to load new settings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
