# DayZ Server Recovery Runbook

When something breaks, **first identify which of three things failed** — the fix
is different for each. Quick gut-check:

| Symptom | What broke | Go to |
|---------|-----------|-------|
| Loot/vehicles/globals/permissions **reset or missing** (often after a DayZ or mod update) | **Config** | [1. Restore config](#1-restore-config) |
| **"missing PBO" kick**, a mod folder is gone, or `@Bitterroot` reverted to a junction | **A mod / PBOs** | [2. Re-download / re-materialize a mod](#2-re-download--re-materialize-a-mod) |
| Server **won't boot**, log spams `!!! Serious stream damage detected` | **Player storage** | [3. Fix corrupted storage](#3-fix-corrupted-storage) |

> Plain-language version: *"my settings got reset"* → config. *"a file is missing"* → mod. *"it crashes on load"* → storage.

## Where the backups live

- **Config backups:** `local_backups\config\*.zip` (rotated, newest 14). Created by
  the **"Back up server config"** action in the Control Center, by
  `admin\backup_config.py`, or automatically every day at 04:00 by the
  **"DayZ Config Backup to OneDrive"** scheduled task.
- **Off-machine copy:** `C:\Users\Owenl\OneDrive\Desktop\games\DayZ\config_backups\`
  (OneDrive syncs these to the cloud — use these if the local disk is gone).
- **Player storage backups:** `local_backups\storage\<map>\*.zip` (from
  `admin\backup_storage.py`).

A config backup contains mission CE (`mod_ce`, `expansion_ce`, `cfgeconomycore`,
`cfgeventspawns`, `globals`, `mapgroupproto`), profile settings, permissions,
the signing keys, and server `.cfg` files. **It does NOT contain mod PBOs**
(those are re-downloadable from the Workshop) **or player storage**.

---

## 1. Restore config

Use when settings were reset/lost (loot, vehicles, AI, globals, permissions, keys).

```powershell
# a) stop the affected map (never restore into a running server)
powershell -ExecutionPolicy Bypass -File admin\server_lifecycle.ps1 -Action stop -Map <map>

# b) pick a backup from before the problem
python admin\backup_config.py --list

# c) PREVIEW what would be restored (changes nothing)
python admin\backup_config.py --restore <zip-name>

# d) APPLY it (overwrites the config files in place)
python admin\backup_config.py --restore <zip-name> --yes

# e) start the map again
powershell -ExecutionPolicy Bypass -File admin\server_lifecycle.ps1 -Action start -Map <map>
```

`<zip-name>` can be just the file name (resolved under `local_backups\config\`)
or a full path (e.g. a zip copied back from OneDrive). Pick the **newest backup
taken before the breakage** — config loss is almost always an update reverting
files, so the latest good zip is the right one.

---

## 2. Re-download / re-materialize a mod

Config restore does **not** bring back mod PBOs. If you get a "client has a PBO
which is not part of the server" kick, a mod folder is missing, or `@Bitterroot`
became a junction again:

- **Most mods:** unsubscribe + resubscribe in the Steam Workshop (or verify the
  DayZ install), then re-run `admin\sync_all_mods_from_client.ps1` with servers
  stopped.
- **`@Bitterroot` specifically** (it must be a real folder + key, not a junction):
  ```powershell
  cmd /c rmdir "C:\Games\Steam\steamapps\common\DayZServer\@Bitterroot"   # removes the junction only
  robocopy "C:\Games\Steam\steamapps\workshop\content\221100\2906823750" `
           "C:\Games\Steam\steamapps\common\DayZServer\@Bitterroot" /E
  ```
  The `BitterrootMF.bikey` is included in the config backup, so a config restore
  puts it back in `keys\`; otherwise copy it from `@Bitterroot\keys\` into `keys\`.

---

## 3. Fix corrupted storage

`!!! Serious stream damage detected during load` = the player-persistence store
(`storage_*`) is corrupted, usually from a hard kill mid-save. **Always stop
servers gracefully** (Control Center Stop, or `server_lifecycle.ps1 -Action stop`)
to avoid this.

```powershell
# Option A - regenerate a clean store (loses persisted vehicles/tents/dropped loot for that map):
#   stop the server, then move the bad store aside; it rebuilds on next boot
Move-Item "mpmissions\<mission>\storage_<N>" "mpmissions\<mission>\storage_<N>.corrupt"

# Option B - restore the last good player-storage backup (newest unless --backup given):
python admin\restore_storage.py --map <map>          # preview / refuses without --yes
python admin\restore_storage.py --map <map> --yes    # apply the restore
```

The map's `<mission>` and `storage_<N>` number are printed near the top of the
server log (`Selected storage directory: ...`).

---

## The daily backup task

- Runs `admin\backup_config_offsite.ps1` every day at 04:00 (catches up if the PC
  was off).
- Check it: `Get-ScheduledTaskInfo -TaskName "DayZ Config Backup to OneDrive"`
  (`LastTaskResult` 0 = success).
- Run it now: `Start-ScheduledTask -TaskName "DayZ Config Backup to OneDrive"`
- Change time / remove: see the header of `admin\backup_config_offsite.ps1`.

**Before any DayZ or mod update, run a config backup first** (Control Center
"Back up server config", or `python admin\backup_config.py`) so you have a
known-good restore point.
