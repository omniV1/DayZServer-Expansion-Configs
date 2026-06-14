# DayZ Expansion Server Config Framework

Public-safe DayZ server configuration and automation for a multi-map Expansion PvE setup.

This repo shares repeatable scripts, example configs, generated economy/AI settings, and launch helpers. It intentionally does not include DayZ binaries, Steam Workshop folders, keys, real server configs, logs, storage, or player/profile persistence.

## Start Here

- [QUICKSTART.md](QUICKSTART.md): setup and first launch
- [MODS.md](MODS.md): generated Workshop/mod manifest
- [REPO_MAP.md](REPO_MAP.md): where everything lives
- [BALANCE.md](BALANCE.md): gameplay targets for AI, loot, events, vehicles, and quests
- [CONTRIBUTING.md](CONTRIBUTING.md): safe contribution rules

## Supported Maps

- Chernarus
- Livonia/Enoch
- Sakhal
- Namalsk
- Takistan
- Deer Isle
- Banov
- Esseker
- Rostow
- Iztek
- Alteria

## What This Provides

- Data-driven map launching through `Launch-DayZMap.ps1`
- Public-safe `serverDZ*.example.cfg` templates
- COT (`@Community-Online-Tools`) as the standard admin tool
- Expansion AI loadouts, patrols, spatial zones, and spawn settings
- Generated first-pass patrol support for imported Workshop maps
- Higher-loot Central Economy support through generated `mod_ce`
- More useful animals, vehicles, heli crashes, police/train-style events where maps support them
- Rare airdrops instead of constant spam
- Repeatable Hryvnia money contracts for Expansion gear progression
- Public repo validation to prevent accidental leaks

## Daily Refresh

From the server root:

```powershell
python admin\build_map_expansion.py --all
python admin\seed_imported_cot_locations.py
python admin\build_map_expansion.py --imported
python admin\tune_player_spawns.py
python admin\apply_ai_ammo.py
python admin\apply_loot.py all --preset arcade
python admin\tune_chernarus_spawn_economy.py
python admin\install_money_quests.py
python admin\tune_quest_ai.py
python admin\standardize_world_events.py
python admin\status_all.py
python admin\validate_public_repo.py
```

Restart affected servers after changing economy, Expansion, AI, event, or quest configs.

## Safety

Before publishing:

```powershell
python admin\validate_public_repo.py
git status --short
```

Do not commit Workshop folders, official DayZ files, player data, Steam IDs, passwords, keys, logs, storage, or real `serverDZ*.cfg` files.
