#!/usr/bin/env python3
"""Place Dr. Jones (@Trader) trader hubs AND matching in-game map markers.

Every map gets a "Trader" server marker (Expansion map icon) at the exact spot
its trader NPCs spawn, so you just open the map and walk to the icon -- no
coordinates needed. NPCs (TraderObjects.txt, IDs 0-6 matching the shared
TraderConfig.txt) are placed as one compact hub anchored to a real building
near a player spawn (building = correct terrain height). Chernarus/Winter use
the existing Krasnostav Airstrip spot; Sakhal keeps its hand-placed village and
only gets a marker.

Writes NPCs to both paths Sakhal uses (profile + mission dir) and the marker
into mpmissions/<mission>/expansion/settings/MapSettings.json.

Caveats (nudge in-game later): the boat trader (marker 6) vehicle spawn lands
on land -- move it to water for afloat boats; heights are best-effort.

  python admin/setup_traders.py            # all maps
  python admin/setup_traders.py --map chernarus
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
ROOT = ADMIN.parent
MISSIONS = ROOT / "mpmissions"

# mission dir -> (profile dir, friendly title). Mirrors admin/map_launch.json.
TARGETS: dict[str, tuple[str, str]] = {
    "dayzOffline.chernarusplus": ("profiles", "Chernarus"),
    "dayzOffline.enoch": ("profiles_enoch", "Livonia"),
    "regular.namalsk": ("profiles_namalsk", "Namalsk"),
    "dayzOffline.TakistanPlus": ("profiles_takistan", "Takistan"),
    "empty.deerisle": ("profiles_deerisle", "Deer Isle"),
    "dayzOffline.banov": ("profiles_banov", "Banov"),
    "dayzOffline.Esseker": ("profiles_esseker", "Esseker"),
    "Offline.rostow": ("profiles_rostow", "Rostow"),
    "empty.Iztek": ("profiles_iztek", "Iztek"),
    "empty.alteria": ("profiles_alteria", "Alteria"),
    "RegularWinter.chernarusplus": ("profiles_winterchernarus", "Winter Chernarus"),
    "empty.Bitterroot": ("profiles_bitterroot", "Bitterroot"),
    "dayz.Deadfall": ("profiles_deadfall", "Deadfall"),
}
# Chernarus-terrain maps: use the existing Krasnostav Airstrip trader spot (x, z).
KRASNO_MAPS = {"dayzOffline.chernarusplus", "RegularWinter.chernarusplus"}
KRASNO_XZ = (11882.0, 12466.0)
# Sakhal already has a hand-placed trader village -> marker only, no NPC change.
SAKHAL = ("dayzOffline.sakhal", (7229.0, 4.0, 7076.0))

# 7 markers (IDs 0-6): (id, (dx,dz) offset, safezone, optional vehicle-spawn (dx,dz)).
MARKERS = [
    (0, (0.0, 0.0), 80, None), (1, (3.0, 0.0), 80, None), (2, (6.0, 0.0), 80, None),
    (3, (0.0, 4.0), 80, None), (4, (3.0, 4.0), 30, None),
    (5, (-6.0, 0.0), 30, (-13.0, 0.0)), (6, (-6.0, 6.0), 30, (-16.0, 12.0)),
]
POS_RE = re.compile(r'pos="([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"')
SPAWN_RE = re.compile(r'<pos\b[^>]*\bx="([-\d.]+)"[^>]*\bz="([-\d.]+)"')


def buildings(mission: Path) -> list[tuple[float, float, float]]:
    f = mission / "mapgrouppos.xml"
    if not f.exists():
        return []
    return [(float(x), float(y), float(z)) for x, y, z in POS_RE.findall(f.read_text(encoding="utf-8", errors="ignore"))]


def spawn_points(mission: Path) -> list[tuple[float, float]]:
    f = mission / "cfgplayerspawnpoints.xml"
    if not f.exists():
        return []
    return [(float(x), float(z)) for x, z in SPAWN_RE.findall(f.read_text(encoding="utf-8", errors="ignore"))]


def nearest_building(blds, x, z):
    return min(blds, key=lambda b: (b[0] - x) ** 2 + (b[2] - z) ** 2)


def trader_location(mission_name: str, mission: Path) -> tuple[float, float, float] | None:
    """(x, y, z) for the hub; y from the nearest building = real terrain height."""
    blds = buildings(mission)
    if not blds:
        return None
    if mission_name in KRASNO_MAPS:
        x, z = KRASNO_XZ
    else:
        spawns = spawn_points(mission)
        if spawns:
            x, z = spawns[0][0], spawns[0][1]
        else:
            x = sum(b[0] for b in blds) / len(blds)
            z = sum(b[2] for b in blds) / len(blds)
    bx, by, bz = nearest_building(blds, x, z)
    return (bx, by, bz)


def render_npcs(title: str, ax: float, ay: float, az: float) -> str:
    out = [
        f"// ---- {title} Trader Markers (auto-placed; see the 'Trader' map marker) ----",
        "// IDs 0-6 -> TraderConfig.txt: 0 Consume 1 Misc 2 Clothing 3 Weapon 4 WeaponSupplies 5 Vehicles 6 Boat.",
        "// Boat trader (6) vehicle spawn is on land -- move into water for afloat boats.",
        "",
    ]
    for mid, (dx, dz), safe, veh in MARKERS:
        out += [f"<TraderMarker> \t\t\t{mid}",
                f"<TraderMarkerPosition>\t{ax + dx:.6f}, {ay:.6f}, {az + dz:.6f}",
                f"<TraderMarkerSafezone>\t{safe}"]
        if veh:
            out += [f"<VehicleSpawn>\t\t\t{ax + veh[0]:.6f}, {ay:.6f}, {az + veh[1]:.6f}", "<VehicleSpawnOri>\t\t0, 0, 0"]
        out.append("")
    return "\n".join(out) + "\n"


def set_map_marker(mission: Path, x: float, y: float, z: float, text: str = "Trader") -> bool:
    f = mission / "expansion" / "settings" / "MapSettings.json"
    if not f.exists():
        return False
    d = json.loads(f.read_text(encoding="utf-8-sig"))
    markers = [m for m in (d.get("ServerMarkers") or [])
               if "trader" not in (str(m.get("m_IconName", "")) + str(m.get("m_Text", "")) + str(m.get("m_UID", ""))).lower()]
    markers.append({
        "m_UID": "ServerMarker_Trader_Hub", "m_Visibility": 6, "m_Is3D": 1,
        "m_Text": text, "m_IconName": "Trader", "m_Color": -13710223,
        "m_Position": [round(x, 1), round(y, 1), round(z, 1)], "m_Locked": 0, "m_Persist": 1,
    })
    d["ServerMarkers"] = markers
    d["EnableServerMarkers"] = 1
    f.write_text(json.dumps(d, indent=4), encoding="utf-8")
    return True


def apply_map(mission_name: str, profile: str, title: str) -> str:
    mission = MISSIONS / mission_name
    if not mission.exists():
        return f"SKIP {mission_name}: missing"
    loc = trader_location(mission_name, mission)
    if loc is None:
        return f"SKIP {mission_name}: no mapgrouppos building data"
    ax, ay, az = loc

    text = render_npcs(title, ax, ay, az)
    settings = ROOT / profile / "ExpansionMod" / "Settings"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "TraderObjects.txt").write_text(text, encoding="utf-8", newline="\n")
    (mission / "TraderObjects.txt").write_text(text, encoding="utf-8", newline="\n")
    for fname in ("TraderConfig.txt", "TraderVehicleParts.txt"):
        if (settings / fname).exists() and not (mission / fname).exists():
            shutil.copy2(settings / fname, mission / fname)

    marker = set_map_marker(mission, ax, ay, az, f"Trader - {title}")
    return f"OK   {mission_name}: hub @ ({ax:.0f}, {ay:.1f}, {az:.0f}) | map marker: {'set' if marker else 'no MapSettings.json'}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map")
    args = ap.parse_args()

    by_key = {p.replace("profiles_", "").replace("profiles", "chernarus"): m for m, (p, _t) in TARGETS.items()}
    if args.map:
        mission_name = by_key.get(args.map.lower())
        if not mission_name:
            print(f"Unknown map: {args.map}. Known: {', '.join(sorted(by_key))}, sakhal")
            return 2
        print(apply_map(mission_name, *TARGETS[mission_name]))
        return 0

    for mission_name, (profile, title) in TARGETS.items():
        print(apply_map(mission_name, profile, title))
    # Sakhal: keep its hand-placed NPCs, just add the map marker.
    sx, sy, sz = SAKHAL[1]
    ok = set_map_marker(MISSIONS / SAKHAL[0], sx, sy, sz, "Trader - Sakhal")
    print(f"OK   {SAKHAL[0]}: NPCs kept | map marker: {'set' if ok else 'no MapSettings.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
