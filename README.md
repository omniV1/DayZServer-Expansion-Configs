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
- Imported community maps default to native map CE for stability; generated `mod_ce` is disabled there until each terrain is verified
- More useful animals, vehicles, heli crashes, police/train-style events where maps support them
- Rare airdrops instead of constant spam
- Repeatable Hryvnia money contracts for Expansion gear progression
- Public repo validation to prevent accidental leaks
- GitHub Actions validation for repo-safe syntax and public-safety checks

## Daily Refresh

From the server root:

```powershell
python admin\build_map_expansion.py --all
python admin\seed_imported_cot_locations.py
python admin\sanitize_imported_expansion.py
python admin\build_map_expansion.py --imported
python admin\tune_player_spawns.py
python admin\apply_ai_ammo.py
python admin\apply_loot.py all --preset arcade
python admin\tune_imported_ce_safety.py
python admin\tune_chernarus_spawn_economy.py
python admin\install_money_quests.py
python admin\tune_quest_ai.py
python admin\standardize_world_events.py
python admin\status_all.py
python admin\validate_imported_maps.py
python admin\validate_public_repo.py
```

Restart affected servers after changing economy, Expansion, AI, event, or quest configs.

For imported maps, run `python admin\sanitize_imported_expansion.py --wipe-storage` once after changing safety/economy settings so old bad objects are not loaded from persistence.

If servers start but do not appear in the DayZ launcher LAN tab, run the LAN visibility repair/check. This syncs query ports, refreshes server/client firewall rules for Steam and the DayZ launcher, checks active UDP endpoints, and prints recent launcher browser warnings:

```powershell
powershell -ExecutionPolicy Bypass -File admin\check_lan_visibility.ps1 -Map all -RepairFirewall
```

If the script shows A2S is OK but the launcher still cannot retrieve the LAN server list, reset the launcher browser cache:

```powershell
powershell -ExecutionPolicy Bypass -File admin\reset_dayz_launcher_browser.ps1 -StopLauncher -OpenLauncher
```

To prove a map can boot, advertise, and answer Steam query, run a smoke test while no other DayZ server is running:

```powershell
powershell -ExecutionPolicy Bypass -File admin\smoke_test_map.ps1 -Map rostow
powershell -ExecutionPolicy Bypass -File admin\smoke_test_maps.ps1 -Map all-imported
powershell -ExecutionPolicy Bypass -File admin\recover_imported_map.ps1 -Map rostow -StopExisting
```

## Safety

Before publishing:

```powershell
python admin\validate_public_repo.py
git status --short
```

Do not commit Workshop folders, official DayZ files, player data, Steam IDs, passwords, keys, logs, storage, or real `serverDZ*.cfg` files.
