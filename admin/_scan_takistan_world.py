from pathlib import Path

addons = Path(r"c:\Games\Steam\steamapps\common\DayZServer\@TakistanPlus\addons")
needles = (
    "worlds\\takistan",
    "worlds/takistan",
    "takistan\\world",
    "takistan/world",
    "cfgworlds",
    "caworld",
    "worldname",
    "takistanplus",
)

for pbo in sorted(addons.glob("*.pbo")):
    t = pbo.read_bytes().decode("latin-1", errors="ignore").lower()
    hits = [n for n in needles if n in t]
    if hits:
        print(f"{pbo.name}: {', '.join(hits)}")
