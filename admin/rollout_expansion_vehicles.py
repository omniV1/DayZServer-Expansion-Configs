#!/usr/bin/env python3
"""Roll Expansion vehicles + items out to community maps that lack expansion_ce.

For each target map:
  1. Copy chernarus expansion_ce (types/spawnabletypes/events) into the map.
  2. Register expansion_ce in cfgeconomycore.xml (before the mod_ce block).
  3. Wire per-model Expansion vehicle events to positions borrowed from that
     map's own vanilla car/boat spawn coords, capping each event's nominal so
     it never out-asks its position count (avoids "failed to spawn N<M" spam).

Idempotent: skips maps that already have expansion_ce registered. Validates
every XML it writes. Maps with no vehicle coords (Deadfall) get items only
(types+spawnabletypes, no events) so there is no disabled-event noise.
"""
from __future__ import annotations
import re, shutil, sys
import xml.etree.ElementTree as ET
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
MISSIONS = SERVER / "mpmissions"
SRC = MISSIONS / "dayzOffline.chernarusplus" / "expansion_ce"

TARGETS = [
    "empty.deerisle", "dayzOffline.Esseker", "dayzOffline.banov", "Offline.rostow",
    "empty.Iztek", "empty.alteria", "RegularWinter.chernarusplus",
    "empty.Bitterroot", "dayz.Deadfall",
]

# Vanilla events we borrow spawn coords from.
CAR_SRC = ["VehicleCivilianSedan", "VehicleSedan02", "VehicleHatchback02",
           "VehicleOffroad02", "VehicleOffroadHatchback", "VehicleTruck01",
           "VehicleTransitBus", "VehicleGolfCart"]
BOAT_SRC = ["VehicleBoat", "VehicleBoatSTAG", "VehicleRubberBoats", "VehicleBoats"]

# Expansion land/air events -> how many positions to assign. nominal in the
# copied events file is capped to <= the count here.
LAND_PLAN = [
    ("VehicleLandRover", 6),
    ("VehicleBus", 4),
    ("VehicleTractor", 4),
    ("VehicleUh1hHelicopter", 3),
    ("VehicleMerlinHelicopter", 1),
    ("VehicleGyroHelicopter", 1),
]
BOAT_PLAN = [
    ("VehicleZodiacBoat", 4),
    ("VehicleUtilityBoat", 3),
]

POS_RE = re.compile(r'<pos\b[^>]*/>')


def extract_pos(text: str, event: str) -> list[str]:
    m = re.search(r'<event name="%s">(.*?)</event>' % re.escape(event), text, re.DOTALL)
    return POS_RE.findall(m.group(1)) if m else []


def pool(text: str, events: list[str]) -> list[str]:
    out, seen = [], set()
    for ev in events:
        for p in extract_pos(text, ev):
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


def take(coords: list[str], n: int, cursor: list[int]) -> list[str]:
    """Take n coords cycling through the pool (cursor is mutable [i])."""
    if not coords:
        return []
    got = []
    for _ in range(n):
        got.append(coords[cursor[0] % len(coords)])
        cursor[0] += 1
    return got


def build_blocks(plan, coords) -> tuple[str, list[str]]:
    cursor = [0]
    chunks, used = [], []
    for ev, n in plan:
        picks = take(coords, n, cursor)
        if not picks:
            continue
        used.append(ev)
        body = "\n".join("\t\t" + p for p in picks)
        chunks.append(f'\t<event name="{ev}">\n{body}\n\t</event>')
    return "\n".join(chunks), used


def cap_zodiac(events_path: Path, cap: int) -> None:
    txt = events_path.read_text(encoding="utf-8")
    def fix(m):
        b = re.sub(r"<nominal>\d+</nominal>", f"<nominal>{cap}</nominal>", m.group(0), count=1)
        b = re.sub(r"<max>\d+</max>", f"<max>{cap}</max>", b, count=1)
        return b
    new = re.sub(r'<event name="VehicleZodiacBoat">.*?</event>', fix, txt, count=1, flags=re.DOTALL)
    if new != txt:
        events_path.write_text(new, encoding="utf-8", newline="\n")


def register_economycore(eco: Path, with_events: bool) -> bool:
    text = eco.read_text(encoding="utf-8")
    if 'folder="expansion_ce"' in text:
        return False
    lines = ['\t<ce folder="expansion_ce">',
             '\t\t<file name="expansion_types.xml" type="types" />',
             '\t\t<file name="expansion_spawnabletypes.xml" type="spawnabletypes" />']
    if with_events:
        lines.append('\t\t<file name="expansion_events.xml" type="events" />')
    lines.append('\t</ce>\n')
    block = "\n".join(lines)
    if '<ce folder="mod_ce">' in text:
        text = text.replace('\t<ce folder="mod_ce">', block + '\t<ce folder="mod_ce">', 1)
    else:
        text = text.replace("</economycore>", block + "</economycore>", 1)
    eco.write_text(text, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    for name in TARGETS:
        m = MISSIONS / name
        if not m.exists():
            print(f"SKIP {name}: mission missing")
            continue
        dest = m / "expansion_ce"
        eco = m / "cfgeconomycore.xml"
        spawns = m / "cfgeventspawns.xml"
        if 'folder="expansion_ce"' in eco.read_text(encoding="utf-8"):
            print(f"SKIP {name}: expansion_ce already registered")
            continue

        sp_text = spawns.read_text(encoding="utf-8")
        car_pool = pool(sp_text, CAR_SRC)
        boat_pool = pool(sp_text, BOAT_SRC)
        has_vehicles = bool(car_pool)

        # 1. copy expansion_ce
        dest.mkdir(exist_ok=True)
        for f in ("expansion_types.xml", "expansion_spawnabletypes.xml"):
            shutil.copy2(SRC / f, dest / f)
        if has_vehicles:
            shutil.copy2(SRC / "expansion_events.xml", dest / "expansion_events.xml")
            cap_zodiac(dest / "expansion_events.xml", 4)

        # 2. register
        register_economycore(eco, with_events=has_vehicles)

        # 3. wire positions
        used = []
        if has_vehicles:
            land_block, land_used = build_blocks(LAND_PLAN, car_pool)
            boat_block, boat_used = build_blocks(BOAT_PLAN, boat_pool) if boat_pool else ("", [])
            blocks = "\n".join(b for b in (land_block, boat_block) if b)
            new_sp = sp_text.replace("</eventposdef>",
                "\t<!-- Expansion vehicle spawns (borrowed from vanilla car/boat coords) -->\n"
                + blocks + "\n</eventposdef>", 1)
            spawns.write_text(new_sp, encoding="utf-8", newline="\n")
            used = land_used + boat_used
            ET.parse(spawns)  # validate

        # validate copied xml
        for f in dest.glob("*.xml"):
            ET.parse(f)
        kind = "vehicles+items" if has_vehicles else "items only (no vehicle coords)"
        print(f"OK   {name}: {kind}; events wired: {', '.join(used) if used else '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
