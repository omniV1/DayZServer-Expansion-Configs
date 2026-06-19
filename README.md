# DayZ Expansion Server Config Framework

Public-safe DayZ server configuration and automation for a multi-map Expansion PvE setup.

This repo shares repeatable scripts, example configs, generated economy/AI settings, and launch helpers. It intentionally does not include DayZ binaries, Steam Workshop folders, keys, real server configs, logs, storage, or player/profile persistence.

## Start Here

- [QUICKSTART.md](QUICKSTART.md): setup and first launch
- [CONTROL_CENTER_ROADMAP.md](CONTROL_CENTER_ROADMAP.md): versioned Control Center roadmap
- [MODS.md](MODS.md): generated Workshop/mod manifest
- [REPO_MAP.md](REPO_MAP.md): where everything lives
- [BALANCE.md](BALANCE.md): gameplay targets for AI, loot, events, vehicles, and quests
- [CONTRIBUTING.md](CONTRIBUTING.md): safe contribution rules

## Local Control Center

Run a browser-based local dashboard from the server root:

```powershell
python admin\control_center.py --open-browser
```

Desktop users can also run `DayZServerControlCenter.exe` from a release zip. On first launch it auto-detects common DayZServer paths or asks for the folder containing `admin\map_launch.json`.

The control center binds to `127.0.0.1` by default and wraps only allowlisted scripts. It can show map status, latest redacted logs, VPP/admin health, LAN checks, config drift, snapshots, smoke tests, guarded generation/recovery jobs, and balance controls for loot presets, AI patrol difficulty/density, zombies, animals, and spawn globals. Risky actions require typed confirmation and guarded edits create a local config snapshot first.

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
- Local web control center for map status, diagnostics, snapshots, and guarded script actions
- UI balance editor for active loot presets, AI patrol caps/difficulty, zombies, animals, and spawn globals
- Public-safe `serverDZ*.example.cfg` templates
- VPP (`@VPPAdminTools`) as the standard admin tool
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
python admin\tune_ce_overtime.py --map all
python admin\tune_chernarus_spawn_economy.py
python admin\install_money_quests.py
python admin\tune_quest_ai.py
python admin\standardize_world_events.py
python admin\status_all.py
python admin\validate_imported_maps.py
python admin\validate_public_repo.py
```

Restart affected servers after changing economy, Expansion, AI, event, or quest configs.

`tune_ce_overtime.py` reads recent RPT logs and caps item classes that cause CE "hard to place" or "search overtime" storms. Restart the affected map after running it so the Central Economy reloads the changed `types.xml`/`mod_ce` values.

For imported maps, run `python admin\sanitize_imported_expansion.py --wipe-storage` once after changing safety/economy settings so old bad objects are not loaded from persistence.

If servers start but do not appear in the DayZ launcher LAN tab, run the LAN visibility repair/check. This syncs query ports, refreshes server/client firewall rules for Steam and the DayZ launcher, checks active UDP endpoints, and prints recent launcher browser warnings:

```powershell
powershell -ExecutionPolicy Bypass -File admin\check_lan_visibility.ps1 -Map all -RepairFirewall
```

Run the `-RepairFirewall` command from **Administrator PowerShell**. The LAN tab depends on both server UDP port rules and client program rules for Steam, Steam WebHelper, DayZ Launcher, DayZ client, and `DayZServer_x64.exe`.

To start one map and verify LAN/query visibility in one command:

```powershell
powershell -ExecutionPolicy Bypass -File admin\check_lan_visibility.ps1 -Map esseker -StartMap
```

The launcher's LAN auto-discovery appears to scan only the usual Steam query range around `27015-27020`. When a map's configured query port is higher, the launch tools create a temporary LAN-visible config under `local_runtime\lan_query\` and move that single map onto a free scanned query port.

VPP admin credentials live in each map's private `profiles*\VPPAdminTools\Permissions` folder and are not published. After adding a new profile/map, sync the local VPP SuperAdmin/password files from the main `profiles` folder:

```powershell
powershell -ExecutionPolicy Bypass -File admin\sync_vpp_admin_profiles.ps1 -Map all
powershell -ExecutionPolicy Bypass -File admin\switch_admin_inputs_to_vpp.ps1 -Map all -IncludeClientProfiles
powershell -ExecutionPolicy Bypass -File admin\check_admin_tooling.ps1 -Map all -IncludeClientProfiles -CheckDesktop
```

`check_admin_tooling.ps1` verifies that launch mod lists use VPP, active server processes are not still using COT, VPP SuperAdmin files exist per profile, server/client input presets bind VPP to `End` and `Home`, and generated Desktop launchers still call `Launch-DayZMap.ps1`.

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
