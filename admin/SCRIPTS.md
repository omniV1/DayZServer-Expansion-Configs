# DayZ Server Admin Scripts

All scripts live under `DayZServer/admin/`. Run PowerShell from the server folder unless noted.

## Map launchers (shared Chernarus mods)

Chernarus mod list: `admin/chernarus_mods.txt` (edit once â€” applies to all maps below).

| Map | Desktop / server start |
|-----|-------------------------|
| Chernarus | `start_chernarus.bat` or `start_chernarus.cmd` (4h scheduled restart) |
| Livonia | `start_Enoch.bat` or `start_enoch.cmd` |
| Sakhal | `start_Sakhal.bat` or `start_sakhal.cmd` (+ `@Zens ExpansionAI Audio`) |
| Namalsk | `start_Namalsk.bat` or `start_namalsk.cmd` (+ `@Namalsk Island`, server mod `@Namalsk Survival (server)`) |
| Takistan | `start_Takistan.bat` or `start_Takistan.cmd` (`@Dabs Framework` before `@TakistanPlus`) |

```powershell
.\Launch-DayZMap.ps1 -Map enoch
.\Launch-DayZMap.ps1 -Map sakhal
.\Launch-DayZMap.ps1 -Map namalsk
.\Launch-DayZMap.ps1 -Map takistan
```

Ports: Chernarus **2302** (query **2303**), Livonia **2402** (query **2403**), Namalsk **2502** (query **2503**), Sakhal **2602** (query **2603**). Sakhal no longer shares 2302 with Chernarus.

Preflight: `powershell -File admin\check_map_launch.ps1 -Map namalsk`

LAN browser: connect on **game port** (2302 / 2402 / 2502 / 2602). Do not use query port. Launcher must not bind `-ip=127.0.0.1` or LAN stays empty.

After adding a mod on Chernarus, append it to `admin/chernarus_mods.txt` and restart any map.

---

## Quick access (AI ammo)

Patrols and spatial AI run dry in long fights â€” this enables **unlimited reload** and adds spare mags to loadouts.

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

**AI War Zones** â€” one active file; swap per map before start:

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
| `apply_loot.py` | Main Python entry â€” orchestrates everything |
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

### Full active-map refresh

```powershell
python admin\build_map_expansion.py --all
python admin\apply_ai_ammo.py
python admin\apply_loot.py all --preset arcade
python admin\tune_chernarus_spawn_economy.py
python admin\install_money_quests.py
python admin\standardize_world_events.py
python admin\validate_public_repo.py
```

Restart each affected map server after the refresh.

### â€œLoot feels too lowâ€

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

