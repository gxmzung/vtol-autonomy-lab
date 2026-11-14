"""Repeatable, hardware-free VTOL regression gate.

Run from any working directory with Python 3.11+ after installing requirements.
No MAVSDK connection, arm or takeoff command is issued by this script.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = (
    ("syntax", [sys.executable, "-m", "compileall", "-q", "src", "tests"]),
    ("unit-regression", [sys.executable, "-m", "pytest", "-q"]),
    ("virtual-normal", [sys.executable, "-m", "src.mission_manager", "--backend", "virtual", "--scenario", "normal", "--mission-file", "config/mission.json"]),
    ("virtual-low-battery", [sys.executable, "-m", "src.mission_manager", "--backend", "virtual", "--scenario", "low_battery", "--mission-file", "config/mission.json"]),
)

def main() -> int:
    for name, command in STEPS:
        print(f"\n[verify] {name}: {' '.join(command)}", flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            print(f"[verify] FAILED: {name} (exit={result.returncode})", file=sys.stderr)
            return result.returncode
    print("\n[verify] All offline commands exited successfully.")
    print("[verify] This does NOT demonstrate PX4, SITL, physical FC or flight safety.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
