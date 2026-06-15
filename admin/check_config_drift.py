#!/usr/bin/env python3
"""Check for drift between map_launch.json, server configs, and start helpers."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CFG_FIELDS = {
    "hostname": re.compile(r'^\s*hostname\s*=\s*"([^"]*)"', re.I | re.M),
    "password": re.compile(r'^\s*password\s*=\s*"([^"]*)"', re.I | re.M),
    "passwordAdmin": re.compile(r'^\s*passwordAdmin\s*=\s*"([^"]*)"', re.I | re.M),
    "shardId": re.compile(r'^\s*shardId\s*=\s*"([^"]*)"', re.I | re.M),
    "instanceId": re.compile(r"^\s*instanceId\s*=\s*(\d+)", re.I | re.M),
    "steamQueryPort": re.compile(r"^\s*steamQueryPort\s*=\s*(\d+)", re.I | re.M),
    "steamPort": re.compile(r"^\s*steamPort\s*=\s*(\d+)", re.I | re.M),
    "template": re.compile(r'^\s*template\s*=\s*"([^"]*)"', re.I | re.M),
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_cfg(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    values: dict[str, str] = {}
    for key, pattern in CFG_FIELDS.items():
        match = pattern.search(text)
        if match:
            values[key] = match.group(1)
    return values


def redacted(values: dict[str, str]) -> dict[str, str]:
    out = dict(values)
    for key in ("password", "passwordAdmin", "shardId"):
        if out.get(key):
            out[key] = "<redacted>" if key != "password" or out[key] else ""
    return out


def expected_start_script(map_name: str) -> Path:
    candidates = [
        ROOT / f"start_{map_name}.cmd",
        ROOT / f"start_{map_name.capitalize()}.cmd",
        ROOT / f"start_{map_name}.bat",
        ROOT / f"start_{map_name.capitalize()}.bat",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def check_helper(map_name: str, errors: list[str], warnings: list[str]) -> None:
    helper = expected_start_script(map_name)
    if not helper.exists():
        errors.append(f"missing start helper: {helper.name}")
        return
    text = helper.read_text(encoding="utf-8-sig", errors="replace")
    if "Launch-DayZMap.ps1" not in text:
        warnings.append(f"{helper.name} does not call Launch-DayZMap.ps1")
        return
    if not re.search(rf"-Map\s+{re.escape(map_name)}\b", text, re.I):
        errors.append(f"{helper.name} does not target -Map {map_name}")


def check_cfg(map_name: str, launch: dict) -> tuple[list[str], list[str], dict[str, str]]:
    errors: list[str] = []
    warnings: list[str] = []
    cfg_path = ROOT / launch["config"]
    if not cfg_path.exists():
        errors.append(f"missing config: {launch['config']}")
        return errors, warnings, {}

    values = parse_cfg(cfg_path)
    q_expected = str(launch.get("steam_query_port", ""))
    steam_expected = str(int(launch["port"]) + 2)
    if values.get("steamQueryPort") != q_expected:
        errors.append(f"{launch['config']} steamQueryPort={values.get('steamQueryPort', 'missing')} expected {q_expected}")
    if values.get("steamPort") != steam_expected:
        errors.append(f"{launch['config']} steamPort={values.get('steamPort', 'missing')} expected {steam_expected}")
    template = values.get("template")
    if not template:
        errors.append(f"{launch['config']} missing mission template")
    elif not (ROOT / "mpmissions" / template).exists():
        errors.append(f"{launch['config']} template folder missing: mpmissions/{template}")
    if values.get("hostname") and launch.get("title") and values["hostname"] != launch["title"].replace("Owens", "My"):
        warnings.append(f"hostname differs from launch title: {values['hostname']!r}")
    if values.get("passwordAdmin") and values["passwordAdmin"] not in {"CHANGE_ME", "CHANGEME", "REPLACE_ME"}:
        warnings.append("passwordAdmin is set locally; output redacted")

    example = ROOT / launch["config"].replace(".cfg", ".example.cfg")
    if not example.exists():
        warnings.append(f"missing public example config: {example.name}")
    else:
        example_values = parse_cfg(example)
        if example_values.get("steamQueryPort") != q_expected:
            errors.append(f"{example.name} steamQueryPort={example_values.get('steamQueryPort', 'missing')} expected {q_expected}")
        if example_values.get("steamPort") != steam_expected:
            errors.append(f"{example.name} steamPort={example_values.get('steamPort', 'missing')} expected {steam_expected}")
        if template and example_values.get("template") != template:
            errors.append(f"{example.name} template={example_values.get('template', 'missing')} expected {template}")

    check_helper(map_name, errors, warnings)
    return errors, warnings, redacted(values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", default="all", help="Map key from admin/map_launch.json, or all.")
    parser.add_argument("--details", action="store_true", help="Print redacted parsed config values.")
    args = parser.parse_args()

    maps = read_json(ROOT / "admin" / "map_launch.json").get("maps", {})
    selected = maps if args.map == "all" else {args.map: maps[args.map]} if args.map in maps else {}
    if not selected:
        print(f"Unknown map: {args.map}")
        return 2

    total_errors = 0
    for map_name, launch in selected.items():
        errors, warnings, values = check_cfg(map_name, launch)
        status = "FAIL" if errors else "WARN" if warnings else "OK"
        print(f"{map_name:9} {status:4} port {launch.get('port')} query {launch.get('steam_query_port')} cfg {launch.get('config')}")
        for err in errors:
            print(f"  error: {err}")
        for warn in warnings:
            print(f"  warn: {warn}")
        if args.details and values:
            details = ", ".join(f"{k}={v}" for k, v in values.items())
            print(f"  cfg: {details}")
        total_errors += len(errors)

    if total_errors:
        print(f"\nConfig drift check FAILED ({total_errors} errors).")
        return 1
    print("\nConfig drift check OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
