#!/usr/bin/env python3
"""Master-driven fixture runner for Block 9 Lane C (PD-CH10-012..013, PD-CH10-007).

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
from sclass.product.erratum_issue_registry import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_OPEN_ISSUE_FIELDS,
    evaluate_pd_ch10_012_frozen_erratum_path,
    evaluate_pd_ch10_013_open_issue_schema,
    evaluate_pd_ch10_007_master_cross_links,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B9CFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b9_c_fixtures(master_path: Path) -> List[B9CFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B9CFixtureExecution] = []

    valid_issue = {f: f"val_{f}" for f in REQUIRED_OPEN_ISSUE_FIELDS}

    cases: List[Tuple[str, str, Callable[[], GateOutput], str, int]] = [
        # CH10-T16 -> PD-CH10-012
        (
            "CH10-T16", "PD-CH10-012",
            lambda: evaluate_pd_ch10_012_frozen_erratum_path(
                formal_erratum_path=False,
                insufficiency_analysis_present=False,
                replay_analysis_present=False,
                ad_hoc_source_edit=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Frozen source edit attempted ad-hoc without erratum path",
            0,
        ),
        # CH10-T17 -> PD-CH10-012
        (
            "CH10-T17", "PD-CH10-012",
            lambda: evaluate_pd_ch10_012_frozen_erratum_path(
                formal_erratum_path=True,
                insufficiency_analysis_present=True,
                replay_analysis_present=True,
                ad_hoc_source_edit=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Formal erratum path with concrete insufficiency and replay analysis",
            0,
        ),
        # CH10-T18 -> PD-CH10-013
        (
            "CH10-T18", "PD-CH10-013",
            lambda: evaluate_pd_ch10_013_open_issue_schema(
                {"impact": "HIGH"},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Open issue schema missing required fields",
            0,
        ),
        # CH10-T19 -> PD-CH10-013
        (
            "CH10-T19", "PD-CH10-013",
            lambda: evaluate_pd_ch10_013_open_issue_schema(
                valid_issue,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Open issue names impact, owner, evidence, blocking phase, status",
            0,
        ),
        # CH10-T7 -> PD-CH10-007
        (
            "CH10-T7", "PD-CH10-007",
            lambda: evaluate_pd_ch10_007_master_cross_links(
                cross_linked_to_master=True,
                unknown_references_present=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Unknown issue/citation/claim reference in registry",
            0,
        ),
    ]

    for fid, mid, fn, notes, exp_idx in cases:
        fixture = parse_master_fixture(master_path, fid)
        expected_str = fixture.expected_gate_strings[exp_idx]
        out: GateOutput = fn()
        if expected_str == "MISSING" and out.state == GateState.MISSING:
            actual_str = "MISSING"
        elif out.state != GateState.SATISFIED:
            actual_str = f"{out.state.value}[{out.must_id}]"
        else:
            actual_str = "SATISFIED"

        status = "RAN-MATCH" if actual_str == expected_str else "MISMATCH"
        results.append(
            B9CFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 9 Lane C fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b9_c_fixtures(master_path)

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
