# Owen's DayZ Server Configs

Public-safe DayZ server configuration and admin tooling for a multi-map private server setup.

This repo is intended to share scripts and configuration patterns, not copyrighted game/server binaries or Steam Workshop mod files.

## What's Included

- Map launch helpers and admin scripts under `admin/`
- Shared mod-list files, launcher helpers, loot/AI tuning scripts
- COT (`@Community-Online-Tools`) as the standard admin tool across active map launches
- Sanitized `serverDZ*.example.cfg` starter configs for each map
- New-map launch stubs for Deer Isle, Banov, Esseker, Rostow, Iztek, and Alteria
- Public-safe loot/event config coverage for Deer Isle, Banov, Esseker, Rostow, Iztek, and Alteria
- Chernarus Expansion mission configuration:
  - Expansion AI tuning
  - Expansion Market/trader configs
  - Expansion Quest contracts that pay Hryvnia
  - Airdrop and world-event tuning

## What's Not Included

The `.gitignore` intentionally excludes:

- `DayZServer_x64.exe`, Steam DLLs, and official server files
- Steam Workshop `@ModName` folders
- BattleEye keys and generated caches
- Logs/crash dumps/RPT files
- Player/account persistence such as ATM, player data, group data, and storage
- Real `serverDZ*.cfg` files, because they can contain admin passwords and local server values

## Current Chernarus Balance

- Medium AI difficulty: accurate enough to matter, not laser-focused
- Fewer AI encounters: major towns, airfields, military zones, events, and contracts
- Solid AI gear via `PvPLoadout`
- More heli crashes, convoys, police situations, and train events
- Rare Expansion airdrops: roughly every 6 hours, limited to a few locations
- Repeatable contract-board quests at Kamenka that pay `ExpansionBanknoteHryvnia`
- Arcade loot economy is active and replicated to Chernarus, Livonia, Sakhal, Namalsk, and Takistan
- Wildlife and usable vehicle events are boosted across active maps where those events exist

## Daily Ops

From the server root, the normal full refresh flow is:

```powershell
python admin\build_map_expansion.py --all
python admin\apply_ai_ammo.py
python admin\apply_loot.py all --preset arcade
python admin\tune_chernarus_spawn_economy.py
python admin\install_money_quests.py
python admin\tune_quest_ai.py
python admin\standardize_world_events.py
python admin\seed_imported_cot_locations.py
python admin\check_imported_ai_ready.py
python admin\status_all.py
python admin\validate_public_repo.py
```

After config changes, restart the affected DayZ server so Central Economy, Expansion missions, AI, and event settings reload.

## Imported Map Patrols

Deer Isle, Banov, Esseker, Rostow, Iztek, and Alteria are launch-ready and have boosted loot/events, money-contract scaffolding, and generated first-pass Expansion patrols. The patrol generator can use either real COT exports or auto-seeded locations from each mission's `mapgrouppos.xml`.

To refresh first-pass imported map patrols:

```powershell
python admin\seed_imported_cot_locations.py
python admin\check_imported_ai_ready.py
python admin\build_map_expansion.py --imported
python admin\apply_ai_ammo.py
python admin\status_all.py
```

To improve those auto-seeded patrols later, launch each imported map, refine/create COT map locations in-game, then rerun:

```powershell
powershell -File .\Launch-DayZMap.ps1 -Map deerisle
python admin\check_imported_ai_ready.py
python admin\build_map_expansion.py --imported
python admin\apply_ai_ammo.py
python admin\status_all.py
```

The expected COT files are `profiles_deerisle\CommunityOnlineTools\Teleports_deerisle.json`, `profiles_banov\CommunityOnlineTools\Teleports_banov.json`, `profiles_esseker\CommunityOnlineTools\Teleports_esseker.json`, `profiles_rostow\CommunityOnlineTools\Teleports_rostow.json`, `profiles_iztek\CommunityOnlineTools\Teleports_iztek.json`, and `profiles_alteria\CommunityOnlineTools\Teleports_alteria.json`.

## Before Using

1. Install DayZ Dedicated Server through Steam.
2. Install the required Workshop mods locally.
3. Copy or adapt the allowed config files from this repo.
4. Copy the matching `serverDZ*.example.cfg` to the real private config filename used by the launcher, then set your own hostname, admin password, ports, shard ID, and server values.
5. Restart the server after changing Expansion, economy, AI, or event configs.
6. For new map mods, subscribe/download them in Steam, then run `powershell -File admin\sync_map_workshop_mods.ps1 -Map all`.

## Publishing Notes

Do not commit Workshop mod folders, official DayZ files, player data, Steam IDs, passwords, or logs.
