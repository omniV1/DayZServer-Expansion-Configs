import shutil
from pathlib import Path

SERVER = Path(r"c:\Games\Steam\steamapps\common\DayZServer\mpmissions")
SOURCE = SERVER / "dayzOffline.chernarusplus" / "mod_ce"
CE_BLOCK = (
    '\n\t<ce folder="mod_ce">\n'
    '\t\t<file name="loot_boost_types.xml" type="types" />\n'
    '\t\t<file name="mod_weapons_types.xml" type="types" />\n'
    '\t\t<file name="mod_weapons_spawnabletypes.xml" type="spawnabletypes" />\n'
    "\t</ce>\n"
)

for name in ["dayzOffline.Takistan", "regular.namalsk"]:
    m = SERVER / name
    dest = m / "mod_ce"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SOURCE, dest)
    eco = m / "cfgeconomycore.xml"
    text = eco.read_text(encoding="utf-8")
    if 'folder="mod_ce"' not in text:
        text = text.replace("</economycore>", CE_BLOCK + "</economycore>")
        eco.write_text(text, encoding="utf-8")
        print(f"{name}: economycore patched")
    g = m / "db" / "globals.xml"
    if g.exists():
        t = g.read_text(encoding="utf-8")
        if 'name="ZombieMaxCount" type="0" value="1000"' in t:
            t = t.replace(
                'name="ZombieMaxCount" type="0" value="1000"',
                'name="ZombieMaxCount" type="0" value="1300"',
            )
            g.write_text(t, encoding="utf-8")
            print(f"{name}: globals patched")
    print(f"{name}: mod_ce ready")
