#!/usr/bin/env python3
"""Master-driven fixture runner for Block 4 Lane B (PD-F10-007, PD-CH3-015..018, PD-CH3-020).

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
from sclass.product.adapter_diff_spec_anchors import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_f10_007_differential_detection,
    evaluate_pd_ch3_015_artifact_binding_integrity,
    evaluate_pd_ch3_016_spec_anchor_resolution,
    evaluate_pd_ch3_017_predicate_measurable_thresholds,
    evaluate_pd_ch3_018_clarification_authorized_outcome,
    evaluate_pd_ch3_020_spec_change_replay_point,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B4BFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b4_b_fixtures(master_path: Path) -> List[B4BFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B4BFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], GateOutput], str]] = [
        # F10-T8 -> PD-F10-007
        (
            "F10-T8", "PD-F10-007",
            lambda: evaluate_pd_f10_007_differential_detection(
                canonical_semantics_primary={"primary_count": 10},
                canonical_semantics_secondary={"primary_count": 9},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "F10-FT8 canonical semantic mismatch while process exit codes agree",
        ),
        # CH3-T15 -> PD-CH3-015
        (
            "CH3-T15", "PD-CH3-015",
            lambda: evaluate_pd_ch3_015_artifact_binding_integrity(
                objective_revision="rev-01",
                source_digest="sha256:stored_bytes",
                artifact_type="REQUIREMENTS_SPEC",
                owning_authority=None,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T15 gaming: owning_authority omitted",
        ),
        # CH3-T16 -> PD-CH3-015
        (
            "CH3-T16", "PD-CH3-015",
            lambda: evaluate_pd_ch3_015_artifact_binding_integrity(
                objective_revision="rev-01",
                source_digest="sha256:stored_bytes",
                artifact_type="REQUIREMENTS_SPEC",
                owning_authority="auth-team",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T16 happy: all named inputs present and valid",
        ),
        # CH3-T17 -> PD-CH3-016
        (
            "CH3-T17", "PD-CH3-016",
            lambda: evaluate_pd_ch3_016_spec_anchor_resolution(
                spec_path="00-SPEC/core.md",
                symbol_or_heading="Section 4.1",
                line_range=(9999, 10000),
                anchor_digest="sha256:anchor123",
                file_length_lines=500,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T17 gaming: line_range beyond file length",
        ),
        # CH3-T18 -> PD-CH3-016
        (
            "CH3-T18", "PD-CH3-016",
            lambda: evaluate_pd_ch3_016_spec_anchor_resolution(
                spec_path="00-SPEC/core.md",
                symbol_or_heading="Section 4.1",
                line_range=(100, 150),
                anchor_digest="sha256:anchor123",
                file_length_lines=500,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T18 happy: resolved exact spec path, symbol, and valid line range",
        ),
        # CH3-T19 -> PD-CH3-017
        (
            "CH3-T19", "PD-CH3-017",
            lambda: evaluate_pd_ch3_017_predicate_measurable_thresholds(
                predicate="coverage_floor",
                threshold_value=0.95,
                threshold_unit=None,
                policy_digest="sha256:pol123",
                policy_revision="rev-1",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T19 gaming: threshold_unit omitted from numeric threshold",
        ),
        # CH3-T20 -> PD-CH3-017
        (
            "CH3-T20", "PD-CH3-017",
            lambda: evaluate_pd_ch3_017_predicate_measurable_thresholds(
                predicate="coverage_floor",
                threshold_value=0.95,
                threshold_unit="percentage",
                policy_digest="sha256:pol123",
                policy_revision="rev-1",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T20 happy: measurable threshold bound to policy digest",
        ),
        # CH3-T21 -> PD-CH3-018
        (
            "CH3-T21", "PD-CH3-018",
            lambda: evaluate_pd_ch3_018_clarification_authorized_outcome(
                clarification_id="CLAR-01",
                authorized_outcome_digest=None,
                resolver_identity="lead-architect",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T21 gaming: authorized_outcome_digest absent",
        ),
        # CH3-T22 -> PD-CH3-018
        (
            "CH3-T22", "PD-CH3-018",
            lambda: evaluate_pd_ch3_018_clarification_authorized_outcome(
                clarification_id="CLAR-01",
                authorized_outcome_digest="sha256:out123",
                resolver_identity="lead-architect",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T22 happy: clarification with authorized outcome digest and confirmed resolver",
        ),
        # CH3-T25 -> PD-CH3-020
        (
            "CH3-T25", "PD-CH3-020",
            lambda: evaluate_pd_ch3_020_spec_change_replay_point(
                spec_anchor_digest="sha256:anchor_changed",
                affected_evidence_digests=["sha256:ev1"],
                earliest_replay_phase=None,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T25 gaming: earliest_replay_phase omitted after spec change",
        ),
        # CH3-T26 -> PD-CH3-020
        (
            "CH3-T26", "PD-CH3-020",
            lambda: evaluate_pd_ch3_020_spec_change_replay_point(
                spec_anchor_digest="sha256:anchor_changed",
                affected_evidence_digests=["sha256:ev1", "sha256:ev2"],
                earliest_replay_phase="P2",
                invalidated_evidence=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH3-T26 happy: spec change identifies earliest replay point and invalidates evidence",
        ),
    ]

    for fid, mid, fn, notes in cases:
        fixture = parse_master_fixture(master_path, fid)
        expected_str = fixture.primary_expected
        out: GateOutput = fn()
        actual_str = f"{out.state.value}[{out.must_id}]" if out.state != GateState.SATISFIED else "SATISFIED"

        status = "RAN-MATCH" if actual_str == expected_str else "MISMATCH"
        results.append(
            B4BFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 4 Lane B fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b4_b_fixtures(master_path)

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
