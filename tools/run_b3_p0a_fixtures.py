#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 2 Lane P0A (PD-CH2-001, 002, 003, 005, 006, 055).

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
from sclass.product.lifecycle_p0a import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    STANDARD_PHASES,
    ELEVEN_DIMENSIONS,
    evaluate_pd_ch2_001_single_lifecycle,
    evaluate_pd_ch2_002_eleven_dimensions,
    evaluate_pd_ch2_003_earlier_phase_validity,
    evaluate_pd_ch2_005_skipped_phase_applicability,
    evaluate_pd_ch2_006_earliest_defect_routing,
    evaluate_pd_ch2_055_downstream_invalidation,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P0AFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p0a_fixtures(master_path: Path) -> List[P0AFixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P0AFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-001 (Line 9968)
        (
            "CH2-T1", "PD-CH2-001",
            lambda: evaluate_pd_ch2_001_single_lifecycle(
                {
                    "work_type": "FEATURE",
                    "phase_sequence": list(STANDARD_PHASES),
                    "alternate_phase": "P12",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: alternate phase P12 -> MISSING[PD-CH2-001]",
        ),
        # PD-CH2-002 (Line 9976)
        (
            "CH2-T2", "PD-CH2-002",
            lambda: evaluate_pd_ch2_002_eleven_dimensions(
                {
                    "phase": "P6",
                    "missing_dimension": "Applicability",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: missing Applicability dimension -> MISSING[PD-CH2-002]",
        ),
        # PD-CH2-003 (Line 1323)
        (
            "CH2-T3", "PD-CH2-003",
            lambda: evaluate_pd_ch2_003_earlier_phase_validity(
                {
                    "current_phase": "P3",
                    "earlier_phase_status": {"P2": "INVALID"},
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: invalid P2 artifact followed by P3 attempt -> MISSING[PD-CH2-003]",
        ),
        # PD-CH2-005 (Line 1324)
        (
            "CH2-T5", "PD-CH2-005",
            lambda: evaluate_pd_ch2_005_skipped_phase_applicability(
                {
                    "skipped_phases": ["P2"],
                    "applicability_declaration_absent": True,
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: applicability declaration absent -> MISSING[PD-CH2-005]",
        ),
        # PD-CH2-006 (Line 1325)
        (
            "CH2-T6", "PD-CH2-006",
            lambda: evaluate_pd_ch2_006_earliest_defect_routing(
                {
                    "defect_found_in": "P6",
                    "earliest_affected_phase": "P2",
                    "routed_phase": "P6",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: requirement defect found during P6 routes to P6 instead of P2 -> MISSING[PD-CH2-006]",
        ),
        # PD-CH2-055 (Line 1353)
        (
            "CH2-T55", "PD-CH2-055",
            lambda: evaluate_pd_ch2_055_downstream_invalidation(
                {
                    "bypass_attempt": True,
                    "authoritative_dependency_digest": "DIGEST-NEW-123",
                    "recomputation_key": {"dependency_digest": "DIGEST-OLD-000"},
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: bypass attempt with stale downstream projection -> MISSING[PD-CH2-055]",
        ),
        (
            "CH2-T56", "PD-CH2-055",
            lambda: evaluate_pd_ch2_055_downstream_invalidation(
                {
                    "authoritative_dependency_digest": "DIGEST-NEW-123",
                    "downstream_invalidated": True,
                    "recomputation_key": {"dependency_digest": "DIGEST-NEW-123"},
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: downstream invalidated and visible in recomputation key -> SATISFIED",
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
            P0AFixtureExecution(
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


def print_summary_table(results: List[P0AFixtureExecution]) -> None:
    print("=" * 89)
    print("LANE B3-P0A FIXTURE RUNNER SUMMARY (7 VECTORS)")
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
    print(f"Status: {match_count}/{len(results)} RAN-MATCH across Lane P0A fixtures.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lane P0A fixtures against master.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", "/mnt/c/Users/dorni/Downloads/S-CLASS-R32-PACKAGE/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"),
        help="Path to authoritative master document",
    )
    args = parser.parse_args()

    master_path = Path(args.master_path).resolve()
    results = run_p0a_fixtures(master_path)
    print_summary_table(results)

    if any(r.status != "RAN-MATCH" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
