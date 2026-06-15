#!/usr/bin/env python3
"""Query a DayZ server Steam query port with A2S_INFO."""
from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERY = b"\xff\xff\xff\xffTSource Engine Query\x00"


def read_c_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.index(b"\x00", offset)
    return data[offset:end].decode("utf-8", errors="replace"), end + 1


def query(host: str, port: int, timeout: float) -> bytes:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(QUERY, (host, port))
        data, _ = sock.recvfrom(4096)
        if data.startswith(b"\xff\xff\xff\xffA") and len(data) >= 9:
            sock.sendto(QUERY + data[5:9], (host, port))
            data, _ = sock.recvfrom(4096)
        return data
    finally:
        sock.close()


def parse_info(data: bytes) -> dict[str, object]:
    if not data.startswith(b"\xff\xff\xff\xffI"):
        raise ValueError(f"Unexpected A2S response: {data[:16]!r}")
    offset = 6
    name, offset = read_c_string(data, offset)
    map_name, offset = read_c_string(data, offset)
    folder, offset = read_c_string(data, offset)
    game, offset = read_c_string(data, offset)
    app_id = int.from_bytes(data[offset : offset + 2], "little")
    offset += 2
    players = data[offset]
    max_players = data[offset + 1]
    bots = data[offset + 2]
    offset += 3
    server_type = chr(data[offset])
    environment = chr(data[offset + 1])
    visibility = data[offset + 2]
    vac = data[offset + 3]
    offset += 4
    version, offset = read_c_string(data, offset)
    return {
        "name": name,
        "map": map_name,
        "folder": folder,
        "game": game,
        "app_id": app_id,
        "players": players,
        "max_players": max_players,
        "bots": bots,
        "server_type": server_type,
        "environment": environment,
        "visibility": visibility,
        "vac": vac,
        "version": version,
    }


def map_port(map_name: str) -> int:
    data = json.loads((ROOT / "admin" / "map_launch.json").read_text(encoding="utf-8"))
    cfg = data["maps"].get(map_name)
    if not cfg:
        known = ", ".join(data["maps"])
        raise SystemExit(f"Unknown map '{map_name}'. Known maps: {known}")
    return int(cfg["steam_query_port"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Query a DayZ Steam query port.")
    parser.add_argument("--map", help="Map key from admin/map_launch.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()

    port = args.port or map_port(args.map or "chernarus")
    data = query(args.host, port, args.timeout)
    info = parse_info(data)
    print(f"{args.host}:{port} A2S_INFO OK")
    for key, value in info.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
