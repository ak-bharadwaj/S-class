#!/usr/bin/env python3
"""Master Conformance Runner for Block 3 (All 69 MUSTs: Wave 1 + Wave 2).

Integrates all 12 lane fixture runners across Block 3:
Wave 1:
  - Lane F4  (PD-F4-001..PD-F4-006, 6 MUSTs)
  - Lane E   (PD-F8-001..PD-F8-004, PD-CH2-064, PD-CH2-065, 6 MUSTs)
  - Lane P11 (PD-CH2-054, PD-CH2-058, PD-CH2-060..PD-CH2-063, 6 MUSTs)
Wave 2:
  - Lane P0A  (PD-CH2-001..003, 005, 006, 055, 6 MUSTs)
  - Lane P0B  (PD-CH2-007..012, 6 MUSTs)
  - Lane P1P4 (PD-CH2-056, 057, 029, 031, 032, 5 MUSTs)
  - Lane P3A  (PD-CH2-013..018, 6 MUSTs)
  - Lane P3B  (PD-CH2-020..025, 6 MUSTs)
  - Lane P3C  (PD-CH2-026, 028, 051..053, 5 MUSTs)
  - Lane P5   (PD-CH2-033..036, 046, 047, 6 MUSTs)
  - Lane P6   (PD-CH2-037..040, 048, 5 MUSTs)
  - Lane P7   (PD-CH2-041..045, 050, 6 MUSTs)

Total MUSTs: 69 (18 Wave 1 + 51 Wave 2).
Uses the shared parser tools/master_fixtures.py exclusively.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    parse_all_must_descriptions,
    resolve_master_path,
    verify_master_sha256,
)

# Import individual lane runners
from tools.run_b3_f4_fixtures import run_f4_fixtures
from tools.run_b3_e_fixtures import run_e_fixtures
from tools.run_b3_p11_fixtures import run_p11_fixtures
from tools.run_b3_p0a_fixtures import run_p0a_fixtures
from tools.run_b3_p0b_fixtures import run_p0b_fixtures
from tools.run_b3_p1p4_fixtures import run_p1p4_fixtures
from tools.run_b3_p3a_fixtures import run_p3a_fixtures
from tools.run_b3_p3b_fixtures import run_p3b_fixtures
from tools.run_b3_p3c_fixtures import run_p3c_fixtures
from tools.run_b3_p5_fixtures import run_p5_fixtures
from tools.run_b3_p6_fixtures import run_p6_fixtures
from tools.run_b3_p7_fixtures import run_p7_fixtures


ALL_B3_MUSTS = [
    # Wave 1: Lane F4 (6 MUSTs)
    ("PD-F4-001", "L-F4", "F4 Lane Selection Base"),
    ("PD-F4-002", "L-F4", "F4 Standard Fast Lane Criteria"),
    ("PD-F4-003", "L-F4", "F4 Critical Deep Lane Criteria"),
    ("PD-F4-004", "L-F4", "F4 Replay Lane Determinism"),
    ("PD-F4-005", "L-F4", "F4 Migration Lane Precedence"),
    ("PD-F4-006", "L-F4", "F4 Lane Selection Immutability"),
    # Wave 1: Lane E (6 MUSTs)
    ("PD-F8-001", "L-E", "F8 Architecture Synthesis Floor"),
    ("PD-F8-002", "L-E", "F8 Synthesis Authority Validation"),
    ("PD-F8-003", "L-E", "F8 Multi-Candidate Pareto Verification"),
    ("PD-F8-004", "L-E", "F8 Traceability Sealing"),
    ("PD-CH2-064", "L-E", "Cross-Phase Invariant Integrity"),
    ("PD-CH2-065", "L-E", "Replay Lineage Immutability"),
    # Wave 1: Lane P11 (6 MUSTs)
    ("PD-CH2-054", "L-P11", "P2-P3 Hand-off Integrity"),
    ("PD-CH2-058", "L-P11", "Architecture Boundary Enforcement"),
    ("PD-CH2-060", "L-P11", "Cross-Phase Invariant Checking"),
    ("PD-CH2-061", "L-P11", "Replay Lineage Immutability"),
    ("PD-CH2-062", "L-P11", "Phase Transition Gate Registry"),
    ("PD-CH2-063", "L-P11", "Post-Release Lineage Preservation"),
    # Wave 2: Lane P0A (6 MUSTs)
    ("PD-CH2-001", "L-P0A", "P0 Global Phase Precedence"),
    ("PD-CH2-002", "L-P0A", "P0 Backward Transition Prohibition"),
    ("PD-CH2-003", "L-P0A", "P0 Gate Result Immutability"),
    ("PD-CH2-005", "L-P0A", "P0 Authority Elevation Prohibition"),
    ("PD-CH2-006", "L-P0A", "P0 Cross-Phase Invariant Integrity"),
    ("PD-CH2-055", "L-P0A", "P0 Scope Boundary Guard"),
    # Wave 2: Lane P0B (6 MUSTs)
    ("PD-CH2-007", "L-P0B", "P0 Fail-Closed Default"),
    ("PD-CH2-008", "L-P0B", "P0 Evidence Lineage Hash Verification"),
    ("PD-CH2-009", "L-P0B", "P0 Cryptographic Signature Integrity"),
    ("PD-CH2-010", "L-P0B", "P0 Environment Parity Check"),
    ("PD-CH2-011", "L-P0B", "P0 Qualified Authority Binding"),
    ("PD-CH2-012", "L-P0B", "P0 Execution Context Isolation"),
    # Wave 2: Lane P1P4 (5 MUSTs)
    ("PD-CH2-056", "L-P1P4", "P1 Problem Formulation Completeness"),
    ("PD-CH2-057", "L-P1P4", "P1 Objective Space Boundedness"),
    ("PD-CH2-029", "L-P1P4", "P4 Architecture Planning Floor"),
    ("PD-CH2-031", "L-P1P4", "P4 Interface Contract Sealing"),
    ("PD-CH2-032", "L-P1P4", "P4 Cross-Module Dependency Check"),
    # Wave 2: Lane P3A (6 MUSTs)
    ("PD-CH2-013", "L-P3A", "P3 Solution Strategy Enumerable"),
    ("PD-CH2-014", "L-P3A", "P3 Tradeoff Space Pareto Boundary"),
    ("PD-CH2-015", "L-P3A", "P3 Feasibility Gate Validation"),
    ("PD-CH2-016", "L-P3A", "P3 Rejection Rationale Persistence"),
    ("PD-CH2-017", "L-P3A", "P3 Strategy Decision Authority"),
    ("PD-CH2-018", "L-P3A", "P3 Precondition Satisfaction"),
    # Wave 2: Lane P3B (6 MUSTs)
    ("PD-CH2-020", "L-P3B", "P3 Decision Audit Trail Completeness"),
    ("PD-CH2-021", "L-P3B", "P3 Multi-Criteria Evaluation Binding"),
    ("PD-CH2-022", "L-P3B", "P3 Sensitivity Analysis Requirement"),
    ("PD-CH2-023", "L-P3B", "P3 Fallback Strategy Specification"),
    ("PD-CH2-024", "L-P3B", "P3 Strategic Assumption Register"),
    ("PD-CH2-025", "L-P3B", "P3 Strategy Invalidation Protocol"),
    # Wave 2: Lane P3C (5 MUSTs)
    ("PD-CH2-026", "L-P3C", "P3 Strategy Lineage Anchoring"),
    ("PD-CH2-028", "L-P3C", "P3 Decision Record Non-repudiation"),
    ("PD-CH2-051", "L-P3C", "P8 Post-Release Monitoring Floor"),
    ("PD-CH2-052", "L-P3C", "P9 Operational Feedback Invariant"),
    ("PD-CH2-053", "L-P3C", "P10 Decommissioning Authority Gate"),
    # Wave 2: Lane P5 (6 MUSTs)
    ("PD-CH2-033", "L-P5", "P5 Implementation Floor Invariant"),
    ("PD-CH2-034", "L-P5", "P5 Code-Spec Traceability Sealing"),
    ("PD-CH2-035", "L-P5", "P5 Automated Test Gate Coverage"),
    ("PD-CH2-036", "L-P5", "P5 Static Verification Enforcement"),
    ("PD-CH2-046", "L-P5", "P5 Security Boundary Audit"),
    ("PD-CH2-047", "L-P5", "P5 Performance Claim Validation"),
    # Wave 2: Lane P6 (5 MUSTs)
    ("PD-CH2-037", "L-P6", "P6 Implementation Governance Scope"),
    ("PD-CH2-038", "L-P6", "P6 Scope Creep Invalidation"),
    ("PD-CH2-039", "L-P6", "P6 Invariant Preservation Check"),
    ("PD-CH2-040", "L-P6", "P6 Change Authority Validation"),
    ("PD-CH2-048", "L-P6", "P6 Test Completeness Verification"),
    # Wave 2: Lane P7 (6 MUSTs)
    ("PD-CH2-041", "L-P7", "P7 Verification Decision Record Authority"),
    ("PD-CH2-042", "L-P7", "P7 Independent Verifier Separation"),
    ("PD-CH2-043", "L-P7", "P7 Requirements Hash Matching"),
    ("PD-CH2-044", "L-P7", "P7 Decision Record Immutability"),
    ("PD-CH2-045", "L-P7", "P7 Negative Result Transition Block"),
    ("PD-CH2-050", "L-P7", "P7 Composite Release Invariant Bundle"),
]


def run_all_block3_fixtures(master_path: Path) -> Tuple[List[Any], Dict[str, str]]:
    verify_master_sha256(master_path)
    
    all_results = []
    lane_runners = [
        ("L-F4", run_f4_fixtures),
        ("L-E", run_e_fixtures),
        ("L-P11", run_p11_fixtures),
        ("L-P0A", run_p0a_fixtures),
        ("L-P0B", run_p0b_fixtures),
        ("L-P1P4", run_p1p4_fixtures),
        ("L-P3A", run_p3a_fixtures),
        ("L-P3B", run_p3b_fixtures),
        ("L-P3C", run_p3c_fixtures),
        ("L-P5", run_p5_fixtures),
        ("L-P6", run_p6_fixtures),
        ("L-P7", run_p7_fixtures),
    ]
    
    must_coverage: Dict[str, str] = {}
    for must_id, lane, desc in ALL_B3_MUSTS:
        must_coverage[must_id] = "NOT_COVERED"

    for lane_id, runner in lane_runners:
        results = runner(master_path)
        for r in results:
            all_results.append((lane_id, r))
            if r.must_id in must_coverage:
                if r.status == "RAN-MATCH":
                    must_coverage[r.must_id] = "COVERED_RAN_MATCH"
                elif must_coverage[r.must_id] != "COVERED_RAN_MATCH":
                    must_coverage[r.must_id] = f"FIXTURE_{r.status}"

    return all_results, must_coverage


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all Block 3 fixtures (Wave 1 + Wave 2).")
    parser.add_argument("--master", type=Path, default=None, help="Path to master design markdown")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    print("=" * 105)
    print("BLOCK 3 COMPREHENSIVE CONFORMANCE FIXTURE RUNNER (ALL 69 MUSTs: WAVE 1 + WAVE 2)")
    print(f"Master: {master_path}")
    print(f"Master SHA-256: {EXPECTED_MASTER_SHA256}")
    print("=" * 105)

    all_results, must_coverage = run_all_block3_fixtures(master_path)

    print(f"{'Lane':<7} | {'Fixture ID':<10} | {'Owner MUST':<12} | {'Master Line':<11} | {'Expected Gate Output':<25} | {'Actual Gate Output':<25} | {'Status':<10}")
    print("-" * 105)

    mismatches = 0
    not_run = 0
    parse_failed = 0
    ran_match = 0

    for lane_id, r in all_results:
        print(f"{lane_id:<7} | {r.fixture_id:<10} | {r.must_id:<12} | L{r.master_line:<10} | {r.expected:<25} | {r.actual:<25} | {r.status:<10}")
        if r.status == "RAN-MATCH":
            ran_match += 1
        elif r.status == "MISMATCH":
            mismatches += 1
        elif r.status == "PARSE_FAILED":
            parse_failed += 1
        else:
            not_run += 1

    print("=" * 105)
    print(f"TOTAL VECTORS EVALUATED: {len(all_results)}")
    print(f"  RAN-MATCH:    {ran_match}")
    print(f"  MISMATCH:     {mismatches}")
    print(f"  NOT_RUN:      {not_run}")
    print(f"  PARSE_FAILED: {parse_failed}")
    print("=" * 105)

    # Print MUST Accountability Table for all 69 MUSTs
    print("\n" + "=" * 105)
    print("BLOCK 3 MUST ACCOUNTABILITY TABLE (ALL 69 MUSTs)")
    print("=" * 105)
    print(f"{'MUST ID':<14} | {'Lane':<8} | {'Status':<22} | {'Description'}")
    print("-" * 105)

    must_descriptions = parse_all_must_descriptions(master_path)
    unaccounted = 0
    for must_id, lane, static_desc in ALL_B3_MUSTS:
        status = must_coverage.get(must_id, "UNACCOUNTED")
        if status != "COVERED_RAN_MATCH":
            unaccounted += 1
        desc = must_descriptions.get(must_id, static_desc)
        print(f"{must_id:<14} | {lane:<8} | {status:<22} | {desc}")

    print("=" * 105)
    print(f"TOTAL BLOCK 3 MUSTs: {len(ALL_B3_MUSTS)}")
    print(f"FULLY COVERED WITH RAN-MATCH: {len(ALL_B3_MUSTS) - unaccounted} / {len(ALL_B3_MUSTS)}")
    print("=" * 105)

    if mismatches > 0 or not_run > 0 or parse_failed > 0 or unaccounted > 0:
        print(f"FAILURE: {mismatches} mismatches, {not_run} not run, {parse_failed} parse failed, {unaccounted} unaccounted MUSTs.")
        return 1

    print("ALL BLOCK 3 FIXTURES PASSED WITH 100% CONFORMANCE (ALL 69 MUSTs FULLY SATISFIED).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
