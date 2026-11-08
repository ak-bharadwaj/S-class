#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 2 Lane P0B (PD-CH2-007, 008, 009, 010, 011, 012).

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
from sclass.product.lifecycle_p0b import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    STANDARD_LIFECYCLE_PHASES,
    evaluate_pd_ch2_007_p8_retry_budget,
    evaluate_pd_ch2_008_p11_non_terminal_reentry,
    evaluate_pd_ch2_009_done_claim_evidence_closure,
    evaluate_pd_ch2_010_green_external_run_evidence,
    evaluate_pd_ch2_011_stack_pack_phase_topology,
    evaluate_pd_ch2_012_mandatory_floor_human_waiver,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P0BFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p0b_fixtures(master_path: Path) -> List[P0BFixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P0BFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-007 (Line 1326)
        (
            "CH2-T7", "PD-CH2-007",
            lambda: evaluate_pd_ch2_007_p8_retry_budget(
                retry_budget_allocated=3,
                retry_budget_consumed=3,
                alternate_retry_path_active=True,
                is_p8_repair=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: RetryBudget exhausted but alternate retry continues -> MISSING[PD-CH2-007]",
        ),
        # PD-CH2-008 (Line 1327)
        (
            "CH2-T8", "PD-CH2-008",
            lambda: evaluate_pd_ch2_008_p11_non_terminal_reentry(
                trigger_type="post_release_regression",
                target_phase="P7",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: post-release regression re-enters at P7 instead of P0 -> MISSING[PD-CH2-008]",
        ),
        # PD-CH2-009 (Line 1328)
        (
            "CH2-T9", "PD-CH2-009",
            lambda: evaluate_pd_ch2_009_done_claim_evidence_closure(
                model_done_claimed=True,
                admissible_evidence_present=False,
                kernel_evaluated_closure=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: agent submits DONE without evidence -> MISSING[PD-CH2-009]",
        ),
        # PD-CH2-010 (Line 1329)
        (
            "CH2-T10", "PD-CH2-010",
            lambda: evaluate_pd_ch2_010_green_external_run_evidence(
                external_run_green=True,
                bound_to_obligation_inputs=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: unrelated green suite submitted for this obligation -> MISSING[PD-CH2-010]",
        ),
        # PD-CH2-011 (Line 1330)
        (
            "CH2-T11", "PD-CH2-011",
            lambda: evaluate_pd_ch2_011_stack_pack_phase_topology(
                stack_pack_topology=("P0", "P1", "P2", "P3_ALT", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"),
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: stack pack introduces alternate phase topology -> MISSING[PD-CH2-011]",
        ),
        # PD-CH2-012 (Line 1331)
        (
            "CH2-T12", "PD-CH2-012",
            lambda: evaluate_pd_ch2_012_mandatory_floor_human_waiver(
                waiver_requested=True,
                has_authorized_waiver_path=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: unsupported override with no frozen authorization -> BLOCKED_ON_HUMAN[PD-CH2-012]",
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
            P0BFixtureExecution(
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


def print_summary_table(results: List[P0BFixtureExecution]) -> None:
    print("=" * 89)
    print("LANE B3-P0B FIXTURE RUNNER SUMMARY (6 VECTORS)")
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
    print(f"Status: {match_count}/{len(results)} RAN-MATCH across Lane P0B fixtures.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lane P0B fixtures against master.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", os.environ.get("SCLASS_MASTER_PATH", "")),
        help="Path to authoritative master document",
    )
    args = parser.parse_args()

    master_path = Path(args.master_path).resolve()
    results = run_p0b_fixtures(master_path)
    print_summary_table(results)

    if any(r.status != "RAN-MATCH" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
