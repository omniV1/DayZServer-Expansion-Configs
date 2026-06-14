#!/usr/bin/env python3
"""Make Expansion quest-spawned AI reliable without increasing general patrol spam."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OBJECTIVES = ROOT / "profiles" / "ExpansionMod" / "Quests" / "Objectives"

AI_OBJECTIVE_DIRS = [
    OBJECTIVES / "AIPatrol",
    OBJECTIVES / "AICamp",
]

QUEST_DESPAWN_TIME = 900.0
QUEST_RESPAWN_TIME = 30.0
QUEST_DESPAWN_RADIUS = 900.0
QUEST_MIN_DIST_RADIUS = 25.0
QUEST_MAX_DIST_RADIUS = 650.0


def quest_spawns(data: dict) -> list[dict]:
    if isinstance(data.get("AISpawn"), dict):
        return [data["AISpawn"]]
    if isinstance(data.get("AISpawns"), list):
        return [spawn for spawn in data["AISpawns"] if isinstance(spawn, dict)]
    return []


def tune_spawn(spawn: dict) -> bool:
    before = json.dumps(spawn, sort_keys=True)
    spawn["Chance"] = 1.0
    spawn["Persist"] = 0
    spawn["UnlimitedReload"] = 1
    spawn["CanBeTriggeredByAI"] = 0
    spawn["LoadBalancingCategory"] = "Quest"
    spawn["DespawnTime"] = max(float(spawn.get("DespawnTime", 0.0) or 0.0), QUEST_DESPAWN_TIME)
    spawn["RespawnTime"] = max(float(spawn.get("RespawnTime", 0.0) or 0.0), QUEST_RESPAWN_TIME)
    spawn["DespawnRadius"] = max(float(spawn.get("DespawnRadius", 0.0) or 0.0), QUEST_DESPAWN_RADIUS)
    spawn["MinDistRadius"] = min(float(spawn.get("MinDistRadius", QUEST_MIN_DIST_RADIUS)), QUEST_MIN_DIST_RADIUS)
    spawn["MaxDistRadius"] = max(float(spawn.get("MaxDistRadius", 0.0) or 0.0), QUEST_MAX_DIST_RADIUS)
    return before != json.dumps(spawn, sort_keys=True)


def tune_file(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    changed = False
    for spawn in quest_spawns(data):
        changed = tune_spawn(spawn) or changed
    if changed:
        path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    changed: list[Path] = []
    for folder in AI_OBJECTIVE_DIRS:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.json")):
            if tune_file(path):
                changed.append(path.relative_to(ROOT))

    if changed:
        print("Tuned quest AI objectives:")
        for path in changed:
            print(f"  - {path}")
    else:
        print("Quest AI objectives already tuned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
