# Quick Start

This repo is a public-safe DayZ Expansion server framework. It ships launch helpers, example configs, generated economy/AI settings, and repeatable tooling for several maps.

It does not include DayZ server binaries, Steam Workshop mod folders, keys, player data, logs, or real private `serverDZ*.cfg` files.

## 1. Clone Or Copy

Place this repo in your DayZ server root, for example:

```powershell
C:\Games\Steam\steamapps\common\DayZServer
```

Install DayZ Dedicated Server through Steam first.

## 2. Install Mods

Review [MODS.md](MODS.md), subscribe/download the Workshop mods you want, then sync map mods from your DayZ client install:

```powershell
powershell -ExecutionPolicy Bypass -File admin\sync_map_workshop_mods.ps1 -Map all
```

For non-map shared mods, copy or sync the required `@ModName` folders into the server root.

## 3. Create Private Server Configs

Copy an example config to the real private config name:

```powershell
Copy-Item serverDZChernarus.example.cfg serverDZChernarus.cfg
```

Then edit the real `.cfg`:

- Set `hostname`
- Set `passwordAdmin`
- Confirm `steamQueryPort`, `steamPort`, and `instanceId`
- Keep the mission template matching [MODS.md](MODS.md)

Real `serverDZ*.cfg` files are ignored so secrets do not get published.

## 4. Validate

Run:

```powershell
python admin\validate_public_repo.py
powershell -ExecutionPolicy Bypass -File admin\check_map_launch.ps1 -Map all
python admin\status_all.py
```

`check_map_launch.ps1` should report config, mission, and mod folders present for the maps you intend to run.

## 5. Generate Or Refresh Gameplay

Normal refresh:

```powershell
python admin\build_map_expansion.py --all
python admin\seed_imported_cot_locations.py
python admin\sanitize_imported_expansion.py
python admin\build_map_expansion.py --imported
python admin\tune_player_spawns.py
python admin\apply_ai_ammo.py
python admin\apply_loot.py all --preset arcade
python admin\tune_chernarus_spawn_economy.py
python admin\install_money_quests.py
python admin\tune_quest_ai.py
python admin\standardize_world_events.py
python admin\status_all.py
```

Restart affected servers after changing economy, Expansion, AI, or event configs.

## 6. Launch

Launch one map:

```powershell
powershell -ExecutionPolicy Bypass -File .\Launch-DayZMap.ps1 -Map chernarus
```

Or use the root helpers:

```powershell
start_chernarus.cmd
start_deerisle.cmd
start_banov.cmd
```

Wait for the RPT log to show the init sequence finished before joining.

## 7. Publish Safely

Before committing or sharing:

```powershell
python admin\validate_public_repo.py
git status --short
```

Do not publish Workshop folders, keys, logs, profile persistence, player data, storage, or real server configs.
