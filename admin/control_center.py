#!/usr/bin/env python3
"""Local browser control center for the DayZ server automation toolkit."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
ADMIN = ROOT / "admin"
STATIC = ADMIN / "control_center"
RUNTIME = ROOT / "local_runtime" / "control_center"
CONFIG_PATH = ADMIN / "control_center_config.json"
LAUNCH_PATH = ADMIN / "map_launch.json"
AI_CONFIG_PATH = ADMIN / "ai_config.json"

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


def powershell_file(script: str, *args: str) -> list[str]:
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ADMIN / script), *args]


def python_file(script: str, *args: str) -> list[str]:
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
        write_json(RUNTIME / f"{job.id}.json", job.to_dict())


CONFIG = load_config()
JOBS = JobStore(int(CONFIG.get("job_retention", 50)))


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
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

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
            elif path == "/api/status":
                self.send_json(200, status_payload())
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
            if parsed.path != "/api/actions/run":
                self.send_error_json(404, "Unknown API route.")
                return
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length > 20_000:
                self.send_error_json(413, "Request body too large.")
                return
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw or "{}")
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
    config = load_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=config.get("host", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(config.get("port", 8765)))
    parser.add_argument("--open-browser", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    if args.host not in {"127.0.0.1", "localhost"} and not config.get("allow_remote_bind", False):
        print("Refusing remote bind. Set allow_remote_bind=true in admin/control_center_config.json first.")
        return 2
    if not LAUNCH_PATH.exists():
        print(f"Missing {LAUNCH_PATH}")
        return 1
    if not STATIC.exists():
        print(f"Missing {STATIC}")
        return 1
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"DayZ Server Control Center running at {url}")
    print("Press Ctrl+C to stop.")
    if args.open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping control center.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
