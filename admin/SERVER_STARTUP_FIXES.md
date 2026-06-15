# Server startup fixes

**Admin scripts:** [SCRIPTS.md](SCRIPTS.md) â€” quick loot: `loot.cmd` from server root.

## 1. SNAFU CE errors â€” fixed

Log showed:
`Type 'ACR_Gun' will be ignored. (Type does not exist.)`

**Cause:** `@SNAFU Weapons` is installed in the server folder but **not** in your `-mod=` launch string. CE only knows types from mods the server actually loads.

**Fix applied:** `mod_ce/mod_weapons_types.xml` now uses **@Techs Weapon Mod** classnames (`TWM_*`), which are on your Chernarus mod line.

**Optional â€” if you want SNAFU loot:** Add to your server launcher `-mod=` list (after other mods):
```
@SNAFU Weapons
```
Then re-run `admin/build_mod_ce.py` with SNAFU names, or merge SNAFU XML from `@SNAFU Weapons/XML_and_Clasnames/`.

---

## 2. Cannot join â€” Expansion Bundle version mismatch

Log showed:
`kicked: 146 (Client has a more recent version ... DayZ-Expansion-Bundle (PBO: ))`

**Cause:** Your **game client** has a newer Workshop build of Expansion than the **server** copy in `DayZServer\@DayZ-Expansion-*`.

**Fix:** Update server Expansion mods to match the client (same Workshop versions):

1. In Steam â†’ DayZ â†’ Workshop, note the latest update time on:
   - DayZ-Expansion-Bundle
   - DayZ-Expansion-Core
   - DayZ-Expansion-AI
   - DayZ-Expansion-Licensed
   - DayZ-Expansion-Market
2. Copy/update those mods into `C:\Games\Steam\steamapps\common\DayZServer\` (same `@FolderName` as client), **or** use SteamCMD workshop sync for your server install.
3. Restart the server completely after updating.
4. Client and server Expansion `meta.cpp` timestamps should match (no kick 146).

---

## 3. Remaining CE warnings (2026-06-01 19:23 restart) â€” fixed

| Warning | Fix |
|---------|-----|
| `TWM_Tikka` type does not exist | Removed from `mod_ce`; added to `cfgignorelist.xml` |
| `Expansion_Longhorn` type does not exist | Removed from Expansion in current Bundle; added to `cfgignorelist.xml` |
| `Expansion_M79` / `ExpansionFlaregun` not spawnable | Normal Expansion CE behaviour â€” ignore |
| `dynamic_009.002` corrupt | Stop server, delete `storage_1\data\dynamic_009.002`, restart |

After restart you should see **4 classes** in mod_ce TypeSetup and no SNAFU/Tikka/Longhorn spam.

---

## 4. Harmless / optional warnings

| Message | Action |
|---------|--------|
| `Server.core.xml` parser error | Regenerated on start; safe to ignore if inputs work |
| `ChristmasTree`, `Expansion_M79` not spawnable | Normal Expansion CE flags |
| `VehicleTransitBus` event missing | Vanilla/event mismatch; low priority |
| `dynamic_009.002` read failed once | Corrupt backup; CE used `.bin` â€” delete `storage_1\data\dynamic_009.002` if repeats |

---

## 4. Regenerate loot after changes

```powershell
python admin\build_mod_ce.py
python admin\replicate_mod_ce.py
```

Restart server. For a full CE types refresh, stop server and delete `mpmissions\dayzOffline.chernarusplus\storage_1\data\types.bin` (and `.001`/`.002`) once â€” **this resets persisted loot counts**.

---

## 5. Takistan â€” â€œNo world with name 'Takistan'â€

**World / mission:** `dayzOffline.TakistanPlus` in `serverDZ_Takistan.cfg` (terrain world name is `TakistanPlus`).

**Root cause (found in RPT):** The server was **not loading any mods**. Either:

1. `-mod=%DAYZ_MODS%` appeared **literally** in the log (batch `start` did not expand the variable), or  
2. `-mod=` was unquoted and broke at `@Dabs Framework`, so **`@TakistanPlus` never loaded**.

**Fix â€” use the PowerShell launcher only:**

```powershell
C:\Games\Steam\steamapps\common\DayZServer\Launch-Takistan.ps1
```

Or double-click `start_Takistan.bat` on the Desktop (it calls that script).

**Check after start:**

```powershell
powershell -File admin\check_takistan.ps1
```

Should say **OK** and the newest RPT must **not** contain `-mod=%DAYZ_MODS%` or `@Dabs/Anims`.

**DayZ client:** Enable `@TakistanPlus` and `@Dabs Framework` before joining (same order: CF, Dabs, then TakistanPlus).

**Sandstorm compile error (`Unknown type 'WeatherEvent'`):** Takistanâ€™s weather PBO needs **Dabs Framework** loaded **before** `@TakistanPlus` in `-mod=`. The launchers use `@CF;@Dabs Framework;@TakistanPlus;...`.

**â€œNo world named Takistanâ€ after reordering mods:** If `-mod=` is **not one quoted argument**, Windows splits at the space in `@Dabs Framework`. With `@CF` first, only `@CF` loads and `@TakistanPlus` is dropped. RPT shows `Can't load @Dabs/Anims` and no `Takistan.pbo`. Use **`Launch-Takistan.ps1`** (call operator, not `Start-Process`) or **`start_Takistan_DIRECT.cmd`** (`"-mod=%DAYZ_MODS%"`). Do not use unquoted `-mod=` lines.

**Server â€œkeeps restartingâ€ every ~10s:** `Launch-Takistan.ps1` used to auto-restart every 10 seconds. That spawns overlapping `DayZServer_x64` processes while the first is still loading. Use **one** launcher window; wait 2â€“5 minutes on first boot. Optional: `powershell -File Launch-Takistan.ps1 -AutoRestart` (60s delay).

**Inputs / `Server.core.xml` parser error on first line:** Harmless on first run; the server recreates the file. â€œDedicated host createdâ€ + Expansion inputs loading means startup is progressing.

**Other maps (Chernarus mod parity):** Edit `admin/chernarus_mods.txt` once, start with `Launch-DayZMap.ps1 -Map enoch|sakhal|namalsk|takistan` or Desktop `start_*.bat`. Takistan is active, but still requires `@Dabs Framework` before `@TakistanPlus`.

## Namalsk / Sakhal â€” launcher shows â€œno modsâ€

**Symptoms:** DayZ join dialog says *Server can't transmit all data* and *(server doesn't require any mods)*, while Chernarus/Enoch list ~9 mods.

**Common causes fixed in this repo:**

1. **Sakhal used the same game port as Chernarus (2302)** â€” only one process can bind; the browser may query the wrong server. Sakhal is now **2602** (query **27019**) in `admin/map_launch.json` and `serverDZSakhal.cfg`.
2. **Per-map `steamQueryPort` must be sequential from 27016** â€” Chernarus **27016**, Livonia **27017**, Namalsk **27018**, Sakhal **27019**. Each map also uses its own `-profiles=` folder (`profiles`, `profiles_enoch`, etc.).
3. **Missing `@CannabisPlus` folder** â€” removed from `admin/chernarus_mods.txt` (was causing RPT load errors).
4. **Joining before init finishes** â€” wait for RPT `Init sequence finished` / `IdleMode` (Namalsk CE init can take 1â€“2 minutes).

**Verify:**

```powershell
powershell -File admin\check_map_launch.ps1 -Map namalsk
```

Latest RPT line 1 must contain `-mod=` with `@Dabs Framework` and **not** `%DAYZ_MODS%`.

**Launcher still truncates mod list:** With ~35 mods, Steam often only advertises the **last** entries (Fish's Knife, Trader, TreeHouse, etc.). That is normal on Chernarus too. Load the **full** mod set in the DayZ client (same as `chernarus_mods.txt` + map extras), then use **KEEP CURRENT SELECTION AND JOIN** if the server list is incomplete.

**Namalsk:** `@Namalsk Island` is prepended early in the mod chain; `@Namalsk Survival (server)` stays on `-serverMod=`.

## Server not listed under LAN tab

**Cause:** `Launch-DayZMap.ps1` used `-ip=127.0.0.1`, which binds the server to **localhost only**. Steam LAN discovery looks on your real network (e.g. `192.168.0.3`), so the LAN list stays empty even when the server is running.

**Fix:** Restart the server after updating the launcher (no `-ip=127.0.0.1` unless you set `bind_ip` in `admin/map_launch.json` to your LAN address).

**Ports to use (game port, not query port):**

| Map | Connect / LAN game port | steamQueryPort (LAN tab) |
|-----|-------------------------|--------------------------|
| Chernarus | **2302** | **27016** |
| Livonia (Enoch) | **2402** | **27017** |
| Namalsk | **2502** | **27018** |
| Sakhal | **2602** | **27019** |
| Takistan | **2702** | **27020** |
| Deer Isle | **2802** | **27021** |
| Banov | **2902** | **27022** |
| Esseker | **3002** | **27023** |
| Rostow | **3102** | **27024** |
| Iztek | **3202** | **27025** |
| Alteria | **3302** | **27026** |

Direct connect in the launcher: `192.168.0.3` + port from the table (e.g. `192.168.0.3:2502` for Namalsk).

**Also check:**

- Steam: Settings > In-Game > enable **Local network game discovery** (wording may vary).
- DayZ launcher **Remote** tab > Add server by IP:port if LAN stays empty.
- If A2S query passes but the launcher UI still hides the server, use `Connect-Rostow.bat` style helpers or direct connect to the game port.
- `shardId = "123abc"` in `serverDZ*.cfg` marks the server **private** (Community tab); LAN can still work once binding is fixed.
- Windows Firewall: allow **UDP** inbound on game + query ports for `DayZServer_x64.exe`.

**Refresh official CE:** `python admin\install_takistan_mission.py`

