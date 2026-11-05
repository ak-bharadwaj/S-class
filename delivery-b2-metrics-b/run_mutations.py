#!/usr/bin/env python3
"""Targeted mutation battery for Lane B2-METRICS-B (performance_claims.py).

Kills 10 non-trivial decision branches:
1. Authority check bypass
2. Unsupported latency promise check bypass (PD-CH5-004)
3. Gaming role / attack_variants check bypass (CH5-T15)
4. Missing corpus_digest check bypass
5. Missing unit check bypass
6. Out of range percentile check bypass
7. Sample count below policy minimum bypass
8. Sample count above 100,000 maximum cap bypass
9. Unmeasured OPEN objective bypass (PD-CH5-011)
10. Inversion of conforming happy fixture return (CH5-T16)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_FILE = REPO_ROOT / "src" / "sclass" / "product" / "performance_claims.py"
TEST_CMD = [sys.executable, "-m", "pytest", "tests/product/test_performance_claims.py", "-q"]

MUTATIONS = [
    (
        "M1: Disable caller authority check in evaluate_performance_claim",
        'if not caller_authority or caller_authority == "AGENT":',
        'if False and (not caller_authority or caller_authority == "AGENT"):',
    ),
    (
        "M2: Disable unsupported latency promise check (PD-CH5-004)",
        'if corpus in ["absent", None, ""] or window in ["absent", None, ""]:',
        'if False and (corpus in ["absent", None, ""] or window in ["absent", None, ""]):',
    ),
    (
        "M3: Disable attack_variants / gaming role check (CH5-T15)",
        'if data.get("attack_variants") is not None or data.get("fixture_role") == "gaming":',
        'if False and (data.get("attack_variants") is not None or data.get("fixture_role") == "gaming"):',
    ),
    (
        "M4: Disable corpus_digest validation check",
        'if not corpus_digest or not isinstance(corpus_digest, str) or not corpus_digest.strip() or corpus_digest in ["absent", "null"]:',
        'if False:',
    ),
    (
        "M5: Disable unit validation check",
        'if not unit or not isinstance(unit, str) or not unit.strip() or unit in ["absent", "null"]:',
        'if False:',
    ),
    (
        "M6: Disable percentile range check",
        'if math.isnan(perc_num) or not (0.0 <= perc_num <= 100.0):',
        'if False and (math.isnan(perc_num) or not (0.0 <= perc_num <= 100.0)):',
    ),
    (
        "M7: Disable sample count policy minimum check",
        'if sample_count < min_required:',
        'if False and sample_count < min_required:',
    ),
    (
        "M8: Disable sample count maximum 100,000 cap check",
        'if sample_count > policy.max_samples_cap:',
        'if False and sample_count > policy.max_samples_cap:',
    ),
    (
        "M9: Disable unmeasured OPEN objective check",
        'if data.get("objective_status") == "OPEN" and not data.get("measured_evidence_ref") and not data.get("baseline"):',
        'if False:',
    ),
    (
        "M10: Invert happy fixture return (CH5-T16)",
        'if data.get("fixture_role") == "happy" or (',
        'if False and (data.get("fixture_role") == "happy" or (',
    ),
]


def git_cmd(*args: str) -> str:
    res = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def run_battery() -> int:
    orig_code = TARGET_FILE.read_text(encoding="utf-8")
    head_sha = git_cmd("rev-parse", "HEAD")

    print(f"=== Mutation Testing Battery: Lane B2-METRICS-B ===")
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
