#!/usr/bin/env python3
"""Install repeatable Expansion money contracts into each active map profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
MONEY = "ExpansionBanknoteHryvnia"

UNITS = [
    "eAI_SurvivorM_Boris",
    "eAI_SurvivorM_Cyril",
    "eAI_SurvivorM_Denis",
    "eAI_SurvivorM_Elias",
    "eAI_SurvivorM_Francis",
    "eAI_SurvivorF_Eva",
    "eAI_SurvivorF_Frida",
    "eAI_SurvivorF_Gabi",
    "eAI_SurvivorF_Helga",
    "eAI_SurvivorF_Irena",
]

MAPS = {
    "enoch": {
        "profile": "profiles_enoch",
        "label": "Livonia",
        "board": ("Bielawa Contract Board", [1573.45, 275.0, 9677.45], [45.0, 0.0, 0.0]),
        "ai": [
            ("Brena Raiders", [6617.63, 275.0, 11211.03], 5, 8000),
            ("Radunin Raiders", [7298.38, 275.0, 6491.9], 6, 12000),
        ],
    },
    "sakhal": {
        "profile": "profiles_sakhal",
        "label": "Sakhal",
        "board": ("Petropavlovsk Contract Board", [6594.96, 45.0, 12733.7], [15.0, 0.0, 0.0]),
        "ai": [
            ("Aniva Raiders", [12755.78, 45.0, 7064.54], 5, 9000),
            ("Burukan Raiders", [6594.96, 45.0, 12733.7], 6, 13000),
        ],
    },
    "namalsk": {
        "profile": "profiles_namalsk",
        "label": "Namalsk",
        "board": ("Tara Harbor Contract Board", [7823.86, 8.0, 7876.53], [180.0, 0.0, 0.0]),
        "ai": [
            ("Tara Raiders", [7823.86, 8.0, 7876.53], 5, 9000),
            ("Brensk Raiders", [4396.13, 8.0, 4727.53], 6, 13000),
        ],
    },
    "takistan": {
        "profile": "profiles_takistan",
        "label": "Takistan",
        "board": ("Zargabad Contract Board", [1157.18, 115.0, 1839.62], [90.0, 0.0, 0.0]),
        "ai": [
            ("Feeruz Abad Raiders", [5364.53, 115.0, 6197.93], 5, 9000),
            ("Rasman Raiders", [6244.28, 115.0, 11217.34], 6, 13000),
        ],
    },
}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")


def reward(amount: int) -> dict:
    return {
        "ClassName": MONEY,
        "Amount": amount,
        "Attachments": [],
        "DamagePercent": 0,
        "HealthPercent": 0,
        "QuestID": -1,
        "Chance": 1.0,
    }


def quest(quest_id: int, title: str, desc: str, objective_text: str, reward_amount: int, objective_type: int) -> dict:
    return {
        "ConfigVersion": 22,
        "ID": quest_id,
        "Type": 1,
        "Title": title,
        "Descriptions": [desc, objective_text, "Trader-funded work for survivors who keep moving."],
        "ObjectiveText": objective_text,
        "FollowUpQuest": -1,
        "Repeatable": 1,
        "IsDailyQuest": 0,
        "IsWeeklyQuest": 0,
        "CancelQuestOnPlayerDeath": 0,
        "Autocomplete": 0,
        "IsGroupQuest": 0,
        "ObjectSetFileName": "",
        "QuestItems": [],
        "Rewards": [reward(reward_amount)],
        "NeedToSelectReward": 0,
        "RandomReward": 0,
        "RandomRewardAmount": -1,
        "RewardsForGroupOwnerOnly": 1,
        "RewardBehavior": 0,
        "QuestGiverIDs": [100],
        "QuestTurnInIDs": [100],
        "IsAchievement": 0,
        "Objectives": [{"ConfigVersion": 28, "ID": quest_id, "ObjectiveType": objective_type}],
        "QuestColor": 0,
        "ReputationReward": 0,
        "ReputationRequirement": -1,
        "PreQuestIDs": [],
        "RequiredFaction": "",
        "FactionReward": "",
        "PlayerNeedQuestItems": 1,
        "DeleteQuestItems": 1,
        "SequentialObjectives": 1,
        "FactionReputationRequirements": {},
        "FactionReputationRewards": {},
        "SuppressQuestLogOnCompetion": 0,
        "Active": 1,
    }


def target_objective(objective_id: int, label: str, amount: int) -> dict:
    return {
        "ConfigVersion": 28,
        "ID": objective_id,
        "ObjectiveType": 2,
        "ObjectiveText": f"Kill {amount} infected anywhere in {label}",
        "TimeLimit": -1,
        "Active": 1,
        "Position": [0.0, 0.0, 0.0],
        "MaxDistance": -1.0,
        "MinDistance": -1.0,
        "Amount": amount,
        "ClassNames": [],
        "CountSelfKill": 0,
        "AllowedWeapons": [],
        "ExcludedClassNames": [],
        "CountAIPlayers": 0,
        "AllowedTargetFactions": [],
        "AllowedDamageZones": [],
    }


def ring_waypoints(center: list[float]) -> list[list[float]]:
    x, y, z = center
    return [[x, y, z], [x + 90, y, z + 45], [x - 70, y, z + 80], [x - 90, y, z - 40], [x + 60, y, z - 75]]


def ai_objective(objective_id: int, name: str, center: list[float], count: int) -> dict:
    return {
        "ConfigVersion": 28,
        "ID": objective_id,
        "ObjectiveType": 7,
        "ObjectiveText": f"Eliminate the {count} raiders at {name}",
        "TimeLimit": -1,
        "Active": 1,
        "MaxDistance": -1.0,
        "MinDistance": -1.0,
        "AllowedWeapons": [],
        "AllowedDamageZones": [],
        "AISpawn": {
            "Name": name,
            "Persist": 0,
            "Faction": "Raiders",
            "Formation": "RANDOM",
            "FormationScale": 0.0,
            "FormationLooseness": 0.0,
            "Loadout": "PvPLoadout",
            "Units": UNITS,
            "NumberOfAI": count,
            "Behaviour": "HALT_OR_LOOP",
            "LootingBehaviour": "",
            "Speed": "JOG",
            "UnderThreatSpeed": "SPRINT",
            "CanBeLooted": 1,
            "UnlimitedReload": 1,
            "SniperProneDistanceThreshold": 300.0,
            "AccuracyMin": 0.42,
            "AccuracyMax": 0.68,
            "ThreatDistanceLimit": 450.0,
            "NoiseInvestigationDistanceLimit": -1.0,
            "DamageMultiplier": 1.0,
            "DamageReceivedMultiplier": 1.0,
            "CanBeTriggeredByAI": 0,
            "MinDistRadius": 50.0,
            "MaxDistRadius": 500.0,
            "DespawnRadius": 700.0,
            "MinSpreadRadius": 0.0,
            "MaxSpreadRadius": 50.0,
            "Chance": 1.0,
            "WaypointInterpolation": "",
            "DespawnTime": 60.0,
            "RespawnTime": 1.0,
            "LoadBalancingCategory": "",
            "UseRandomWaypointAsStartPoint": 1,
            "Waypoints": ring_waypoints(center),
        },
    }


def npc(data: dict) -> dict:
    name, pos, orientation = data["board"]
    return {
        "ConfigVersion": 6,
        "ID": 100,
        "ClassName": "ExpansionQuestBoardLarge",
        "Position": pos,
        "Orientation": orientation,
        "NPCName": name,
        "DefaultNPCText": "Paid work is posted here. Finish the job, come back, and collect Hryvnia for the traders.",
        "Waypoints": [],
        "NPCEmoteID": 46,
        "NPCEmoteIsStatic": 0,
        "NPCLoadoutFile": "",
        "NPCInteractionEmoteID": 1,
        "NPCQuestCancelEmoteID": 60,
        "NPCQuestStartEmoteID": 58,
        "NPCQuestCompleteEmoteID": 39,
        "NPCFaction": "InvincibleObservers",
        "NPCType": 1,
        "Active": 1,
    }


def install_map(map_key: str, data: dict) -> int:
    root = SERVER / data["profile"] / "ExpansionMod" / "Quests"
    label = data["label"]
    write_json(root / "NPCs/QuestNPC_100.json", npc(data))
    write_json(root / "Objectives/Target/Objective_TA_100.json", target_objective(100, label, 10))
    write_json(root / "Objectives/Target/Objective_TA_101.json", target_objective(101, label, 25))
    write_json(root / "Objectives/AIPatrol/Objective_AIP_102.json", ai_objective(102, data["ai"][0][0], data["ai"][0][1], data["ai"][0][2]))
    write_json(root / "Objectives/AIPatrol/Objective_AIP_103.json", ai_objective(103, data["ai"][1][0], data["ai"][1][1], data["ai"][1][2]))
    write_json(root / "Quests/Quest_100.json", quest(100, "[Contract] Thin the Horde", f"Clear infected in {label} for trader pay.", f"Kill 10 infected anywhere in {label}.", 1500, 2))
    write_json(root / "Quests/Quest_101.json", quest(101, "[Contract] Sweep the Streets", f"A larger infected bounty is posted in {label}.", f"Kill 25 infected anywhere in {label}.", 4000, 2))
    write_json(root / "Quests/Quest_102.json", quest(102, f"[Contract] {data['ai'][0][0]}", f"Raiders are disrupting trader routes in {label}.", f"Clear {data['ai'][0][2]} raiders at {data['ai'][0][0]}.", data["ai"][0][3], 7))
    write_json(root / "Quests/Quest_103.json", quest(103, f"[Contract] {data['ai'][1][0]}", f"An armed group is holding ground in {label}.", f"Clear {data['ai'][1][2]} raiders at {data['ai'][1][0]}.", data["ai"][1][3], 7))
    return 9


def main() -> int:
    parser = argparse.ArgumentParser(description="Install repeatable Hryvnia quest contracts.")
    parser.add_argument("maps", nargs="*", choices=sorted(MAPS), help="Maps to install. Defaults to non-Chernarus active maps.")
    args = parser.parse_args()
    targets = args.maps or list(MAPS)
    for key in targets:
        count = install_map(key, MAPS[key])
        print(f"{key}: installed {count} money quest files")
    print("Chernarus Quest_100-103 are preserved in profiles/ExpansionMod/Quests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
