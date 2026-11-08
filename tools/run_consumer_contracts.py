#!/usr/bin/env python3
"""Run W4 GATE-B-2 consumer contracts across Python 3.10-3.13 and capture log."""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = REPO_ROOT / "delivery-2-block2" / "consumer_contracts.log"

lines = [
    "=" * 80,
    "GATE-B-2 CONSUMER CONTRACTS TEST LOG (tests/product/test_block2_consumer_contracts_f1_f3.py)",
    "=" * 80,
]

for v in ["3.10", "3.11", "3.12", "3.13"]:
    lines.append(f"=== Python {v} ===")
    cmd = [
        f"/home/runner/venv-{v}/bin/python",
        "-m",
        "pytest",
        "tests/product/test_block2_consumer_contracts_f1_f3.py",
        "-q",
        "--no-header",
    ]
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    lines.append(res.stdout.strip())
    lines.append("")

lines.append("=" * 80)
LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Updated", LOG_PATH)
