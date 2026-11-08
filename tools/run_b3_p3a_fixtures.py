#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 2 Lane P3A (PD-CH2-013, 014, 015, 016, 017, 018).

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
from sclass.product.lifecycle_p3a import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_013_requirement_coverage,
    evaluate_pd_ch2_014_domain_invariants,
    evaluate_pd_ch2_015_architecture_provenance,
    evaluate_pd_ch2_016_dependency_relationships,
    evaluate_pd_ch2_017_domain_model_substance,
    evaluate_pd_ch2_018_architecture_record_substance,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P3AFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p3a_fixtures(master_path: Path) -> List[P3AFixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P3AFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-013 (Line 1820)
        (
            "CH2-T13", "PD-CH2-013",
            lambda: evaluate_pd_ch2_013_requirement_coverage(
                requirements=[{"id": "REQ-1", "semantic_coverage": False, "explicit_applicability": False}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: unmapped requirement -> MISSING[PD-CH2-013]",
        ),
        # PD-CH2-014 (Line 1821)
        (
            "CH2-T14", "PD-CH2-014",
            lambda: evaluate_pd_ch2_014_domain_invariants(
                domain_entities=[{"name": "Account", "invariants": []}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: no invariant represented -> MISSING[PD-CH2-014]",
        ),
        # PD-CH2-015 (Line 1822)
        (
            "CH2-T15", "PD-CH2-015",
            lambda: evaluate_pd_ch2_015_architecture_provenance(
                architecture_elements=[{"name": "Gateway", "provenance": None}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: architecture provenance absent -> MISSING[PD-CH2-015]",
        ),
        # PD-CH2-016 (Line 1823)
        (
            "CH2-T16", "PD-CH2-016",
            lambda: evaluate_pd_ch2_016_dependency_relationships(
                material_dependencies=[{"source": "ServiceA", "destination": "Database"}],
                represented_edges=[("ServiceA", "Other")],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: edge absent -> MISSING[PD-CH2-016]",
        ),
        # PD-CH2-017 (Line 1824)
        (
            "CH2-T17", "PD-CH2-017",
            lambda: evaluate_pd_ch2_017_domain_model_substance(
                domain_model={"entities": [{"name": "User", "fields": [], "constraints": []}]},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: names only -> MISSING[PD-CH2-017]",
        ),
        # PD-CH2-018 (Line 1825)
        (
            "CH2-T18", "PD-CH2-018",
            lambda: evaluate_pd_ch2_018_architecture_record_substance(
                architecture_record={"components": ["API", "Worker"], "interactions": [], "boundaries": [], "contracts": []},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: components only -> MISSING[PD-CH2-018]",
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
            P3AFixtureExecution(
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


def print_summary_table(results: List[P3AFixtureExecution]) -> None:
    print("=" * 89)
    print("LANE B3-P3A FIXTURE RUNNER SUMMARY (6 VECTORS)")
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
    print(f"Status: {match_count}/{len(results)} RAN-MATCH across Lane P3A fixtures.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Lane P3A fixtures against master.")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", os.environ.get("SCLASS_MASTER_PATH", "")),
        help="Path to authoritative master document",
    )
    args = parser.parse_args()

    master_path = Path(args.master_path).resolve()
    results = run_p3a_fixtures(master_path)
    print_summary_table(results)

    if any(r.status != "RAN-MATCH" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
