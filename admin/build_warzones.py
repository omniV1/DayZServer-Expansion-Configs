#!/usr/bin/env python3
"""Generate per-map AI War Zones JSON from mission landmark coordinates."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
OUT_DIR = SERVER / "profiles" / "AIWarZones" / "maps"
ACTIVE = SERVER / "profiles" / "AIWarZones" / "AIWarZones_Settings.json"

BASE_ZONE = {
    "zoneChance": 100.0,
    "zoneAllowDomination": 0,
    "zoneAINoiseInvestigationRange": 900.0,
    "zoneAIThreatDetectionRange": 700.0,
    "zoneAIMaxAccuracy": 0.8999999761581421,
    "zoneAIMinAccuracy": 0.6000000238418579,
    "zoneAIBodyCleanupTime": 180.0,
    "zoneSmokeGrenadeMax": 4,
    "zoneBurnEffectMax": 3,
    "zoneExplosionEffectMax": 3,
    "aTeamAIType": 0,
    "aTeamAIActivity": 2,
    "aTeamAICanBeLooted": 1,
    "aTeamAIUnlimitedReload": 1,
    "aTeamMaxMoveSpeed": 3.0,
    "aTeamMinMoveSpeed": 2.0,
    "aTeamFaction": "West",
    "aTeamLoadout": "WestLoadout, NBCLoadout",
    "aTeamSmokeColor": "Red",
    "bTeamAIType": 0,
    "bTeamAIActivity": 2,
    "bTeamAICanBeLooted": 1,
    "bTeamAIUnlimitedReload": 1,
    "bTeamMaxMoveSpeed": 3.0,
    "bTeamMinMoveSpeed": 2.0,
    "bTeamFaction": "East",
    "bTeamLoadout": "PoliceLoadout, BanditLoadout",
    "bTeamSmokeColor": "White",
}


def spawns(cx: float, cy: float, cz: float, points: list[tuple[float, float, float]]) -> str:
    return ", ".join(f"{cx + dx} {cy + dy} {cz + dz}" for dx, dy, dz in points)


def zone(
    name: str,
    cx: float,
    cy: float,
    cz: float,
    radius: float,
    ai_max: int = 8,
    domination: int = 0,
    fx: float | None = None,
    a_offs: list | None = None,
    b_offs: list | None = None,
) -> dict:
    z = deepcopy(BASE_ZONE)
    z.update(
        {
            "zoneName": name,
            "zonePosition": f"{cx} {cy} {cz}",
            "zoneRadius": radius,
            "zoneAIMax": ai_max,
            "zoneAllowDomination": domination,
            "zoneRadiusFX": fx if fx is not None else min(radius * 0.65, 150.0),
            "aTeamSpawnPosition": spawns(
                cx,
                cy,
                cz,
                a_offs
                or [
                    (-120, 0, -80),
                    (-90, 0, 100),
                    (-60, 0, -40),
                ],
            ),
            "bTeamSpawnPosition": spawns(
                cx,
                cy,
                cz,
                b_offs
                or [
                    (120, 0, 80),
                    (90, 0, -100),
                    (60, 0, 40),
                ],
            ),
        }
    )
    return z


def config_for(map_id: str, zones: list[dict], max_concurrent: int = 2) -> dict:
    return {
        "configVersion": 1,
        "Enabled": 1,
        "logLevel": 0,
        "maxConcurrentZones": max_concurrent,
        "WarZones": zones,
    }


CHERNARUS = config_for(
    "chernarusplus",
    [
        zone("The Battle Of Berezino", 12001.6, 54.13, 9069.11, 178, 7),
        zone("The Raid At Vybor", 4541.89, 317.73, 8327.46, 250, 12),
        zone("Situation at Krasnostav PD", 11066.2, 228.02, 12488.2, 95, 7),
        zone("Chernogorsk PD Raid", 6632.47, 7.72, 2586.3, 195, 7),
        zone("Electro Street Fights", 10486.6, 6.14, 2348.88, 250, 7),
        zone("The Fight For Control - NWAF", 4488.51, 339.14, 9696.89, 310, 10, domination=1, fx=70),
    ],
)

ENOCH = config_for(
    "enoch",
    [
        zone("Topolin Street Battle", 1858.82, 183.63, 7330.87, 220, 10),
        zone("Brena City Fight", 6617.63, 182.0, 11211.03, 240, 10),
        zone("Swarog Military Assault", 5424.36, 440.45, 1501.20, 300, 12, domination=1, fx=90),
        zone("Nadbor Raid", 6109.5, 417.0, 3983.17, 200, 8),
        zone("Kopa Prison Clash", 5968.21, 244.83, 9102.40, 160, 8),
        zone("Gieraltow Farm War", 11240.02, 339.0, 4380.37, 200, 8),
    ],
)

SAKHAL = config_for(
    "sakhal",
    [
        zone("Petropavlovsk Streets", 4749.0, 22.0, 10695.0, 250, 10),
        zone("Severomorsk Battle", 9544.0, 28.0, 13656.0, 220, 10),
        zone("Nogovo Airfield Fight", 7814.0, 25.0, 7949.0, 280, 12, domination=1, fx=85),
        zone("Rudnogorsk Harbor", 13587.0, 12.0, 12152.0, 200, 8),
        zone("Aniva Coast War", 12895.0, 18.0, 7273.0, 230, 8),
    ],
)

TAKISTAN = config_for(
    "takistan",
    [
        zone("Rasman Central", 4618.0, 6.65, 12330.0, 220, 10),
        zone("Northern Highlands", 8138.61, 428.84, 8564.82, 260, 10),
        zone("Krasnostav Airfield", 11087.84, 226.42, 12478.97, 300, 12, domination=1, fx=95),
        zone("Zelenogorsk Outskirts", 2796.0, 192.0, 5166.0, 200, 8),
        zone("Southern City Clash", 6906.81, 7.28, 3086.96, 220, 8),
    ],
)

NAMALSK = config_for(
    "namalsk",
    [
        zone("Vorkuta Airfield", 6319.98, 31.21, 9374.18, 280, 12, domination=1, fx=90),
        zone("Jalovisko Traders", 8599.36, 14.73, 10492.20, 200, 8),
        zone("Tara Harbor Fight", 8053.95, 1.85, 7595.73, 180, 7),
        zone("Central Namalsk", 5028.84, 45.0, 7618.27, 220, 8),
    ],
    max_concurrent=2,
)

BITTERROOT = config_for(
    "bitterroot",
    [
        zone("Hamilton City Market", 7200.0, 380.0, 8400.0, 220, 10),
        zone("Stevensville Standoff", 4500.0, 350.0, 6200.0, 180, 8),
        zone("Bitterroot Ranch Raid", 9800.0, 400.0, 10500.0, 200, 8),
        zone("FEMA Camp Assault", 6500.0, 450.0, 4800.0, 250, 10),
        zone("Forest Road Ambush", 3200.0, 500.0, 9000.0, 200, 8),
        zone("Fort Bitterroot - The Battle", 5800.0, 500.0, 7600.0, 300, 12, domination=1, fx=90),
    ],
)

DEADFALL = config_for(
    "deadfall",
    [
        zone("Mill District Clash", 5000.0, 80.0, 5800.0, 180, 8),
        zone("Deadfall Central", 5500.0, 100.0, 4500.0, 220, 10),
        zone("Industrial Zone Fight", 3500.0, 90.0, 6500.0, 200, 8),
        zone("Harbor Front Raid", 7500.0, 60.0, 7200.0, 180, 7),
        zone("The Funnel - Deadfall Core", 5000.0, 95.0, 6000.0, 280, 12, domination=1, fx=85),
    ],
)

WINTER_CHERNARUS = config_for(
    "winterchernarus",
    [
        zone("The Battle Of Berezino", 12001.6, 54.13, 9069.11, 178, 7),
        zone("The Raid At Vybor", 4541.89, 317.73, 8327.46, 250, 12),
        zone("Situation at Krasnostav PD", 11066.2, 228.02, 12488.2, 95, 7),
        zone("Chernogorsk PD Raid", 6632.47, 7.72, 2586.3, 195, 7),
        zone("Electro Street Fights", 10486.6, 6.14, 2348.88, 250, 7),
        zone("The Fight For Control - NWAF", 4488.51, 339.14, 9696.89, 310, 10, domination=1, fx=70),
    ],
)

MAP_CONFIGS = {
    "chernarus": CHERNARUS,
    "chernarusplus": CHERNARUS,
    "enoch": ENOCH,
    "livonia": ENOCH,
    "sakhal": SAKHAL,
    "takistan": TAKISTAN,
    "namalsk": NAMALSK,
    "regular.namalsk": NAMALSK,
    "winterchernarus": WINTER_CHERNARUS,
    "bitterroot": BITTERROOT,
    "deadfall": DEADFALL,
}


def write_all() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for key, cfg in [
        ("chernarus", CHERNARUS),
        ("enoch", ENOCH),
        ("sakhal", SAKHAL),
        ("takistan", TAKISTAN),
        ("namalsk", NAMALSK),
        ("winterchernarus", WINTER_CHERNARUS),
        ("bitterroot", BITTERROOT),
        ("deadfall", DEADFALL),
    ]:
        path = OUT_DIR / f"{key}.json"
        path.write_text(json.dumps(cfg, indent=4) + "\n", encoding="utf-8")
        print(f"  wrote {path.relative_to(SERVER)} ({len(cfg['WarZones'])} zones)")


if __name__ == "__main__":
    write_all()
