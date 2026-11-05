#!/usr/bin/env python3
"""Targeted mutation battery for Lane B2-METRICS-A (metrics.py).

Kills 10 non-trivial decision branches:
1. Authority check bypass in evaluate_f9_metric
2. Denominator missing check bypass in evaluate_f9_metric
3. Denominator zero NOT_APPLICABLE bypass
4. Paired evaluation requirement bypass
5. Goodhart detection logic bypass
6. Agent self-report contamination of canonical cost
7. Gaming variants / gaming role rejection bypass in CH5-T17
8. Shortened observation window bypass in CH5-T17
9. Forged telemetry estimate bypass in CH5-T17
10. Omission of UNAVAILABLE telemetry metric in project_metrics_from_events
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_FILE = REPO_ROOT / "src" / "sclass" / "product" / "metrics.py"
TEST_CMD = [sys.executable, "-m", "pytest", "tests/product/test_metrics.py", "-q"]

MUTATIONS = [
    (
        "M1: Disable caller authority check in evaluate_f9_metric",
        'if not caller_authority or caller_authority == "AGENT":',
        'if False and (not caller_authority or caller_authority == "AGENT"):',
    ),
    (
        "M2: Disable denominator missing check",
        'if denom is None:',
        'if False and denom is None:',
    ),
    (
        "M3: Disable zero-denominator NOT_APPLICABLE classification",
        'if denom == 0 or denom == "0":',
        'if False and (denom == 0 or denom == "0"):',
    ),
    (
        "M4: Disable paired_evaluation requirement",
        'if paired_eval is not True:',
        'if False and paired_eval is not True:',
    ),
    (
        "M5: Invert Goodhart detection logic (flagged = False)",
        'flagged = fc_improved and fb_worsened',
        'flagged = False',
    ),
    (
        "M6: Allow agent self-report to contaminate canonical cost",
        'canonical_cost = data.get("canonical_cost")',
        'canonical_cost = data.get("agent_reported_cost")',
    ),
    (
        "M7: Disable attack_variants / gaming role check in CH5-T17",
        'if data.get("attack_variants") is not None or data.get("fixture_role") == "gaming":',
        'if False and (data.get("attack_variants") is not None or data.get("fixture_role") == "gaming"):',
    ),
    (
        "M8: Disable observation window manipulation check",
        'if obs_win is None or obs_win == "shortened" or obs_win == "invalid":',
        'if False and (obs_win is None or obs_win == "shortened" or obs_win == "invalid"):',
    ),
    (
        "M9: Disable forged telemetry check",
        'if telem in ["forged", "estimate", "ESTIMATE"]:',
        'if False and (telem in ["forged", "estimate", "ESTIMATE"]):',
    ),
    (
        "M10: Omit UNAVAILABLE telemetry metric from projection",
        'if telemetry_status == "UNAVAILABLE":',
        'if False and telemetry_status == "UNAVAILABLE":',
    ),
]


def git_cmd(*args: str) -> str:
    res = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def run_battery() -> int:
    orig_code = TARGET_FILE.read_text(encoding="utf-8")
    head_sha = git_cmd("rev-parse", "HEAD")

    print(f"=== Mutation Testing Battery: Lane B2-METRICS-A ===")
    print(f"Base commit C: {head_sha}")
    print(f"Total mutations: {len(MUTATIONS)}\n")

    killed = 0
    survived = 0

    for i, (name, target, replacement) in enumerate(MUTATIONS, 1):
        if target not in orig_code:
            print(f"[{i:02d}/{len(MUTATIONS)}] ERROR: Target not found for {name}")
            return 1

        mutated_code = orig_code.replace(target, replacement, 1)
        TARGET_FILE.write_text(mutated_code, encoding="utf-8")

        proc = subprocess.run(TEST_CMD, cwd=REPO_ROOT, capture_output=True, text=True)

        # Restore immediately
        TARGET_FILE.write_text(orig_code, encoding="utf-8")

        if proc.returncode != 0:
            print(f"[{i:02d}/{len(MUTATIONS)}] KILLED: {name}")
            killed += 1
        else:
            print(f"[{i:02d}/{len(MUTATIONS)}] SURVIVED (UNEXPECTED): {name}")
            survived += 1

    print(f"\nResults: {killed}/{len(MUTATIONS)} killed, {survived} survived")
    print(f"Kill rate: {killed / len(MUTATIONS) * 100:.1f}%")

    return 0 if survived == 0 else 1


if __name__ == "__main__":
    sys.exit(run_battery())
