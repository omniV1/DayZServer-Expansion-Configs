"""
Install the official TakistanPlus mission from CypeR79's GitHub repo.

Preserves expansion/ and mod_ce/ under mpmissions/dayzOffline.TakistanPlus.
https://github.com/CypeR79/DayZ-Projects/tree/main/TakistanPlus
"""
from __future__ import annotations

import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

SERVER = Path(r"c:\Games\Steam\steamapps\common\DayZServer")
MISSION = SERVER / "mpmissions" / "dayzOffline.TakistanPlus"
ZIP_URL = "https://github.com/CypeR79/DayZ-Projects/archive/refs/heads/main.zip"
KEEP_DIRS = {"expansion", "mod_ce"}
CE_BLOCK = """
\t<ce folder="expansion_ce">
\t\t<file name="expansion_types.xml" type="types" />
\t\t<file name="expansion_spawnabletypes.xml" type="spawnabletypes" />
\t\t<file name="expansion_events.xml" type="events" />
\t</ce>

\t<ce folder="mod_ce">
\t\t<file name="loot_boost_types.xml" type="types" />
\t\t<file name="mod_weapons_types.xml" type="types" />
\t\t<file name="mod_weapons_spawnabletypes.xml" type="spawnabletypes" />
\t\t<file name="mod_optics_types.xml" type="types" />
\t</ce>
"""


def _restore_ce_hooks(backup: Path) -> None:
    src_ec = backup / "expansion_ce"
    if src_ec.is_dir() and not (MISSION / "expansion_ce").exists():
        shutil.copytree(src_ec, MISSION / "expansion_ce")
    eco = MISSION / "cfgeconomycore.xml"
    text = eco.read_text(encoding="utf-8")
    if "mod_ce" not in text:
        text = text.replace("</economycore>", CE_BLOCK + "\n</economycore>")
        eco.write_text(text, encoding="utf-8")


def main() -> None:
    if not MISSION.is_dir():
        raise SystemExit(f"Mission folder missing: {MISSION}")

    backup = MISSION.parent / f"{MISSION.name}.backup"
    if backup.exists():
        shutil.rmtree(backup)
    shutil.copytree(MISSION, backup)
    print(f"Backup: {backup}")

    with tempfile.TemporaryDirectory() as tmp:
        zpath = Path(tmp) / "repo.zip"
        print("Downloading official mission...")
        urllib.request.urlretrieve(ZIP_URL, zpath)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(tmp)
        src = Path(tmp) / "DayZ-Projects-main" / "TakistanPlus" / "mission"
        if not src.is_dir():
            raise SystemExit(f"Expected mission folder not in zip: {src}")

        for item in list(MISSION.iterdir()):
            if item.name in KEEP_DIRS:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        for item in src.iterdir():
            dest = MISSION / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

    _restore_ce_hooks(backup)

    print(f"Installed official CE/map files into {MISSION}")
    print("Kept: expansion/, mod_ce/")
    print("Next: restart server; enable @TakistanPlus + @Dabs Framework on client.")


if __name__ == "__main__":
    main()
