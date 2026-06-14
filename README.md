# Owen's DayZ Server Configs

Public-safe DayZ server configuration and admin tooling for a multi-map private server setup.

This repo is intended to share scripts and configuration patterns, not copyrighted game/server binaries or Steam Workshop mod files.

## What's Included

- Map launch helpers and admin scripts under `admin/`
- Shared mod-list files, launcher helpers, loot/AI tuning scripts
- COT (`@Community-Online-Tools`) as the standard admin tool across active map launches
- Sanitized `serverDZ*.example.cfg` starter configs for each map
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
python admin\status_all.py
python admin\validate_public_repo.py
```

After config changes, restart the affected DayZ server so Central Economy, Expansion missions, AI, and event settings reload.

## Before Using

1. Install DayZ Dedicated Server through Steam.
2. Install the required Workshop mods locally.
3. Copy or adapt the allowed config files from this repo.
4. Copy the matching `serverDZ*.example.cfg` to the real private config filename used by the launcher, then set your own hostname, admin password, ports, shard ID, and server values.
5. Restart the server after changing Expansion, economy, AI, or event configs.

## Publishing Notes

Do not commit Workshop mod folders, official DayZ files, player data, Steam IDs, passwords, or logs.
