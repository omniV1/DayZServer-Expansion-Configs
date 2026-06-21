#!/usr/bin/env python3
"""Local browser control center for the DayZ server automation toolkit."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import os
import re
import runpy
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
import zipfile
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse
import xml.etree.ElementTree as ET

FROZEN = bool(getattr(sys, "frozen", False))
APP_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
EXE_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
USER_CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DayZServerControlCenter"
USER_SETTINGS_PATH = USER_CONFIG_DIR / "settings.json"


def resource_path(*parts: str) -> Path:
    bundled = APP_BASE.joinpath(*parts)
    if bundled.exists():
        return bundled
    return Path(__file__).resolve().parent.joinpath(*parts)


ROOT = Path(__file__).resolve().parent.parent
ADMIN = ROOT / "admin"
STATIC = resource_path("control_center")
RUNTIME = ROOT / "local_runtime" / "control_center"
CONFIG_PATH = ADMIN / "control_center_config.json"
LAUNCH_PATH = ADMIN / "map_launch.json"
AI_CONFIG_PATH = ADMIN / "ai_config.json"
LOOT_CONFIG_PATH = ADMIN / "loot_config.json"

APP_VERSION = "1.7.0"
RELEASE_CHANNEL = "stable"
REPO_URL = "https://github.com/omniV1/DayZServer-Expansion-Configs"
RELEASES_URL = f"{REPO_URL}/releases"
LATEST_RELEASE_URL = f"{REPO_URL}/releases/latest"

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
MAX_OUTPUT_CHARS = 240_000

FATAL_PATTERNS = [
    re.compile(r"ENGINE\s+\(F\):\s+Crashed|Exception code:|Minidump has been generated", re.I),
    re.compile(r"\btermination in:|\[ERROR\]\[Server config\]|server config.*invalid", re.I),
    re.compile(r"NO VALID SPAWNS|no valid regular player spawn points", re.I),
    re.compile(r"cannot open file|cannot load file|missing .*pbo|file .* not found", re.I),
    re.compile(r"bind failed|address already in use|steamgameserver_init.*failed|port .* already", re.I),
    re.compile(r"\bSCRIPT\s+ERROR\b|\bNULL pointer\b|\bClass .* not found\b", re.I),
]

REDACTIONS = [
    (re.compile(r"(passwordAdmin\s*=\s*\")[^\"]*(\")", re.I), r"\1<redacted>\2"),
    (re.compile(r"(password\s*=\s*\")[^\"]*(\")", re.I), r"\1<redacted>\2"),
    (re.compile(r"(RConPassword\s+)\S+", re.I), r"\1<redacted>"),
    (re.compile(r"\b7656\d{13,}\b"), "<steamid>"),
    (re.compile(r"\bgho_[A-Za-z0-9_]+\b"), "<token>"),
]


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def app_log_path() -> Path:
    return USER_CONFIG_DIR / "control_center.log"


def log_message(message: str) -> None:
    timestamp = dt.datetime.now().isoformat(timespec="seconds")
    try:
        USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with app_log_path().open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except OSError:
        pass


def safe_print(message: str) -> None:
    log_message(message)
    if sys.stdout is not None:
        print(message)


def is_server_root(path: Path) -> bool:
    return (path / "admin" / "map_launch.json").exists() and (path / "Launch-DayZMap.ps1").exists()


def set_server_root(path: Path) -> None:
    global ROOT, ADMIN, RUNTIME, CONFIG_PATH, LAUNCH_PATH, AI_CONFIG_PATH, LOOT_CONFIG_PATH
    resolved = path.resolve()
    if not is_server_root(resolved):
        raise ValueError(f"Not a DayZServer config root: {resolved}")
    ROOT = resolved
    ADMIN = ROOT / "admin"
    RUNTIME = ROOT / "local_runtime" / "control_center"
    CONFIG_PATH = ADMIN / "control_center_config.json"
    LAUNCH_PATH = ADMIN / "map_launch.json"
    AI_CONFIG_PATH = ADMIN / "ai_config.json"
    LOOT_CONFIG_PATH = ADMIN / "loot_config.json"


def read_user_settings() -> dict[str, Any]:
    return read_json(USER_SETTINGS_PATH, {})


def save_user_settings(values: dict[str, Any]) -> None:
    current = read_user_settings()
    current.update(values)
    write_json(USER_SETTINGS_PATH, current)


def parent_candidates(path: Path) -> list[Path]:
    candidates = [path]
    candidates.extend(path.parents)
    return candidates


def common_server_roots() -> list[Path]:
    roots = [
        Path(r"C:\Games\Steam\steamapps\common\DayZServer"),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam" / "steamapps" / "common" / "DayZServer",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Steam" / "steamapps" / "common" / "DayZServer",
    ]
    for drive in "DEFG":
        roots.extend(
            [
                Path(f"{drive}:\\SteamLibrary\\steamapps\\common\\DayZServer"),
                Path(f"{drive}:\\Games\\Steam\\steamapps\\common\\DayZServer"),
            ]
        )
    return roots


def detect_server_root(cli_root: str | None) -> Path | None:
    settings = read_user_settings()
    candidates: list[Path] = []
    for value in (
        cli_root,
        os.environ.get("DAYZ_SERVER_ROOT"),
        settings.get("server_root"),
    ):
        if value:
            candidates.append(Path(str(value)).expanduser())
    candidates.extend(parent_candidates(Path.cwd()))
    candidates.extend(parent_candidates(EXE_DIR))
    if not FROZEN:
        candidates.extend(parent_candidates(Path(__file__).resolve().parent))
    candidates.extend(common_server_roots())

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if is_server_root(resolved):
            return resolved
    return None


def pick_server_root_dialog() -> Path | None:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "Welcome to DayZ Server Control Center",
            "First, point the app at your DayZServer folder.\n\n"
            "This is the folder that contains DayZServer_x64.exe. It must also include:\n"
            "  - admin\\map_launch.json\n"
            "  - Launch-DayZMap.ps1\n\n"
            "A typical path looks like:\n"
            "  C:\\Games\\Steam\\steamapps\\common\\DayZServer\n\n"
            "Click OK, then select that folder. Nothing is changed until you choose an action.",
        )
        selected = filedialog.askdirectory(title="Select your DayZServer folder")
        root.destroy()
        if selected:
            path = Path(selected)
            if is_server_root(path):
                return path
            messagebox.showerror(
                "That folder is not a DayZServer root",
                "The selected folder is missing admin\\map_launch.json or Launch-DayZMap.ps1.\n\n"
                "Pick the folder that contains DayZServer_x64.exe and try again.",
            )
    except Exception:
        return None
    return None


def configure_server_root(cli_root: str | None) -> bool:
    root = detect_server_root(cli_root)
    if root is None:
        root = pick_server_root_dialog()
    if root is None:
        safe_print("Could not find DayZServer root. Rerun with --server-root C:\\Path\\To\\DayZServer.")
        return False
    set_server_root(root)
    save_user_settings({"server_root": str(ROOT)})
    return True


def load_config() -> dict[str, Any]:
    defaults = {
        "version": 1,
        "host": "127.0.0.1",
        "port": 8765,
        "allow_remote_bind": False,
        "snapshot_before_mutation": True,
        "job_retention": 50,
        "max_log_lines": 400,
    }
    data = read_json(CONFIG_PATH, {})
    defaults.update(data)
    return defaults


def load_launch() -> dict[str, Any]:
    return read_json(LAUNCH_PATH, {"maps": {}})


def map_configs() -> dict[str, dict[str, Any]]:
    return load_launch().get("maps", {})


def imported_maps() -> set[str]:
    data = read_json(AI_CONFIG_PATH, {})
    values = data.get("imported_expansion_maps", [])
    return {str(value) for value in values}


def redact(text: str) -> str:
    out = text
    for pattern, replacement in REDACTIONS:
        out = pattern.sub(replacement, out)
    return out


def tail_file(path: Path, limit: int) -> list[str]:
    lines: deque[str] = deque(maxlen=limit)
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            lines.append(redact(line.rstrip("\r\n")))
    return list(lines)


def newest_log(profile_dir: Path) -> Path | None:
    if not profile_dir.exists():
        return None
    candidates: list[Path] = []
    for pattern in ("*.RPT", "*.log", "*.adm"):
        candidates.extend(path for path in profile_dir.rglob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def safe_rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def parse_cfg_value(text: str, name: str) -> str:
    match = re.search(rf'(?im)^\s*{re.escape(name)}\s*=\s*"?([^";\r\n]+)', text)
    return match.group(1).strip() if match else ""


def read_cfg_public_values(config_name: str) -> dict[str, str]:
    path = ROOT / config_name
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return {
        "template": parse_cfg_value(text, "template"),
        "steamQueryPort": parse_cfg_value(text, "steamQueryPort"),
        "steamPort": parse_cfg_value(text, "steamPort"),
        "hostname": parse_cfg_value(text, "hostname"),
    }


def collect_mods_for_map(name: str, cfg: dict[str, Any]) -> list[str]:
    launch = load_launch()
    mods_file = cfg.get("mods_file") or launch.get("mods_file") or "chernarus_mods.txt"
    mods_path = ADMIN / mods_file
    raw = mods_path.read_text(encoding="utf-8-sig", errors="replace") if mods_path.exists() else ""
    parts: list[str] = []
    for item in cfg.get("prepend_mods") or []:
        if str(item).strip():
            parts.append(str(item).strip())
    for item in raw.split(";"):
        if item.strip():
            parts.append(item.strip())
    for item in cfg.get("extra_mods") or []:
        if str(item).strip():
            parts.append(str(item).strip())
    for item in cfg.get("server_mods") or []:
        if str(item).strip():
            parts.append(str(item).strip())
    seen: set[str] = set()
    ordered: list[str] = []
    for item in parts:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def netstat_udp_ports() -> dict[int, set[int]]:
    try:
        proc = subprocess.run(
            ["netstat", "-ano", "-p", "UDP"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        return {}
    ports: dict[int, set[int]] = {}
    for line in proc.stdout.splitlines():
        if "UDP" not in line:
            continue
        match = re.search(r"\sUDP\s+\S+:(\d+)\s+\S+\s+(\d+)\s*$", line, re.I)
        if not match:
            continue
        port = int(match.group(1))
        pid = int(match.group(2))
        ports.setdefault(port, set()).add(pid)
    return ports


def dayz_process_count() -> int:
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-Process DayZServer_x64 -ErrorAction SilentlyContinue | Measure-Object).Count",
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        return 0
    try:
        return int(proc.stdout.strip() or "0")
    except ValueError:
        return 0


def running_server_game_ports() -> set[int]:
    """Game ports of running DayZServer_x64 processes, read from their -port= command line.

    This sees a server the instant it starts (before UDP ports bind), unlike netstat.
    """
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='DayZServer_x64.exe'\" | "
                "ForEach-Object { $_.CommandLine }",
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=15,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        return set()
    return {int(match.group(1)) for match in re.finditer(r"-port=(\d+)", proc.stdout or "")}


# Adapters that are NOT your real LAN. If one of these outranks the physical NIC
# (lower interface metric), Steam's LAN server browser broadcasts on it instead of
# the LAN, so servers answer A2S but never appear in the DayZ launcher LAN tab.
VIRTUAL_ADAPTER_KEYWORDS = (
    "tailscale", "vethernet", "hyper-v", "hyper v", "default switch", "wireguard",
    "wg", "vpn", "zerotier", "hamachi", "wsl", "virtualbox", "vmware", "nordvpn",
    "proton", "mullvad", "openvpn", "expressvpn", "tunnel", "tun", "tap", "brave",
    "radmin", "loopback",
)


def is_private_lan_ip(ip: str | None) -> bool:
    if not ip:
        return False
    return (
        ip.startswith("192.168.")
        or ip.startswith("10.")
        or bool(re.match(r"172\.(1[6-9]|2\d|3[01])\.", ip))
    )


def is_virtual_adapter(alias: str | None) -> bool:
    if not alias:
        return False
    low = alias.lower()
    return any(keyword in low for keyword in VIRTUAL_ADAPTER_KEYWORDS)


def network_adapters() -> list[dict[str, Any]]:
    """Connected IPv4 adapters with alias, interface metric, IP, and default-route flag."""
    script = (
        "$def = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue)."
        "InterfaceIndex; "
        "$addrs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue; "
        "$out = foreach ($i in (Get-NetIPInterface -AddressFamily IPv4 -ErrorAction SilentlyContinue "
        "| Where-Object { $_.ConnectionState -eq 'Connected' })) { "
        "$ip = ($addrs | Where-Object { $_.InterfaceIndex -eq $i.ifIndex } | "
        "Select-Object -First 1 -ExpandProperty IPAddress); "
        "[pscustomobject]@{ alias = $i.InterfaceAlias; metric = [int]$i.InterfaceMetric; "
        "ip = $ip; defaultRoute = ($def -contains $i.ifIndex) } }; "
        "@($out) | ConvertTo-Json -Compress -Depth 3"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=20,
            creationflags=CREATE_NO_WINDOW,
        )
        data = json.loads((proc.stdout or "").strip() or "[]")
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    return [a for a in data if isinstance(a, dict)]


def lan_visibility_payload() -> dict[str, Any]:
    """Detect a VPN/virtual adapter outranking the real LAN NIC, which hides servers
    from the DayZ launcher LAN tab even though they answer A2S fine."""
    adapters = network_adapters()
    if not adapters:
        return {
            "status": "unknown",
            "message": "Could not read network adapters on this machine.",
            "adapters": [],
            "blockingAdapters": [],
            "lanAdapter": None,
        }
    lan_candidates = [
        a for a in adapters
        if is_private_lan_ip(a.get("ip")) and not is_virtual_adapter(a.get("alias"))
    ]
    lan_adapter = min(lan_candidates, key=lambda a: a.get("metric", 9999)) if lan_candidates else None
    blocking: list[dict[str, Any]] = []
    if lan_adapter is not None:
        lan_metric = lan_adapter.get("metric", 9999)
        for a in adapters:
            if is_virtual_adapter(a.get("alias")) and a.get("metric", 9999) <= lan_metric:
                blocking.append(a)
    if lan_adapter is None:
        message = (
            "No physical LAN adapter with a private IP was found. If you only use Wi-Fi or a VPN, "
            "the launcher LAN tab may not work; connect the real network adapter."
        )
        status = "unknown"
    elif blocking:
        names = ", ".join(f"{a['alias']} (metric {a.get('metric', '?')})" for a in blocking)
        status = "warning"
        message = (
            f"A VPN/virtual adapter outranks your LAN adapter '{lan_adapter['alias']}' "
            f"(metric {lan_adapter.get('metric', '?')}): {names}. Steam broadcasts LAN discovery on the "
            "lower-metric adapter, so your servers answer direct queries but never appear in the DayZ "
            "launcher LAN tab. Make the LAN adapter preferred, or disable the VPN while playing LAN."
        )
    else:
        status = "ok"
        message = (
            f"Your LAN adapter '{lan_adapter['alias']}' (metric {lan_adapter.get('metric', '?')}) is "
            "preferred over any VPN/virtual adapter. The launcher LAN tab should see local servers."
        )
    fix = None
    fix_revert = None
    if lan_adapter is not None and blocking:
        fix = f"Set-NetIPInterface -InterfaceAlias '{lan_adapter['alias']}' -InterfaceMetric 1"
        fix_revert = f"Set-NetIPInterface -InterfaceAlias '{lan_adapter['alias']}' -AutomaticMetric Enabled"
    return {
        "status": status,
        "message": message,
        "adapters": adapters,
        "blockingAdapters": blocking,
        "lanAdapter": lan_adapter,
        "fix": fix,
        "fixRevert": fix_revert,
        "fixNote": (
            "Run the fix in an Administrator PowerShell, then reset the launcher browser cache "
            "(admin\\reset_dayz_launcher_browser.ps1 -StopLauncher -OpenLauncher) and re-check the LAN tab."
        ),
    }


def log_status(profile_dir: str, max_lines: int = 800) -> dict[str, Any]:
    log = newest_log(ROOT / profile_dir)
    if not log:
        return {"file": None, "ready": False, "blockers": 0, "updated": None}
    lines = tail_file(log, max_lines)
    ready = any("Player connect enabled" in line for line in lines)
    blockers = sum(1 for line in lines if any(pattern.search(line) for pattern in FATAL_PATTERNS))
    stat = log.stat()
    return {
        "file": safe_rel(log),
        "ready": ready,
        "blockers": blockers,
        "updated": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def maps_payload() -> list[dict[str, Any]]:
    maps = map_configs()
    imported = imported_maps()
    result: list[dict[str, Any]] = []
    for name, cfg in maps.items():
        cfg_values = read_cfg_public_values(str(cfg.get("config", "")))
        mission = cfg_values.get("template") or ""
        mods = collect_mods_for_map(name, cfg)
        missing_mods = [mod for mod in mods if not (ROOT / mod).exists()]
        result.append(
            {
                "key": name,
                "title": cfg.get("title", name),
                "config": cfg.get("config"),
                "configExists": (ROOT / str(cfg.get("config", ""))).exists(),
                "port": cfg.get("port"),
                "queryPort": cfg.get("steam_query_port"),
                "steamPort": int(cfg.get("port", 0) or 0) + 2,
                "profilesDir": cfg.get("profiles_dir") or f"profiles_{name}",
                "mission": mission,
                "missionExists": bool(mission) and (ROOT / "mpmissions" / mission).exists(),
                "modCount": len(mods),
                "missingMods": missing_mods,
                "isImported": name in imported,
                "cpu": cfg.get("cpu"),
                "extraMods": cfg.get("extra_mods") or [],
                "serverMods": cfg.get("server_mods") or [],
            }
        )
    return result


def status_payload() -> dict[str, Any]:
    udp = netstat_udp_ports()
    process_count = dayz_process_count()
    maps = []
    for item in maps_payload():
        port = int(item["port"] or 0)
        query = int(item["queryPort"] or 0)
        steam = int(item["steamPort"] or 0)
        maps.append(
            {
                "key": item["key"],
                "title": item["title"],
                "gameActive": port in udp,
                "queryActive": query in udp,
                "steamActive": steam in udp,
                "pids": sorted(set().union(udp.get(port, set()), udp.get(query, set()), udp.get(steam, set()))),
                "log": log_status(item["profilesDir"]),
            }
        )
    return {
        "root": str(ROOT),
        "processCount": process_count,
        "generatedAt": dt.datetime.now().isoformat(timespec="seconds"),
        "maps": maps,
    }


def mission_for_map(map_name: str) -> str:
    maps = map_configs()
    if map_name not in maps:
        raise ValueError(f"Unknown map: {map_name}")
    values = read_cfg_public_values(str(maps[map_name].get("config", "")))
    mission = values.get("template") or ""
    if not mission:
        raise ValueError(f"Map has no mission template in config: {map_name}")
    return mission


def mission_dir_for_map(map_name: str) -> Path:
    mission = mission_for_map(map_name)
    path = ROOT / "mpmissions" / mission
    if not path.exists():
        raise ValueError(f"Mission folder missing for {map_name}: {mission}")
    return path


def clamp_number(value: Any, name: str, min_value: float, max_value: float, integer: bool = False) -> int | float:
    try:
        number = int(value) if integer else float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if number < min_value or number > max_value:
        raise ValueError(f"{name} must be between {min_value:g} and {max_value:g}.")
    return number


def selected_balance_maps(value: Any) -> list[str]:
    maps = map_configs()
    if value in (None, "", "all"):
        return list(maps)
    if isinstance(value, str):
        names = [value.lower()]
    elif isinstance(value, list):
        names = [str(item).lower() for item in value]
    else:
        raise ValueError("maps must be 'all', one map, or a list of maps.")
    unknown = [name for name in names if name not in maps]
    if unknown:
        raise ValueError(f"Unknown map(s): {', '.join(unknown)}")
    return names


def get_cap(settings: dict[str, Any], category: str) -> int | None:
    entries = settings.get("LoadBalancingCategories", {}).get(category, [])
    if not entries:
        return None
    value = entries[0].get("MaxPatrols")
    return int(value) if isinstance(value, int) else None


def set_cap(settings: dict[str, Any], category: str, value: int) -> bool:
    changed = False
    entries = settings.setdefault("LoadBalancingCategories", {}).setdefault(category, [])
    if not entries:
        entries.append({"MinPlayers": 0, "MaxPlayers": 255, "MaxPatrols": value})
        return True
    for entry in entries:
        if entry.get("MaxPatrols") != value:
            entry["MaxPatrols"] = value
            changed = True
    return changed


def read_globals(mission_dir: Path) -> dict[str, int]:
    path = mission_dir / "db" / "globals.xml"
    values: dict[str, int] = {}
    if not path.exists():
        return values
    root = ET.parse(path).getroot()
    for var in root.findall("var"):
        name = var.get("name")
        value = var.get("value")
        if name in {"ZombieMaxCount", "AnimalMaxCount", "SpawnInitial", "InitialSpawn", "RespawnLimit", "RespawnTypes"}:
            try:
                values[name] = int(value or "0")
            except ValueError:
                values[name] = 0
    return values


def write_globals(mission_dir: Path, values: dict[str, int]) -> list[str]:
    path = mission_dir / "db" / "globals.xml"
    if not path.exists():
        raise ValueError(f"Missing globals file: {safe_rel(path)}")
    tree = ET.parse(path)
    root = tree.getroot()
    changed: list[str] = []
    for var in root.findall("var"):
        name = var.get("name")
        if name in values:
            new_value = str(values[name])
            if var.get("value") != new_value:
                var.set("value", new_value)
                changed.append(name)
    if changed:
        ET.indent(tree, space="    ")
        tree.write(path, encoding="UTF-8", xml_declaration=True)
    return changed


def ai_summary(mission_dir: Path) -> dict[str, Any]:
    path = mission_dir / "expansion" / "settings" / "AIPatrolSettings.json"
    if not path.exists():
        return {"exists": False}
    data = read_json(path, {})
    patrols = data.get("Patrols", [])
    min_values = sorted({p.get("NumberOfAI") for p in patrols if isinstance(p.get("NumberOfAI"), int)})
    max_values = sorted({p.get("NumberOfAIMax") for p in patrols if isinstance(p.get("NumberOfAIMax"), int)})
    return {
        "exists": True,
        "patrols": len(patrols),
        "enabled": data.get("Enabled"),
        "patrolMax": get_cap(data, "Patrol"),
        "globalMax": get_cap(data, "Global"),
        "objectPatrolMax": get_cap(data, "ObjectPatrol"),
        "heliPatrolMax": get_cap(data, "HelicopterWreck"),
        "accuracyMin": data.get("AccuracyMin"),
        "accuracyMax": data.get("AccuracyMax"),
        "damageMultiplier": data.get("DamageMultiplier"),
        "minAI": min_values[0] if len(min_values) == 1 else None,
        "maxAI": max_values[0] if len(max_values) == 1 else None,
        "minAIValues": min_values,
        "maxAIValues": max_values,
    }


def write_ai_settings(mission_dir: Path, values: dict[str, Any]) -> list[str]:
    path = mission_dir / "expansion" / "settings" / "AIPatrolSettings.json"
    if not path.exists():
        raise ValueError(f"Missing AI patrol settings: {safe_rel(path)}")
    data = read_json(path, {})
    changed: list[str] = []

    cap_fields = {
        "patrolMax": "Patrol",
        "globalMax": "Global",
        "objectPatrolMax": "ObjectPatrol",
        "heliPatrolMax": "HelicopterWreck",
    }
    for field, category in cap_fields.items():
        if field in values:
            value = int(clamp_number(values[field], field, -1, 200, integer=True))
            if set_cap(data, category, value):
                changed.append(field)

    numeric_fields = {
        "accuracyMin": (0.0, 1.0),
        "accuracyMax": (0.0, 1.0),
        "damageMultiplier": (0.1, 5.0),
    }
    for field, (low, high) in numeric_fields.items():
        if field in values:
            value = clamp_number(values[field], field, low, high)
            if data.get(field) != value:
                data[field] = value
                changed.append(field)

    patrol_numeric_fields = {
        "minAI": ("NumberOfAI", 0, 20),
        "maxAI": ("NumberOfAIMax", 0, 20),
        "accuracyMin": ("AccuracyMin", 0.0, 1.0),
        "accuracyMax": ("AccuracyMax", 0.0, 1.0),
        "damageMultiplier": ("DamageMultiplier", 0.1, 5.0),
    }
    if "minAI" in values and "maxAI" in values and int(values["minAI"]) > int(values["maxAI"]):
        raise ValueError("minAI cannot be greater than maxAI.")
    for patrol in data.get("Patrols", []):
        for field, spec in patrol_numeric_fields.items():
            if field not in values:
                continue
            target, low, high = spec
            integer = field in {"minAI", "maxAI"}
            value = clamp_number(values[field], field, low, high, integer=integer)
            if patrol.get(target) != value:
                patrol[target] = value
                if field not in changed:
                    changed.append(field)
        if patrol.get("UnlimitedReload") != 1:
            patrol["UnlimitedReload"] = 1
            if "UnlimitedReload" not in changed:
                changed.append("UnlimitedReload")

    if changed:
        write_json(path, data)
    return changed


def balance_payload() -> dict[str, Any]:
    loot = read_json(LOOT_CONFIG_PATH, {})
    maps = []
    for map_info in maps_payload():
        mission_dir = ROOT / "mpmissions" / map_info["mission"] if map_info.get("mission") else None
        maps.append(
            {
                "key": map_info["key"],
                "title": map_info["title"],
                "mission": map_info["mission"],
                "loot": read_globals(mission_dir) if mission_dir and mission_dir.exists() else {},
                "ai": ai_summary(mission_dir) if mission_dir and mission_dir.exists() else {"exists": False},
            }
        )
    return {
        "loot": {
            "activePreset": loot.get("active_preset"),
            "presets": loot.get("presets", {}),
        },
        "maps": maps,
    }


def app_payload() -> dict[str, Any]:
    return {
        "version": APP_VERSION,
        "channel": RELEASE_CHANNEL,
        "root": str(ROOT),
        "host": CONFIG.get("host", "127.0.0.1"),
        "port": int(CONFIG.get("port", 8765) or 8765),
        "frozen": FROZEN,
        "runtimeDir": safe_rel(RUNTIME),
        "userConfigDir": str(USER_CONFIG_DIR),
        "snapshotBeforeMutation": bool(CONFIG.get("snapshot_before_mutation", True)),
        "repoUrl": REPO_URL,
        "releasesUrl": RELEASES_URL,
        "latestReleaseUrl": LATEST_RELEASE_URL,
    }


def recent_blockers(profile_dir: str, max_lines: int = 800, limit: int = 6) -> list[str]:
    log = newest_log(ROOT / profile_dir)
    if not log:
        return []
    lines = tail_file(log, max_lines)  # already redacted line-by-line
    hits = [line for line in lines if any(pattern.search(line) for pattern in FATAL_PATTERNS)]
    return hits[-limit:]


def report_payload(map_filter: str | None) -> dict[str, Any]:
    maps = map_configs()
    if map_filter in (None, "", "all"):
        selected = list(maps)
        scope = "all"
    else:
        name = str(map_filter).lower()
        if name not in maps:
            raise ValueError(f"Unknown map: {name}")
        selected = [name]
        scope = name

    status = status_payload()
    status_by_key = {item["key"]: item for item in status["maps"]}
    maps_info = {item["key"]: item for item in maps_payload()}
    generated_at = dt.datetime.now().isoformat(timespec="seconds")

    lines: list[str] = [
        "DayZ Server Control Center - Support Report",
        f"Generated: {generated_at}",
        f"App version: {APP_VERSION} ({RELEASE_CHANNEL})",
        f"Server root: {ROOT}",
        f"Scope: {scope}",
        f"DayZ server processes running: {status['processCount']}",
        "",
        "This report is public-safe: passwords, Steam IDs, and tokens are redacted, and no",
        "player, storage, or profile contents are included.",
        "",
    ]

    for name in selected:
        info = maps_info.get(name, {})
        state = status_by_key.get(name, {})
        log = state.get("log") or {}
        lines.append(f"== {info.get('title', name)} ({name}) ==")
        lines.append(
            f"  Config: {info.get('config')} "
            f"[{'present' if info.get('configExists') else 'MISSING'}]"
        )
        lines.append(
            f"  Mission: {info.get('mission') or '(none)'} "
            f"[{'present' if info.get('missionExists') else 'MISSING'}]"
        )
        lines.append(
            f"  Ports: game {info.get('port')} ({'active' if state.get('gameActive') else 'idle'}), "
            f"query {info.get('queryPort')} ({'active' if state.get('queryActive') else 'idle'}), "
            f"steam {info.get('steamPort')} ({'active' if state.get('steamActive') else 'idle'})"
        )
        lines.append(f"  Profiles dir: {info.get('profilesDir')}")
        missing = info.get("missingMods") or []
        lines.append(f"  Mods: {info.get('modCount')} listed; {len(missing)} missing")
        for mod in missing:
            lines.append(f"    - MISSING {mod}")
        lines.append(f"  Imported map: {'yes' if info.get('isImported') else 'no'}")
        if log.get("file"):
            lines.append(f"  Latest log: {log.get('file')} (updated {log.get('updated')})")
            lines.append(
                f"    Ready state reached: {'yes' if log.get('ready') else 'no'}; "
                f"blockers detected: {log.get('blockers')}"
            )
            for blocker in recent_blockers(info.get("profilesDir") or f"profiles_{name}"):
                lines.append(f"      ! {blocker}")
        else:
            lines.append("  Latest log: none found")
        lines.append("")

    text = redact("\n".join(lines).rstrip() + "\n")
    return {"scope": scope, "generatedAt": generated_at, "maps": selected, "text": text}


def backup_dir() -> Path:
    return ADMIN / "backups"


def parse_snapshot_name(name: str) -> dict[str, Any]:
    base = name[:-4] if name.lower().endswith(".zip") else name
    match = re.match(r"^(\d{8})-(\d{6})(?:-(.*))?$", base)
    if not match:
        return {"label": base or "config", "created": None}
    date, clock, label = match.group(1), match.group(2), match.group(3)
    created = f"{date[0:4]}-{date[4:6]}-{date[6:8]}T{clock[0:2]}:{clock[2:4]}:{clock[4:6]}"
    return {"label": label or "config", "created": created}


def snapshots_payload() -> dict[str, Any]:
    directory = backup_dir()
    snapshots: list[dict[str, Any]] = []
    if directory.exists():
        for path in sorted(directory.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = path.stat()
            meta = parse_snapshot_name(path.name)
            files: int | None = None
            try:
                with zipfile.ZipFile(path) as handle:
                    files = sum(1 for entry in handle.namelist() if entry != "SNAPSHOT.txt")
            except (OSError, zipfile.BadZipFile):
                files = None
            snapshots.append(
                {
                    "name": path.name,
                    "label": meta["label"],
                    "created": meta["created"],
                    "modified": dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sizeKb": round(stat.st_size / 1024, 1),
                    "files": files,
                }
            )
    return {"dir": safe_rel(directory), "count": len(snapshots), "snapshots": snapshots}


def validate_snapshot_name(payload: dict[str, Any]) -> Path:
    name = str(payload.get("snapshot") or "").strip()
    if not name:
        raise ValueError("This action requires a snapshot name.")
    if name != Path(name).name or not name.lower().endswith(".zip"):
        raise ValueError("Invalid snapshot name.")
    directory = backup_dir().resolve()
    target = (directory / name).resolve()
    if not str(target).startswith(str(directory)) or not target.exists():
        raise ValueError(f"Snapshot not found: {name}")
    return target


BE_CONFIG_NAME = "BEServer_x64.cfg"


def rcon_map(payload_or_name: Any) -> str:
    name = (payload_or_name.get("map") if isinstance(payload_or_name, dict) else payload_or_name) or ""
    name = str(name).lower()
    if name not in map_configs():
        raise ValueError(f"Unknown map: {name}")
    return name


def map_profile_dir(map_name: str) -> Path:
    cfg = map_configs()[map_name]
    return ROOT / (cfg.get("profiles_dir") or f"profiles_{map_name}")


def default_rcon_port(map_name: str) -> int:
    # game/steam/query ports never use gamePort+4, and maps are spaced 100 apart, so this
    # stays unique per map and lets several servers expose RCon at once.
    return int(map_configs()[map_name].get("port", 2302) or 2302) + 4


def be_config_path(map_name: str) -> Path:
    # DayZ resolves -BEpath relative to the profile, so BattlEye reads its config from
    # <profile>/BattlEye/battleye/BEServer_x64.cfg (verified against the active config it writes).
    return map_profile_dir(map_name) / "BattlEye" / "battleye" / BE_CONFIG_NAME


def read_rcon_config(map_name: str) -> dict[str, Any]:
    folder = be_config_path(map_name).parent
    # The master BEServer_x64.cfg is what we write; once a server boots, BattlEye consumes
    # it and keeps the live values in BEServer_x64_active_<hash>.cfg, so check both.
    candidates: list[Path] = []
    master = folder / BE_CONFIG_NAME
    if master.exists():
        candidates.append(master)
    candidates.extend(
        sorted(folder.glob("BEServer_x64_active_*.cfg"), key=lambda p: p.stat().st_mtime, reverse=True)
    )
    for path in candidates:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        pass_match = re.search(r"(?im)^\s*RConPassword\s+(\S+)", text)
        if not pass_match:
            continue
        port_match = re.search(r"(?im)^\s*RConPort\s+(\d+)", text)
        return {
            "configured": True,
            "port": int(port_match.group(1)) if port_match else default_rcon_port(map_name),
            "password": pass_match.group(1),
        }
    return {"configured": False, "port": default_rcon_port(map_name), "password": None}


def map_server_running(map_name: str) -> bool:
    ports = netstat_udp_ports()
    game = int(map_configs()[map_name].get("port", 0) or 0)
    return game in ports


def rcon_status_payload(map_name: str) -> dict[str, Any]:
    cfg = read_rcon_config(map_name)
    return {
        "map": map_name,
        "configured": cfg["configured"],
        "port": cfg["port"],
        "configPath": safe_rel(be_config_path(map_name)),
        "running": map_server_running(map_name),
        "commands": ["players", "kick", "ban", "say"],
        "note": (
            "Enable RCon, then start or restart this map so BattlEye loads the config. "
            "RCon takes ~20-30s after the server boots before it answers."
        ),
    }


def enable_rcon(payload: dict[str, Any]) -> dict[str, Any]:
    map_name = rcon_map(payload)
    cfg = read_rcon_config(map_name)
    try:
        port = int(payload.get("port") or cfg["port"])
    except (TypeError, ValueError) as exc:
        raise ValueError("RCon port must be a number.") from exc
    if not (1024 <= port <= 65535):
        raise ValueError("RCon port must be between 1024 and 65535.")
    regenerate = bool(payload.get("regenerate"))
    password = cfg["password"] if (cfg["password"] and not regenerate) else secrets.token_hex(12)
    path = be_config_path(map_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"RConPassword {password}\nRConPort {port}\nRestrictRCon 0\nMaxPing 350\n",
        encoding="utf-8",
    )
    return {
        "enabled": True,
        "map": map_name,
        "port": port,
        "regenerated": regenerate or not cfg["password"],
        "message": (
            f"RCon enabled for {map_name} on port {port}. Restart this map so BattlEye reloads "
            "the config. The password is stored only in the ignored profile BattlEye folder."
        ),
        "status": rcon_status_payload(map_name),
    }


def rcon_send(port: int, password: str, command: str, timeout: float = 6.0) -> str:
    import importlib.util

    spec = importlib.util.spec_from_file_location("rcon_client", ADMIN / "rcon_client.py")
    if spec is None or spec.loader is None:
        raise ValueError("Missing admin/rcon_client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.send_command("127.0.0.1", port, password, command, timeout)
    except module.RConError as exc:
        raise ValueError(str(exc)) from exc


def sanitize_rcon_text(value: Any, limit: int = 200) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text[:limit]


def run_rcon(payload: dict[str, Any]) -> dict[str, Any]:
    map_name = rcon_map(payload)
    cfg = read_rcon_config(map_name)
    if not cfg["configured"]:
        raise ValueError("RCon is not enabled for this map yet. Use Enable RCon first.")
    command = str(payload.get("command") or "").lower()
    if command == "players":
        rcon_cmd = "players"
    elif command == "kick":
        player = int(clamp_number(payload.get("id"), "id", 0, 1000, integer=True))
        reason = sanitize_rcon_text(payload.get("reason") or "Kicked by admin")
        rcon_cmd = f"kick {player} {reason}".strip()
    elif command == "ban":
        player = int(clamp_number(payload.get("id"), "id", 0, 1000, integer=True))
        minutes = int(clamp_number(payload.get("minutes", 0), "minutes", 0, 525600, integer=True))
        reason = sanitize_rcon_text(payload.get("reason") or "Banned by admin")
        rcon_cmd = f"ban {player} {minutes} {reason}".strip()
    elif command == "say":
        message = sanitize_rcon_text(payload.get("message"))
        if not message:
            raise ValueError("A broadcast message is required.")
        rcon_cmd = f"say -1 {message}"
    else:
        raise ValueError(f"Unknown RCon command: {command}")
    output = rcon_send(int(cfg["port"]), str(cfg["password"]), rcon_cmd)
    return {"command": command, "output": redact(output) or "(no output)", "status": rcon_status_payload(map_name)}


SCHEDULE_WARNINGS_MAX = 8
SCHEDULE_INTERVAL_MIN_HOURS = 0.05  # ~3 minutes, mostly for testing
SCHEDULE_INTERVAL_MAX_HOURS = 24


def schedule_due_actions(schedule: dict[str, Any], now_ts: float) -> list[dict[str, Any]]:
    """Pure decision: given a schedule and the current time, what should fire now."""
    if not schedule.get("enabled"):
        return []
    next_ts = schedule.get("nextRestart")
    if not next_ts:
        return []
    if now_ts >= next_ts:
        return [{"type": "restart"}]
    actions: list[dict[str, Any]] = []
    warned = set(schedule.get("warnedMinutes", []))
    for minutes in sorted(schedule.get("warnings", []), reverse=True):
        warn_ts = next_ts - minutes * 60
        if now_ts >= warn_ts and minutes not in warned:
            actions.append({"type": "warn", "minutes": minutes})
    return actions


def normalize_warnings(value: Any, interval_hours: float) -> list[int]:
    interval_minutes = int(interval_hours * 60)
    result: list[int] = []
    for item in value or []:
        try:
            minutes = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= minutes < interval_minutes and minutes not in result:
            result.append(minutes)
    return sorted(result, reverse=True)[:SCHEDULE_WARNINGS_MAX]


class RestartScheduler:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.schedules: dict[str, dict[str, Any]] = {}
        self.thread: threading.Thread | None = None
        self.started = False

    def path(self) -> Path:
        return RUNTIME / "schedules.json"

    def load(self) -> None:
        data = read_json(self.path(), {"schedules": {}})
        with self.lock:
            self.schedules = data.get("schedules", {}) if isinstance(data, dict) else {}

    def _save_locked(self) -> None:
        write_json(self.path(), {"schedules": self.schedules})

    def payload(self) -> dict[str, Any]:
        maps = map_configs()
        with self.lock:
            items = []
            for name in maps:
                sched = self.schedules.get(name, {})
                items.append(
                    {
                        "map": name,
                        "title": maps[name].get("title", name),
                        "enabled": bool(sched.get("enabled")),
                        "intervalHours": sched.get("intervalHours", 4),
                        "warnings": sched.get("warnings", [30, 15, 5, 1]),
                        "nextRestart": sched.get("nextRestart"),
                        "lastRestart": sched.get("lastRestart"),
                    }
                )
        return {"schedules": items, "now": time.time(), "schedulerRunning": self.started}

    def save_schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = rcon_map(payload)
        enabled = bool(payload.get("enabled"))
        interval = clamp_number(
            payload.get("intervalHours", 4), "intervalHours",
            SCHEDULE_INTERVAL_MIN_HOURS, SCHEDULE_INTERVAL_MAX_HOURS,
        )
        warnings = normalize_warnings(payload.get("warnings", [30, 15, 5, 1]), float(interval))
        with self.lock:
            sched = self.schedules.setdefault(name, {})
            sched["enabled"] = enabled
            sched["intervalHours"] = float(interval)
            sched["warnings"] = warnings
            if enabled:
                sched["nextRestart"] = time.time() + float(interval) * 3600
                sched["warnedMinutes"] = []
            else:
                sched["nextRestart"] = None
            self._save_locked()
        return self.payload()

    def remove_schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = rcon_map(payload)
        with self.lock:
            self.schedules.pop(name, None)
            self._save_locked()
        return self.payload()

    def _tick(self) -> None:
        now_ts = time.time()
        with self.lock:
            snapshot = {name: dict(sched) for name, sched in self.schedules.items()}
        for name, sched in snapshot.items():
            for action in schedule_due_actions(sched, now_ts):
                if action["type"] == "warn":
                    self._warn(name, action["minutes"])
                elif action["type"] == "restart":
                    self._restart(name, sched)

    def _warn(self, name: str, minutes: int) -> None:
        message = f"Server restart in {minutes} minute{'s' if minutes != 1 else ''}."
        try:
            run_rcon({"map": name, "command": "say", "message": message})
        except Exception as exc:  # noqa: BLE001 - warnings are best effort (RCon may be down).
            log_message(f"[scheduler] warn {name} {minutes}m failed: {exc}")
        with self.lock:
            sched = self.schedules.get(name)
            if sched is not None:
                sched.setdefault("warnedMinutes", []).append(minutes)
                self._save_locked()

    def _restart(self, name: str, sched: dict[str, Any]) -> None:
        try:
            start_action({"action": "restart_map", "map": name, "confirm": "RESTART"})
        except Exception as exc:  # noqa: BLE001 - keep the scheduler alive on a failed restart.
            log_message(f"[scheduler] restart {name} failed: {exc}")
        interval = float(sched.get("intervalHours", 4))
        with self.lock:
            current = self.schedules.get(name)
            if current is not None:
                current["lastRestart"] = time.time()
                current["nextRestart"] = time.time() + interval * 3600
                current["warnedMinutes"] = []
                self._save_locked()

    def _run(self) -> None:
        while True:
            try:
                self._tick()
            except Exception as exc:  # noqa: BLE001 - never let the scheduler thread die.
                log_message(f"[scheduler] tick error: {exc}")
            time.sleep(20)

    def start(self) -> None:
        self.load()
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            self.started = True


SCHEDULER = RestartScheduler()


WATCHDOG_TICK_SECONDS = 30
WATCHDOG_GRACE_TICKS = 2  # confirm down across two ticks before relaunching (covers restart gaps)
WATCHDOG_MAX_RESTARTS = 3
WATCHDOG_WINDOW_SECONDS = 600


class Watchdog:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.enabled: dict[str, bool] = {}
        self.runtime: dict[str, dict[str, Any]] = {}
        self.thread: threading.Thread | None = None
        self.started = False

    def path(self) -> Path:
        return RUNTIME / "watchdog.json"

    def load(self) -> None:
        data = read_json(self.path(), {"maps": {}})
        maps = data.get("maps", {}) if isinstance(data, dict) else {}
        with self.lock:
            self.enabled = {name: bool(entry.get("enabled")) for name, entry in maps.items()}

    def _save_locked(self) -> None:
        write_json(self.path(), {"maps": {name: {"enabled": value} for name, value in self.enabled.items()}})

    def _rt(self, name: str) -> dict[str, Any]:
        return self.runtime.setdefault(
            name, {"down": 0, "restarts": [], "paused": False, "pausedReason": None, "lastAction": None, "lastActionAt": None}
        )

    def payload(self) -> dict[str, Any]:
        maps = map_configs()
        ports = running_server_game_ports()
        now = time.time()
        with self.lock:
            items = []
            for name in maps:
                rt = self.runtime.get(name, {})
                game = int(maps[name].get("port", 0) or 0)
                items.append(
                    {
                        "map": name,
                        "title": maps[name].get("title", name),
                        "enabled": self.enabled.get(name, False),
                        "running": game in ports,
                        "paused": rt.get("paused", False),
                        "pausedReason": rt.get("pausedReason"),
                        "recentRestarts": len([t for t in rt.get("restarts", []) if t > now - WATCHDOG_WINDOW_SECONDS]),
                        "lastAction": rt.get("lastAction"),
                        "lastActionAt": rt.get("lastActionAt"),
                    }
                )
        return {"maps": items, "now": now, "watchdogRunning": self.started}

    def set_enabled(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = rcon_map(payload)
        enabled = bool(payload.get("enabled"))
        with self.lock:
            self.enabled[name] = enabled
            rt = self._rt(name)
            if enabled:
                rt["paused"] = False
                rt["pausedReason"] = None
                rt["down"] = 0
            self._save_locked()
        if enabled:
            game = int(map_configs()[name].get("port", 0) or 0)
            if game not in running_server_game_ports():
                self._relaunch(name, immediate=True)
        return self.payload()

    def _relaunch(self, name: str, immediate: bool = False) -> None:
        try:
            start_action({"action": "start_map", "map": name})
        except Exception as exc:  # noqa: BLE001 - keep the watchdog alive on a failed start.
            log_message(f"[watchdog] start {name} failed: {exc}")
            return
        with self.lock:
            rt = self._rt(name)
            rt["restarts"].append(time.time())
            rt["down"] = 0
            rt["lastAction"] = "started (keep-alive on)" if immediate else "relaunched after crash"
            rt["lastActionAt"] = dt.datetime.now().isoformat(timespec="seconds")
        log_message(f"[watchdog] {'started' if immediate else 'relaunched'} {name}")

    def tick(self) -> None:
        with self.lock:
            enabled_maps = [name for name, value in self.enabled.items() if value]
        if not enabled_maps:
            return
        ports = running_server_game_ports()
        maps = map_configs()
        to_relaunch: list[str] = []
        now = time.time()
        for name in enabled_maps:
            if name not in maps:
                continue
            game = int(maps[name].get("port", 0) or 0)
            with self.lock:
                rt = self._rt(name)
                if game in ports:
                    rt["down"] = 0
                    continue
                if rt.get("paused"):
                    continue
                rt["down"] += 1
                if rt["down"] < WATCHDOG_GRACE_TICKS:
                    continue
                rt["restarts"] = [t for t in rt["restarts"] if t > now - WATCHDOG_WINDOW_SECONDS]
                if len(rt["restarts"]) >= WATCHDOG_MAX_RESTARTS:
                    rt["paused"] = True
                    rt["pausedReason"] = (
                        f"Paused after {WATCHDOG_MAX_RESTARTS} restarts in "
                        f"{WATCHDOG_WINDOW_SECONDS // 60} min. Fix the crash, then re-enable keep-alive."
                    )
                    log_message(f"[watchdog] {name} crash-looped; paused")
                    continue
            to_relaunch.append(name)
        for name in to_relaunch:
            self._relaunch(name)

    def _run(self) -> None:
        while True:
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 - never let the watchdog thread die.
                log_message(f"[watchdog] tick error: {exc}")
            time.sleep(WATCHDOG_TICK_SECONDS)

    def start(self) -> None:
        self.load()
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            self.started = True


WATCHDOG = Watchdog()


DAYZ_SERVER_APPID = "223350"
DAYZ_WORKSHOP_APPID = "221100"
STEAM_USERNAME_RE = re.compile(r"^[A-Za-z0-9_@.\-]{1,64}$")


def find_steamcmd() -> Path | None:
    settings = read_user_settings()
    candidates: list[Path] = []
    configured = settings.get("steamcmd_path")
    if configured:
        candidates.append(Path(str(configured)))
    candidates.append(ROOT / "local_runtime" / "steamcmd" / "steamcmd.exe")
    candidates.append(Path(r"C:\steamcmd\steamcmd.exe"))
    found_on_path = shutil.which("steamcmd")
    if found_on_path:
        candidates.append(Path(found_on_path))
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except OSError:
            continue
    return None


def catalog_mod_ids() -> list[str]:
    data = read_json(ADMIN / "map_workshop_catalog.json", {})
    ids: list[str] = []
    if isinstance(data, dict):
        for entry in data.values():
            if isinstance(entry, dict):
                wid = entry.get("workshop_id")
                if wid and str(wid).isdigit():
                    ids.append(str(wid))
    return sorted(set(ids))


META_PUBLISHEDID_RE = re.compile(r"publishedid\s*=\s*(\d+)", re.IGNORECASE)
META_NAME_RE = re.compile(r'name\s*=\s*"([^"]*)"', re.IGNORECASE)
WORKSHOP_DETAILS_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)


def mod_local_mtime(folder: Path) -> float:
    """Newest modification time of a mod folder (folder + immediate children).

    meta.cpp's `timestamp` field is a DayZ-internal value, not unix epoch, so the
    folder mtime is the reliable signal for "when was this mod last updated locally".
    """
    newest = 0.0
    try:
        newest = folder.stat().st_mtime
    except OSError:
        return 0.0
    try:
        for child in folder.iterdir():
            try:
                newest = max(newest, child.stat().st_mtime)
            except OSError:
                continue
    except OSError:
        pass
    return newest


def scan_installed_mods() -> list[dict[str, Any]]:
    """Read every `@*/meta.cpp` in the server root for its Workshop publishedid."""
    mods: list[dict[str, Any]] = []
    try:
        entries = sorted(ROOT.glob("@*"))
    except OSError:
        entries = []
    for folder in entries:
        if not folder.is_dir():
            continue
        meta = folder / "meta.cpp"
        if not meta.exists():
            continue
        try:
            text = meta.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        id_match = META_PUBLISHEDID_RE.search(text)
        if not id_match:
            continue
        name_match = META_NAME_RE.search(text)
        published_id = id_match.group(1)
        name = (name_match.group(1).strip() if name_match else "") or folder.name.lstrip("@")
        mtime = mod_local_mtime(folder)
        mods.append(
            {
                "folder": folder.name,
                "name": name,
                "publishedId": published_id,
                "localUpdated": mtime,
                "localUpdatedText": (
                    dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    if mtime
                    else "unknown"
                ),
            }
        )
    mods.sort(key=lambda m: m["name"].lower())
    return mods


def fetch_workshop_details(ids: list[str]) -> dict[str, dict[str, Any]]:
    """Query Steam's public, no-key Workshop API for each published file id."""
    import urllib.error
    import urllib.request

    if not ids:
        return {}
    details: dict[str, dict[str, Any]] = {}
    # Steam's no-key endpoint rejects large batches (54 returns HTTP 400; 30 is fine),
    # so request in chunks and merge the results.
    chunk_size = 25
    for start in range(0, len(ids), chunk_size):
        chunk = ids[start : start + chunk_size]
        fields = [("itemcount", str(len(chunk)))]
        for index, wid in enumerate(chunk):
            fields.append((f"publishedfileids[{index}]", wid))
        body = "&".join(f"{key}={value}" for key, value in fields).encode("utf-8")
        request = urllib.request.Request(
            WORKSHOP_DETAILS_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "DayZServerControlCenter/1.0 (+local admin tool)",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed Steam host
            data = json.loads(response.read().decode("utf-8"))
        for item in data.get("response", {}).get("publishedfiledetails", []):
            if isinstance(item, dict) and item.get("publishedfileid"):
                details[str(item["publishedfileid"])] = item
    return details


def mods_updates_payload(check_remote: bool = False) -> dict[str, Any]:
    mods = scan_installed_mods()
    remote_error: str | None = None
    details: dict[str, dict[str, Any]] = {}
    # publishedid 0 means a local/non-Workshop mod; Steam rejects it, so never query it.
    queryable = sorted({m["publishedId"] for m in mods if m["publishedId"] not in {"0", ""}})
    if check_remote and queryable:
        try:
            details = fetch_workshop_details(queryable)
        except Exception as exc:  # noqa: BLE001 - network/parse errors are user-facing.
            remote_error = (
                "Could not reach the Steam Workshop API. Check your internet "
                f"connection and try again. ({exc})"
            )
    update_count = 0
    for mod in mods:
        mod["workshop"] = mod["publishedId"] not in {"0", ""}
        item = details.get(mod["publishedId"]) if details else None
        mod["checked"] = bool(item) if check_remote else False
        if item and item.get("result") == 1:
            remote_updated = int(item.get("time_updated") or 0)
            mod["title"] = item.get("title") or mod["name"]
            mod["remoteUpdated"] = remote_updated
            mod["remoteUpdatedText"] = (
                dt.datetime.fromtimestamp(remote_updated).strftime("%Y-%m-%d %H:%M")
                if remote_updated
                else "unknown"
            )
            mod["fileSize"] = int(item.get("file_size") or 0)
            mod["updateAvailable"] = bool(
                remote_updated and mod["localUpdated"] and remote_updated > mod["localUpdated"]
            )
            if mod["updateAvailable"]:
                update_count += 1
        else:
            mod["remoteUpdated"] = 0
            mod["remoteUpdatedText"] = ""
            mod["updateAvailable"] = False
            if check_remote and item is not None:
                mod["title"] = mod["name"]
    return {
        "mods": mods,
        "modCount": len(mods),
        "checked": check_remote and remote_error is None,
        "updateCount": update_count,
        "remoteError": remote_error,
        "note": (
            "Compares each installed mod's folder date against the Steam Workshop "
            "\"last updated\" date. Checking contacts Steam over the internet; the rest "
            "of the app stays local. After an update shows, use the Updates tab to run "
            "SteamCMD update-mods."
        ),
    }


def updates_status_payload() -> dict[str, Any]:
    settings = read_user_settings()
    steamcmd = find_steamcmd()
    ids = catalog_mod_ids()
    return {
        "steamcmdFound": steamcmd is not None,
        "steamcmdPath": str(steamcmd) if steamcmd else None,
        "username": settings.get("steam_username") or "",
        "usernameSet": bool(settings.get("steam_username")),
        "serverAppId": DAYZ_SERVER_APPID,
        "workshopAppId": DAYZ_WORKSHOP_APPID,
        "modIds": ids,
        "modCount": len(ids),
        "note": (
            "Updates open a SteamCMD console window. Log in once (password + Steam Guard) so "
            "SteamCMD caches the session; later updates reuse it. No password is stored here."
        ),
    }


def save_updates_settings(payload: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if "username" in payload:
        username = str(payload.get("username") or "").strip()
        if username and not STEAM_USERNAME_RE.fullmatch(username):
            raise ValueError("Invalid Steam username.")
        values["steam_username"] = username
    if "steamcmdPath" in payload:
        values["steamcmd_path"] = str(payload.get("steamcmdPath") or "").strip()
    if values:
        save_user_settings(values)
    return updates_status_payload()


def require_steamcmd() -> Path:
    steamcmd = find_steamcmd()
    if steamcmd is None:
        raise ValueError("SteamCMD is not installed yet. Use Install SteamCMD first.")
    return steamcmd


def require_steam_username() -> str:
    username = str(read_user_settings().get("steam_username") or "").strip()
    if not username:
        raise ValueError("Set your Steam username first (Updates tab). No password is stored.")
    if not STEAM_USERNAME_RE.fullmatch(username):
        raise ValueError("Stored Steam username is invalid; set it again.")
    return username


ADM_LINE_RE = re.compile(r"^(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\s*\|\s*(?P<rest>.*)$")
ADM_GUID = r"[A-Za-z0-9+/=]+"
ADM_CONNECT_RE = re.compile(rf'Player "(?P<name>.*?)" \(id=(?P<guid>{ADM_GUID})(?: pos=<[^>]*>)?\) is connected')
ADM_DISCONNECT_RE = re.compile(rf'Player "(?P<name>.*?)" \(id=(?P<guid>{ADM_GUID}) pos=<[^>]*>\) has been disconnected')
ADM_KILL_RE = re.compile(rf'Player "(?P<victim>.*?)" \(DEAD\) \(id=(?P<vguid>{ADM_GUID}) pos=<[^>]*>\) killed by (?P<rest>.*)$')
ADM_KILLER_PLAYER_RE = re.compile(rf'Player "(?P<name>.*?)" \(id=(?P<guid>{ADM_GUID})')
ADM_KILLER_AI_RE = re.compile(r'AI "(?P<name>.*?)"')
ADM_WEAPON_RE = re.compile(r"with (?P<weapon>.+?) from (?P<dist>[\d.]+) meters")
ADM_FILE_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
ADM_MAX_FILES = 25


def adm_file_date(path: Path) -> dt.date:
    match = ADM_FILE_DATE_RE.search(path.name)
    if match:
        try:
            return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    return dt.date.fromtimestamp(path.stat().st_mtime)


def parse_adm_file(path: Path) -> list[dict[str, Any]]:
    base_date = adm_file_date(path)
    events: list[dict[str, Any]] = []
    last_seconds = -1
    day_offset = 0
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return events
    for line in text.splitlines():
        line_match = ADM_LINE_RE.match(line.strip())
        if not line_match:
            continue
        seconds = int(line_match["h"]) * 3600 + int(line_match["m"]) * 60 + int(line_match["s"])
        if seconds < last_seconds:
            day_offset += 1  # log rolled past midnight
        last_seconds = seconds
        when = dt.datetime.combine(base_date, dt.time()) + dt.timedelta(days=day_offset, seconds=seconds)
        rest = line_match["rest"]

        connect = ADM_CONNECT_RE.search(rest)
        if connect:
            events.append({"type": "connect", "dt": when, "name": connect["name"], "guid": connect["guid"]})
            continue
        disconnect = ADM_DISCONNECT_RE.search(rest)
        if disconnect:
            events.append({"type": "disconnect", "dt": when, "name": disconnect["name"], "guid": disconnect["guid"]})
            continue
        kill = ADM_KILL_RE.search(rest)
        if kill:
            killer_rest = kill["rest"]
            weapon_match = ADM_WEAPON_RE.search(killer_rest)
            player_killer = ADM_KILLER_PLAYER_RE.match(killer_rest)
            ai_killer = ADM_KILLER_AI_RE.match(killer_rest)
            if player_killer:
                killer_type, killer_name, killer_guid = "player", player_killer["name"], player_killer["guid"]
            elif ai_killer:
                killer_type, killer_name, killer_guid = "ai", ai_killer["name"], None
            else:
                killer_type, killer_name, killer_guid = "other", killer_rest.split(" ")[0].strip(), None
            events.append(
                {
                    "type": "kill",
                    "dt": when,
                    "victim": kill["victim"],
                    "vguid": kill["vguid"],
                    "killerType": killer_type,
                    "killerName": killer_name,
                    "killerGuid": killer_guid,
                    "weapon": weapon_match["weapon"] if weapon_match else None,
                    "distance": float(weapon_match["dist"]) if weapon_match else None,
                }
            )
    return events


def recent_adm_files(map_name: str, limit: int = ADM_MAX_FILES) -> list[Path]:
    profile = map_profile_dir(map_name)
    if not profile.exists():
        return []
    files = [p for p in profile.glob("*.ADM") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def collect_adm_events(map_name: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in recent_adm_files(map_name):
        events.extend(parse_adm_file(path))
    events.sort(key=lambda e: e["dt"])
    return events


def players_payload(map_name: str) -> dict[str, Any]:
    map_name = rcon_map(map_name)
    events = collect_adm_events(map_name)
    notes = read_player_notes()
    players: dict[str, dict[str, Any]] = {}
    open_session: dict[str, dt.datetime] = {}

    def ensure(guid: str, name: str) -> dict[str, Any]:
        entry = players.setdefault(
            guid,
            {"guid": guid, "name": name, "firstSeen": None, "lastSeen": None,
             "sessions": 0, "playtimeMinutes": 0.0, "kills": 0, "deaths": 0},
        )
        if name:
            entry["name"] = name
        return entry

    for ev in events:
        if ev["type"] == "connect":
            entry = ensure(ev["guid"], ev["name"])
            entry["firstSeen"] = entry["firstSeen"] or ev["dt"]
            entry["lastSeen"] = ev["dt"]
            open_session[ev["guid"]] = ev["dt"]
        elif ev["type"] == "disconnect":
            entry = ensure(ev["guid"], ev["name"])
            entry["lastSeen"] = ev["dt"]
            start = open_session.pop(ev["guid"], None)
            if start:
                entry["sessions"] += 1
                entry["playtimeMinutes"] += max(0.0, (ev["dt"] - start).total_seconds() / 60.0)
        elif ev["type"] == "kill":
            victim = ensure(ev["vguid"], ev["victim"])
            victim["deaths"] += 1
            victim["lastSeen"] = ev["dt"]
            if ev["killerType"] == "player" and ev.get("killerGuid"):
                killer = ensure(ev["killerGuid"], ev["killerName"])
                killer["kills"] += 1
                killer["lastSeen"] = ev["dt"]

    result = []
    for guid, entry in players.items():
        result.append(
            {
                "guid": guid,
                "name": entry["name"],
                "firstSeen": entry["firstSeen"].isoformat(timespec="seconds") if entry["firstSeen"] else None,
                "lastSeen": entry["lastSeen"].isoformat(timespec="seconds") if entry["lastSeen"] else None,
                "sessions": entry["sessions"],
                "playtimeMinutes": round(entry["playtimeMinutes"], 1),
                "kills": entry["kills"],
                "deaths": entry["deaths"],
                "note": notes.get(guid, ""),
            }
        )
    result.sort(key=lambda p: p["lastSeen"] or "", reverse=True)
    return {"map": map_name, "players": result, "filesScanned": len(recent_adm_files(map_name))}


def killfeed_payload(map_name: str, limit: int = 60) -> dict[str, Any]:
    map_name = rcon_map(map_name)
    kills = [ev for ev in collect_adm_events(map_name) if ev["type"] == "kill"]
    kills.sort(key=lambda e: e["dt"], reverse=True)
    feed = []
    for ev in kills[: max(1, min(limit, 200))]:
        feed.append(
            {
                "at": ev["dt"].isoformat(timespec="seconds"),
                "victim": ev["victim"],
                "killer": ev["killerName"],
                "killerType": ev["killerType"],
                "weapon": ev["weapon"],
                "distance": round(ev["distance"], 1) if ev["distance"] is not None else None,
            }
        )
    return {"map": map_name, "kills": feed}


def player_notes_path() -> Path:
    return RUNTIME / "player_notes.json"


def read_player_notes() -> dict[str, str]:
    data = read_json(player_notes_path(), {})
    return data if isinstance(data, dict) else {}


def save_player_note(payload: dict[str, Any]) -> dict[str, Any]:
    guid = str(payload.get("guid") or "").strip()
    if not guid or not re.fullmatch(ADM_GUID, guid):
        raise ValueError("A valid player id is required.")
    note = str(payload.get("note") or "").replace("\r", " ").replace("\n", " ").strip()[:500]
    notes = read_player_notes()
    if note:
        notes[guid] = note
    else:
        notes.pop(guid, None)
    write_json(player_notes_path(), notes)
    return {"guid": guid, "note": note}


def vpp_profile_ready(name: str, cfg: dict[str, Any]) -> bool:
    profile = cfg.get("profiles_dir") or f"profiles_{name}"
    perms = ROOT / profile / "VPPAdminTools" / "Permissions"
    return (perms / "credentials.txt").exists() and (perms / "SuperAdmins" / "SuperAdmins.txt").exists()


SETUP_STEP_KEYS = (
    "server_root",
    "private_configs",
    "missions",
    "mods",
    "vpp",
    "validation",
)


def setup_state_path() -> Path:
    return RUNTIME / "setup_state.json"


def read_setup_state() -> dict[str, Any]:
    state = read_json(setup_state_path(), {})
    if not isinstance(state, dict):
        return {}
    return state


def write_setup_state(values: dict[str, Any]) -> dict[str, Any]:
    state = read_setup_state()
    completed = {str(item) for item in state.get("completedSteps", []) if str(item) in SETUP_STEP_KEYS}

    step = values.get("step")
    if step is not None:
        if str(step) not in SETUP_STEP_KEYS:
            raise ValueError(f"Unknown setup step: {step}")
        if bool(values.get("done", True)):
            completed.add(str(step))
        else:
            completed.discard(str(step))

    if "dismissIntro" in values:
        state["dismissIntro"] = bool(values["dismissIntro"])

    state["completedSteps"] = [key for key in SETUP_STEP_KEYS if key in completed]
    state["updatedAt"] = dt.datetime.now().isoformat(timespec="seconds")
    write_json(setup_state_path(), state)
    return state


def setup_payload() -> dict[str, Any]:
    maps = maps_payload()
    config_cfgs = map_configs()
    saved = read_setup_state()
    completed = {str(item) for item in saved.get("completedSteps", [])}

    config_missing = [m["key"] for m in maps if not m["configExists"]]
    mission_missing = [m["key"] for m in maps if not m["missionExists"]]
    mod_missing = [m["key"] for m in maps if m["missingMods"]]
    vpp_missing = [name for name, cfg in config_cfgs.items() if not vpp_profile_ready(name, cfg)]
    map_count = len(maps)

    def status_for(missing: list[str]) -> str:
        return "ok" if not missing else "todo"

    steps: list[dict[str, Any]] = [
        {
            "key": "server_root",
            "title": "Server folder confirmed",
            "status": "ok",
            "summary": f"Using {ROOT.name}",
            "detail": (
                "The app found a valid DayZServer root. It must contain admin\\map_launch.json "
                "and Launch-DayZMap.ps1. Everything else on this page is checked against this folder."
            ),
            "items": [str(ROOT)],
            "fixAction": None,
        },
        {
            "key": "private_configs",
            "title": "Private server configs",
            "status": status_for(config_missing),
            "summary": "all present" if not config_missing else f"{len(config_missing)} of {map_count} missing",
            "detail": (
                "Each map needs its real serverDZ*.cfg next to the server EXE. These stay private and "
                "git-ignored because they can hold admin passwords and ports. Copy the matching "
                "serverDZ*.example.cfg and fill in your values for any map listed here."
            ),
            "items": config_missing,
            "fixAction": "config_drift",
        },
        {
            "key": "missions",
            "title": "Mission folders",
            "status": status_for(mission_missing),
            "summary": "all present" if not mission_missing else f"{len(mission_missing)} of {map_count} missing",
            "detail": (
                "Every launch entry points at a mission folder under mpmissions. A missing mission "
                "folder means the map cannot boot. Install or copy the mission files for any map listed here."
            ),
            "items": mission_missing,
            "fixAction": None,
        },
        {
            "key": "mods",
            "title": "Workshop mods",
            "status": status_for(mod_missing),
            "summary": "all listed mods present" if not mod_missing else f"{len(mod_missing)} map(s) missing mods",
            "detail": (
                "The server root must contain every @Mod folder named in a map's mod list. Missing mod "
                "folders cause launcher mismatches and join failures. Copy the Workshop mods for any map listed here."
            ),
            "items": mod_missing,
            "fixAction": None,
        },
        {
            "key": "vpp",
            "title": "VPP admin tooling",
            "status": "ok" if not vpp_missing else "warn",
            "summary": "credentials present" if not vpp_missing else f"{len(vpp_missing)} map(s) missing VPP files",
            "detail": (
                "VPP Admin Tools needs credentials.txt and SuperAdmins.txt inside each map profile's "
                "VPPAdminTools\\Permissions folder. Without them the in-game admin menu will not authorize you. "
                "Run Sync VPP Profiles after you have created your private source profile."
            ),
            "items": vpp_missing,
            "fixAction": "sync_vpp_profiles",
        },
        {
            "key": "validation",
            "title": "Run safe validation",
            "status": "action",
            "summary": "recommended read-only check",
            "detail": (
                "Run the public repo and imported-map validators. They are read-only and confirm your "
                "tracked files are public-safe and parse cleanly before you share or publish anything."
            ),
            "items": [],
            "fixAction": "validate_public_repo",
        },
    ]

    for step in steps:
        step["done"] = step["key"] in completed

    def needs_attention(step: dict[str, Any]) -> bool:
        if step["status"] in {"todo", "warn"}:
            return True
        if step["status"] == "action" and not step["done"]:
            return True
        return False

    next_step = next((step["key"] for step in steps if needs_attention(step)), None)
    blocking = [step["key"] for step in steps if step["status"] in {"todo", "warn"}]

    return {
        "version": APP_VERSION,
        "root": str(ROOT),
        "ready": not blocking,
        "recommendedNext": next_step,
        "dismissIntro": bool(saved.get("dismissIntro", False)),
        "updatedAt": saved.get("updatedAt"),
        "steps": steps,
    }


TROUBLESHOOTING_SYMPTOMS: list[dict[str, Any]] = [
    {
        "key": "wont_boot",
        "title": "Server will not boot",
        "explanation": (
            "The map never reaches 'Player connect enabled'. This is usually a config, mission, or mod "
            "problem, or a fatal error in the latest RPT log. Work from the logs outward and change nothing "
            "until you know the cause."
        ),
        "steps": [
            {"action": "triage_logs", "note": "Scan the latest RPT/script log for the actual blocker first."},
            {"action": "config_drift", "note": "Confirm the launch config, real config, and helpers agree."},
            {"action": "check_map_launch", "note": "Verify mission folder, mod folders, and ports exist."},
            {"action": "smoke_test_map", "note": "Do a controlled start that stops itself, to watch boot live."},
            {"action": "recover_imported_map", "note": "Imported maps only: clean risky generated content, then retest."},
        ],
    },
    {
        "key": "not_in_launcher",
        "title": "Map does not show in the launcher",
        "explanation": (
            "The server runs but does not appear in the DayZ in-game server browser. This is almost always "
            "the Steam query port not being visible: it is inactive, blocked by Windows Firewall, or mismatched "
            "between the config and the launch entry."
        ),
        "steps": [
            {"action": "lan_visibility_check", "note": "Check the query port UDP endpoint and A2S response."},
            {"action": "check_map_launch", "note": "Confirm the steamQueryPort matches between config and launch entry."},
            {"action": "sync_desktop_launchers", "note": "Regenerate desktop start files if ports were changed."},
            {
                "tab": "maintenance",
                "note": "If the query port is active but still hidden, allow the DayZ server EXE through Windows Firewall.",
            },
        ],
    },
    {
        "key": "vpp_not_opening",
        "title": "VPP admin menu does not open",
        "explanation": (
            "Pressing the admin key does nothing in-game. Either the VPP credentials/SuperAdmins files are "
            "missing from the map profile, or the input binding was lost or overwritten by old COT inputs."
        ),
        "steps": [
            {"action": "check_admin_tooling", "note": "Check VPP files, input presets, and client profiles."},
            {"action": "sync_vpp_profiles", "note": "Copy your private VPP credentials/SuperAdmins into map profiles."},
            {"action": "repair_vpp_inputs", "note": "Remove stale COT inputs and rebind VPP to End/Home."},
        ],
    },
    {
        "key": "loot_warnings",
        "title": "Loot is causing placement warnings",
        "explanation": (
            "The RPT log fills with loot/economy placement warnings, or loot feels wrong. Usually the loot "
            "preset is too high for the map, or generated loot files drifted from the active preset."
        ),
        "steps": [
            {"action": "triage_logs", "note": "Confirm the warnings are loot/economy placement related."},
            {"action": "status_all", "note": "Review the active loot preset and per-map economy summary."},
            {"tab": "balance", "note": "Lower the active loot preset (Low/Medium) for heavy maps in the Balance tab."},
            {"action": "apply_loot_current", "note": "Regenerate and apply loot files from the active preset."},
        ],
    },
    {
        "key": "ai_density",
        "title": "AI is too rare or too aggressive",
        "explanation": (
            "Expansion AI encounters feel empty, or too frequent and too lethal. This is tuned by patrol caps "
            "and difficulty in the AI patrol settings, not by a single switch. Adjust gradually and restart."
        ),
        "steps": [
            {"action": "status_all", "note": "See current AI patrol counts and caps per map."},
            {"tab": "balance", "note": "Raise/lower patrol caps and AI/group, and adjust accuracy/damage in the Balance tab."},
            {"action": "smoke_test_map", "note": "Restart the map and smoke test to confirm the new feel."},
        ],
    },
    {
        "key": "imported_loop",
        "title": "Imported map loops or hangs on boot",
        "explanation": (
            "A community/imported map restarts repeatedly or hangs during boot. This is typically risky generated "
            "Expansion placements or poisoned imported storage. Recover the map before touching storage, and only "
            "wipe storage as a last resort."
        ),
        "steps": [
            {"action": "triage_logs", "note": "Find the boot-time blocker before changing anything."},
            {"action": "validate_imported_maps", "note": "Check the imported map for risky generated content."},
            {"action": "recover_imported_map", "note": "Run the guarded imported-map cleanup/recovery flow."},
            {"action": "wipe_imported_storage", "note": "Last resort: wipe imported storage after recovery still fails."},
        ],
    },
]


def troubleshooting_payload() -> dict[str, Any]:
    specs = action_specs()
    symptoms: list[dict[str, Any]] = []
    for symptom in TROUBLESHOOTING_SYMPTOMS:
        steps: list[dict[str, Any]] = []
        for step in symptom["steps"]:
            action_key = step.get("action")
            if action_key is not None:
                spec = specs.get(action_key)
                if spec is None:
                    raise ValueError(f"Troubleshooting references unknown action: {action_key}")
                steps.append(
                    {
                        "kind": "action",
                        "action": action_key,
                        "label": spec.label,
                        "risk": spec.risk,
                        "mapMode": spec.map_mode,
                        "confirm": spec.confirm,
                        "note": step.get("note", ""),
                    }
                )
            else:
                steps.append(
                    {
                        "kind": "tab",
                        "tab": step.get("tab"),
                        "note": step.get("note", ""),
                    }
                )
        symptoms.append(
            {
                "key": symptom["key"],
                "title": symptom["title"],
                "explanation": symptom["explanation"],
                "steps": steps,
            }
        )
    return {"symptoms": symptoms}


def snapshot_for_api(label: str) -> None:
    if not CONFIG.get("snapshot_before_mutation", True):
        return
    code, output = run_command(python_file("snapshot_configs.py", "--label", label), 240)
    if code != 0:
        raise ValueError(f"Snapshot failed before saving balance settings:\n{output}")


ZOMBIE_FIELD_RANGES: dict[str, tuple[int, int]] = {
    "ZombieMaxCount": (0, 5000),
    "AnimalMaxCount": (0, 1000),
    "SpawnInitial": (0, 10000),
    "InitialSpawn": (0, 2000),
    "RespawnLimit": (0, 1000),
    "RespawnTypes": (0, 500),
}


def validate_balance_payload(
    payload: dict[str, Any],
) -> tuple[str | None, list[str], dict[str, int], list[str], dict[str, Any]]:
    """Validate and clamp a balance save/preview payload without writing anything."""
    loot_preset: str | None = None
    if "lootPreset" in payload:
        loot = read_json(LOOT_CONFIG_PATH, {})
        loot_preset = str(payload["lootPreset"])
        if loot_preset not in loot.get("presets", {}):
            raise ValueError(f"Unknown loot preset: {loot_preset}")

    zombie_maps: list[str] = []
    zombie_values: dict[str, int] = {}
    if "zombies" in payload:
        data = payload["zombies"] or {}
        zombie_maps = selected_balance_maps(data.get("maps", "all"))
        for field, (low, high) in ZOMBIE_FIELD_RANGES.items():
            if field in data:
                zombie_values[field] = int(clamp_number(data[field], field, low, high, integer=True))

    ai_maps: list[str] = []
    ai_values: dict[str, Any] = {}
    if "ai" in payload:
        data = payload["ai"] or {}
        ai_maps = selected_balance_maps(data.get("maps", "all"))
        ai_values = {key: value for key, value in data.items() if key != "maps" and value not in ("", None)}
        if "minAI" in ai_values and "maxAI" in ai_values and int(ai_values["minAI"]) > int(ai_values["maxAI"]):
            raise ValueError("minAI cannot be greater than maxAI.")
        for field in ("patrolMax", "globalMax", "objectPatrolMax", "heliPatrolMax"):
            if field in ai_values:
                clamp_number(ai_values[field], field, -1, 200, integer=True)
        for field in ("minAI", "maxAI"):
            if field in ai_values:
                clamp_number(ai_values[field], field, 0, 20, integer=True)
        for field in ("accuracyMin", "accuracyMax"):
            if field in ai_values:
                clamp_number(ai_values[field], field, 0.0, 1.0)
        if "damageMultiplier" in ai_values:
            clamp_number(ai_values["damageMultiplier"], "damageMultiplier", 0.1, 5.0)

    return loot_preset, zombie_maps, zombie_values, ai_maps, ai_values


def preview_balance(payload: dict[str, Any]) -> dict[str, Any]:
    """Compute what a balance save would change, without writing or snapshotting."""
    loot_preset, zombie_maps, zombie_values, ai_maps, ai_values = validate_balance_payload(payload)
    files: list[str] = []
    changes: list[str] = []
    maps_affected: list[str] = []
    restart_required = False
    needs_loot_apply = False

    if loot_preset:
        loot = read_json(LOOT_CONFIG_PATH, {})
        if loot.get("active_preset") != loot_preset:
            files.append(safe_rel(LOOT_CONFIG_PATH))
            changes.append(f"Loot active preset -> {loot_preset}")
            needs_loot_apply = True

    if zombie_values:
        for name in zombie_maps:
            mission_dir = mission_dir_for_map(name)
            current = read_globals(mission_dir)
            diffs = [field for field, value in zombie_values.items() if current.get(field) != value]
            if diffs:
                files.append(safe_rel(mission_dir / "db" / "globals.xml"))
                maps_affected.append(name)
                changes.append(f"{name} globals: {', '.join(diffs)}")
                restart_required = True

    if ai_values:
        ai_fields = sorted(ai_values)
        for name in ai_maps:
            path = mission_dir_for_map(name) / "expansion" / "settings" / "AIPatrolSettings.json"
            if not path.exists():
                continue
            files.append(safe_rel(path))
            maps_affected.append(name)
            changes.append(f"{name} AI: {', '.join(ai_fields)}")
            restart_required = True

    return {
        "changes": changes,
        "files": sorted(set(files)),
        "maps": sorted(set(maps_affected)),
        "restartRequired": restart_required,
        "needsLootApply": needs_loot_apply,
        "snapshot": bool(CONFIG.get("snapshot_before_mutation", True)),
        "snapshotLabel": "control-center-balance",
        "hasChanges": bool(changes),
    }


def save_balance(payload: dict[str, Any]) -> dict[str, Any]:
    loot_preset, zombie_maps, zombie_values, ai_maps, ai_values = validate_balance_payload(payload)

    if not any([loot_preset, zombie_values, ai_values]):
        return {"changed": [], "balance": balance_payload()}

    snapshot_for_api("control-center-balance")
    changed: list[str] = []

    if loot_preset:
        loot = read_json(LOOT_CONFIG_PATH, {})
        if loot.get("active_preset") != loot_preset:
            loot["active_preset"] = loot_preset
            write_json(LOOT_CONFIG_PATH, loot)
            changed.append(f"loot active preset={loot_preset}")

    if zombie_values:
        for name in zombie_maps:
            changed_fields = write_globals(mission_dir_for_map(name), zombie_values)
            if changed_fields:
                changed.append(f"{name} globals: {', '.join(changed_fields)}")

    if ai_values:
        for name in ai_maps:
            changed_fields = write_ai_settings(mission_dir_for_map(name), ai_values)
            if changed_fields:
                changed.append(f"{name} AI: {', '.join(changed_fields)}")

    return {"changed": changed, "balance": balance_payload()}


EVENT_FIELDS = ("nominal", "min", "max", "lifetime", "restock")
EVENT_FIELD_RANGES: dict[str, tuple[int, int]] = {
    "nominal": (0, 2000),
    "min": (0, 2000),
    "max": (0, 2000),
    "lifetime": (0, 5_000_000),
    "restock": (0, 5_000_000),
}
EVENT_CATEGORY_LABELS = {
    "vehicles": "Vehicles",
    "heli": "Helicopter crashes",
    "airdrops": "Airdrops and crates",
    "static": "Static events (police, convoy, train)",
    "animals": "Animals and wildlife",
    "infected": "Infected spawns",
    "loot": "Loot and resources",
    "other": "Other events",
}


def event_category(name: str) -> str:
    lower = name.lower()
    if name.startswith("Vehicle"):
        return "vehicles"
    if "heli" in lower:
        return "heli"
    if "airplane" in lower or "crate" in lower or "airdrop" in lower:
        return "airdrops"
    if name.startswith("Static"):
        return "static"
    if name.startswith("Animal") or name.startswith("Ambient"):
        return "animals"
    if name.startswith("Infected"):
        return "infected"
    if name.startswith("Trajectory") or name.startswith("Item") or name == "Loot":
        return "loot"
    return "other"


def events_file_for_map(map_name: str) -> Path:
    mission = mission_for_map(map_name)
    return ROOT / "mpmissions" / mission / "db" / "events.xml"


def _event_int(event: ET.Element, field: str) -> int | None:
    el = event.find(field)
    if el is None or el.text is None:
        return None
    text = el.text.strip()
    try:
        return int(text)
    except ValueError:
        return None


def read_events(map_name: str) -> list[dict[str, Any]]:
    path = events_file_for_map(map_name)
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    out: list[dict[str, Any]] = []
    for event in root.findall("event"):
        name = event.get("name") or ""
        entry: dict[str, Any] = {"name": name, "category": event_category(name)}
        active = _event_int(event, "active")
        entry["active"] = 1 if active is None else active
        for field in EVENT_FIELDS:
            entry[field] = _event_int(event, field)
        out.append(entry)
    return out


def events_payload(map_name: str) -> dict[str, Any]:
    if map_name not in map_configs():
        raise ValueError(f"Unknown map: {map_name}")
    events = read_events(map_name)
    path = events_file_for_map(map_name)
    return {
        "map": map_name,
        "file": safe_rel(path) if path.exists() else None,
        "exists": path.exists(),
        "categoryLabels": EVENT_CATEGORY_LABELS,
        "events": events,
    }


def validate_events_payload(map_name: str, changes: Any) -> dict[str, dict[str, int]]:
    if map_name not in map_configs():
        raise ValueError(f"Unknown map: {map_name}")
    if not isinstance(changes, dict):
        raise ValueError("events must be an object of event name to fields.")
    known = {entry["name"] for entry in read_events(map_name)}
    clean: dict[str, dict[str, int]] = {}
    for name, fields in changes.items():
        if name not in known:
            raise ValueError(f"Unknown event for {map_name}: {name}")
        if not isinstance(fields, dict):
            raise ValueError(f"Event {name} fields must be an object.")
        entry: dict[str, int] = {}
        for key, value in fields.items():
            if value in ("", None):
                continue
            if key == "active":
                entry["active"] = int(clamp_number(value, f"{name}.active", 0, 1, integer=True))
            elif key in EVENT_FIELD_RANGES:
                low, high = EVENT_FIELD_RANGES[key]
                entry[key] = int(clamp_number(value, f"{name}.{key}", low, high, integer=True))
            else:
                raise ValueError(f"Unknown event field: {key}")
        if "min" in entry and "max" in entry and entry["max"] != 0 and entry["min"] > entry["max"]:
            raise ValueError(f"{name}: min cannot be greater than max.")
        if entry:
            clean[name] = entry
    return clean


def write_events(map_name: str, changes: Any) -> list[str]:
    clean = validate_events_payload(map_name, changes)
    path = events_file_for_map(map_name)
    if not path.exists():
        raise ValueError(f"Missing events file: {safe_rel(path)}")
    tree = ET.parse(path)
    root = tree.getroot()
    by_name = {event.get("name"): event for event in root.findall("event")}
    changed: list[str] = []
    for name, fields in clean.items():
        event = by_name.get(name)
        if event is None:
            continue
        for field, value in fields.items():
            el = event.find(field)
            if el is None:
                el = ET.SubElement(event, field)
            new_value = str(value)
            if (el.text or "") != new_value:
                el.text = new_value
                changed.append(f"{name}.{field}")
    if changed:
        ET.indent(tree, space="    ")
        tree.write(path, encoding="UTF-8", xml_declaration=True)
    return changed


def preview_events(payload: dict[str, Any]) -> dict[str, Any]:
    map_name = str(payload.get("map") or "")
    clean = validate_events_payload(map_name, payload.get("events") or {})
    current = {entry["name"]: entry for entry in read_events(map_name)}
    changes: list[str] = []
    for name, fields in clean.items():
        diffs = [field for field, value in fields.items() if current.get(name, {}).get(field) != value]
        if diffs:
            changes.append(f"{name}: {', '.join(diffs)}")
    file_rel = safe_rel(events_file_for_map(map_name)) if changes else None
    return {
        "changes": changes,
        "files": [file_rel] if file_rel else [],
        "maps": [map_name] if changes else [],
        "restartRequired": bool(changes),
        "needsLootApply": False,
        "snapshot": bool(CONFIG.get("snapshot_before_mutation", True)),
        "snapshotLabel": "control-center-events",
        "hasChanges": bool(changes),
    }


def save_events(payload: dict[str, Any]) -> dict[str, Any]:
    map_name = str(payload.get("map") or "")
    preview = preview_events(payload)
    if not preview["hasChanges"]:
        return {"changed": [], "events": events_payload(map_name)}
    snapshot_for_api("control-center-events")
    changed = write_events(map_name, payload.get("events") or {})
    return {"changed": changed, "events": events_payload(map_name)}


# --- Mission builder --------------------------------------------------------
# Generates Expansion quest contracts into a map's private (git-ignored)
# <profiles_dir>/ExpansionMod/Quests folder. Control-Center missions use a
# dedicated ID range so they never collide with hand-authored or money quests.

MISSION_ID_MIN = 9000
MISSION_ID_MAX = 9999
MISSION_MONEY = "ExpansionBanknoteHryvnia"
MISSION_BOARD_NPC_ID = 100
MISSION_UNITS = [
    "eAI_SurvivorM_Boris",
    "eAI_SurvivorM_Cyril",
    "eAI_SurvivorM_Denis",
    "eAI_SurvivorM_Elias",
    "eAI_SurvivorM_Francis",
    "eAI_SurvivorF_Eva",
    "eAI_SurvivorF_Frida",
    "eAI_SurvivorF_Gabi",
    "eAI_SurvivorF_Helga",
    "eAI_SurvivorF_Irena",
]
MISSION_TYPES = {
    "infected_clear": {
        "label": "Infected clear",
        "help": "Kill a number of infected anywhere on the map.",
        "objectiveType": 2,
        "needsLocation": False,
    },
    "ai_clear": {
        "label": "AI clear",
        "help": "Eliminate a group of hostile AI raiders at a location.",
        "objectiveType": 7,
        "needsLocation": True,
    },
}


def quests_dir_for_map(map_name: str) -> Path:
    cfg = map_configs().get(map_name)
    if cfg is None:
        raise ValueError(f"Unknown map: {map_name}")
    profile = cfg.get("profiles_dir") or f"profiles_{map_name}"
    return ROOT / profile / "ExpansionMod" / "Quests"


def existing_mission_ids(map_name: str) -> list[int]:
    quests = quests_dir_for_map(map_name) / "Quests"
    ids: list[int] = []
    if quests.exists():
        for path in quests.glob("Quest_*.json"):
            match = re.match(r"Quest_(\d+)\.json$", path.name)
            if match:
                value = int(match.group(1))
                if MISSION_ID_MIN <= value <= MISSION_ID_MAX:
                    ids.append(value)
    return sorted(ids)


def next_mission_id(map_name: str) -> int:
    ids = existing_mission_ids(map_name)
    candidate = (max(ids) + 1) if ids else MISSION_ID_MIN
    if candidate > MISSION_ID_MAX:
        raise ValueError("Mission ID range is full. Remove some generated missions first.")
    return candidate


def board_npc_exists(map_name: str) -> bool:
    return (quests_dir_for_map(map_name) / "NPCs" / f"QuestNPC_{MISSION_BOARD_NPC_ID}.json").exists()


def mission_reward(amount: int, class_name: str = MISSION_MONEY) -> dict[str, Any]:
    return {
        "ClassName": class_name,
        "Amount": amount,
        "Attachments": [],
        "DamagePercent": 0,
        "HealthPercent": 0,
        "QuestID": -1,
        "Chance": 1.0,
    }


def mission_target_objective(objective_id: int, objective_text: str, amount: int) -> dict[str, Any]:
    return {
        "ConfigVersion": 28,
        "ID": objective_id,
        "ObjectiveType": 2,
        "ObjectiveText": objective_text,
        "TimeLimit": -1,
        "Active": 1,
        "Position": [0.0, 0.0, 0.0],
        "MaxDistance": -1.0,
        "MinDistance": -1.0,
        "Amount": amount,
        "ClassNames": [],
        "CountSelfKill": 0,
        "AllowedWeapons": [],
        "ExcludedClassNames": [],
        "CountAIPlayers": 0,
        "AllowedTargetFactions": [],
        "AllowedDamageZones": [],
    }


def mission_ring_waypoints(center: list[float]) -> list[list[float]]:
    x, y, z = center
    return [[x, y, z], [x + 90, y, z + 45], [x - 70, y, z + 80], [x - 90, y, z - 40], [x + 60, y, z - 75]]


def mission_ai_objective(objective_id: int, name: str, center: list[float], count: int) -> dict[str, Any]:
    return {
        "ConfigVersion": 28,
        "ID": objective_id,
        "ObjectiveType": 7,
        "ObjectiveText": f"Eliminate the {count} raiders at {name}",
        "TimeLimit": -1,
        "Active": 1,
        "MaxDistance": -1.0,
        "MinDistance": -1.0,
        "AllowedWeapons": [],
        "AllowedDamageZones": [],
        "AISpawn": {
            "Name": name,
            "Persist": 0,
            "Faction": "Raiders",
            "Formation": "RANDOM",
            "FormationScale": 0.0,
            "FormationLooseness": 0.0,
            "Loadout": "PvPLoadout",
            "Units": MISSION_UNITS,
            "NumberOfAI": count,
            "Behaviour": "HALT_OR_LOOP",
            "LootingBehaviour": "",
            "Speed": "JOG",
            "UnderThreatSpeed": "SPRINT",
            "CanBeLooted": 1,
            "UnlimitedReload": 1,
            "SniperProneDistanceThreshold": 300.0,
            "AccuracyMin": 0.42,
            "AccuracyMax": 0.68,
            "ThreatDistanceLimit": 450.0,
            "NoiseInvestigationDistanceLimit": -1.0,
            "DamageMultiplier": 1.0,
            "DamageReceivedMultiplier": 1.0,
            "CanBeTriggeredByAI": 0,
            "MinDistRadius": 50.0,
            "MaxDistRadius": 500.0,
            "DespawnRadius": 700.0,
            "MinSpreadRadius": 0.0,
            "MaxSpreadRadius": 50.0,
            "Chance": 1.0,
            "WaypointInterpolation": "",
            "DespawnTime": 60.0,
            "RespawnTime": 1.0,
            "LoadBalancingCategory": "",
            "UseRandomWaypointAsStartPoint": 1,
            "Waypoints": mission_ring_waypoints(center),
        },
    }


def mission_quest_json(
    quest_id: int,
    title: str,
    description: str,
    objective_text: str,
    rewards: list[dict[str, Any]],
    objective_type: int,
    repeatable: bool,
) -> dict[str, Any]:
    return {
        "ConfigVersion": 22,
        "ID": quest_id,
        "Type": 1,
        "Title": f"[CC] {title}",
        "Descriptions": [description, objective_text, "Created with the Control Center mission builder."],
        "ObjectiveText": objective_text,
        "FollowUpQuest": -1,
        "Repeatable": 1 if repeatable else 0,
        "IsDailyQuest": 0,
        "IsWeeklyQuest": 0,
        "CancelQuestOnPlayerDeath": 0,
        "Autocomplete": 0,
        "IsGroupQuest": 0,
        "ObjectSetFileName": "",
        "QuestItems": [],
        "Rewards": rewards,
        "NeedToSelectReward": 0,
        "RandomReward": 0,
        "RandomRewardAmount": -1,
        "RewardsForGroupOwnerOnly": 1,
        "RewardBehavior": 0,
        "QuestGiverIDs": [MISSION_BOARD_NPC_ID],
        "QuestTurnInIDs": [MISSION_BOARD_NPC_ID],
        "IsAchievement": 0,
        "Objectives": [{"ConfigVersion": 28, "ID": quest_id, "ObjectiveType": objective_type}],
        "QuestColor": 0,
        "ReputationReward": 0,
        "ReputationRequirement": -1,
        "PreQuestIDs": [],
        "RequiredFaction": "",
        "FactionReward": "",
        "PlayerNeedQuestItems": 1,
        "DeleteQuestItems": 1,
        "SequentialObjectives": 1,
        "FactionReputationRequirements": {},
        "FactionReputationRewards": {},
        "SuppressQuestLogOnCompetion": 0,
        "Active": 1,
    }


def validate_mission_payload(payload: dict[str, Any]) -> dict[str, Any]:
    map_name = str(payload.get("map") or "").lower()
    if map_name not in map_configs():
        raise ValueError(f"Unknown map: {map_name}")
    mtype = str(payload.get("type") or "")
    if mtype not in MISSION_TYPES:
        raise ValueError(f"Unknown mission type: {mtype}")
    title = str(payload.get("title") or "").strip()
    if not title:
        raise ValueError("Title is required.")
    if len(title) > 80:
        raise ValueError("Title must be 80 characters or fewer.")
    description = (str(payload.get("description") or title).strip())[:300]
    payout = int(clamp_number(payload.get("payout", 0), "payout", 0, 1_000_000, integer=True))
    amount = int(clamp_number(payload.get("amount", 1), "amount", 1, 500, integer=True))
    repeatable = bool(payload.get("repeatable", True))
    objective_text = (str(payload.get("objectiveText") or "").strip())[:200]

    spec: dict[str, Any] = {
        "map": map_name,
        "type": mtype,
        "title": title,
        "description": description,
        "payout": payout,
        "amount": amount,
        "repeatable": repeatable,
        "objectiveText": objective_text,
    }

    if MISSION_TYPES[mtype]["needsLocation"]:
        location = payload.get("location") or []
        if not (isinstance(location, list) and len(location) == 3):
            raise ValueError("This mission type requires a location [x, y, z].")
        spec["location"] = [float(clamp_number(value, "location", -100000, 100000)) for value in location]
        spec["aiName"] = (str(payload.get("aiName") or title).strip())[:60]

    item = payload.get("itemReward")
    if isinstance(item, dict):
        class_name = str(item.get("className") or "").strip()
        if class_name:
            item_amount = int(clamp_number(item.get("amount", 1), "itemReward.amount", 1, 500, integer=True))
            spec["itemReward"] = {"className": class_name, "amount": item_amount}

    return spec


def build_mission_files(spec: dict[str, Any], quest_id: int) -> list[tuple[str, dict[str, Any]]]:
    label = map_configs()[spec["map"]].get("title", spec["map"])
    rewards = [mission_reward(spec["payout"])]
    if spec.get("itemReward"):
        rewards.append(mission_reward(spec["itemReward"]["amount"], spec["itemReward"]["className"]))

    files: list[tuple[str, dict[str, Any]]] = []
    if spec["type"] == "infected_clear":
        objective_text = spec["objectiveText"] or f"Kill {spec['amount']} infected anywhere in {label}"
        files.append(
            (f"Objectives/Target/Objective_TA_{quest_id}.json", mission_target_objective(quest_id, objective_text, spec["amount"]))
        )
        objective_type = 2
    else:
        objective_text = spec["objectiveText"] or f"Eliminate {spec['amount']} raiders at {spec['aiName']}"
        files.append(
            (f"Objectives/AIPatrol/Objective_AIP_{quest_id}.json", mission_ai_objective(quest_id, spec["aiName"], spec["location"], spec["amount"]))
        )
        objective_type = 7

    files.append(
        (
            f"Quests/Quest_{quest_id}.json",
            mission_quest_json(quest_id, spec["title"], spec["description"], objective_text, rewards, objective_type, spec["repeatable"]),
        )
    )
    return files


def missions_payload(map_name: str) -> dict[str, Any]:
    if map_name not in map_configs():
        raise ValueError(f"Unknown map: {map_name}")
    quests = quests_dir_for_map(map_name) / "Quests"
    missions: list[dict[str, Any]] = []
    for quest_id in existing_mission_ids(map_name):
        data = read_json(quests / f"Quest_{quest_id}.json", {})
        objectives = data.get("Objectives") or [{}]
        missions.append(
            {
                "id": quest_id,
                "title": data.get("Title", ""),
                "active": data.get("Active", 1),
                "repeatable": data.get("Repeatable", 0),
                "rewards": [
                    {"className": reward.get("ClassName"), "amount": reward.get("Amount")}
                    for reward in data.get("Rewards", [])
                ],
                "objectiveType": objectives[0].get("ObjectiveType"),
            }
        )
    return {
        "map": map_name,
        "questsDir": safe_rel(quests_dir_for_map(map_name)),
        "boardNpcExists": board_npc_exists(map_name),
        "moneyClass": MISSION_MONEY,
        "nextId": next_mission_id(map_name),
        "types": [
            {"key": key, "label": value["label"], "help": value["help"], "needsLocation": value["needsLocation"]}
            for key, value in MISSION_TYPES.items()
        ],
        "missions": missions,
    }


def preview_mission(payload: dict[str, Any]) -> dict[str, Any]:
    spec = validate_mission_payload(payload)
    quest_id = next_mission_id(spec["map"])
    files = build_mission_files(spec, quest_id)
    quests_dir = quests_dir_for_map(spec["map"])
    file_entries = [{"path": safe_rel(quests_dir / rel), "exists": (quests_dir / rel).exists()} for rel, _ in files]
    summary = [
        f"Type: {MISSION_TYPES[spec['type']]['label']}",
        f"Reward: {spec['payout']} {MISSION_MONEY}",
    ]
    if spec.get("itemReward"):
        summary.append(f"Item reward: {spec['itemReward']['amount']}x {spec['itemReward']['className']}")
    summary.append("Repeatable" if spec["repeatable"] else "One-time")
    return {
        "map": spec["map"],
        "questId": quest_id,
        "title": spec["title"],
        "boardNpcExists": board_npc_exists(spec["map"]),
        "files": file_entries,
        "summary": summary,
        "questJson": files[-1][1],
        "restartRequired": True,
        "snapshot": bool(CONFIG.get("snapshot_before_mutation", True)),
        "snapshotLabel": "control-center-mission",
        "hasChanges": True,
    }


def install_mission(payload: dict[str, Any]) -> dict[str, Any]:
    spec = validate_mission_payload(payload)
    quest_id = next_mission_id(spec["map"])
    files = build_mission_files(spec, quest_id)
    quests_dir = quests_dir_for_map(spec["map"])
    for rel, _ in files:
        if (quests_dir / rel).exists():
            raise ValueError(f"Refusing to overwrite existing file: {rel}")
    snapshot_for_api("control-center-mission")
    written: list[str] = []
    for rel, data in files:
        path = quests_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        written.append(safe_rel(path))
    return {"map": spec["map"], "questId": quest_id, "written": written, "missions": missions_payload(spec["map"])}


def validate_mission_ref(payload: dict[str, Any]) -> tuple[str, int, Path]:
    map_name = str(payload.get("map") or "").lower()
    if map_name not in map_configs():
        raise ValueError(f"Unknown map: {map_name}")
    try:
        quest_id = int(payload.get("id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Mission id must be a number.") from exc
    if not (MISSION_ID_MIN <= quest_id <= MISSION_ID_MAX):
        raise ValueError("Only Control Center missions (9000-9999) can be managed here.")
    quest_path = quests_dir_for_map(map_name) / "Quests" / f"Quest_{quest_id}.json"
    if not quest_path.exists():
        raise ValueError(f"Mission {quest_id} not found on {map_name}.")
    return map_name, quest_id, quest_path


def mission_update_fields(payload: dict[str, Any]) -> dict[str, int]:
    fields: dict[str, int] = {}
    if payload.get("payout") not in ("", None):
        fields["payout"] = int(clamp_number(payload["payout"], "payout", 0, 1_000_000, integer=True))
    if "active" in payload:
        fields["active"] = 1 if bool(payload["active"]) else 0
    if "repeatable" in payload:
        fields["repeatable"] = 1 if bool(payload["repeatable"]) else 0
    return fields


def preview_mission_update(payload: dict[str, Any]) -> dict[str, Any]:
    map_name, _quest_id, quest_path = validate_mission_ref(payload)
    fields = mission_update_fields(payload)
    data = read_json(quest_path, {})
    changes: list[str] = []
    if "payout" in fields:
        current = (data.get("Rewards") or [{}])[0].get("Amount")
        if current != fields["payout"]:
            changes.append(f"payout {current} -> {fields['payout']}")
    if "active" in fields and data.get("Active") != fields["active"]:
        changes.append(f"active -> {fields['active']}")
    if "repeatable" in fields and data.get("Repeatable") != fields["repeatable"]:
        changes.append(f"repeatable -> {fields['repeatable']}")
    return {
        "changes": changes,
        "files": [safe_rel(quest_path)] if changes else [],
        "maps": [map_name] if changes else [],
        "restartRequired": bool(changes),
        "needsLootApply": False,
        "snapshot": bool(CONFIG.get("snapshot_before_mutation", True)),
        "snapshotLabel": "control-center-mission",
        "hasChanges": bool(changes),
    }


def update_mission(payload: dict[str, Any]) -> dict[str, Any]:
    map_name, _quest_id, quest_path = validate_mission_ref(payload)
    preview = preview_mission_update(payload)
    if not preview["hasChanges"]:
        return {"changed": [], "missions": missions_payload(map_name)}
    fields = mission_update_fields(payload)
    snapshot_for_api("control-center-mission")
    data = read_json(quest_path, {})
    changed: list[str] = []
    if "payout" in fields and data.get("Rewards"):
        if data["Rewards"][0].get("Amount") != fields["payout"]:
            data["Rewards"][0]["Amount"] = fields["payout"]
            changed.append("payout")
    if "active" in fields and data.get("Active") != fields["active"]:
        data["Active"] = fields["active"]
        changed.append("active")
    if "repeatable" in fields and data.get("Repeatable") != fields["repeatable"]:
        data["Repeatable"] = fields["repeatable"]
        changed.append("repeatable")
    if changed:
        quest_path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    return {"changed": changed, "missions": missions_payload(map_name)}


def mission_file_paths(map_name: str, quest_id: int) -> list[Path]:
    quests_dir = quests_dir_for_map(map_name)
    paths = [quests_dir / "Quests" / f"Quest_{quest_id}.json"]
    paths.append(quests_dir / "Objectives" / "Target" / f"Objective_TA_{quest_id}.json")
    paths.append(quests_dir / "Objectives" / "AIPatrol" / f"Objective_AIP_{quest_id}.json")
    return paths


def remove_mission(payload: dict[str, Any]) -> dict[str, Any]:
    map_name, quest_id, _quest_path = validate_mission_ref(payload)
    if str(payload.get("confirm") or "") != "REMOVE":
        raise ValueError("Removing a mission requires confirmation text: REMOVE")
    quests_root = quests_dir_for_map(map_name).resolve()
    snapshot_for_api("control-center-mission")
    removed: list[str] = []
    for path in mission_file_paths(map_name, quest_id):
        if not path.exists():
            continue
        if not str(path.resolve()).startswith(str(quests_root)):
            raise ValueError("Refusing to delete a path outside the map Quests folder.")
        path.unlink()
        removed.append(safe_rel(path))
    return {"removed": removed, "missions": missions_payload(map_name)}


def powershell_file(script: str, *args: str) -> list[str]:
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ADMIN / script), *args]


def python_file(script: str, *args: str) -> list[str]:
    if FROZEN:
        return [sys.executable, "--server-root", str(ROOT), "--run-admin-script", script, *args]
    return [sys.executable, str(ADMIN / script), *args]


def powershell_command(command: str) -> list[str]:
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]


@dataclass(frozen=True)
class ActionSpec:
    label: str
    group: str
    description: str
    risk: str
    builder: Callable[[dict[str, Any], str | None], list[list[str]]]
    map_mode: str = "none"
    timeout: int = 180
    snapshot: bool = False
    confirm: str | None = None


def map_or_all(payload: dict[str, Any], maps: dict[str, Any]) -> str:
    value = str(payload.get("map") or "all").lower()
    if value != "all" and value not in maps:
        raise ValueError(f"Unknown map: {value}")
    return value


def one_map(payload: dict[str, Any], maps: dict[str, Any]) -> str:
    value = str(payload.get("map") or "").lower()
    if not value or value == "all":
        raise ValueError("This action requires one map.")
    if value not in maps:
        raise ValueError(f"Unknown map: {value}")
    return value


def imported_or_all(payload: dict[str, Any], maps: dict[str, Any]) -> str:
    value = str(payload.get("map") or "").lower()
    allowed = imported_maps()
    if value == "all-imported":
        return value
    if not value:
        raise ValueError("This action requires an imported map or all-imported.")
    if value not in allowed:
        raise ValueError(f"Map must be imported: {', '.join(sorted(allowed))}, or all-imported")
    return value


def action_specs() -> dict[str, ActionSpec]:
    return {
        "status_all": ActionSpec(
            "Status all maps",
            "diagnostics",
            "Print compact AI, loot, events, and map status.",
            "read",
            lambda _p, _m: [python_file("status_all.py")],
        ),
        "check_map_launch": ActionSpec(
            "Check map launch",
            "diagnostics",
            "Verify configs, ports, missions, and mod folders.",
            "read",
            lambda _p, m: [powershell_file("check_map_launch.ps1", "-Map", m or "all")],
            map_mode="all",
            timeout=240,
        ),
        "check_admin_tooling": ActionSpec(
            "Check VPP admin tooling",
            "maintenance",
            "Verify VPP mod lists, profile files, inputs, and Desktop launchers.",
            "read",
            lambda _p, m: [
                powershell_file(
                    "check_admin_tooling.ps1",
                    "-Map",
                    m or "all",
                    "-IncludeClientProfiles",
                    "-CheckDesktop",
                )
            ],
            map_mode="all",
            timeout=240,
        ),
        "validate_public_repo": ActionSpec(
            "Validate public repo",
            "maintenance",
            "Check tracked files for parse errors, private paths, and secrets.",
            "read",
            lambda _p, _m: [python_file("validate_public_repo.py")],
        ),
        "validate_imported_maps": ActionSpec(
            "Validate imported maps",
            "maintenance",
            "Check imported-map cleanup guardrails and Expansion safety.",
            "read",
            lambda _p, _m: [python_file("validate_imported_maps.py")],
        ),
        "triage_logs": ActionSpec(
            "Triage latest logs",
            "diagnostics",
            "Scan recent RPT/script logs for likely blockers.",
            "read",
            lambda _p, m: [python_file("triage_latest_logs.py", "--map", m or "all")],
            map_mode="all",
        ),
        "config_drift": ActionSpec(
            "Check config drift",
            "diagnostics",
            "Compare launch config, real configs, examples, and start helpers.",
            "read",
            lambda _p, m: [python_file("check_config_drift.py", "--map", m or "all")],
            map_mode="all",
        ),
        "lan_visibility_check": ActionSpec(
            "Check LAN visibility",
            "diagnostics",
            "Check UDP endpoints and A2S visibility without repairing firewall.",
            "read",
            lambda _p, m: [powershell_file("check_lan_visibility.ps1", "-Map", m or "all")],
            map_mode="all",
            timeout=240,
        ),
        "snapshot_configs": ActionSpec(
            "Create config snapshot",
            "maintenance",
            "Create an ignored local zip backup of public-safe configs and local server cfg files.",
            "guarded",
            lambda _p, _m: [python_file("snapshot_configs.py", "--label", "control-center")],
            timeout=240,
        ),
        "apply_loot_current": ActionSpec(
            "Apply active loot preset",
            "generation",
            "Rebuild and replicate mod_ce, patch globals, and save the current active loot preset.",
            "guarded",
            lambda _p, _m: [python_file("apply_loot.py", "all")],
            timeout=900,
            snapshot=True,
        ),
        "smoke_test_map": ActionSpec(
            "Smoke test one map",
            "map",
            "Start one map, wait for Player connect enabled, query A2S, and stop it.",
            "guarded",
            lambda _p, m: [powershell_file("smoke_test_map.ps1", "-Map", m or "", "-TimeoutSeconds", "240")],
            map_mode="one",
            timeout=420,
            snapshot=True,
        ),
        "sync_vpp_profiles": ActionSpec(
            "Sync VPP profiles",
            "maintenance",
            "Copy local private VPP credentials/SuperAdmin files to map profiles.",
            "guarded",
            lambda _p, m: [powershell_file("sync_vpp_admin_profiles.ps1", "-Map", m or "all")],
            map_mode="all",
            snapshot=True,
        ),
        "repair_vpp_inputs": ActionSpec(
            "Repair VPP inputs",
            "maintenance",
            "Remove stale COT inputs and bind VPP to End/Home in server and client presets.",
            "guarded",
            lambda _p, m: [
                powershell_file("switch_admin_inputs_to_vpp.ps1", "-Map", m or "all", "-IncludeClientProfiles")
            ],
            map_mode="all",
            snapshot=True,
        ),
        "sync_desktop_launchers": ActionSpec(
            "Sync Desktop launchers",
            "maintenance",
            "Regenerate the Desktop start_*.bat files from map_launch.json.",
            "guarded",
            lambda _p, _m: [powershell_file("sync_desktop_launchers.ps1")],
            timeout=120,
            snapshot=True,
        ),
        "restore_snapshot": ActionSpec(
            "Restore config snapshot",
            "backup",
            "Overwrite current public-safe configs with a chosen snapshot. Snapshots current state first.",
            "high",
            lambda payload, _m: [
                python_file("snapshot_configs.py", "--restore", str(validate_snapshot_name(payload)), "--yes")
            ],
            timeout=240,
            snapshot=True,
            confirm="RESTORE",
        ),
        "start_map": ActionSpec(
            "Start map server",
            "lifecycle",
            "Launch one map in a new console via Launch-DayZMap.ps1 and leave it running.",
            "guarded",
            lambda _p, m: [powershell_file("server_lifecycle.ps1", "-Action", "start", "-Map", m or "")],
            map_mode="one",
            timeout=120,
        ),
        "stop_map": ActionSpec(
            "Stop map server",
            "lifecycle",
            "Stop only the DayZServer_x64 process for the selected map (matched by its launch port).",
            "high",
            lambda _p, m: [powershell_file("server_lifecycle.ps1", "-Action", "stop", "-Map", m or "")],
            map_mode="one",
            timeout=90,
            confirm="STOP",
        ),
        "restart_map": ActionSpec(
            "Restart map server",
            "lifecycle",
            "Stop the selected map (if running) and start it again via Launch-DayZMap.ps1.",
            "high",
            lambda _p, m: [powershell_file("server_lifecycle.ps1", "-Action", "restart", "-Map", m or "")],
            map_mode="one",
            timeout=150,
            confirm="RESTART",
        ),
        "repair_firewall": ActionSpec(
            "Repair DayZ firewall rules",
            "lifecycle",
            "Repair Windows Firewall rules and re-check LAN/A2S visibility for the selected map(s).",
            "guarded",
            lambda _p, m: [powershell_file("check_lan_visibility.ps1", "-Map", m or "all", "-RepairFirewall")],
            map_mode="all",
            timeout=240,
        ),
        "install_steamcmd": ActionSpec(
            "Install SteamCMD",
            "updates",
            "Download SteamCMD into local_runtime and run its first-time self-update (no login).",
            "guarded",
            lambda _p, _m: [powershell_file("steamcmd_update.ps1", "-Action", "install")],
            timeout=600,
        ),
        "steam_login": ActionSpec(
            "Log in to Steam",
            "updates",
            "Open a SteamCMD console to log in once (password + Steam Guard). The session is cached.",
            "guarded",
            lambda _p, _m: [
                powershell_file(
                    "steamcmd_update.ps1", "-Action", "login",
                    "-SteamCmd", str(require_steamcmd()), "-Username", require_steam_username(),
                )
            ],
            timeout=60,
        ),
        "update_server": ActionSpec(
            "Update DayZ server",
            "updates",
            "Open a SteamCMD console to update and validate the dedicated server (app 223350). Stop servers first.",
            "guarded",
            lambda _p, _m: [
                powershell_file(
                    "steamcmd_update.ps1", "-Action", "update-server",
                    "-SteamCmd", str(require_steamcmd()), "-Username", require_steam_username(),
                    "-ServerDir", str(ROOT),
                )
            ],
            timeout=60,
        ),
        "update_mods": ActionSpec(
            "Update Workshop mods",
            "updates",
            "Open a SteamCMD console to download the latest imported-map Workshop mods, then Sync Workshop mods.",
            "guarded",
            lambda _p, _m: [
                powershell_file(
                    "steamcmd_update.ps1", "-Action", "update-mods",
                    "-SteamCmd", str(require_steamcmd()), "-Username", require_steam_username(),
                    "-ModIds", ",".join(catalog_mod_ids()) or "0",
                )
            ],
            timeout=60,
        ),
        "stop_dayz_servers": ActionSpec(
            "Stop DayZ server processes",
            "high-risk",
            "Force-stop running DayZServer_x64.exe processes.",
            "high",
            lambda _p, _m: [
                powershell_command(
                    "$p=Get-Process DayZServer_x64 -ErrorAction SilentlyContinue; "
                    "if ($p) { $ids=($p|ForEach-Object Id) -join ', '; "
                    "Write-Host \"Stopping DayZServer_x64.exe PID(s): $ids\"; "
                    "$p | Stop-Process -Force; Start-Sleep -Seconds 2 } "
                    "else { Write-Host 'No DayZServer_x64.exe processes running.' }"
                )
            ],
            timeout=90,
            snapshot=True,
            confirm="STOP",
        ),
        "wipe_imported_storage": ActionSpec(
            "Wipe imported storage",
            "high-risk",
            "Delete imported-map storage_* folders and risky generated Expansion placements.",
            "high",
            lambda _p, _m: [python_file("sanitize_imported_expansion.py", "--wipe-storage")],
            timeout=360,
            snapshot=True,
            confirm="WIPE",
        ),
        "recover_imported_map": ActionSpec(
            "Recover imported map",
            "high-risk",
            "Sanitize imported maps, tune spawns/CE safety, validate, and smoke test.",
            "high",
            lambda _p, m: [powershell_file("recover_imported_map.ps1", "-Map", m or "", "-StopExisting")],
            map_mode="imported",
            timeout=1200,
            snapshot=True,
            confirm="RECOVER",
        ),
        "full_generation_refresh": ActionSpec(
            "Full generation refresh",
            "generation",
            "Run the documented full refresh for Expansion, AI ammo, loot, CE safety, events, and validation.",
            "high",
            lambda _p, _m: [
                python_file("build_map_expansion.py", "--all"),
                python_file("seed_imported_cot_locations.py"),
                python_file("sanitize_imported_expansion.py"),
                python_file("build_map_expansion.py", "--imported"),
                python_file("tune_player_spawns.py"),
                python_file("apply_ai_ammo.py"),
                python_file("apply_loot.py", "all", "--preset", "arcade"),
                python_file("tune_imported_ce_safety.py"),
                python_file("tune_ce_overtime.py", "--map", "all"),
                python_file("tune_chernarus_spawn_economy.py"),
                python_file("install_money_quests.py"),
                python_file("tune_quest_ai.py"),
                python_file("standardize_world_events.py"),
                python_file("status_all.py"),
                python_file("validate_imported_maps.py"),
                python_file("validate_public_repo.py"),
            ],
            timeout=1800,
            snapshot=True,
            confirm="REFRESH",
        ),
    }


@dataclass
class Job:
    id: str
    action: str
    label: str
    map: str | None
    risk: str
    status: str = "queued"
    created_at: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    started_at: str | None = None
    ended_at: str | None = None
    returncode: int | None = None
    output: str = ""
    commands: list[str] = field(default_factory=list)
    error: str | None = None

    def append(self, text: str) -> None:
        self.output = (self.output + text)[-MAX_OUTPUT_CHARS:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "label": self.label,
            "map": self.map,
            "risk": self.risk,
            "status": self.status,
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "endedAt": self.ended_at,
            "returncode": self.returncode,
            "output": self.output,
            "commands": self.commands,
            "error": self.error,
        }


class JobStore:
    def __init__(self, retention: int) -> None:
        self.retention = retention
        self.lock = threading.Lock()
        self.jobs: dict[str, Job] = {}
        RUNTIME.mkdir(parents=True, exist_ok=True)

    def add(self, job: Job) -> None:
        with self.lock:
            self.jobs[job.id] = job
            self._prune_locked()
            self._write_locked(job)

    def update(self, job: Job) -> None:
        with self.lock:
            self.jobs[job.id] = job
            self._write_locked(job)

    def get(self, job_id: str) -> Job | None:
        with self.lock:
            return self.jobs.get(job_id)

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            jobs = sorted(self.jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [job.to_dict() for job in jobs]

    def _prune_locked(self) -> None:
        if len(self.jobs) <= self.retention:
            return
        sorted_jobs = sorted(self.jobs.values(), key=lambda item: item.created_at, reverse=True)
        keep = {job.id for job in sorted_jobs[: self.retention]}
        self.jobs = {job_id: job for job_id, job in self.jobs.items() if job_id in keep}

    def _write_locked(self, job: Job) -> None:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        write_json(RUNTIME / f"{job.id}.json", job.to_dict())


CONFIG: dict[str, Any] = {}
JOBS = JobStore(50)


def command_display(args: list[str]) -> str:
    display = []
    for item in args:
        if " " in item or ";" in item:
            display.append(f'"{item}"')
        else:
            display.append(item)
    return redact(" ".join(display))


def run_command(args: list[str], timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        output = proc.stdout
        if proc.stderr:
            output += "\n" + proc.stderr
        return proc.returncode, redact(output)
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\n" + (exc.stderr or "")
        return 124, redact(output + f"\nTimed out after {timeout} seconds.\n")


def selected_map_for(spec: ActionSpec, payload: dict[str, Any]) -> str | None:
    maps = map_configs()
    if spec.map_mode == "all":
        return map_or_all(payload, maps)
    if spec.map_mode == "one":
        return one_map(payload, maps)
    if spec.map_mode == "imported":
        return imported_or_all(payload, maps)
    return None


def start_action(payload: dict[str, Any]) -> Job:
    specs = action_specs()
    action = str(payload.get("action") or "")
    if action not in specs:
        raise ValueError(f"Unknown action: {action}")
    spec = specs[action]
    confirm = str(payload.get("confirm") or "")
    if spec.confirm and confirm != spec.confirm:
        raise ValueError(f"Action requires confirmation text: {spec.confirm}")
    selected_map = selected_map_for(spec, payload)
    commands = spec.builder(payload, selected_map)
    if not commands:
        raise ValueError("Action has no commands.")

    job = Job(
        id=uuid.uuid4().hex[:12],
        action=action,
        label=spec.label,
        map=selected_map,
        risk=spec.risk,
        commands=[command_display(command) for command in commands],
    )
    JOBS.add(job)
    thread = threading.Thread(target=run_job, args=(job, spec, commands), daemon=True)
    thread.start()
    return job


def run_job(job: Job, spec: ActionSpec, commands: list[list[str]]) -> None:
    job.status = "running"
    job.started_at = dt.datetime.now().isoformat(timespec="seconds")
    JOBS.update(job)
    try:
        all_commands = list(commands)
        if spec.snapshot and CONFIG.get("snapshot_before_mutation", True):
            all_commands.insert(0, python_file("snapshot_configs.py", "--label", "control-center"))

        final_code = 0
        for index, command in enumerate(all_commands, start=1):
            job.append(f"\n$ {command_display(command)}\n")
            JOBS.update(job)
            code, output = run_command(command, spec.timeout)
            if output:
                job.append(output if output.endswith("\n") else output + "\n")
            final_code = code
            JOBS.update(job)
            if code != 0:
                job.append(f"\nCommand {index} failed with exit code {code}.\n")
                break
        job.returncode = final_code
        job.status = "succeeded" if final_code == 0 else "failed"
    except Exception as exc:  # noqa: BLE001 - keep local UI jobs from dying silently.
        job.status = "failed"
        job.returncode = 1
        job.error = str(exc)
        job.append(f"\nERROR: {exc}\n")
    finally:
        job.ended_at = dt.datetime.now().isoformat(timespec="seconds")
        JOBS.update(job)


def actions_payload() -> list[dict[str, Any]]:
    items = []
    for key, spec in action_specs().items():
        items.append(
            {
                "key": key,
                "label": spec.label,
                "group": spec.group,
                "description": spec.description,
                "risk": spec.risk,
                "mapMode": spec.map_mode,
                "confirm": spec.confirm,
            }
        )
    return items


def logs_payload(map_name: str, limit: int) -> dict[str, Any]:
    maps = map_configs()
    if map_name not in maps:
        raise ValueError(f"Unknown map: {map_name}")
    profile = maps[map_name].get("profiles_dir") or f"profiles_{map_name}"
    log = newest_log(ROOT / profile)
    if not log:
        return {"map": map_name, "file": None, "lines": []}
    max_lines = min(max(1, limit), int(CONFIG.get("max_log_lines", 400)))
    return {"map": map_name, "file": safe_rel(log), "lines": tail_file(log, max_lines)}


class Handler(BaseHTTPRequestHandler):
    server_version = "DayZControlCenter/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        log_message("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def send_json(self, status: int, data: Any) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: int, message: str) -> None:
        self.send_json(status, {"error": message})

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API.
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/api/maps":
                self.send_json(200, maps_payload())
            elif path == "/api/app":
                self.send_json(200, app_payload())
            elif path == "/api/setup":
                self.send_json(200, setup_payload())
            elif path == "/api/troubleshooting":
                self.send_json(200, troubleshooting_payload())
            elif path == "/api/events":
                map_name = str(query.get("map", [""])[0]).lower()
                self.send_json(200, events_payload(map_name))
            elif path == "/api/missions":
                map_name = str(query.get("map", [""])[0]).lower()
                self.send_json(200, missions_payload(map_name))
            elif path == "/api/status":
                self.send_json(200, status_payload())
            elif path == "/api/balance":
                self.send_json(200, balance_payload())
            elif path == "/api/actions":
                self.send_json(200, actions_payload())
            elif path == "/api/jobs":
                self.send_json(200, JOBS.list())
            elif path.startswith("/api/jobs/"):
                job_id = path.rsplit("/", 1)[-1]
                job = JOBS.get(job_id)
                if not job:
                    self.send_error_json(404, "Job not found.")
                else:
                    self.send_json(200, job.to_dict())
            elif path == "/api/logs":
                map_name = str(query.get("map", [""])[0]).lower()
                limit = int(query.get("lines", ["200"])[0])
                self.send_json(200, logs_payload(map_name, limit))
            elif path == "/api/report":
                map_name = str(query.get("map", ["all"])[0]).lower()
                self.send_json(200, report_payload(map_name))
            elif path == "/api/snapshots":
                self.send_json(200, snapshots_payload())
            elif path == "/api/rcon/status":
                map_name = str(query.get("map", [""])[0]).lower()
                self.send_json(200, rcon_status_payload(rcon_map(map_name)))
            elif path == "/api/schedules":
                self.send_json(200, SCHEDULER.payload())
            elif path == "/api/updates/status":
                self.send_json(200, updates_status_payload())
            elif path == "/api/mods/updates":
                check = str(query.get("check", ["0"])[0]).lower() in {"1", "true", "yes"}
                self.send_json(200, mods_updates_payload(check))
            elif path == "/api/lan/visibility":
                self.send_json(200, lan_visibility_payload())
            elif path == "/api/watchdog":
                self.send_json(200, WATCHDOG.payload())
            elif path == "/api/players":
                map_name = str(query.get("map", [""])[0]).lower()
                self.send_json(200, players_payload(map_name))
            elif path == "/api/killfeed":
                map_name = str(query.get("map", [""])[0]).lower()
                limit = int(query.get("limit", ["60"])[0])
                self.send_json(200, killfeed_payload(map_name, limit))
            elif path.startswith("/api/"):
                self.send_error_json(404, "Unknown API route.")
            else:
                self.serve_static(path)
        except Exception as exc:  # noqa: BLE001 - report UI errors as JSON where possible.
            if self.path.startswith("/api/"):
                self.send_error_json(500, str(exc))
            else:
                self.send_error(500, str(exc))

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API.
        try:
            parsed = urlparse(self.path)
            if parsed.path not in {
                "/api/actions/run",
                "/api/balance/save",
                "/api/balance/preview",
                "/api/events/preview",
                "/api/events/save",
                "/api/missions/preview",
                "/api/missions/install",
                "/api/missions/update/preview",
                "/api/missions/update",
                "/api/missions/remove",
                "/api/setup/save",
                "/api/rcon/enable",
                "/api/rcon/run",
                "/api/schedules/save",
                "/api/schedules/remove",
                "/api/updates/settings",
                "/api/players/note",
                "/api/watchdog/set",
            }:
                self.send_error_json(404, "Unknown API route.")
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > 20_000:
                self.send_error_json(413, "Request body too large.")
                return
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw or "{}")
            if parsed.path == "/api/balance/save":
                self.send_json(200, save_balance(payload))
            elif parsed.path == "/api/balance/preview":
                self.send_json(200, preview_balance(payload))
            elif parsed.path == "/api/events/preview":
                self.send_json(200, preview_events(payload))
            elif parsed.path == "/api/events/save":
                self.send_json(200, save_events(payload))
            elif parsed.path == "/api/missions/preview":
                self.send_json(200, preview_mission(payload))
            elif parsed.path == "/api/missions/install":
                self.send_json(200, install_mission(payload))
            elif parsed.path == "/api/missions/update/preview":
                self.send_json(200, preview_mission_update(payload))
            elif parsed.path == "/api/missions/update":
                self.send_json(200, update_mission(payload))
            elif parsed.path == "/api/missions/remove":
                self.send_json(200, remove_mission(payload))
            elif parsed.path == "/api/setup/save":
                write_setup_state(payload)
                self.send_json(200, setup_payload())
            elif parsed.path == "/api/rcon/enable":
                self.send_json(200, enable_rcon(payload))
            elif parsed.path == "/api/rcon/run":
                self.send_json(200, run_rcon(payload))
            elif parsed.path == "/api/schedules/save":
                self.send_json(200, SCHEDULER.save_schedule(payload))
            elif parsed.path == "/api/schedules/remove":
                self.send_json(200, SCHEDULER.remove_schedule(payload))
            elif parsed.path == "/api/updates/settings":
                self.send_json(200, save_updates_settings(payload))
            elif parsed.path == "/api/players/note":
                self.send_json(200, save_player_note(payload))
            elif parsed.path == "/api/watchdog/set":
                self.send_json(200, WATCHDOG.set_enabled(payload))
            else:
                job = start_action(payload)
                self.send_json(202, job.to_dict())
        except ValueError as exc:
            self.send_error_json(400, str(exc))
        except json.JSONDecodeError as exc:
            self.send_error_json(400, f"Invalid JSON: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.send_error_json(500, str(exc))

    def serve_static(self, request_path: str) -> None:
        if request_path in {"", "/"}:
            request_path = "/index.html"
        rel = unquote(request_path).lstrip("/")
        target = (STATIC / rel).resolve()
        if not str(target).startswith(str(STATIC.resolve())):
            self.send_error(403)
            return
        if not target.exists() or not target.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--no-open-browser", action="store_true", help="Do not auto-open a browser when bundled as an EXE.")
    parser.add_argument("--server-root", help="Path to the DayZServer root containing admin\\map_launch.json.")
    parser.add_argument("--run-admin-script", help=argparse.SUPPRESS)
    args, script_args = parser.parse_known_args()
    if script_args and not args.run_admin_script:
        parser.error(f"unrecognized arguments: {' '.join(script_args)}")
    args.script_args = script_args
    return args


def run_admin_script(script: str, script_args: list[str], cli_root: str | None) -> int:
    if not configure_server_root(cli_root):
        return 2
    script_name = Path(script).name
    if script != script_name or not script_name.endswith(".py"):
        safe_print(f"Refusing unsafe admin script path: {script}")
        return 2
    script_path = ADMIN / script_name
    if not script_path.exists():
        safe_print(f"Missing admin script: {script_path}")
        return 2

    os.chdir(ROOT)
    old_argv = sys.argv
    sys.argv = [str(script_path), *script_args]
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        safe_print(str(code))
        return 1
    finally:
        sys.argv = old_argv
    return 0


def main() -> int:
    global CONFIG
    args = parse_args()
    if args.run_admin_script:
        return run_admin_script(args.run_admin_script, args.script_args, args.server_root)
    if not configure_server_root(args.server_root):
        return 2
    config = load_config()
    CONFIG = config
    JOBS.retention = int(config.get("job_retention", 50))
    host = args.host or config.get("host", "127.0.0.1")
    port = args.port or int(config.get("port", 8765))
    if host not in {"127.0.0.1", "localhost"} and not config.get("allow_remote_bind", False):
        safe_print("Refusing remote bind. Set allow_remote_bind=true in admin/control_center_config.json first.")
        return 2
    if not LAUNCH_PATH.exists():
        safe_print(f"Missing {LAUNCH_PATH}")
        return 1
    if not STATIC.exists():
        safe_print(f"Missing {STATIC}")
        return 1
    SCHEDULER.start()
    WATCHDOG.start()
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    safe_print(f"DayZ Server Control Center running at {url}")
    safe_print(f"DayZServer root: {ROOT}")
    safe_print("Press Ctrl+C to stop.")
    should_open_browser = args.open_browser or (FROZEN and not args.no_open_browser)
    if should_open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        safe_print("Stopping control center.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        log_message(f"Fatal startup error: {exc!r}")
        raise
