#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 2 Lane P3C (PD-CH2-026, 028, 051, 052, 053).

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
from sclass.product.lifecycle_p3c_p8_p10 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_026_adr_design_digest_binding,
    evaluate_pd_ch2_028_unique_must_ids,
    evaluate_pd_ch2_051_p8_retry_budget_exhaustion,
    evaluate_pd_ch2_052_p9_task_aggregation_findings_closure,
    evaluate_pd_ch2_053_p10_kernel_release_evaluation,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P3CFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p3c_fixtures(master_path: Path) -> List[P3CFixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P3CFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-026 (Line 1832)
        (
            "CH2-T26", "PD-CH2-026",
            lambda: evaluate_pd_ch2_026_adr_design_digest_binding(
                adr_sources=[{"id": "ADR-1", "digest": "sha256:1", "lint_passed": False, "is_stale": True}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: stale/unresolved -> MISSING[PD-CH2-026]",
        ),
        # PD-CH2-028 (Line 1833)
        (
            "CH2-T28", "PD-CH2-028",
            lambda: evaluate_pd_ch2_028_unique_must_ids(
                must_ids=["MID-1", "MID-2", "MID-1"],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: duplicate ID -> MISSING[PD-CH2-028]",
        ),
        # PD-CH2-051 (Line 2215)
        (
            "CH2-T51", "PD-CH2-051",
            lambda: evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
                retry_budget_remaining=0,
                earliest_affected_phase="P2",
                routed_phase="P2",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: exhausted budget -> BLOCKED_ON_HUMAN[PD-CH2-051]",
        ),
        # PD-CH2-052 (Line 2281)
        (
            "CH2-T52", "PD-CH2-052",
            lambda: evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
                required_p7_tasks=["T-1", "T-2"],
                aggregated_p7_tasks=["T-1"],
                open_mandatory_findings=[],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: one required P7 result omitted -> MISSING[PD-CH2-052]",
        ),
        # PD-CH2-053 (Line 2347)
        (
            "CH2-T53", "PD-CH2-053",
            lambda: evaluate_pd_ch2_053_p10_kernel_release_evaluation(
                kernel_release_evaluation="DENIED",
                product_checks_pass=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: kernel ReleaseEvaluation=DENIED -> DENIED",
        ),
    ]

    for fid, mid, runner, notes in cases:
        parsed = parse_master_fixture(master_path, fid)
        # Runtime assertion: returned master line contains fixture ID
        target_line = lines[parsed.line_number - 1]
        assert fid in target_line, (
            f"Runtime assertion failure: line {parsed.line_number} does not contain {fid}: {target_line}"
        )

        gate_res: Any = runner()
        actual_str = str(gate_res)

        match = False
        for exp in parsed.expected_gate_strings:
            if exp == actual_str:
                match = True
                break

        status = "RAN-MATCH" if match else "RAN-MISMATCH"
        results.append(
            P3CFixtureExecution(
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


def print_summary_table(results: List[P3CFixtureExecution]) -> None:
    print("=" * 89)
    print("LANE B3-P3C FIXTURE RUNNER SUMMARY (5 VECTORS)")
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
    print(f"Status: {match_count}/{len(results)} RAN-MATCH across Lane P3C fixtures.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lane P3C fixtures against master.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", os.environ.get("SCLASS_MASTER_PATH", "")),
        help="Path to authoritative master document",
    )
    args = parser.parse_args()

    master_path = Path(args.master_path).resolve()
    results = run_p3c_fixtures(master_path)
    print_summary_table(results)

    if any(r.status != "RAN-MATCH" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
