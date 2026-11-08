#!/usr/bin/env python3
"""Master-driven fixture runner for Block 4 Lane E (PD-CH4-010, PD-CH4-014, PD-CH4-016, PD-CH4-002, 005, 006).

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
from sclass.product.isolation_claims import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch4_010_test_input_write_isolation,
    evaluate_pd_ch4_014_authorized_delta_scope,
    evaluate_pd_ch4_016_independent_evidence_producers,
    evaluate_pd_ch4_002_execution_claim_receipt,
    evaluate_pd_ch4_005_evidence_freshness_identity,
    evaluate_pd_ch4_006_canonical_closure_vs_prose,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B4EFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b4_e_fixtures(master_path: Path) -> List[B4EFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B4EFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], GateOutput], str]] = [
        # CH4-T12 -> PD-CH4-010
        (
            "CH4-T12", "PD-CH4-010",
            lambda: evaluate_pd_ch4_010_test_input_write_isolation(
                implementation_write_paths=["src/feature.py"],
                test_input_paths=["tests/test_feature.py"],
                manifest_unchanged=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T12 altered manifest in P7 evidence",
        ),
        # CH4-T19 -> PD-CH4-014
        (
            "CH4-T19", "PD-CH4-014",
            lambda: evaluate_pd_ch4_014_authorized_delta_scope(
                observed_delta_paths=["src/feature.py", "unauthorized_file.txt"],
                authorized_write_paths=["src/feature.py"],
                green_test_run=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T19 delta outside authorized scope returns BLOCKED",
        ),
        # CH4-T20 -> PD-CH4-014
        (
            "CH4-T20", "PD-CH4-014",
            lambda: evaluate_pd_ch4_014_authorized_delta_scope(
                observed_delta_paths=["src/feature.py"],
                authorized_write_paths=["src/feature.py"],
                green_test_run=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T20 delta strictly within authorized scope",
        ),
        # CH4-T23 -> PD-CH4-016
        (
            "CH4-T23", "PD-CH4-016",
            lambda: evaluate_pd_ch4_016_independent_evidence_producers(
                primary_producer="producer-A",
                independent_producer="producer-A",
                is_self_review=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T23 self-review or shared unqualified adapter",
        ),
        # CH4-T24 -> PD-CH4-016
        (
            "CH4-T24", "PD-CH4-016",
            lambda: evaluate_pd_ch4_016_independent_evidence_producers(
                primary_producer="producer-A",
                independent_producer="producer-B-independent",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T24 distinct independent evidence producers",
        ),
        # CH4-T2 -> PD-CH4-002
        (
            "CH4-T2", "PD-CH4-002",
            lambda: evaluate_pd_ch4_002_execution_claim_receipt(
                has_execution_claim=True,
                has_structured_results=False,
                raw_result_digest=None,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T2 agent says PASS without receipt",
        ),
        # CH4-T5 -> PD-CH4-005
        (
            "CH4-T5", "PD-CH4-005",
            lambda: evaluate_pd_ch4_005_evidence_freshness_identity(
                requirement_revision_digest="sha256:rev2",
                evidence_requirement_digest="sha256:rev1_stale",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T5 changed requirement with old green evidence",
        ),
        # CH4-T28 -> PD-CH4-005
        (
            "CH4-T28", "PD-CH4-005",
            lambda: evaluate_pd_ch4_005_evidence_freshness_identity(
                requirement_revision_digest="sha256:rev1",
                evidence_requirement_digest="sha256:rev1",
                target_identity_match=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T28 receipt matches target, adapter, environment, and floor",
        ),
        # CH4-T6 -> PD-CH4-006
        (
            "CH4-T6", "PD-CH4-006",
            lambda: evaluate_pd_ch4_006_canonical_closure_vs_prose(
                agent_prose_done_claim=True,
                kernel_obligation_closure=False,
                has_admissible_evidence=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T6 agent says done but closure absent",
        ),
        # CH4-T29 -> PD-CH4-006
        (
            "CH4-T29", "PD-CH4-006",
            lambda: evaluate_pd_ch4_006_canonical_closure_vs_prose(
                agent_prose_done_claim=True,
                kernel_obligation_closure=True,
                has_admissible_evidence=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T29 completion derives from kernel obligation closure and evidence",
        ),
    ]

    for fid, mid, fn, notes in cases:
        fixture = parse_master_fixture(master_path, fid)
        expected_str = fixture.primary_expected
        out: GateOutput = fn()
        # Handle cases where master fixture expected string is "MISSING" without brackets
        if expected_str == "MISSING" and out.state == GateState.MISSING:
            actual_str = "MISSING"
        else:
            actual_str = f"{out.state.value}[{out.must_id}]" if out.state != GateState.SATISFIED else "SATISFIED"

        status = "RAN-MATCH" if actual_str == expected_str else "MISMATCH"
        results.append(
            B4EFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 4 Lane E fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b4_e_fixtures(master_path)

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
