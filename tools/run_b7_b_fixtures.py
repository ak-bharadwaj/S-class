#!/usr/bin/env python3
"""Master-driven fixture runner for Block 7 Lane B (PD-CH7-014, PD-CH7-015).

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
from sclass.product.notification_skill_normalization import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch7_014_notification_projections,
    evaluate_pd_ch7_015_external_skill_normalization,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B7BFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b7_b_fixtures(master_path: Path) -> List[B7BFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B7BFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], GateOutput], str, int]] = [
        # CH7-T20 -> PD-CH7-014
        (
            "CH7-T20", "PD-CH7-014",
            lambda: evaluate_pd_ch7_014_notification_projections(
                derived_from_gate_projection=True,
                implies_approval_on_model_message=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Notification implies approval/closure on model-generated message",
            0,
        ),
        # CH7-T21 -> PD-CH7-014
        (
            "CH7-T21", "PD-CH7-014",
            lambda: evaluate_pd_ch7_014_notification_projections(
                derived_from_gate_projection=True,
                implies_approval_on_model_message=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Notification derived strictly from gate projection",
            0,
        ),
        # CH7-T22 -> PD-CH7-015
        (
            "CH7-T22", "PD-CH7-015",
            lambda: evaluate_pd_ch7_015_external_skill_normalization(
                normalized_into_sclass_owned_checks=True,
                creates_alternate_lifecycle_or_loop=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "External skill content creates alternate lifecycle or agent loop",
            0,
        ),
        # CH7-T23 -> PD-CH7-015
        (
            "CH7-T23", "PD-CH7-015",
            lambda: evaluate_pd_ch7_015_external_skill_normalization(
                normalized_into_sclass_owned_checks=True,
                creates_alternate_lifecycle_or_loop=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "External skill content normalized into S-Class-owned checks",
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
            B7BFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 7 Lane B fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b7_b_fixtures(master_path)

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
