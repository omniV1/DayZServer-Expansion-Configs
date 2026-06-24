#!/usr/bin/env python3
"""Generate a DayZ Launcher import preset (HTML) for a map's CLIENT mods.

A client only needs the server's -mod entries (not -serverMod), and exactly one
map/terrain mod. This builds an importable preset with precisely that set, with
each mod's real Workshop id read from its @mod/meta.cpp, so you can import it in
the launcher (Mods -> Preset -> Import) and join without the "missing PBO" /
"too many mods" mess from loading every map at once.

Usage:
  python build_client_preset.py --map deadfall
  python build_client_preset.py --map deadfall --out C:\\Users\\me\\Downloads\\deadfall_preset.html
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
if str(ADMIN) not in sys.path:
    sys.path.insert(0, str(ADMIN))

import control_center as cc

ROOT = cc.ROOT

# Some Workshop mods ship meta.cpp with publishedid = 0 (the author left it
# blank), so the real id can't be read from disk. Map those to their known
# Workshop ids here. Genuinely local/server-only mods are left out so they're
# correctly skipped from client presets.
ID_OVERRIDES = {
    "@Pandemic Weapons-Clothing Camo Overlay": "2008244263",
}


def published_id(mod_folder: str) -> str | None:
    """Steam Workshop id for a mod: an override, else meta.cpp publishedid."""
    if mod_folder in ID_OVERRIDES:
        return ID_OVERRIDES[mod_folder]
    meta = ROOT / mod_folder / "meta.cpp"
    if not meta.exists():
        return None
    text = meta.read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"publishedid\s*=\s*(\d+)", text)
    if not match or match.group(1) == "0":
        # publishedid 0 = a local/server-only mod, not a Workshop item; clients
        # can't import it by id, so it must not appear in a client preset.
        return None
    return match.group(1)


def display_name(mod_folder: str) -> str:
    meta = ROOT / mod_folder / "meta.cpp"
    if meta.exists():
        text = meta.read_text(encoding="utf-8-sig", errors="replace")
        match = re.search(r'name\s*=\s*"([^"]+)"', text)
        if match:
            return match.group(1)
    return mod_folder.lstrip("@")


ROW = """        <tr data-type="ModContainer">
          <td data-type="DisplayName">{name}</td>
          <td>
            <span class="from-steam">Steam</span>
          </td>
          <td>
            <a href="http://steamcommunity.com/sharedfiles/filedetails/?id={id}" data-type="Link">http://steamcommunity.com/sharedfiles/filedetails/?id={id}</a>
          </td>
        </tr>"""

PAGE = """<?xml version="1.0" encoding="utf-8"?>
<html>
  <!--Created by DayZ Server Control Center-->
  <head>
    <meta name="dayz:Type" content="list" />
    <title>DayZ Mods - {map}</title>
  </head>
  <body>
    <h1>DayZ Mods - {map}</h1>
    <p>Import in DayZ Launcher: Mods -&gt; Preset -&gt; Import. {count} mods.</p>
    <div class="mod-list">
      <table>
{rows}
      </table>
    </div>
  </body>
</html>
"""


def build(map_name: str) -> tuple[str, list[str]]:
    cfg = cc.map_configs().get(map_name)
    if not cfg:
        raise SystemExit(f"Unknown map: {map_name}")
    server_mods = set(cfg.get("server_mods") or [])
    client_mods = [m for m in cc.collect_mods_for_map(map_name, cfg) if m not in server_mods]

    rows, missing = [], []
    for mod in client_mods:
        mod_id = published_id(mod)
        if not mod_id:
            missing.append(mod)
            continue
        rows.append(ROW.format(name=display_name(mod), id=mod_id))
    html = PAGE.format(map=map_name, count=len(rows), rows="\n".join(rows))
    return html, missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True)
    parser.add_argument("--out", help="Output HTML path (default: local_runtime/presets/<map>_preset.html).")
    args = parser.parse_args()

    html, missing = build(args.map)
    out = Path(args.out) if args.out else (ROOT / "local_runtime" / "presets" / f"{args.map}_preset.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {args.map} client preset -> {out}")
    if missing:
        print(f"WARNING: no meta.cpp/publishedid for {len(missing)} mod(s): {', '.join(missing)}")
        print("  (these are likely local-only mods; add their Workshop ids manually if needed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
