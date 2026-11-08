#!/usr/bin/env python3
"""Master-driven fixture runner for Block 4 Lane D (PD-CH3-010..012, PD-CH3-014, PD-CH4-012, PD-CH4-009).

Parses authoritative fixtures directly from the hash-verified Master Product Design
document using the shared parser (tools/master_fixtures.py), executes real evaluators,
and verifies results against master expected outputs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from sclass.product.gate import GateOutput, GateState
from sclass.product.execution_flow_testinput import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_TEST_INPUT_KEYS,
    evaluate_pd_ch3_010_flow_baseline_binding,
    evaluate_pd_ch3_011_adapter_qualification_disclosure,
    evaluate_pd_ch3_012_ux_interruption_budget_authority,
    evaluate_pd_ch3_014_lifecycle_example_adversarial_failure,
    evaluate_pd_ch4_012_reference_exact_resolution,
    evaluate_pd_ch4_009_test_input_set_binding,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B4DFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b4_d_fixtures(master_path: Path) -> List[B4DFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B4DFixtureExecution] = []

    full_test_inputs = {k: f"content_{k}" for k in REQUIRED_TEST_INPUT_KEYS}
    partial_test_inputs = dict(full_test_inputs)
    del partial_test_inputs["fixtures"]

    cases: List[Tuple[str, str, Callable[[], GateOutput], str]] = [
        # CH3-T10 -> PD-CH3-010
        (
            "CH3-T10", "PD-CH3-010",
            lambda: evaluate_pd_ch3_010_flow_baseline_binding(
                flow_type="MIGRATION",
                baseline_digest=None,
                rollback_inputs_bound=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T10 migration without rollback binding",
        ),
        # CH3-T11 -> PD-CH3-011
        (
            "CH3-T11", "PD-CH3-011",
            lambda: evaluate_pd_ch3_011_adapter_qualification_disclosure(
                adapter_identity="browser-adapter",
                is_qualified=False,
                marked_supported=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T11 unqualified browser adapter presented as supported",
        ),
        # CH3-T12 -> PD-CH3-012
        (
            "CH3-T12", "PD-CH3-012",
            lambda: evaluate_pd_ch3_012_ux_interruption_budget_authority(
                human_decision_required=True,
                decision_suppressed_by_cap=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T12 cap suppresses required approval",
        ),
        # CH3-T14 -> PD-CH3-014
        (
            "CH3-T14", "PD-CH3-014",
            lambda: evaluate_pd_ch3_014_lifecycle_example_adversarial_failure(
                exercises_real_gate_outputs=True,
                has_adversarial_claim_failure=False,
                has_test_integrity_failure=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T14 example omits either F7 hallucinated-reference or TestInputSet weakening failure",
        ),
        # CH4-T15 -> PD-CH4-012
        (
            "CH4-T15", "PD-CH4-012",
            lambda: evaluate_pd_ch4_012_reference_exact_resolution(
                path_reference="src/unknown.py",
                symbol_reference="eval_gate",
                target_snapshot_pinned=False,
                is_unresolved=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T15 unresolved or ambiguous reference",
        ),
        # CH4-T16 -> PD-CH4-012
        (
            "CH4-T16", "PD-CH4-012",
            lambda: evaluate_pd_ch4_012_reference_exact_resolution(
                path_reference="src/core.py",
                symbol_reference="eval_gate",
                target_snapshot_pinned=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T16 reference resolved exactly against pinned snapshot",
        ),
        # CH4-T27 -> PD-CH4-009
        (
            "CH4-T27", "PD-CH4-009",
            lambda: evaluate_pd_ch4_009_test_input_set_binding(
                test_input_set=partial_test_inputs,
                is_before_red=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T27 omission in TestInputSet",
        ),
        # CH4-T9 -> PD-CH4-009
        (
            "CH4-T9", "PD-CH4-009",
            lambda: evaluate_pd_ch4_009_test_input_set_binding(
                test_input_set=full_test_inputs,
                is_before_red=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T9 complete digest-bound TestInputSet before red",
        ),
    ]

    for fid, mid, fn, notes in cases:
        fixture = parse_master_fixture(master_path, fid)
        expected_str = fixture.primary_expected
        out: GateOutput = fn()
        actual_str = f"{out.state.value}[{out.must_id}]" if out.state != GateState.SATISFIED else "SATISFIED"

        status = "RAN-MATCH" if actual_str == expected_str else "MISMATCH"
        results.append(
            B4DFixtureExecution(
                fixture_id=fid,
                must_id=mid,
                master_line=fixture.line_number,
                expected=expected_str,
                actual=actual_str,
                status=status,
                notes=notes,
            )
        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Block 4 Lane D fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b4_d_fixtures(master_path)

    print(f"{'Fixture ID':<16} | {'MUST ID':<12} | {'Line':<6} | {'Expected':<28} | {'Actual':<28} | {'Status':<10}")
    print("-" * 110)
    mismatches = 0
    for r in results:
        print(f"{r.fixture_id:<16} | {r.must_id:<12} | {r.master_line:<6} | {r.expected:<28} | {r.actual:<28} | {r.status:<10}")
        if r.status != "RAN-MATCH":
            mismatches += 1

    print("-" * 110)
    print(f"Total fixtures executed: {len(results)}, Mismatches: {mismatches}")
    return 1 if mismatches > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
