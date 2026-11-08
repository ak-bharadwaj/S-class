#!/usr/bin/env python3
"""Master-driven fixture runner for Block 4 Lane C (PD-CH3-001..003, PD-CH3-006..007, PD-CH3-009).

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
from sclass.product.lifecycle_phase_admission import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch3_001_phase_artifact_anchors,
    evaluate_pd_ch3_002_normative_requirements_completeness,
    evaluate_pd_ch3_003_clarification_scope_entry,
    evaluate_pd_ch3_006_external_tool_candidate_trust,
    evaluate_pd_ch3_007_work_type_decision_projection,
    evaluate_pd_ch3_009_flow_gates_and_lane_computation,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B4CFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b4_c_fixtures(master_path: Path) -> List[B4CFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B4CFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], GateOutput], str]] = [
        # CH3-T1 -> PD-CH3-001
        (
            "CH3-T1", "PD-CH3-001",
            lambda: evaluate_pd_ch3_001_phase_artifact_anchors(
                objective_revision="rev-02",
                spec_anchor_digests=["sha256:anchor1"],
                expected_objective_revision="rev-01",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T1 mismatched objective/anchor digest",
        ),
        # CH3-T2 -> PD-CH3-002
        (
            "CH3-T2", "PD-CH3-002",
            lambda: evaluate_pd_ch3_002_normative_requirements_completeness(
                requirements=[{"id": "REQ-1", "text": "Unlinked requirement", "acceptance_links": []}],
                non_goals=["non-goal-1"],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T2 unlinked criterion or normative placeholder",
        ),
        # CH3-T3 -> PD-CH3-003
        (
            "CH3-T3", "PD-CH3-003",
            lambda: evaluate_pd_ch3_003_clarification_scope_entry(
                scope_changed=True,
                canonical_decision_recorded=False,
                human_confirmed=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T3 agent claims confirmation with no USER/POLICY outcome",
        ),
        # CH3-T6 -> PD-CH3-006
        (
            "CH3-T6", "PD-CH3-006",
            lambda: evaluate_pd_ch3_006_external_tool_candidate_trust(
                tool_identity="unqualified-process-tool",
                qualification_recorded=False,
                claimed_authoritative=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T6 unqualified process source claimed authoritative",
        ),
        # CH3-T7 -> PD-CH3-007
        (
            "CH3-T7", "PD-CH3-007",
            lambda: evaluate_pd_ch3_007_work_type_decision_projection(
                canonical_decision_outcome="DEC-FEATURE",
                projected_work_type="FEATURE",
                agent_override_attempted=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T7 agent-only work-type label change",
        ),
        # CH3-T9 -> PD-CH3-009
        (
            "CH3-T9", "PD-CH3-009",
            lambda: evaluate_pd_ch3_009_flow_gates_and_lane_computation(
                flow_identity="endpoint_flow",
                contract_tests_present=False,
                computed_lane="STANDARD_LANE",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T9 endpoint flow omits contract test or uses agent-selected lane",
        ),
    ]

    for fid, mid, fn, notes in cases:
        fixture = parse_master_fixture(master_path, fid)
        expected_str = fixture.primary_expected
        out: GateOutput = fn()
        actual_str = f"{out.state.value}[{out.must_id}]" if out.state != GateState.SATISFIED else "SATISFIED"

        status = "RAN-MATCH" if actual_str == expected_str else "MISMATCH"
        results.append(
            B4CFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 4 Lane C fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b4_c_fixtures(master_path)

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
