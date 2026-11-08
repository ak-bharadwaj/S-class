#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 2 Lane P1P4 (PD-CH2-056, 057, 029, 031, 032).

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
from sclass.product.lifecycle_p1_p4 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_056_discovery_completeness,
    evaluate_pd_ch2_057_skill_depth_precedence,
    evaluate_pd_ch2_029_task_caps,
    evaluate_pd_ch2_031_work_graph_acyclic,
    evaluate_pd_ch2_032_write_set_overlap,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P1P4FixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p1p4_fixtures(master_path: Path) -> List[P1P4FixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P1P4FixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-056 (Line 1668)
        (
            "CH2-T57", "PD-CH2-056",
            lambda: evaluate_pd_ch2_056_discovery_completeness(
                target_snapshot_resolved=False,
                index_coverage_ratio=0.75,
                high_impact_unknowns_resolved=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: unresolvable snapshot / incomplete coverage -> MISSING[PD-CH2-056]",
        ),
        (
            "CH2-T58", "PD-CH2-056",
            lambda: evaluate_pd_ch2_056_discovery_completeness(
                target_snapshot_resolved=True,
                index_coverage_ratio=1.0,
                high_impact_unknowns_resolved=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: fully resolved snapshot, 1.0 coverage, resolved unknowns -> SATISFIED",
        ),
        # PD-CH2-057 (Line 1687)
        (
            "CH2-T59", "PD-CH2-057",
            lambda: evaluate_pd_ch2_057_skill_depth_precedence(
                skills_resolved=True,
                pinned_skill_digests=[],
                policy_floor_respected=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: pinned_skill_digests omitted from step-pack binding -> MISSING[PD-CH2-057]",
        ),
        (
            "CH2-T60", "PD-CH2-057",
            lambda: evaluate_pd_ch2_057_skill_depth_precedence(
                skills_resolved=True,
                pinned_skill_digests=["sha256:abc1234"],
                policy_floor_respected=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: skills resolved and digests pinned -> SATISFIED",
        ),
        # PD-CH2-029 (Line 1921)
        (
            "CH2-T29", "PD-CH2-029",
            lambda: evaluate_pd_ch2_029_task_caps(
                lane_type="MICRO",
                task_units=7,
                task_count=1,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: MICRO task of 7 units exceeds 4-unit cap -> MISSING[PD-CH2-029]",
        ),
        # PD-CH2-031 (Line 1922)
        (
            "CH2-T31", "PD-CH2-031",
            lambda: evaluate_pd_ch2_031_work_graph_acyclic(
                graph_edges={"T1": ["T2"], "T2": ["T1"]},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: dependency cycle -> MISSING[PD-CH2-031]",
        ),
        # PD-CH2-032 (Line 1923)
        (
            "CH2-T32", "PD-CH2-032",
            lambda: evaluate_pd_ch2_032_write_set_overlap(
                tasks=[
                    {"task_id": "T1", "declared_write_set": {"fileA.py"}, "serialized": True},
                    {"task_id": "T2", "declared_write_set": {"fileA.py"}, "serialized": True},
                ],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: known overlap serialized -> SATISFIED",
        ),
    ]

    for fid, mid, runner, notes in cases:
        parsed = parse_master_fixture(master_path, fid)
        # Runtime assertion: returned master line contains fixture ID
        target_line = lines[parsed.line_number - 1]
        assert fid in target_line, (
            f"Runtime assertion failure: line {parsed.line_number} does not contain {fid}: {target_line}"
        )

        gate_res: GateOutput = runner()
        actual_str = str(gate_res)

        match = False
        for exp in parsed.expected_gate_strings:
            if exp == actual_str:
                match = True
                break

        status = "RAN-MATCH" if match else "RAN-MISMATCH"
        results.append(
            P1P4FixtureExecution(
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


def print_summary_table(results: List[P1P4FixtureExecution]) -> None:
    print("=" * 89)
    print("LANE B3-P1P4 FIXTURE RUNNER SUMMARY (7 VECTORS)")
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
    print(f"Status: {match_count}/{len(results)} RAN-MATCH across Lane P1P4 fixtures.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lane P1P4 fixtures against master.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", "/mnt/c/Users/dorni/Downloads/S-CLASS-R32-PACKAGE/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"),
        help="Path to authoritative master document",
    )
    args = parser.parse_args()

    master_path = Path(args.master_path).resolve()
    results = run_p1p4_fixtures(master_path)
    print_summary_table(results)

    if any(r.status != "RAN-MATCH" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
