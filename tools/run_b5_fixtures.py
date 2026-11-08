#!/usr/bin/env python3
"""Master-driven fixture runner for Block 5 Lane B5 (PD-CH8-008..PD-CH8-013).

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
from sclass.product.enforcement_workspace_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch8_008_prevention_boundary,
    evaluate_pd_ch8_009_workspace_promotion,
    evaluate_pd_ch8_010_out_of_band_edits,
    evaluate_pd_ch8_011_parallel_work_serialization,
    evaluate_pd_ch8_012_repository_intelligence,
    evaluate_pd_ch8_013_budget_exhaustion_ledger,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B5FixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b5_fixtures(master_path: Path) -> List[B5FixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B5FixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], GateOutput], str, int]] = [
        # CH8-T8 -> PD-CH8-008
        (
            "CH8-T8", "PD-CH8-008",
            lambda: evaluate_pd_ch8_008_prevention_boundary(
                prevention_claimed=True,
                inside_qualified_enforcement_boundary=False,
                is_native_ide_activity=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Prevention claimed outside launched qualified enforcement boundary",
            0,
        ),
        # CH8-T9 -> PD-CH8-008
        (
            "CH8-T9", "PD-CH8-008",
            lambda: evaluate_pd_ch8_008_prevention_boundary(
                prevention_claimed=True,
                inside_qualified_enforcement_boundary=True,
                is_native_ide_activity=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Prevention claimed inside qualified enforcement boundary",
            0,
        ),
        # CH8-T10 -> PD-CH8-009
        (
            "CH8-T10", "PD-CH8-009",
            lambda: evaluate_pd_ch8_009_workspace_promotion(
                target_verified=False,
                kernel_release_authority=True,
                rollback_evidence_preserved=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Workspace promotion attempted without verified target",
            0,
        ),
        # CH8-T11 -> PD-CH8-009
        (
            "CH8-T11", "PD-CH8-009",
            lambda: evaluate_pd_ch8_009_workspace_promotion(
                target_verified=True,
                kernel_release_authority=True,
                rollback_evidence_preserved=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Workspace promotion with verified target, authority, and rollback evidence",
            0,
        ),
        # CH8-T12 -> PD-CH8-010
        (
            "CH8-T12", "PD-CH8-010",
            lambda: evaluate_pd_ch8_010_out_of_band_edits(
                out_of_band_edits_detected=True,
                re_snapshot_taken=False,
                digest_comparison_passed=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Out-of-band edits without re-snapshot and digest comparison",
            0,
        ),
        # CH8-T13 -> PD-CH8-010
        (
            "CH8-T13", "PD-CH8-010",
            lambda: evaluate_pd_ch8_010_out_of_band_edits(
                out_of_band_edits_detected=True,
                re_snapshot_taken=True,
                digest_comparison_passed=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Out-of-band edits followed by re-snapshot and matching digest comparison",
            0,
        ),
        # CH8-T14 -> PD-CH8-011
        (
            "CH8-T14", "PD-CH8-011",
            lambda: evaluate_pd_ch8_011_parallel_work_serialization(
                dependencies_satisfied=False,
                canonical_delta_order=True,
                overlapping_writes_serialized=True,
                target_identity_match=True,
                all_task_verification_pass=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Parallel work violating dependency ordering",
            0,
        ),
        # CH8-T15 -> PD-CH8-011
        (
            "CH8-T15", "PD-CH8-011",
            lambda: evaluate_pd_ch8_011_parallel_work_serialization(
                dependencies_satisfied=True,
                canonical_delta_order=True,
                overlapping_writes_serialized=True,
                target_identity_match=True,
                all_task_verification_pass=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Parallel work obeying dependencies, delta order, serialization, and verification",
            0,
        ),
        # CH8-T16 -> PD-CH8-012
        (
            "CH8-T16", "PD-CH8-012",
            lambda: evaluate_pd_ch8_012_repository_intelligence(
                discloses_coverage=False,
                discloses_freshness=True,
                unresolved_symbol_present=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Repository intelligence missing index coverage disclosure",
            0,
        ),
        # CH8-T17 -> PD-CH8-012
        (
            "CH8-T17", "PD-CH8-012",
            lambda: evaluate_pd_ch8_012_repository_intelligence(
                discloses_coverage=True,
                discloses_freshness=True,
                unresolved_symbol_present=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Repository intelligence disclosing freshness and coverage with zero unresolved symbols",
            0,
        ),
        # CH8-T18 -> PD-CH8-013
        (
            "CH8-T18", "PD-CH8-013",
            lambda: evaluate_pd_ch8_013_budget_exhaustion_ledger(
                budget_exhausted=True,
                routed_to_authorized_repair=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Budget exhaustion without routing to authorized repair",
            0,
        ),
        # CH8-T19 -> PD-CH8-013
        (
            "CH8-T19", "PD-CH8-013",
            lambda: evaluate_pd_ch8_013_budget_exhaustion_ledger(
                budget_exhausted=False,
                routed_to_authorized_repair=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Budget within frozen limits using authoritative cost metrics",
            0,
        ),
    ]

    for fid, mid, fn, notes, exp_idx in cases:
        fixture = parse_master_fixture(master_path, fid)
        expected_str = fixture.expected_gate_strings[exp_idx]
        out: GateOutput = fn()
        actual_str = f"{out.state.value}[{out.must_id}]" if out.state != GateState.SATISFIED else "SATISFIED"

        status = "RAN-MATCH" if actual_str == expected_str else "MISMATCH"
        results.append(
            B5FixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 5 Lane B5 fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b5_fixtures(master_path)

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
