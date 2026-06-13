"""Backward-compatible wrapper — use build_map_expansion.py."""
from __future__ import annotations

import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(
        subprocess.call(
            [sys.executable, str(__file__).replace("build_takistan_ai.py", "build_map_expansion.py"), "takistan"],
        )
    )
