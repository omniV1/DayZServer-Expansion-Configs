#!/usr/bin/env python3
"""Minimal BattlEye RCon client for local DayZ server administration.

Implements the BattlEye RCon UDP protocol (login, command, multi-packet response)
well enough to run one-shot admin commands such as `players`, `kick`, `ban`, and
`say`. It opens a socket, logs in, sends a single command, reads the reply, and
closes -- no long-lived keepalive loop is needed for one-shot use.

Protocol reference (BattlEye RCon):
  packet = b"BE" + crc32(payload) [4 bytes little-endian] + payload
  payload = 0xFF + <packet type> + <data>
  login   (0x00): data = password;            reply 0xFF 0x00 <0x01 ok | 0x00 fail>
  command (0x01): data = <seq byte> + command; reply 0xFF 0x01 <seq> [multipacket] <text>
"""
from __future__ import annotations

import argparse
import socket
import struct
import sys
import zlib


class RConError(Exception):
    """Raised when an RCon login or command cannot be completed."""


def _packet(packet_type: int, data: bytes = b"") -> bytes:
    payload = bytes([0xFF, packet_type]) + data
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return b"BE" + struct.pack("<I", crc) + payload


def _strip_header(datagram: bytes) -> bytes:
    # b"BE" (2) + crc (4) = 6-byte header, then the 0xFF-prefixed payload.
    return datagram[6:]


def send_command(host: str, port: int, password: str, command: str, timeout: float = 5.0) -> str:
    """Log in, run one command, and return its text response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.send(_packet(0x00, password.encode("latin-1", "ignore")))
        try:
            login = _strip_header(sock.recv(4096))
        except socket.timeout as exc:
            raise RConError("No response from RCon (is the server running with RCon enabled?)") from exc
        if len(login) < 3 or login[0] != 0xFF or login[1] != 0x00:
            raise RConError("Unexpected RCon login response.")
        if login[2] != 0x01:
            raise RConError("RCon login failed (wrong password?).")

        sock.send(_packet(0x01, bytes([0x00]) + command.encode("latin-1", "ignore")))
        parts: dict[int, bytes] = {}
        total = 1
        while True:
            try:
                body = _strip_header(sock.recv(8192))
            except socket.timeout:
                break
            if len(body) < 3 or body[0] != 0xFF or body[1] != 0x01:
                continue  # skip server messages / keepalives during a one-shot command
            rest = body[3:]
            if rest[:1] == b"\x00" and len(rest) >= 3:
                total = rest[1]
                parts[rest[2]] = rest[3:]
            else:
                parts[0] = rest
                total = 1
            if len(parts) >= total:
                break
        return b"".join(parts[index] for index in sorted(parts)).decode("latin-1", "replace").strip()
    finally:
        sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    try:
        print(send_command(args.host, args.port, args.password, args.command, args.timeout))
    except RConError as exc:
        print(f"RCon error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
