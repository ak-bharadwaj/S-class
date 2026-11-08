#!/usr/bin/env python3
"""Master-driven fixture runner for Block 4 Lane F (PD-CH4-007, PD-CH4-008).

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
from sclass.product.context_resume_threats import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch4_007_context_resume_anchors,
    evaluate_pd_ch4_008_threat_matrix_containment,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B4FFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b4_f_fixtures(master_path: Path) -> List[B4FFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B4FFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], GateOutput], str]] = [
        # CH4-T7 -> PD-CH4-007
        (
            "CH4-T7", "PD-CH4-007",
            lambda: evaluate_pd_ch4_007_context_resume_anchors(
                canonical_anchors_present=False,
                pinned_guidance_digests=["sha256:g1"],
                step_pack_digest="sha256:pack",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T7 missing anchor in context resume",
        ),
        # CH4-T30 -> PD-CH4-007
        (
            "CH4-T30", "PD-CH4-007",
            lambda: evaluate_pd_ch4_007_context_resume_anchors(
                canonical_anchors_present=True,
                pinned_guidance_digests=["sha256:g1"],
                step_pack_digest="sha256:pack",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T30 happy: resumed step pack rebuilt from canonical anchors",
        ),
        # CH4-T8 -> PD-CH4-008
        (
            "CH4-T8", "PD-CH4-008",
            lambda: evaluate_pd_ch4_008_threat_matrix_containment(
                threat_matrix_rows=[
                    {
                        "threat_id": "T-01",
                        "detection": "det_module",
                        "gate": "ExecutionGate",
                        "containment": None,
                        "fixture": "CH4-T8",
                    }
                ],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "CH4-T8 any row missing control/fixture",
        ),
    ]

    for fid, mid, fn, notes in cases:
        fixture = parse_master_fixture(master_path, fid)
        expected_str = fixture.primary_expected
        out: GateOutput = fn()
        actual_str = f"{out.state.value}[{out.must_id}]" if out.state != GateState.SATISFIED else "SATISFIED"

        status = "RAN-MATCH" if actual_str == expected_str else "MISMATCH"
        results.append(
            B4FFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 4 Lane F fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b4_f_fixtures(master_path)

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
