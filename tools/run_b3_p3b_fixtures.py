#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 2 Lane P3B (PD-CH2-020, 021, 022, 023, 024, 025).

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
from sclass.product.lifecycle_p3b import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_020_decidable_invariants,
    evaluate_pd_ch2_021_cross_entity_constraints,
    evaluate_pd_ch2_022_change_surface_boundary_closure,
    evaluate_pd_ch2_023_boundary_data_flow_contracts,
    evaluate_pd_ch2_024_interface_signatures_typed_contracts,
    evaluate_pd_ch2_025_unknown_contradiction_handling,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P3BFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p3b_fixtures(master_path: Path) -> List[P3BFixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P3BFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-020 (Line 1826)
        (
            "CH2-T20", "PD-CH2-020",
            lambda: evaluate_pd_ch2_020_decidable_invariants(
                invariants=[{"name": "HaltingInv", "fragment": "UNDECIDABLE", "supported": False, "claimed_pass": True}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: unsupported PASS -> MISSING[PD-CH2-020]",
        ),
        # PD-CH2-021 (Line 1827)
        (
            "CH2-T21", "PD-CH2-021",
            lambda: evaluate_pd_ch2_021_cross_entity_constraints(
                constraints=[{"id": "C-1", "relationship": None, "cardinality": "1..*"}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: no relation -> MISSING[PD-CH2-021]",
        ),
        # PD-CH2-022 (Line 1828)
        (
            "CH2-T22", "PD-CH2-022",
            lambda: evaluate_pd_ch2_022_change_surface_boundary_closure(
                change_surface_boundaries=["A", "B", "Uncovered"],
                dependency_edges=[("A", "B")],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: edge absent -> MISSING[PD-CH2-022]",
        ),
        # PD-CH2-023 (Line 1829)
        (
            "CH2-T23", "PD-CH2-023",
            lambda: evaluate_pd_ch2_023_boundary_data_flow_contracts(
                data_flows=[{"id": "F-1", "source": "API", "destination": "Queue", "contract": "Avro", "transformation": None}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: no transform -> MISSING[PD-CH2-023]",
        ),
        # PD-CH2-024 (Line 1830)
        (
            "CH2-T24", "PD-CH2-024",
            lambda: evaluate_pd_ch2_024_interface_signatures_typed_contracts(
                interfaces=[{"name": "GetUser", "signature_type": "RawDict", "domain_contract_type": "UserDTO", "requirement_predicate_type": "UserDTO"}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: mismatch -> MISSING[PD-CH2-024]",
        ),
        # PD-CH2-025 (Line 1831)
        (
            "CH2-T25", "PD-CH2-025",
            lambda: evaluate_pd_ch2_025_unknown_contradiction_handling(
                has_unknown_contradiction=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: unknown result -> MISSING[PD-CH2-025]",
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
            P3BFixtureExecution(
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


def print_summary_table(results: List[P3BFixtureExecution]) -> None:
    print("=" * 89)
    print("LANE B3-P3B FIXTURE RUNNER SUMMARY (6 VECTORS)")
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
    print(f"Status: {match_count}/{len(results)} RAN-MATCH across Lane P3B fixtures.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lane P3B fixtures against master.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", os.environ.get("SCLASS_MASTER_PATH", "")),
        help="Path to authoritative master document",
    )
    args = parser.parse_args()

    master_path = Path(args.master_path).resolve()
    results = run_p3b_fixtures(master_path)
    print_summary_table(results)

    if any(r.status != "RAN-MATCH" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
