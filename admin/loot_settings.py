"""Load loot presets from admin/loot_config.json."""
from __future__ import annotations

import json
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
SERVER = ADMIN.parent
CONFIG_PATH = ADMIN / "loot_config.json"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_preset(name: str | None = None) -> dict:
    cfg = load_config()
    key = name or cfg.get("active_preset", "medium")
    presets = cfg["presets"]
    if key not in presets:
        raise KeyError(f"Unknown preset '{key}'. Choose: {', '.join(presets)}")
    return presets[key]


def set_active_preset(name: str) -> None:
    cfg = load_config()
    if name not in cfg["presets"]:
        raise KeyError(f"Unknown preset '{name}'")
    cfg["active_preset"] = name
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def source_mission() -> Path:
    cfg = load_config()
    return SERVER / "mpmissions" / cfg["source_mission"]


def replicate_missions() -> list[str]:
    return load_config()["replicate_missions"]


def vanilla_loot_maps() -> list[str]:
    """Missions kept at vanilla loot density (no mod_ce boost / expansion_ce).

    Used for sparse maps whose loot points can't absorb the boost without
    LootRespawner search-overtime (e.g. Deadfall)."""
    return load_config().get("vanilla_loot_maps", [])
