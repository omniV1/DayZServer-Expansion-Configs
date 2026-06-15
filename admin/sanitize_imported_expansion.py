#!/usr/bin/env python3
"""Disable risky generated Expansion world placements on imported maps."""
from __future__ import annotations

import json
import shutil
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MISSIONS = {
    "deerisle": "empty.deerisle",
    "banov": "dayzOffline.banov",
    "esseker": "dayzOffline.Esseker",
    "rostow": "Offline.rostow",
    "iztek": "empty.Iztek",
    "alteria": "empty.alteria",
}

RISKY_DIRS = [
    "expansion/missions",
    "expansion/objects",
    "expansion/p2pmarket",
    "expansion/personalstorage",
    "expansion/traders",
    "expansion/traderzones",
]

SETTING_DEFAULTS = {
    "MarketSettings.json": {
        "m_Version": 17,
        "MarketSystemEnabled": 0,
        "NetworkCategories": [],
        "CurrencyIcon": "",
        "ATMSystemEnabled": 0,
        "MaxDepositMoney": 100000,
        "DefaultDepositMoney": 0,
        "ATMPlayerTransferEnabled": 0,
        "ATMPartyLockerEnabled": 0,
        "MaxPartyDepositMoney": 100000,
        "UseWholeMapForATMPlayerList": 0,
        "SellPricePercent": 0.0,
        "NetworkBatchSize": 0,
        "MaxVehicleDistanceToTrader": 0.0,
        "MaxLargeVehicleDistanceToTrader": 0.0,
        "LargeVehicles": [],
        "LandSpawnPositions": [],
        "AirSpawnPositions": [],
        "WaterSpawnPositions": [],
        "MarketMenuColors": {},
        "Currencies": [],
        "VehicleKeys": [],
        "MaxSZVehicleParkingTime": 0.0,
        "SZVehicleParkingTicketFine": 0,
        "SZVehicleParkingFineUseKey": 1,
        "TrainSpawnPositions": [],
        "DisallowUnpersisted": 0,
        "DisableClientSellTransactionDetails": 0,
    },
    "P2PMarketSettings.json": {"m_Version": 3, "Enabled": 0},
    "PersonalStorageSettings.json": {"m_Version": 1, "Enabled": 0},
    "SafeZoneSettings.json": {
        "m_Version": 11,
        "Enabled": 0,
        "FrameRateCheckSafeZoneInMs": 0,
        "CircleZones": [],
        "PolygonZones": [],
        "CylinderZones": [],
        "ActorsPerTick": 5,
        "DisablePlayerCollision": 0,
        "DisableVehicleDamageInSafeZone": 0,
        "EnableForceSZCleanup": 0,
        "ItemLifetimeInSafeZone": 0.0,
        "EnableForceSZCleanupVehicles": 0,
        "VehicleLifetimeInSafeZone": 3600.0,
        "ForceSZCleanup_ExcludedItems": ["ExpansionVehicleCover"],
    },
}


def safe_rmtree(path: Path) -> bool:
    resolved = path.resolve()
    root = ROOT.resolve()
    if not str(resolved).startswith(str(root)):
        raise RuntimeError(f"Refusing to delete outside server root: {path}")
    if not path.exists():
        return False
    shutil.rmtree(path)
    return True


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Disable risky generated Expansion world placements on imported maps.")
    parser.add_argument("--wipe-storage", action="store_true", help="Also delete imported-map storage_* folders to clear persisted bad objects.")
    args = parser.parse_args()

    removed = 0
    for key, mission in MISSIONS.items():
        mission_root = ROOT / "mpmissions" / mission
        if not mission_root.exists():
            print(f"{key}: missing mission folder")
            continue
        for rel in RISKY_DIRS:
            if safe_rmtree(mission_root / rel):
                removed += 1
                print(f"{key}: removed {rel}")
        settings_dir = mission_root / "expansion" / "settings"
        for name, data in SETTING_DEFAULTS.items():
            write_json(settings_dir / name, data)
        print(f"{key}: disabled Market/P2P/PersonalStorage/SafeZone settings")
        if args.wipe_storage:
            for storage in mission_root.glob("storage_*"):
                if safe_rmtree(storage):
                    removed += 1
                    print(f"{key}: wiped {storage.name}")
    print(f"Removed {removed} risky generated folder(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
