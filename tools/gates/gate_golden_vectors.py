#!/usr/bin/env python3
"""Gate 4 (Blocking): Golden Vectors Reproduction Gate.

Verifies that state digests, C1 serialization, and event histories reproduce exactly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    print("=== Gate 4: Golden Vectors Reproduction Gate ===")
    cmd = [sys.executable, "-m", "pytest", "tests/vectors/test_golden_vectors.py", "-v"]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)

    print(res.stdout)
    if res.returncode != 0:
        print("FAILED: Golden vector verification failed:")
        if res.stderr:
            print(res.stderr, file=sys.stderr)
        sys.exit(1)

    print("=== Gate 4 Result: PASS ===")


if __name__ == "__main__":
    main()
