"""Remove stale Expansion CE types/events (helicopters, UAZ, dead vanilla variants)."""
from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
SERVER = ADMIN.parent
MISSIONS_ROOT = SERVER / "mpmissions"

EXPANSION_MISSIONS = [
    "dayzOffline.chernarusplus",
    "dayzOffline.enoch",
    "dayzOffline.sakhal",
    "regular.namalsk",
]

STALE_TYPE_PREFIXES = (
    "ExpansionMh6",
    "ExpansionUAZ",
    "OffroadHatchback_",
    "Hatchback_02_BlackRust",
    "Hatchback_02_BlueRust",
    "Hatchback_02_Red",
    "Hatchback_02_RedRust",
    "Hatchback_02_BanditKitty",
    "Hatchback_02_Door_",
    "Hatchback_02_Hood_BanditKitty",
    "Hatchback_02_Trunk_BanditKitty",
)

STALE_EVENTS = frozenset({"VehicleUAZ", "VehicleVodnik", "VehicleMH6Helicopter"})

CFGIGNORE_EXTRA = [
    "OffroadHatchback_WhiteRust",
    "OffroadHatchback_Green",
    "OffroadHatchback_GreenRust",
    "Hatchback_02_BlackRust",
    "Hatchback_02_BlueRust",
    "Hatchback_02_Red",
    "Hatchback_02_RedRust",
    "Hatchback_02_BanditKitty",
    "Hatchback_02_Door_1_1_BanditKitty",
    "Hatchback_02_Door_1_2_BanditKitty",
    "Hatchback_02_Door_2_1_BanditKitty",
    "Hatchback_02_Door_2_2_BanditKitty",
    "Hatchback_02_Hood_BanditKitty",
    "Hatchback_02_Trunk_BanditKitty",
    "Static_FrozenScientist_DE",
]


def _stale_type(name: str) -> bool:
    return any(name.startswith(p) or name == p for p in STALE_TYPE_PREFIXES)


def _prune_types_xml(path: Path) -> int:
    tree = ET.parse(path)
    root = tree.getroot()
    removed = 0
    for typ in list(root.findall("type")):
        name = typ.get("name", "")
        if _stale_type(name):
            root.remove(typ)
            removed += 1
    if removed:
        tree.write(path, encoding="UTF-8", xml_declaration=True)
    return removed


def _prune_spawnable_xml(path: Path) -> int:
    tree = ET.parse(path)
    root = tree.getroot()
    removed = 0
    for typ in list(root.findall("type")):
        name = typ.get("name", "")
        if _stale_type(name):
            root.remove(typ)
            removed += 1
    if removed:
        tree.write(path, encoding="UTF-8", xml_declaration=True)
    return removed


def _prune_events_xml(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    original = text
    for ev in STALE_EVENTS:
        text = re.sub(
            rf'\s*<event name="{re.escape(ev)}">.*?</event>\s*',
            "\n",
            text,
            flags=re.DOTALL,
        )
    if text != original:
        path.write_text(text, encoding="utf-8")
        return len(STALE_EVENTS)
    return 0


def patch_cfgignorelist(mission: Path) -> int:
    path = mission / "cfgignorelist.xml"
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    added = 0
    for name in CFGIGNORE_EXTRA:
        if f'name="{name}"' in text:
            continue
        text = text.replace("</ignore>", f'\t<type name="{name}"></type>\n</ignore>')
        added += 1
    if added:
        path.write_text(text, encoding="utf-8")
    return added


def prune_mission(mission: Path) -> list[str]:
    ce = mission / "expansion_ce"
    if not ce.exists():
        return []
    lines = []
    t = ce / "expansion_types.xml"
    s = ce / "expansion_spawnabletypes.xml"
    e = ce / "expansion_events.xml"
    if t.exists():
        n = _prune_types_xml(t)
        if n:
            lines.append(f"  types -{n}")
    if s.exists():
        n = _prune_spawnable_xml(s)
        if n:
            lines.append(f"  spawnable -{n}")
    if e.exists():
        n = _prune_events_xml(e)
        if n:
            lines.append(f"  events pruned")
    ign = patch_cfgignorelist(mission)
    if ign:
        lines.append(f"  cfgignorelist +{ign}")
    return lines


def replicate_expansion_ce(source_name: str) -> list[str]:
    src = MISSIONS_ROOT / source_name / "expansion_ce"
    if not src.exists():
        return []
    out = []
    for name in EXPANSION_MISSIONS:
        if name == source_name:
            continue
        dest = MISSIONS_ROOT / name / "expansion_ce"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        patch_cfgignorelist(MISSIONS_ROOT / name)
        out.append(f"  OK   {name}/expansion_ce")
    return out


def main() -> int:
    source = EXPANSION_MISSIONS[0]
    print(f"Pruning expansion_ce under {source} ...")
    for line in prune_mission(MISSIONS_ROOT / source):
        print(line)
    print("Replicating expansion_ce to other maps:")
    for line in replicate_expansion_ce(source):
        print(line)
    for name in EXPANSION_MISSIONS[1:]:
        for line in prune_mission(MISSIONS_ROOT / name):
            if line:
                print(f"{name}:")
                for ln in line:
                    print(ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
