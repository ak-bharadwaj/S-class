#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 2 Lane P6 (PD-CH2-037, 038, 039, 040, 048).

Parses authoritative fixtures directly from the hash-verified Master Product Design
document using the shared parser (tools/master_fixtures.py), executes real evaluators,
and outputs an audited status table.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p6 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_037_execution_gate_authorization,
    evaluate_pd_ch2_038_scope_growth_stop,
    evaluate_pd_ch2_039_implementation_claims,
    evaluate_pd_ch2_040_canonical_delta_kernel_receipt,
    evaluate_pd_ch2_048_test_input_set_exclusion_check,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P6FixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p6_fixtures(master_path: Path) -> List[P6FixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P6FixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-037 (Line 2072)
        (
            "CH2-T37", "PD-CH2-037",
            lambda: evaluate_pd_ch2_037_execution_gate_authorization(
                has_execution_gate_auth=False,
                task_id="T1",
                scope="src",
                target="src/core.py",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: no authorization -> MISSING[PD-CH2-037]",
        ),
        # PD-CH2-038 (Line 2073)
        (
            "CH2-T38", "PD-CH2-038",
            lambda: evaluate_pd_ch2_038_scope_growth_stop(
                is_out_of_scope=True,
                delta_files=["src/unapproved.py"],
                declared_scope={"src/core.py"},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: out-of-scope delta -> MISSING[PD-CH2-038]",
        ),
        # PD-CH2-039 (Line 2074) - expected MISSING[PD-F7-006]
        (
            "CH2-T39", "PD-CH2-039",
            lambda: evaluate_pd_ch2_039_implementation_claims(
                claimed_symbols=["MissingPostDeltaSymbol"],
                post_delta_symbols={"ExistingSymbol"},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: symbol absent post-delta -> MISSING[PD-F7-006]",
        ),
        # PD-CH2-040 (Line 2075)
        (
            "CH2-T40", "PD-CH2-040",
            lambda: evaluate_pd_ch2_040_canonical_delta_kernel_receipt(
                has_kernel_receipt=False,
                kernel_receipt_digest=None,
                kernel_denied=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: no kernel receipt -> MISSING[PD-CH2-040]",
        ),
        # PD-CH2-048 (Line 2076)
        (
            "CH2-T48", "PD-CH2-048",
            lambda: evaluate_pd_ch2_048_test_input_set_exclusion_check(
                p6_tests_frozen_invoked=False,
                p6_modifies_test_input_set=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: P6 composition omits P6-TESTS-FROZEN -> MISSING[PD-CH2-048]",
        ),
    ]

    for fid, mid, runner, notes in cases:
        parsed = parse_master_fixture(master_path, fid)
        # Runtime assertion: returned master line contains fixture ID
        target_line = lines[parsed.line_number - 1]
        assert fid in target_line, (
            f"Runtime assertion failure: line {parsed.line_number} does not contain {fid}: {target_line}"
        )

        gate_res: Any = runner()
        actual_str = str(gate_res)

        match = False
        for exp in parsed.expected_gate_strings:
            if exp == actual_str:
                match = True
                break

        status = "RAN-MATCH" if match else "RAN-MISMATCH"
        results.append(
            P6FixtureExecution(
                fixture_id=fid,
                must_id=mid,
                master_line=parsed.line_number,
                expected=", ".join(parsed.expected_gate_strings),
                actual=actual_str,
                status=status,
                notes=notes,
            )
        )

    return results


def print_summary_table(results: List[P6FixtureExecution]) -> None:
    print("=" * 89)
    print("LANE B3-P6 FIXTURE RUNNER SUMMARY (5 VECTORS)")
    print("=" * 89)
    header = f"{'Fixture ID':<10} | {'Owner MUST':<12} | {'Master Line':<11} | {'Expected Gate Output':<24} | {'Actual Gate Output':<24} | {'Status':<9}"
    print(header)
    print("-" * 89)
    all_match = True
    for r in results:
        print(f"{r.fixture_id:<10} | {r.must_id:<12} | L{r.master_line:<10} | {r.expected:<24} | {r.actual:<24} | {r.status:<9}")
        if r.status != "RAN-MATCH":
            all_match = False
    print("=" * 89)
    match_count = sum(1 for r in results if r.status == "RAN-MATCH")
    print(f"Status: {match_count}/{len(results)} RAN-MATCH across Lane P6 fixtures.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lane P6 fixtures against master.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", "/mnt/c/Users/dorni/Downloads/S-CLASS-R32-PACKAGE/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"),
        help="Path to authoritative master document",
    )
    args = parser.parse_args()

    master_path = Path(args.master_path).resolve()
    results = run_p6_fixtures(master_path)
    print_summary_table(results)

    if any(r.status != "RAN-MATCH" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
