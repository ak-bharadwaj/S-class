#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 2 Lane P5 (PD-CH2-033, 034, 035, 036, 046, 047).

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
from sclass.product.lifecycle_p5 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_033_delta_sequence,
    evaluate_pd_ch2_034_red_run_validity,
    evaluate_pd_ch2_035_executable_spec_constraints,
    evaluate_pd_ch2_036_adapter_qualification,
    evaluate_pd_ch2_046_test_input_set_binding,
    evaluate_pd_ch2_047_red_classification_source,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P5FixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p5_fixtures(master_path: Path) -> List[P5FixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P5FixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-033 (Line 1994)
        (
            "CH2-T33", "PD-CH2-033",
            lambda: evaluate_pd_ch2_033_delta_sequence(
                test_delta_seq=5,
                impl_delta_seq=3,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: implementation delta ordered first -> MISSING[PD-CH2-033]",
        ),
        # PD-CH2-034 (Line 1995)
        (
            "CH2-T34", "PD-CH2-034",
            lambda: evaluate_pd_ch2_034_red_run_validity(
                adapter_qualified=True,
                run_failed_designed_test=True,
                failure_class="AssertionError",
                designed_class="AssertionError",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: valid red -> SATISFIED",
        ),
        # PD-CH2-035 (Line 1996)
        (
            "CH2-T35", "PD-CH2-035",
            lambda: evaluate_pd_ch2_035_executable_spec_constraints(
                is_executable_f1_f2=False,
                finite_domain=False,
                is_prose_only=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: prose-only/unbounded predicate -> MISSING[PD-CH2-035]",
        ),
        # PD-CH2-036 (Line 1997)
        (
            "CH2-T36", "PD-CH2-036",
            lambda: evaluate_pd_ch2_036_adapter_qualification(
                adapter_name="unverified-custom",
                is_f10_qualified=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: unqualified adapter -> MISSING[PD-CH2-036]",
        ),
        # PD-CH2-046 (Line 1998)
        (
            "CH2-T46", "PD-CH2-046",
            lambda: evaluate_pd_ch2_046_test_input_set_binding(
                primary_test_digest="sha256:unbound_digest",
                bound_test_input_set={"conftest.py": "sha256:conf123"},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: red run requested before primary test digest is bound -> MISSING[PD-CH2-046]",
        ),
        # PD-CH2-047 (Line 1999)
        (
            "CH2-T47", "PD-CH2-047",
            lambda: evaluate_pd_ch2_047_red_classification_source(
                adapter_structured_result={"failed_test": "test_wrong", "failure_reason": "ZeroDivisionError"},
                designed_test_tuple=("test_correct", "AssertionError"),
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: agent says right reason but adapter result targets wrong behavior -> MISSING[PD-CH2-047]",
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
            P5FixtureExecution(
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


def print_summary_table(results: List[P5FixtureExecution]) -> None:
    print("=" * 89)
    print("LANE B3-P5 FIXTURE RUNNER SUMMARY (6 VECTORS)")
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
    print(f"Status: {match_count}/{len(results)} RAN-MATCH across Lane P5 fixtures.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lane P5 fixtures against master.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", os.environ.get("SCLASS_MASTER_PATH", "")),
        help="Path to authoritative master document",
    )
    args = parser.parse_args()

    master_path = Path(args.master_path).resolve()
    results = run_p5_fixtures(master_path)
    print_summary_table(results)

    if any(r.status != "RAN-MATCH" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
