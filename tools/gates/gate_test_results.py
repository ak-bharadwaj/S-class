#!/usr/bin/env python3
"""Gate 2 (Blocking): Zero Skip / Zero XFail Enforcement Gate.

Runs pytest and parses summary info. Fails if any test is skipped, xfailed, or failed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    print("=== Gate 2: Zero Skip / Zero XFail Enforcement Gate ===")
    cmd = [sys.executable, "-m", "pytest", "-v"]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)

    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    # Check for failures
    if res.returncode != 0:
        print("FAILED: pytest exited with non-zero exit code.")
        sys.exit(1)

    # Parse short test summary line
    # Example: "248 passed, 3 skipped in 10.5s"
    summary_match = re.search(r"=+\s*(.*?)\s+in\s+[\d\.]+s\s*=+", res.stdout)
    if summary_match:
        summary_text = summary_match.group(1)
        print(f"Summary: {summary_text}")

        if "skipped" in summary_text:
            print("FAILED: Gate requires ZERO skipped tests.")
            sys.exit(1)
        if "xfailed" in summary_text or "xfail" in summary_text:
            print("FAILED: Gate requires ZERO xfail tests.")
            sys.exit(1)
        if "failed" in summary_text:
            print("FAILED: One or more tests failed.")
            sys.exit(1)

    print("=== Gate 2 Result: PASS ===")


if __name__ == "__main__":
    main()
