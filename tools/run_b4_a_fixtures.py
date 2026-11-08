#!/usr/bin/env python3
"""Master-driven fixture runner for Block 4 Lane A (PD-F10-001..PD-F10-006).

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
from sclass.product.adapter_qualification_contract import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    FROZEN_ADAPTER_TESTS,
    ADDITIONAL_PRODUCT_TESTS,
    FROZEN_EVIDENCE_BINDING_FIELDS,
    evaluate_pd_f10_001_contract_invocation,
    evaluate_pd_f10_002_usable_adapter_binding,
    evaluate_pd_f10_003_adapter_registration_authority,
    evaluate_pd_f10_004_execution_gate_enforcement,
    evaluate_pd_f10_005_qualification_matrix,
    evaluate_pd_f10_006_independent_verification,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B4AFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b4_a_fixtures(master_path: Path) -> List[B4AFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B4AFixtureExecution] = []

    # Helper for building full tests
    frozen_all = {t: {"result": "PASS"} for t in FROZEN_ADAPTER_TESTS}
    additional_a2_fail = {t: {"result": "PASS"} for t in ADDITIONAL_PRODUCT_TESTS}
    additional_a2_fail["A2_differential_result_detection"] = {"result": "FAIL"}

    cases: List[Tuple[str, str, Callable[[], GateOutput], str, int]] = [
        # F10-T1 -> PD-F10-001
        (
            "F10-T1", "PD-F10-001",
            lambda: evaluate_pd_f10_001_contract_invocation(
                tool_call={"tool_identity": "validator-x", "version": "1.2.3"},
                adapter_record=None,
                category="syntax-validator",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "F10-FT1 direct tool call without adapter record",
            0,
        ),
        # F10-T2 -> PD-F10-002
        (
            "F10-T2", "PD-F10-002",
            lambda: evaluate_pd_f10_002_usable_adapter_binding(
                {
                    "adapter_id": "A-1",
                    "tool_identity": "validator-x@1.2.3",
                    "qualification_record_ref": None,
                    "evidence_binding_fields": ["obligation_id", "target_snapshot"],
                },
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "F10-FT2 adapter with no qualification record and incomplete evidence binding",
            0,
        ),
        # F10-T3 -> PD-F10-003
        (
            "F10-T3", "PD-F10-003",
            lambda: evaluate_pd_f10_003_adapter_registration_authority(
                actor="agent",
                operation="REGISTER_ADAPTER",
                canonical_write_authorized=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "F10-FT3 agent attempts registration",
            0,
        ),
        # F10-T4 -> PD-F10-003
        (
            "F10-T4", "PD-F10-003",
            lambda: evaluate_pd_f10_003_adapter_registration_authority(
                actor="admin",
                operation="UPDATE_ADAPTER",
                canonical_write_authorized=True,
                evidence_adapter_digest="D1",
                current_adapter_digest="D2",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "F10-FT4 adapter digest changes after evidence receipt",
            0,
        ),
        # F10-T5 -> PD-F10-004
        (
            "F10-T5", "PD-F10-004",
            lambda: evaluate_pd_f10_004_execution_gate_enforcement(
                authorized_request=None,
                execution_lease=None,
                budget_reservation=None,
                fence=None,
                worker_execute_attempt=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "F10-FT5 executor invoked without ExecutionGate; bounded timeout path",
            0,
        ),
        # F10-T6 -> PD-F10-005
        (
            "F10-T6", "PD-F10-005",
            lambda: evaluate_pd_f10_005_qualification_matrix(
                frozen_required_tests=frozen_all,
                additional_product_tests=additional_a2_fail,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "F10-FT6 all 14 frozen tests pass but A2 fails",
            0,
        ),
        # F10-T7 Branch 1 -> BLOCKED_ON_HUMAN[PD-F10-006]
        (
            "F10-T7", "PD-F10-006",
            lambda: evaluate_pd_f10_006_independent_verification(
                is_critical_lane=True,
                qualified_independent_verifier=None,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "F10-FT7 branch 1: no qualified independent verifier",
            0,
        ),
        # F10-T7 Branch 2 -> MISSING[PD-F10-006]
        (
            "F10-T7", "PD-F10-006",
            lambda: evaluate_pd_f10_006_independent_verification(
                is_critical_lane=True,
                qualified_independent_verifier="verifier-b@4.2",
                primary_result="PASS",
                independent_result="FAIL",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "F10-FT7 branch 2: separate contradictory run",
            1,
        ),
    ]

    for fid, mid, fn, notes, exp_idx in cases:
        fixture = parse_master_fixture(master_path, fid)
        expected_str = fixture.expected_gate_strings[exp_idx]
        out: GateOutput = fn()
        actual_str = f"{out.state.value}[{out.must_id}]" if out.state != GateState.SATISFIED else "SATISFIED"

        status = "RAN-MATCH" if actual_str == expected_str else "MISMATCH"
        results.append(
            B4AFixtureExecution(
                fixture_id=fid if exp_idx == 0 else f"{fid}_branch{exp_idx+1}",
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
    parser = argparse.ArgumentParser(description="Run Block 4 Lane A fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b4_a_fixtures(master_path)

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
