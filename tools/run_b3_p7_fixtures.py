#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 2 Lane P7 (PD-CH2-041, 042, 043, 044, 045, 050).

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
from sclass.product.lifecycle_p7 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_041_evidence_binding,
    evaluate_pd_ch2_042_adapter_qualification,
    evaluate_pd_ch2_043_independence_floor,
    evaluate_pd_ch2_044_freshness_predicate,
    evaluate_pd_ch2_045_closure_ownership,
    evaluate_pd_ch2_050_deterministic_rerun,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P7FixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p7_fixtures(master_path: Path) -> List[P7FixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P7FixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-041 (Line 2144)
        (
            "CH2-T41", "PD-CH2-041",
            lambda: evaluate_pd_ch2_041_evidence_binding(
                evidence_identity_bound=True,
                current_target_bound=False,
                current_step_bound=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: missing target/step -> MISSING[PD-CH2-041]",
        ),
        # PD-CH2-042 (Line 2145)
        (
            "CH2-T42", "PD-CH2-042",
            lambda: evaluate_pd_ch2_042_adapter_qualification(
                adapter_name="unverified-custom",
                is_f10_qualified=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: unqualified adapter -> MISSING[PD-CH2-042]",
        ),
        # PD-CH2-043 (Line 2146)
        (
            "CH2-T43", "PD-CH2-043",
            lambda: evaluate_pd_ch2_043_independence_floor(
                independence_level=1,
                required_floor=3,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: floor not met -> MISSING[PD-CH2-043]",
        ),
        # PD-CH2-044 (Line 2147)
        (
            "CH2-T44", "PD-CH2-044",
            lambda: evaluate_pd_ch2_044_freshness_predicate(
                evidence_digest="sha256:old_stale_evidence",
                current_code_digest="sha256:current_code",
                is_stale=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: stale digest -> MISSING[PD-CH2-044]",
        ),
        # PD-CH2-045 (Line 2148)
        (
            "CH2-T45", "PD-CH2-045",
            lambda: evaluate_pd_ch2_045_closure_ownership(
                kernel_closure_result=None,
                agent_asserts_closure=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: agent asserts closure without kernel result -> MISSING[PD-CH2-045]",
        ),
        # PD-CH2-050 (Line 2149)
        (
            "CH2-T50", "PD-CH2-050",
            lambda: evaluate_pd_ch2_050_deterministic_rerun(
                rerun_results=["PASS", "FAIL"],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: same inputs with rerun results [PASS, FAIL] -> non-SATISFIED",
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
            if "non-SATISFIED" in exp and actual_str != "SATISFIED":
                match = True
                break

        status = "RAN-MATCH" if match else "RAN-MISMATCH"
        results.append(
            P7FixtureExecution(
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


def print_summary_table(results: List[P7FixtureExecution]) -> None:
    print("=" * 89)
    print("LANE B3-P7 FIXTURE RUNNER SUMMARY (6 VECTORS)")
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
    print(f"Status: {match_count}/{len(results)} RAN-MATCH across Lane P7 fixtures.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lane P7 fixtures against master.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", os.environ.get("SCLASS_MASTER_PATH", "")),
        help="Path to authoritative master document",
    )
    args = parser.parse_args()

    master_path = Path(args.master_path).resolve()
    results = run_p7_fixtures(master_path)
    print_summary_table(results)

    if any(r.status != "RAN-MATCH" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
