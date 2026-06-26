#!/usr/bin/env python3
"""Scan each map's newest server RPT for loot-spawn health.

Reports, per profile that has an RPT:
  - the LootRespawner init line (Nominal vs map capacity)
  - count of "search overtime" / "hard to place" / "exceeded max tests" warnings

A map with many such warnings is oversaturated for its loot points and should
be added to loot_config "vanilla_loot_maps" then de-tuned:
    python admin/detune_map_loot.py --map <mission>

Usage:  python admin/audit_loot_health.py
"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
INIT_RE = re.compile(r"Nominal:(\d+), Total in Map:\s*(\d+)")
WARN_RE = re.compile(r"search overtime|hard to place|exceeded max tests")


def newest_rpt(profile_dir: Path) -> Path | None:
    rpts = sorted(profile_dir.glob("*.RPT"), key=lambda p: p.stat().st_mtime, reverse=True)
    return rpts[0] if rpts else None


def main() -> int:
    profiles = sorted(SERVER.glob("profiles*"))
    print(f"{'profile':<26}{'RPT date':<13}{'nominal':>8}{'capacity':>9}{'warns':>7}  status")
    print("-" * 78)
    for prof in profiles:
        if not prof.is_dir():
            continue
        rpt = newest_rpt(prof)
        if not rpt:
            print(f"{prof.name:<26}{'(never booted)':<13}")
            continue
        when = datetime.fromtimestamp(rpt.stat().st_mtime).strftime("%m-%d %H:%M")
        text = rpt.read_text(encoding="utf-8", errors="ignore")
        m = INIT_RE.search(text)
        warns = len(WARN_RE.findall(text))
        nominal, cap = (m.group(1), m.group(2)) if m else ("?", "?")
        status = "OK" if warns == 0 else f"{warns} overtime warns -> consider de-tune"
        if not m and warns == 0:
            status = "no loot-init (incomplete boot?)"
        print(f"{prof.name:<26}{when:<13}{nominal:>8}{cap:>9}{warns:>7}  {status}")
    print("\nNote: counts reflect each profile's NEWEST RPT. A stale date = booted")
    print("before the loot declog; re-boot for current numbers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
