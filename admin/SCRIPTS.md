# DayZ Server Admin Scripts

All scripts live under `DayZServer/admin/`. Run PowerShell from the server folder unless noted.

## Map launchers (shared Chernarus mods)

Chernarus mod list: `admin/chernarus_mods.txt` (edit once - applies to all maps below). COT (`@Community-Online-Tools`) is the standard admin tool.

| Map | Desktop / server start |
|-----|-------------------------|
| Chernarus | `start_chernarus.bat` or `start_chernarus.cmd` (4h scheduled restart) |
| Livonia | `start_Enoch.bat` or `start_enoch.cmd` |
| Sakhal | `start_Sakhal.bat` or `start_sakhal.cmd` (+ `@Zens ExpansionAI Audio`) |
| Namalsk | `start_Namalsk.bat` or `start_namalsk.cmd` (+ `@Namalsk Island`, server mod `@Namalsk Survival (server)`) |
| Takistan | `start_Takistan.bat` or `start_Takistan.cmd` (`@Dabs Framework` before `@TakistanPlus`) |
| Deer Isle | `start_deerisle.cmd` or generated Desktop `start_deerisle.bat` |
| Banov | `start_banov.cmd` or generated Desktop `start_banov.bat` |
| Esseker | `start_esseker.cmd` or generated Desktop `start_esseker.bat` |
| Rostow | `start_rostow.cmd` or generated Desktop `start_rostow.bat` |
| Iztek | `start_iztek.cmd` or generated Desktop `start_iztek.bat` |
| Alteria | `start_alteria.cmd` or generated Desktop `start_alteria.bat` |

```powershell
.\Launch-DayZMap.ps1 -Map enoch
.\Launch-DayZMap.ps1 -Map sakhal
.\Launch-DayZMap.ps1 -Map namalsk
.\Launch-DayZMap.ps1 -Map takistan
```

Ports: Chernarus **2302** (query **27016**), Livonia **2402** (query **27017**), Namalsk **2502** (query **27018**), Sakhal **2602** (query **27019**), Takistan **2702** (query **27020**), Deer Isle **2802** (query **27021**), Banov **2902** (query **27022**), Esseker **3002** (query **27023**), Rostow **3102** (query **27024**), Iztek **3202** (query **27025**), Alteria **3302** (query **27026**).

Preflight: `powershell -File admin\check_map_launch.ps1 -Map namalsk`

Create a Desktop launcher for any map listed in `admin/map_launch.json`:

```powershell
powershell -File admin\new_map_desktop_launcher.ps1 -Map takistan
powershell -File admin\sync_desktop_launchers.ps1
```

Sync downloaded map Workshop folders into the server root:

```powershell
powershell -File admin\sync_map_workshop_mods.ps1 -Map all -OpenMissingWorkshopPages
python admin\repair_mission_xml.py dayzOffline.banov dayzOffline.Esseker Offline.rostow empty.Iztek empty.alteria empty.deerisle
```

LAN/direct connect uses the **game port**, not the query port. Launcher must not bind `-ip=127.0.0.1` or LAN stays empty.

Imported map stability workflow:

```powershell
python admin\sanitize_imported_expansion.py --wipe-storage
python admin\tune_player_spawns.py
python admin\tune_imported_ce_safety.py
python admin\validate_imported_maps.py
powershell -ExecutionPolicy Bypass -File admin\smoke_test_maps.ps1 -Map all-imported
```

If the DayZ launcher UI does not list a server but the smoke test passes, use the matching `Connect-*.bat` helper or Direct Connect to the game port.

One-map recovery:

```powershell
powershell -ExecutionPolicy Bypass -File admin\recover_imported_map.ps1 -Map rostow -StopExisting
```

After adding a mod on Chernarus, append it to `admin/chernarus_mods.txt` and restart any map.

---

## Quick access (AI ammo)

Patrols and spatial AI run dry in long fights - this enables **unlimited reload** and adds spare mags to loadouts.

| Command | What it does |
|---------|----------------|
| `ai-ammo.cmd` | Apply all AI ammo patches |
| `ai-ammo.cmd -Status` | Show current reload/mag settings |

```powershell
.\admin\apply-ai-ammo.ps1
python admin\apply_ai_ammo.py --status
```

Restart server after applying (or wait for AI to respawn).

---

## Quick access (AI patrols on all maps)

Sync **Chernarus patrol caps / radii / unlimited reload** to Livonia, Sakhal, Namalsk, and Takistan (keeps each map's own routes):

```bat
admin\replicate-ai.ps1
```

Or: `python admin\replicate_ai_settings.py` then `python admin\apply_ai_ammo.py`

| Map | Patrol file | Notes |
|-----|-------------|--------|
| Chernarus | yes | Source + full waypoints |
| Livonia (enoch) | yes | Own routes; synced globals |
| Sakhal | yes | Own routes; synced globals |
| Namalsk | created if missing | Object/heli patrols only until you add routes |
| Takistan | yes | Active via `dayzOffline.TakistanPlus`; keep Dabs before TakistanPlus |

**Spatial AI** on other maps: copies Group + timers (no Chernarus XYZ). Set `"sync_spatial_fixed_locations": true` in `admin/ai_config.json` only after you add map coords.

**AI War Zones** - one active file; swap per map before start:

```bat
warzones.cmd enoch
warzones.cmd sakhal
warzones.cmd takistan
warzones.cmd namalsk
warzones.cmd chernarus
```

Map packs: `profiles/AIWarZones/maps/*.json` (built from `admin/build_warzones.py`).  
Coords from mission `AILocationSettings` / event spawns / trader maps.

Config: `admin/ai_config.json`

---

## Quick access (loot)

| What you want | Command |
|---------------|---------|
| Apply full loot pass (build + globals + all maps) | `loot.cmd` or `.\admin\apply-loot.ps1` |
| Check current preset / files | `loot.cmd -Action status` |
| More loot (default **saturated**) | `loot.cmd -Action all` |
| Even more loot | `loot.cmd -Action all -Preset arcade` |
| Maximum loot (arcade) | `loot.cmd -Action all -Preset arcade` |
| Only rebuild XML (Chernarus source) | `loot.cmd -Action build` |
| Only copy to other maps | `loot.cmd -Action replicate` |
| Save default preset name | `loot.cmd -Action set-preset -Preset medium` |

**After any loot change:** restart the DayZ server so Central Economy reloads.

**Tune numbers:** edit `admin/loot_config.json` (presets: `light`, `medium`, `high`, `saturated`, `arcade`).

---

## Loot toolchain (files)

| File | Role |
|------|------|
| `loot.cmd` | Launcher at server root (calls `apply-loot.ps1`) |
| `apply-loot.ps1` | PowerShell wrapper with `-Action` / `-Preset` |
| `apply_loot.py` | Main Python entry - orchestrates everything |
| `loot_config.json` | Presets and mission list (edit multipliers here) |
| `loot_settings.py` | Loads config (used by other scripts) |
| `build_mod_ce.py` | Generates `mpmissions/.../mod_ce/*.xml` |
| `replicate_mod_ce.py` | Legacy copy-only (prefer `apply_loot.py replicate`) |
| `patch_loot_globals.py` | Legacy globals patch (prefer `apply_loot.py globals`) |

Python equivalent (no PowerShell):

```bat
python admin\apply_loot.py all --preset high
python admin\apply_loot.py status
```

---

## Other admin scripts

| Script | Purpose |
|--------|---------|
| `sync_expansion_from_client.ps1` | Copy Workshop Expansion PBOs from client to server `@DayZ-Expansion-*` |
| `build_aipatrol_chernarus.py` | Regenerate Chernarus `AIPatrolSettings.json` |
| `replicate_mod_ce.py` | Copy `mod_ce` to Enoch / Sakhal / Takistan / Namalsk |
| `finish_replicate.py` | One-off replication helper (if present) |
| `chernarus-test-notes.txt` | In-game AI/loot test checklist |
| `SERVER_STARTUP_FIXES.md` | Known startup / mod issues |

---

## Typical workflows

### Local config snapshot

```powershell
python admin\snapshot_configs.py --label before-risky-change
python admin\snapshot_configs.py --list
python admin\snapshot_configs.py --restore admin\backups\YYYYMMDD-HHMMSS-config.zip --yes
```

Snapshots stay local under ignored `admin/backups/` and skip storage, logs, Workshop folders, binaries, and keys.

### Quick balance status

```powershell
python admin\status_all.py
python admin\triage_latest_logs.py --map all
python admin\check_config_drift.py --map all
```

Shows the active loot preset, Expansion mission pacing, AI patrol counts, `mod_ce` wiring, key globals, event categories, and enabled airdrops for each active map.
The log triage command scans recent profile logs for launch blockers such as invalid spawns, bad server config, missing files, mod load failures, and port binding problems.
The drift check compares launch ports, server config ports, mission templates, example configs, and start helpers with secrets redacted.

### Full active-map refresh

```powershell
python admin\build_map_expansion.py --all
python admin\apply_ai_ammo.py
python admin\apply_loot.py all --preset arcade
python admin\tune_chernarus_spawn_economy.py
python admin\install_money_quests.py
python admin\tune_quest_ai.py
python admin\standardize_world_events.py
python admin\validate_public_repo.py
```

Restart each affected map server after the refresh.

### "Loot feels too low"

1. `loot.cmd -Action status`
2. `loot.cmd -Action all -Preset high`
3. Restart server

### New map added to server

1. Add mission folder under `mpmissions/`
2. Add name to `replicate_missions` in `loot_config.json`
3. Wire `cfgeconomycore.xml` with `mod_ce` block (or run `apply_loot.py replicate` after manual wire)
4. `loot.cmd -Action replicate`

### Expansion version mismatch (kick 146)

```powershell
.\admin\sync_expansion_from_client.ps1
```

---

## Source mission

Chernarus (`dayzOffline.chernarusplus`) is the **source** for generated `mod_ce`. Other maps receive a copy on `replicate`. Change `source_mission` in `loot_config.json` if you build from another map.

