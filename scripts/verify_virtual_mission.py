"""Fail-closed virtual-only VTOL verification entrypoint.

No PX4/MAVSDK connection or hardware commands are issued.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    ("syntax", [sys.executable, "-m", "compileall", "-q", "src", "tests"]),
    ("regression", [sys.executable, "-m", "pytest", "-q"]),
    # The targeted tests assert both final state and exact failure code.
    ("semantic-mission-assertions", [
        sys.executable, "-m", "pytest", "-q",
        "tests/test_failure_scenarios.py",
    ]),
)

def main() -> int:
    for name, command in CHECKS:
        print(f"\n[verify] {name}: {' '.join(command)}", flush=True)
        outcome = subprocess.run(command, cwd=ROOT, check=False)
        if outcome.returncode != 0:
            print(f"[verify] FAIL {name} (exit={outcome.returncode})", file=sys.stderr)
            return outcome.returncode
    print("\n[verify] PASS: offline regression + scenario state/failure-code assertions")
    print("[verify] NOT evidence of PX4, SITL, flight safety, or real hardware.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
