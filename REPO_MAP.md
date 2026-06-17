# Repo Map

This repo keeps DayZ's expected server-root layout intact. Files are organized by clear naming and documentation instead of moving operational paths that launchers depend on.

## Start Here

- [README.md](README.md): overview and daily workflow
- [QUICKSTART.md](QUICKSTART.md): first setup path
- [MODS.md](MODS.md): generated Workshop/mod manifest
- [BALANCE.md](BALANCE.md): gameplay balance goals
- [CONTRIBUTING.md](CONTRIBUTING.md): safe contribution rules

## Root Launch Files

- `Launch-DayZMap.ps1`: data-driven map launcher
- `start_*.cmd`: one-click map launch helpers
- `serverDZ*.example.cfg`: public-safe server config templates
- `serverDZ*.cfg`: real private configs, ignored by Git

## Admin Tooling

The `admin/` folder contains all repeatable automation:

- `map_launch.json`: map ports, profiles, config names, extra mods
- `map_workshop_catalog.json`: imported map Workshop IDs and mission templates
- `workshop_manifest.json`: generated public mod manifest data
- `control_center.py`: local browser UI/API for safe script orchestration
- `control_center/`: static UI files for the local control center
- `control_center_config.json`: public-safe defaults for local UI host, port, and guardrails
- `validate_public_repo.py`: checks for unsafe tracked files and parse errors
- `check_map_launch.ps1`: verifies launch prerequisites
- `status_all.py`: compact balance/status report
- `generate_public_docs.py`: regenerates `MODS.md` and `admin/workshop_manifest.json`

## Gameplay Generators

- `build_map_expansion.py`: Expansion AI, spawn settings, spatial zones, loadouts
- `seed_imported_cot_locations.py`: creates COT-style location caches from imported map mission data
- `sanitize_imported_expansion.py`: disables/removes generated imported-map world placements until coordinates are verified
- `tune_player_spawns.py`: widens imported-map player spawn generators so custom maps do not fall back to `{0,0,0}`
- `apply_loot.py`: applies the selected loot preset and generated `mod_ce`
- `tune_chernarus_spawn_economy.py`: multi-map animal and vehicle event tuning
- `standardize_world_events.py`: rare airdrops and richer static events
- `install_money_quests.py`: repeatable Hryvnia contracts
- `tune_quest_ai.py`: reliable quest-spawned AI
- `apply_ai_ammo.py`: AI reload/ammo staying power

## Public Mission Subsets

Only public-safe mission subsets are tracked:

- `db/events.xml`
- `db/globals.xml`
- `mod_ce/**`
- selected `expansion/Loadouts/**`
- selected `expansion/settings/**`

Full mission folders, storage, logs, backups, profiles, and Workshop files stay private.

## Local Private Paths

These are expected locally but ignored:

- `@ModName/`
- `keys/`
- `profiles*/`
- `logs/`
- `storage_*/`
- real `serverDZ*.cfg`
- DayZ binaries and Steam DLLs

## Adding A Map

1. Add the Workshop mod and mission files locally.
2. Add an entry to `admin/map_launch.json`.
3. Add an entry to `admin/map_workshop_catalog.json`.
4. Add a `serverDZ_Map.example.cfg`.
5. Add a root `start_map.cmd`.
6. If sharing generated config, extend `.gitignore` with only public-safe mission subsets.
7. Run validation and launch checks.
