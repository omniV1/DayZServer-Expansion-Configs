"""Copy mod_ce loot structure to all mission folders.

Prefer:  python admin/apply_loot.py replicate
"""
import shutil
import sys
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
sys.path.insert(0, str(ADMIN))

import loot_settings

SERVER = loot_settings.SERVER / "mpmissions"
_cfg = loot_settings.load_config()
SOURCE = SERVER / _cfg["source_mission"] / "mod_ce"
CE_BLOCK = """
\t<ce folder="mod_ce">
\t\t<file name="loot_boost_types.xml" type="types" />
\t\t<file name="mod_weapons_types.xml" type="types" />
\t\t<file name="mod_weapons_spawnabletypes.xml" type="spawnabletypes" />
\t\t<file name="mod_optics_types.xml" type="types" />
\t</ce>
"""


def ensure_optics_in_economycore(mission: Path) -> bool:
    eco = mission / "cfgeconomycore.xml"
    text = eco.read_text(encoding="utf-8")
    if "mod_optics_types.xml" in text:
        return False
    if 'folder="mod_ce"' not in text:
        return False
    text = text.replace(
        '\t\t<file name="mod_weapons_spawnabletypes.xml" type="spawnabletypes" />',
        '\t\t<file name="mod_weapons_spawnabletypes.xml" type="spawnabletypes" />\n'
        '\t\t<file name="mod_optics_types.xml" type="types" />',
    )
    eco.write_text(text, encoding="utf-8")
    return True

MISSIONS = loot_settings.replicate_missions()


def patch_economycore(mission: Path):
    eco = mission / "cfgeconomycore.xml"
    text = eco.read_text(encoding="utf-8")
    if "folder=\"mod_ce\"" in text:
        return False
    text = text.replace("</economycore>", CE_BLOCK + "\n</economycore>")
    eco.write_text(text, encoding="utf-8")
    return True


def solo_patrol_caps(mission: Path):
    ai = mission / "expansion" / "settings" / "AIPatrolSettings.json"
    if not ai.exists():
        return False
    import json
    data = json.loads(ai.read_text(encoding="utf-8"))
    changed = False
    lb = data.get("LoadBalancingCategories", {})
    for entry in lb.get("Global", []):
        if entry.get("MinPlayers") == 0 and entry.get("MaxPlayers") == 10:
            if entry.get("MaxPatrols", 0) < 12:
                entry["MaxPatrols"] = 12
                changed = True
    if changed:
        ai.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    return changed


if __name__ == "__main__":
    import apply_loot

    for line in apply_loot.replicate_mod_ce():
        print(line)
    import json

    for name in MISSIONS:
        m = SERVER / name
        try:
            pat = solo_patrol_caps(m)
            if pat:
                print(f"  OK   {name}: patrol_caps updated")
        except json.JSONDecodeError as e:
            print(f"  WARN {name}: patrol_caps skipped ({e})")
