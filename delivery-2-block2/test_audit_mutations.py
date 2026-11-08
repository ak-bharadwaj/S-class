#!/usr/bin/env python3
"""Mutation tests for tools/block2_audit.py proving rejection of Section 0 false claims."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO_ROOT / "tools" / "block2_audit.py"
MASTER_DOC = Path(os.environ.get("SCLASS_MASTER_PATH", str(REPO_ROOT / "tests" / "fixtures" / "synthetic_master.md")))

# Minimal valid base report
VALID_BASE_REPORT = """# Block 2 Verification Report
Date: 2026-11-07
Commit SHAs: 38a97b1d e826352f fb5604e4 7b32675a
QUALIFIED_EVALUATOR_BOUNDARY: QUALIFIED_EVALUATOR

## Environment
- Python 3.12.16 (main, Oct 26 2026, 14:08:45) [Clang 23.1.3 ]

## Fixtures
| Fixture ID | Owner MUST | Inputs | Expected Output | Actual Output | Status |
|---|---|---|---|---|---|
| F5-T1 | PD-F5-001 | H1 | SATISFIED | SATISFIED | RAN-MATCH |
| F5-T2 | PD-F5-002 | C-01, C-09 | MISSING[PD-F5-002] | MISSING[PD-F5-002] | RAN-MATCH |
| F9-T1 | PD-F9-001 | H1 | SATISFIED | SATISFIED | RAN-MATCH |
| F9-T2 | PD-F9-002 | no denominator | MISSING[PD-F9-002] | MISSING[PD-F9-002] | RAN-MATCH |
"""

MUTATION_CASES = [
    (
        "Section 0 Claim 1: Invented commit SHA 1ba538d3",
        "Commit SHAs: 38a97b1d e826352f fb5604e4 7b32675a",
        "Commit SHAs: 1ba538d3 1dff03fb 87a950a4 8bb94ba3",
        "[Check 1 FAIL] Invented or unreproducible hex/SHA: '1ba538d3'",
    ),
    (
        "Section 0 Claim 2: False QUALIFIED_EVALUATOR_BOUNDARY string",
        "QUALIFIED_EVALUATOR_BOUNDARY: QUALIFIED_EVALUATOR",
        "QUALIFIED_EVALUATOR_BOUNDARY: sclass.product.gate_evaluator",
        "[Check 6 FAIL] False QUALIFIED_EVALUATOR_BOUNDARY 'sclass.product.gate_evaluator'",
    ),
    (
        "Section 0 Claim 3a: Invented fixture ID CH5-PAIR-1A",
        "| F5-T1 | PD-F5-001 |",
        "| CH5-PAIR-1A | PD-CH5-001 |",
        "[Check 3 FAIL] Invented fixture ID 'CH5-PAIR-1A'",
    ),
    (
        "Section 0 Claim 3b: False expected value for F5-T2 (BLOCKED instead of MISSING)",
        "| F5-T2 | PD-F5-002 | C-01, C-09 | MISSING[PD-F5-002] |",
        "| F5-T2 | PD-F5-002 | C-01, C-09 | BLOCKED |",
        "[Check 4 FAIL] Contradictory expected value for F5-T2",
    ),
    (
        "Section 0 Claim 3c: False expected value for F9-T2 (SATISFIED instead of MISSING)",
        "| F9-T2 | PD-F9-002 | no denominator | MISSING[PD-F9-002] |",
        "| F9-T2 | PD-F9-002 | no denominator | SATISFIED |",
        "[Check 4 FAIL] Contradictory expected value for F9-T2",
    ),
    (
        "Section 0 Claim 4: Fake evaluator sclass.conformance.v6_suite",
        "## Fixtures",
        "## Fixtures\\nEvaluator: sclass.conformance.v6_suite (40/32/24/14/10)",
        "[Check 6 FAIL] Invented evaluator 'sclass.conformance.v6_suite'",
    ),
    (
        "Section 0 Claim 6: Fabricated baseline test count 637",
        "## Environment",
        "## Environment\\nBaseline passed 637 tests",
        "[Check 5 FAIL] Unsourced number '637'",
    ),
    (
        "Section 0 Claim 7: Fabricated python -VV version string",
        "Python 3.12.16 (main, Oct 26 2026, 14:08:45) [Clang 23.1.3 ]",
        "Python 3.12.16 (main, Mar 10 2026, 14:08:45) [GCC 13.3.0 ]",
        "[Check 2 FAIL] Python version string 'Python 3.12.16 (main, Mar 10 2026, 14:08:45) [GCC 13.3.0 ]'",
    ),
]


def run_mutation_tests() -> int:
    print("=" * 60)
    print("RUNNING BLOCK 2 CLAIMS AUDITOR MUTATION TESTS")
    print("=" * 60)

    # First, create a mock raw log capturing true python versions
    tmp_logs = Path(tempfile.mkdtemp(prefix="block2_logs_"))
    ver_log = tmp_logs / "python_versions.log"
    ver_log.write_text(
        "Python 3.10.22 (main, Oct  9 2026, 15:21:30) [Clang 22.1.3 ]\n"
        "Python 3.11.18 (main, Oct 26 2026, 14:05:07) [Clang 23.1.3 ]\n"
        "Python 3.12.16 (main, Oct 26 2026, 14:08:45) [Clang 23.1.3 ]\n"
        "Python 3.13.18 (main, Oct 26 2026, 14:08:20) [Clang 23.1.3 ]\n"
    )

    passed_mutations = 0
    total_mutations = len(MUTATION_CASES)

    for desc, orig, mutant, expected_err_sub in MUTATION_CASES:
        mutated_text = VALID_BASE_REPORT.replace(orig, mutant)
        if mutated_text == VALID_BASE_REPORT:
            print(f"[FAIL] Mutation setup failed: '{orig}' not found in base report!", file=sys.stderr)
            return 1

        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(mutated_text)
            tmp_report = Path(f.name)

        try:
            res = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT_SCRIPT),
                    str(tmp_report),
                    "--master-path",
                    str(MASTER_DOC),
                    "--logs-dir",
                    str(tmp_logs),
                    "--repo-root",
                    str(REPO_ROOT),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if res.returncode == 0:
                print(f"[FAIL] Auditor accepted false claim: {desc}", file=sys.stderr)
                return 1

            if expected_err_sub not in res.stderr and expected_err_sub not in res.stdout:
                print(f"[FAIL] Auditor rejected, but expected error message not found: {desc}", file=sys.stderr)
                print(f"Expected: {expected_err_sub}", file=sys.stderr)
                print(f"Got stderr:\n{res.stderr}", file=sys.stderr)
                return 1

            print(f"  [OK] Successfully rejected: {desc}")
            passed_mutations += 1
        finally:
            if tmp_report.exists():
                tmp_report.unlink()

    print("-" * 60)
    print(f"MUTATION TESTING COMPLETE: {passed_mutations}/{total_mutations} false claims rejected (100% kill rate).")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(run_mutation_tests())
