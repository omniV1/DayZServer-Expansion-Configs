#!/usr/bin/env python3
"""Replicate Chernarus's working Expansion Market trader to other maps.

Chernarus has a functioning Expansion Market (Green Mountain general trader).
Each other map only needs, per mission: MarketSystemEnabled=1, a traderzone
JSON (position + radius + stock), and a traders .map (the vendor NPCs). The
market category PRICES come from the shared profile (ExpansionMod/Market), so
they don't need copying.

This copies Chernarus's Green Mountain zone + NPCs to each target map, moved to
a verified on-surface anchor (player-provided coords where given), flattening
NPC heights to that surface so nobody floats/sinks. It also points the existing
"Trader" map marker at the same spot.

  python admin/setup_expansion_traders.py --map deerisle   # one map
  python admin/setup_expansion_traders.py                  # all configured
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
ROOT = ADMIN.parent
MISSIONS = ROOT / "mpmissions"
SRC = MISSIONS / "dayzOffline.chernarusplus" / "expansion"
SRC_ZONE = SRC / "traderzones" / "GreenMountain.json"
SRC_NPCS = SRC / "traders" / "GreenMountain_Traders.map"
SRC_ZONE_POS = (3728.27001953125, 403.0, 6003.60009765625)  # Green Mountain zone center (translation reference)

# mission -> (x, y, z). Player-verified on-surface spots where provided;
# scalespeeder-tested for banov/livonia; Green Mountain for Winter (same terrain).
ANCHORS: dict[str, tuple[float, float, float]] = {
    "empty.deerisle": (5833.08, 74.025, 3805.85),
    "regular.namalsk": (6324.11, 20.7178, 9485.18),
    "empty.Iztek": (2778.99, 10.4521, 3060.39),
    "empty.alteria": (6770.13, 26.155, 2151.14),
    "dayz.Deadfall": (1077.48, 164.937, 9088.56),
    "empty.Bitterroot": (8552.33, 147.652, 2075.61),
    "dayzOffline.TakistanPlus": (524.744, 246.513, 2653.68),
    "dayzOffline.banov": (4872.03, 201.70, 4761.95),
    "dayzOffline.enoch": (8707.17, 289.09, 8071.56),
    "RegularWinter.chernarusplus": (3728.27, 403.0, 6003.60),
}
KEY_TO_MISSION = {
    "deerisle": "empty.deerisle", "namalsk": "regular.namalsk", "iztek": "empty.Iztek",
    "alteria": "empty.alteria", "deadfall": "dayz.Deadfall", "bitterroot": "empty.Bitterroot",
    "takistan": "dayzOffline.TakistanPlus", "banov": "dayzOffline.banov",
    "enoch": "dayzOffline.enoch", "winterchernarus": "RegularWinter.chernarusplus",
}
# Quest contract board (ExpansionQuestBoardLarge, ID 100) lives in the profile,
# not the mission. Reposition it next to the market so it's reachable + auto-marked.
MISSION_PROFILE = {
    "empty.deerisle": "profiles_deerisle", "regular.namalsk": "profiles_namalsk", "empty.Iztek": "profiles_iztek",
    "empty.alteria": "profiles_alteria", "dayz.Deadfall": "profiles_deadfall", "empty.Bitterroot": "profiles_bitterroot",
    "dayzOffline.TakistanPlus": "profiles_takistan", "dayzOffline.banov": "profiles_banov",
    "dayzOffline.enoch": "profiles_enoch", "RegularWinter.chernarusplus": "profiles_winterchernarus",
}
BOARD_TEMPLATE = ROOT / "profiles" / "ExpansionMod" / "Quests" / "NPCs" / "QuestNPC_100.json"


def place_board(mission_name: str, x: float, y: float, z: float) -> list | None:
    prof = MISSION_PROFILE.get(mission_name)
    if not prof:
        return None
    npc_dir = ROOT / prof / "ExpansionMod" / "Quests" / "NPCs"
    npc_dir.mkdir(parents=True, exist_ok=True)
    bp = npc_dir / "QuestNPC_100.json"
    src = bp if bp.exists() else (BOARD_TEMPLATE if BOARD_TEMPLATE.exists() else None)
    board = json.loads(src.read_text(encoding="utf-8-sig")) if src else {}
    board.setdefault("ConfigVersion", 6)
    board.setdefault("Orientation", [0.0, 0.0, 0.0])
    board.update({"ID": 100, "ClassName": "ExpansionQuestBoardLarge",
                  "Position": [round(x + 3, 2), round(y, 2), round(z - 10, 2)], "Active": 1})
    bp.write_text(json.dumps(board, indent=1), encoding="utf-8")
    return board["Position"]


def build_zone(mission: Path, x: float, y: float, z: float) -> None:
    zone = json.loads(SRC_ZONE.read_text(encoding="utf-8-sig"))
    zone["Position"] = [round(x, 3), round(y, 3), round(z, 3)]
    out = mission / "expansion" / "traderzones"
    out.mkdir(parents=True, exist_ok=True)
    (out / "GreenMountain.json").write_text(json.dumps(zone, indent=1), encoding="utf-8")


def build_npcs(mission: Path, x: float, y: float, z: float) -> int:
    rx, _ry, rz = SRC_ZONE_POS
    lines_out = []
    for line in SRC_NPCS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        px, _py, pz = (float(v) for v in parts[1].split())
        # keep the camp's X/Z layout, flatten Y to the verified surface
        parts[1] = f"{x + (px - rx):.6f} {y:.6f} {z + (pz - rz):.6f}"
        lines_out.append("|".join(parts))
    out = mission / "expansion" / "traders"
    out.mkdir(parents=True, exist_ok=True)
    (out / "GreenMountain_Traders.map").write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    return len(lines_out)


def enable_market(mission: Path) -> None:
    f = mission / "expansion" / "settings" / "MarketSettings.json"
    d = json.loads(f.read_text(encoding="utf-8-sig"))
    if d.get("MarketSystemEnabled") != 1:
        d["MarketSystemEnabled"] = 1
        f.write_text(json.dumps(d, indent=4), encoding="utf-8")


def align_marker(mission: Path, x: float, y: float, z: float) -> None:
    f = mission / "expansion" / "settings" / "MapSettings.json"
    if not f.exists():
        return
    d = json.loads(f.read_text(encoding="utf-8-sig"))
    markers = [m for m in (d.get("ServerMarkers") or []) if m.get("m_IconName") != "Trader"]
    markers.append({
        "m_UID": "ServerMarker_Trader_Hub", "m_Visibility": 6, "m_Is3D": 1,
        "m_Text": "Trader", "m_IconName": "Trader", "m_Color": -13710223,
        "m_Position": [round(x, 1), round(y, 1), round(z, 1)], "m_Locked": 0, "m_Persist": 1,
    })
    d["ServerMarkers"] = markers
    d["EnableServerMarkers"] = 1
    f.write_text(json.dumps(d, indent=4), encoding="utf-8")


def apply_map(mission_name: str) -> str:
    mission = MISSIONS / mission_name
    if mission_name not in ANCHORS:
        return f"SKIP {mission_name}: no anchor configured"
    if not mission.exists():
        return f"SKIP {mission_name}: missing"
    x, y, z = ANCHORS[mission_name]
    enable_market(mission)
    build_zone(mission, x, y, z)
    n = build_npcs(mission, x, y, z)
    align_marker(mission, x, y, z)
    board = place_board(mission_name, x, y, z)
    return f"OK   {mission_name}: market + {n} vendors @ ({x:.0f},{y:.1f},{z:.0f}), marker aligned, bounty board {'@ '+str([round(v,0) for v in board]) if board else 'skipped'}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map")
    args = ap.parse_args()
    if args.map:
        mission = KEY_TO_MISSION.get(args.map.lower())
        if not mission:
            print(f"Unknown map: {args.map}. Known: {', '.join(sorted(KEY_TO_MISSION))}")
            return 2
        print(apply_map(mission))
        return 0
    for mission_name in ANCHORS:
        print(apply_map(mission_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
