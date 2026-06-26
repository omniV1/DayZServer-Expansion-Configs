#!/usr/bin/env python3
"""
DayZ server loot toolchain — single entry point.

Examples:
  python admin/apply_loot.py all
  python admin/apply_loot.py all --preset high
  python admin/apply_loot.py build --preset arcade
  python admin/apply_loot.py globals
  python admin/apply_loot.py replicate
  python admin/apply_loot.py status
  python admin/apply_loot.py set-preset medium
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
if str(ADMIN) not in sys.path:
    sys.path.insert(0, str(ADMIN))

import build_mod_ce
import loot_settings
import prune_expansion_ce

SERVER = loot_settings.SERVER
MISSIONS_ROOT = SERVER / "mpmissions"

CE_BLOCK = """
\t<ce folder="mod_ce">
\t\t<file name="loot_boost_types.xml" type="types" />
\t\t<file name="mod_weapons_types.xml" type="types" />
\t\t<file name="mod_weapons_spawnabletypes.xml" type="spawnabletypes" />
\t\t<file name="mod_optics_types.xml" type="types" />
\t</ce>
"""


def apply_preset_to_build(preset_name: str) -> None:
    build_mod_ce.load_preset(preset_name)


def patch_globals_all(preset_name: str) -> list[str]:
    p = loot_settings.get_preset(preset_name)
    globals_map = p["globals"]
    lines_out = []
    for mission_dir in MISSIONS_ROOT.iterdir():
        g = mission_dir / "db" / "globals.xml"
        if not g.exists():
            continue
        text = g.read_text(encoding="utf-8")
        original = text
        for var, value in globals_map.items():
            text, n = re.subn(
                rf'(name="{re.escape(var)}" type="0" value=")\d+(")',
                rf"\g<1>{value}\2",
                text,
                count=1,
            )
            if n == 0:
                lines_out.append(f"  WARN {mission_dir.name}: missing {var}")
        if text != original:
            g.write_text(text, encoding="utf-8")
            lines_out.append(f"  OK   {mission_dir.name}/db/globals.xml")
    return lines_out


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


def patch_economycore(mission: Path) -> bool:
    eco = mission / "cfgeconomycore.xml"
    text = eco.read_text(encoding="utf-8")
    if 'folder="mod_ce"' in text:
        return False
    text = text.replace("</economycore>", CE_BLOCK + "\n</economycore>")
    eco.write_text(text, encoding="utf-8")
    return True


def replicate_mod_ce() -> list[str]:
    cfg = loot_settings.load_config()
    source = SERVER / "mpmissions" / cfg["source_mission"] / "mod_ce"
    if not source.exists():
        raise FileNotFoundError(f"Missing {source} — run build first.")
    lines_out = []
    vanilla = set(loot_settings.vanilla_loot_maps())
    for name in loot_settings.replicate_missions():
        if name in vanilla:
            lines_out.append(f"  SKIP {name}: vanilla_loot_maps (no boost)")
            continue
        m = MISSIONS_ROOT / name
        dest = m / "mod_ce"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
        eco = patch_economycore(m)
        opt = ensure_optics_in_economycore(m)
        lines_out.append(f"  OK   {name}: copied mod_ce (economycore={eco}, optics={opt})")
    return lines_out


def cmd_status() -> int:
    cfg = loot_settings.load_config()
    active = cfg["active_preset"]
    p = loot_settings.get_preset(active)
    src = loot_settings.source_mission()
    mod_ce = src / "mod_ce"
    print(f"Config:     {loot_settings.CONFIG_PATH}")
    print(f"Preset:     {active} — {p['description']}")
    print(f"Source:     {src.name}")
    print(f"mod_ce:     {'present' if mod_ce.exists() else 'MISSING (run build)'}")
    if mod_ce.exists():
        for f in sorted(mod_ce.glob("*.xml")):
            print(f"  - {f.name} ({f.stat().st_size // 1024} KB)")
    g = src / "db" / "globals.xml"
    if g.exists():
        for key in p["globals"]:
            m = re.search(rf'name="{key}" type="0" value="(\d+)"', g.read_text(encoding="utf-8"))
            val = m.group(1) if m else "?"
            target = p["globals"][key]
            mark = "OK" if str(target) == val else f"want {target}"
            print(f"  {key}: {val} ({mark})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply DayZ central economy loot settings.")
    parser.add_argument(
        "action",
        choices=["all", "build", "globals", "replicate", "status", "set-preset"],
        help="What to run",
    )
    parser.add_argument(
        "--preset",
        choices=list(loot_settings.load_config()["presets"].keys()),
        help="Loot preset (default: active_preset in loot_config.json)",
    )
    args = parser.parse_args()
    preset = args.preset or loot_settings.load_config().get("active_preset", "medium")

    if args.action == "set-preset":
        if not args.preset:
            print("Use: apply_loot.py set-preset --preset medium|high|...")
            return 1
        loot_settings.set_active_preset(args.preset)
        print(f"Active preset set to: {args.preset}")
        return 0

    if args.action == "status":
        return cmd_status()

    print(f"Preset: {preset} ({loot_settings.get_preset(preset)['description']})")
    print("Stop the server before applying if you want a clean CE reload.\n")

    if args.action in ("all", "build"):
        print("Pruning stale expansion_ce types/events:")
        prune_expansion_ce.main()
        print()
        apply_preset_to_build(preset)
        # Point build at source mission from config
        src = loot_settings.source_mission()
        build_mod_ce.MISSION = src
        build_mod_ce.MOD_CE = src / "mod_ce"
        build_mod_ce.TYPES_DB = src / "db" / "types.xml"
        build_mod_ce.main()
        print()

    if args.action in ("all", "globals"):
        print("Patching db/globals.xml on all missions:")
        for line in patch_globals_all(preset):
            print(line)
        print()

    if args.action in ("all", "replicate"):
        print("Replicating mod_ce to other maps:")
        for line in replicate_mod_ce():
            print(line)
        print()

    if args.action == "all":
        loot_settings.set_active_preset(preset)
        print(f"Done. Active preset saved as '{preset}'. Restart the DayZ server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
