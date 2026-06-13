import json
from copy import deepcopy

BASE = r"c:\Games\Steam\steamapps\common\DayZServer\mpmissions"
legacy_path = f"{BASE}\\dayzOffline.chernarusplus\\expansion\\Patrols\\PatrolSettings.json"
enoch_path = f"{BASE}\\dayzOffline.enoch\\expansion\\settings\\AIPatrolSettings.json"
out_path = f"{BASE}\\dayzOffline.chernarusplus\\expansion\\settings\\AIPatrolSettings.json"

with open(legacy_path, encoding="utf-8") as f:
    legacy = json.load(f)
with open(enoch_path, encoding="utf-8") as f:
    enoch = json.load(f)

FACTION_MAP = {"WEST": "West", "EAST": "East", "INSURGENT": "Raiders", "CIVILIAN": "Civilian"}
LOADOUT_MAP = {"WEST": "WestLoadout", "EAST": "EastLoadout", "INSURGENT": "BanditLoadout", "CIVILIAN": "CivilianLoadout"}
BEHAVIOUR_MAP = {"LOOP": "LOOP_OR_ALTERNATE", "REVERSE": "ALTERNATE"}


def make_waypoint_patrol(group, idx):
    fac = group["Faction"]
    behaviour = BEHAVIOUR_MAP.get(group["Behaviour"], group["Behaviour"])
    loadout = group.get("LoadoutFile") or LOADOUT_MAP.get(fac, "")
    loadout_name = loadout.replace(".json", "") if loadout else ""
    return {
        "Name": f"ChernarusPatrol_{idx}_{FACTION_MAP.get(fac, fac)}",
        "Persist": 0,
        "Faction": FACTION_MAP.get(fac, fac),
        "Formation": "RANDOM",
        "FormationScale": -1.0,
        "FormationLooseness": 0.0,
        "Loadout": loadout_name,
        "Units": [],
        "NumberOfAI": group["NumberOfAI"],
        "NumberOfAIMax": 0,
        "Behaviour": behaviour,
        "LootingBehaviour": "DEFAULT",
        "Speed": group.get("Speed", "WALK"),
        "UnderThreatSpeed": "SPRINT",
        "DefaultStance": "STANDING",
        "DefaultLookAngle": 0.0,
        "CanBeLooted": 1,
        "LootDropOnDeath": "",
        "UnlimitedReload": 0,
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
        "Waypoints": group["Waypoints"],
    }


object_patrols_fixed = []
for p in enoch["Patrols"]:
    if not p.get("ObjectClassName"):
        continue
    p2 = deepcopy(p)
    oc = p2.get("ObjectClassName", "")
    if oc == "Land_Wreck_hb01_aban1_police":
        p2["ObjectClassName"] = "Land_Wreck_sed01_aban1_police"
        p2["Loadout"] = "PoliceLoadout"
    elif oc == "Land_Wreck_hb01_aban2_police":
        p2["ObjectClassName"] = "Land_Wreck_sed01_aban2_police"
        p2["Loadout"] = "PoliceLoadout"
    object_patrols_fixed.append(p2)

waypoint_patrols = [make_waypoint_patrol(g, i) for i, g in enumerate(legacy["Group"])]

config = {
    "m_Version": 32,
    "Enabled": 1,
    "FormationScale": -1.0,
    "DespawnTime": 600.0,
    "RespawnTime": -1.0,
    "MinDistRadius": 400.0,
    "MaxDistRadius": 1000.0,
    "DespawnRadius": 1100.0,
    "AccuracyMin": -1.0,
    "AccuracyMax": -1.0,
    "ThreatDistanceLimit": -1.0,
    "NoiseInvestigationDistanceLimit": -1.0,
    "MaxFlankingDistance": -1.0,
    "EnableFlankingOutsideCombat": -1,
    "DamageMultiplier": -1.0,
    "DamageReceivedMultiplier": -1.0,
    "ShoryukenChance": 0.009999999776482582,
    "ShoryukenDamageMultiplier": 3.0,
    "LoadBalancingCategories": deepcopy(enoch["LoadBalancingCategories"]),
    "Patrols": object_patrols_fixed + waypoint_patrols,
}

for entry in config["LoadBalancingCategories"]["Global"]:
    if entry["MinPlayers"] == 0 and entry["MaxPlayers"] == 10:
        entry["MaxPatrols"] = 12
for entry in config["LoadBalancingCategories"]["Patrol"]:
    entry["MaxPatrols"] = 10

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=4)
    f.write("\n")

print(f"Wrote {len(config['Patrols'])} patrols")
