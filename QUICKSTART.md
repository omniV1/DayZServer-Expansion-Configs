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
python admin\control_center.py --open-browser
python admin\validate_public_repo.py
powershell -ExecutionPolicy Bypass -File admin\check_map_launch.ps1 -Map all
python admin\status_all.py
python admin\validate_imported_maps.py
```

The control center is optional, but it is the easiest first stop: it lists maps, missing configs/mods, latest log status, VPP health, launch checks, guarded maintenance actions, and balance controls for loot, AI, zombies, animals, and spawn globals.

For release builds, download and run `DayZServerControlCenter.exe`; it opens the same local dashboard and asks for your DayZServer folder if needed.

### Why Windows may warn you (and why it is safe)

The desktop release is a new, independent open-source app, so Windows SmartScreen may show **"Windows protected your PC"** the first time you run it. This is the normal warning for any app that has not yet built download reputation — it is **not** a virus alert.

To run it: click **More info**, then **Run anyway**.

Why you can trust it:

- **Open source** — the exe is built from the Python code in this repo (`admin/control_center.py` + `admin/control_center/`). You can read exactly what it does, or run the script directly with `python admin\control_center.py` instead of the exe.
- **Local only** — it binds to `127.0.0.1`, opens no public ports, and runs only an allowlisted set of admin scripts. Nothing is uploaded; the one optional internet call (the Workshop mod-update check) happens only when you click the button.
- **Verifiable download** — each release zip ships with a `.sha256` checksum. Confirm your download matches before running:

  ```powershell
  Get-FileHash .\DayZServerControlCenter-<version>-windows.zip -Algorithm SHA256
  ```

  Compare the printed hash to the `.sha256` file on the release page.

The warning fades on its own as more people download and run the app. Signed releases may come later.

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
python admin\tune_imported_ce_safety.py
python admin\tune_chernarus_spawn_economy.py
python admin\install_money_quests.py
python admin\tune_quest_ai.py
python admin\standardize_world_events.py
python admin\status_all.py
```

Restart affected servers after changing economy, Expansion, AI, or event configs.

For imported maps that previously looped during startup, clear persisted bad objects once:

```powershell
python admin\sanitize_imported_expansion.py --wipe-storage
```

If a running server does not appear in the DayZ launcher LAN/community list, add the UDP firewall rules:

```powershell
powershell -ExecutionPolicy Bypass -File admin\ensure_dayz_firewall.ps1 -Map all
python admin\query_dayz_server.py --map rostow --host 127.0.0.1
```

You can also use `Connect-Rostow.bat`, `Connect-DeerIsle.bat`, and the other `Connect-*.bat` helpers to direct-connect locally once the RPT shows `Player connect enabled`.

To test one map end-to-end while no other DayZ server is running:

```powershell
powershell -ExecutionPolicy Bypass -File admin\smoke_test_map.ps1 -Map rostow
powershell -ExecutionPolicy Bypass -File admin\smoke_test_maps.ps1 -Map all-imported
powershell -ExecutionPolicy Bypass -File admin\recover_imported_map.ps1 -Map rostow -StopExisting
```

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
