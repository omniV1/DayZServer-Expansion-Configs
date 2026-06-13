# Owen's DayZ Server Configs

Public-safe DayZ server configuration and admin tooling for a multi-map private server setup.

This repo is intended to share scripts and configuration patterns, not copyrighted game/server binaries or Steam Workshop mod files.

## What's Included

- Map launch helpers and admin scripts under `admin/`
- Shared mod-list files, launcher helpers, loot/AI tuning scripts
- A sanitized `serverDZChernarus.example.cfg` starter config
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

## Before Using

1. Install DayZ Dedicated Server through Steam.
2. Install the required Workshop mods locally.
3. Copy or adapt the allowed config files from this repo.
4. Copy `serverDZChernarus.example.cfg` to `serverDZChernarus.cfg`, then set your own hostname, admin password, ports, shard ID, and server values.
5. Restart the server after changing Expansion, economy, AI, or event configs.

## Publishing Notes

Do not commit Workshop mod folders, official DayZ files, player data, Steam IDs, passwords, or logs.
