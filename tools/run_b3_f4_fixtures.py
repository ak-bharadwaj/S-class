#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 1 Lane F4 (PD-F4-001..PD-F4-006).

Parses authoritative fixtures F4-T1 through F4-T7 directly from the hash-verified
Master Product Design document using the shared parser (tools/master_fixtures.py),
executes evaluate_f4_lane_selection, and outputs an audited status table with exact
master line citations.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from sclass.product.f4_lane_selection import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_f4_lane_selection,
    get_depth_budget,
)
from sclass.product.gate import GateOutput, GateState
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class F4FixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_f4_fixtures(master_path: Path) -> List[F4FixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[F4FixtureExecution] = []

    # Concrete inputs strictly matching Master Product Design table (lines 594-600)
    # F4-T1: L594
    mf1 = parse_master_fixture(master_path, "F4-T1")
    assert "F4-T1" in lines[mf1.line_number - 1], f"Line {mf1.line_number} does not contain F4-T1"
    p1 = {
        "depth_dimensions": {
            "planning": "D1", "discovery": "D1", "context": "D1", "domain_model": "D0",
            "data_model": "D0", "architecture": "D0", "testing": "D1", "verification": "D1",
            "recovery": "D0", "independence": "D0",
        },
        "risk_tier": "LOW", "failure_impact": "LOW", "regulatory_sensitivity": "NONE",
        "required_independence": "NONE", "irreversibility": False, "rollback_capability": True,
        "estimated_files": 2, "modules": 1,
        "change_surface": {"databases": 0, "external_integrations": 0, "deployment_surfaces": 0, "apis": 0, "schemas": 0},
        "security_sensitivity": "NONE",
        "external_effects": {"external_systems": 0, "user_visible_effects": False, "financial_effects": False, "security_effects": False},
        "critical_flag": False, "requested_lane": "MICRO",
    }
    out1 = evaluate_f4_lane_selection(p1, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    actual1 = str(out1)
    status1 = "RAN-MATCH" if actual1 in mf1.expected_gate_strings else "RAN-MISMATCH"
    results.append(F4FixtureExecution("F4-T1", "PD-F4-001", mf1.line_number, mf1.primary_expected, actual1, status1, "Micro eligible -> computed MICRO"))

    # F4-T2: L595
    mf2 = parse_master_fixture(master_path, "F4-T2")
    assert "F4-T2" in lines[mf2.line_number - 1], f"Line {mf2.line_number} does not contain F4-T2"
    p2 = {
        "depth_dimensions": {
            "planning": "D2", "discovery": "D2", "context": "D2", "domain_model": "D3",
            "data_model": "D3", "architecture": "D3", "testing": "D3", "verification": "D4",
            "recovery": "D3", "independence": "D3",
        },
        "critical_flag": False, "requested_lane": "CRITICAL",
    }
    out2 = evaluate_f4_lane_selection(p2, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    actual2 = str(out2)
    status2 = "RAN-MATCH" if actual2 in mf2.expected_gate_strings else "RAN-MISMATCH"
    results.append(F4FixtureExecution("F4-T2", "PD-F4-001", mf2.line_number, mf2.primary_expected, actual2, status2, "Verification depth D4 -> computed CRITICAL"))

    # F4-T3: L596
    mf3 = parse_master_fixture(master_path, "F4-T3")
    assert "F4-T3" in lines[mf3.line_number - 1], f"Line {mf3.line_number} does not contain F4-T3"
    p3 = {
        "depth_dimensions": {
            "planning": "D1", "discovery": "D1", "context": "D1", "domain_model": "D1",
            "data_model": "D0", "architecture": "D1", "testing": "D1", "verification": "D1",
            "recovery": "D1", "independence": "D0",
        },
        "risk_tier": "LOW", "failure_impact": "LOW",
        "change_surface": {"apis": 1, "databases": 0, "schemas": 0, "external_integrations": 0, "deployment_surfaces": 0},
        "external_effects": {"external_systems": 0, "user_visible_effects": False, "financial_effects": False, "security_effects": False},
        "security_sensitivity": "NONE", "critical_flag": False, "requested_lane": "MICRO",
    }
    out3 = evaluate_f4_lane_selection(p3, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    actual3 = str(out3)
    status3 = "RAN-MATCH" if actual3 in mf3.expected_gate_strings else "RAN-MISMATCH"
    results.append(F4FixtureExecution("F4-T3", "PD-F4-002", mf3.line_number, mf3.primary_expected, actual3, status3, "API change rejects MICRO request -> MISSING[PD-F4-002]"))

    # F4-T4: L597 (Master specifies two branches: DDL present -> SATISFIED / absent -> MISSING[PD-F1-003])
    mf4 = parse_master_fixture(master_path, "F4-T4")
    assert "F4-T4" in lines[mf4.line_number - 1], f"Line {mf4.line_number} does not contain F4-T4"
    # Branch A: DDL present
    p4_present = {
        "depth_dimensions": {
            "planning": "D1", "discovery": "D1", "context": "D1", "domain_model": "D1",
            "data_model": "D1", "architecture": "D1", "testing": "D1", "verification": "D1",
            "recovery": "D1", "independence": "D0",
        },
        "risk_tier": "LOW", "failure_impact": "LOW",
        "change_surface": {"databases": 1, "apis": 0, "schemas": 0, "external_integrations": 0, "deployment_surfaces": 0},
        "external_effects": {"external_systems": 0, "user_visible_effects": False, "financial_effects": False, "security_effects": False},
        "security_sensitivity": "NONE", "critical_flag": False,
        "f1_artifact_class": "data", "f1_required_representation": "DDL",
        "requested_lane": "STANDARD", "ddl_present": True,
    }
    out4_a = evaluate_f4_lane_selection(p4_present, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    actual4_a = str(out4_a)
    # Branch B: DDL absent
    p4_absent = dict(p4_present)
    p4_absent["ddl_present"] = False
    out4_b = evaluate_f4_lane_selection(p4_absent, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    actual4_b = str(out4_b)

    branch_match = (actual4_a == "SATISFIED" and actual4_b == "MISSING[PD-F1-003]")
    status4 = "RAN-MATCH" if branch_match else "RAN-MISMATCH"
    combined_actual4 = f"{actual4_a} (DDL present) / {actual4_b} (DDL absent)"
    results.append(F4FixtureExecution("F4-T4", "PD-F4-003", mf4.line_number, "SATISFIED / MISSING[PD-F1-003]", combined_actual4, status4, "DDL present SATISFIED; DDL absent MISSING[PD-F1-003]"))

    # F4-T5: L598
    mf5 = parse_master_fixture(master_path, "F4-T5")
    assert "F4-T5" in lines[mf5.line_number - 1], f"Line {mf5.line_number} does not contain F4-T5"
    p5 = {
        "profile_derived_depth": "D1", "policy_floor": "D3", "requested_lane": "STANDARD",
    }
    out5 = evaluate_f4_lane_selection(p5, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    actual5 = str(out5)
    status5 = "RAN-MATCH" if actual5 in mf5.expected_gate_strings else "RAN-MISMATCH"
    results.append(F4FixtureExecution("F4-T5", "PD-F4-006", mf5.line_number, mf5.primary_expected, actual5, status5, "Policy floor D3 overrides profile D1 -> SATISFIED"))

    # F4-T6: L599 (Replay EngineeringProfile revision 8)
    mf6 = parse_master_fixture(master_path, "F4-T6")
    assert "F4-T6" in lines[mf6.line_number - 1], f"Line {mf6.line_number} does not contain F4-T6"
    p6 = {
        "prior_lane": "STANDARD", "security_change": True, "policy_critical_predicate": True,
        "canonical_profile_revision": 8, "recorded_lane": "CRITICAL",
        "replayed_profile_revision": 8, "requested_lane": "CRITICAL",
    }
    out6 = evaluate_f4_lane_selection(p6, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    actual6 = str(out6)
    rev8_reproduced = (
        out6.explain.get("replayed_profile_revision") == 8 and
        out6.explain.get("computed_lane") == "CRITICAL"
    )
    status6 = "RAN-MATCH" if (actual6 in mf6.expected_gate_strings and rev8_reproduced) else "RAN-MISMATCH"
    note6 = f"EngineeringProfile rev 8 replay -> {out6.explain.get('computed_lane')}"
    results.append(F4FixtureExecution("F4-T6", "PD-F4-005", mf6.line_number, mf6.primary_expected, actual6, status6, note6))

    # F4-T7: L600 (Exact budget triple lookup: 8192 / EVAL-LARGE / 2)
    mf7 = parse_master_fixture(master_path, "F4-T7")
    assert "F4-T7" in lines[mf7.line_number - 1], f"Line {mf7.line_number} does not contain F4-T7"
    p7 = {
        "depth": "D3", "max_assignments": 8192, "adapter_resource_limits_class": "EVAL-LARGE",
        "interruption_budget": 2, "requested_lane": "STANDARD",
    }
    out7 = evaluate_f4_lane_selection(p7, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    actual7 = str(out7)
    bt = out7.explain.get("budget_triple", {})
    triple_matched = (
        bt.get("max_assignments") == 8192 and
        bt.get("adapter_resource_limits_class") == "EVAL-LARGE" and
        bt.get("interruption_budget") == 2
    )
    status7 = "RAN-MATCH" if (actual7 in mf7.expected_gate_strings and triple_matched) else "RAN-MISMATCH"
    note7 = f"Triple: {bt.get('max_assignments')}/{bt.get('adapter_resource_limits_class')}/{bt.get('interruption_budget')}"
    results.append(F4FixtureExecution("F4-T7", "PD-F4-004", mf7.line_number, mf7.primary_expected, actual7, status7, note7))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Block 3 Wave 1 Lane F4 Fixtures")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", ""),
        help="Path to authoritative Master Product Design Markdown file.",
    )
    args = parser.parse_args()

    if not args.master_path:
        print("FATAL: --master-path argument or SCLASS_MASTER_PATH environment variable required.", file=sys.stderr)
        return 1

    master_path = Path(args.master_path)
    try:
        verify_master_sha256(master_path)
    except Exception as ex:
        print(f"FATAL: Master verification failed: {ex}", file=sys.stderr)
        return 1

    results = run_f4_fixtures(master_path)

    print("=========================================================================================")
    print("BLOCK 3 WAVE 1 — LANE F4 FIXTURE CONFORMANCE TABLE")
    print("=========================================================================================")
    print(f"Master Doc SHA256: {EXPECTED_MASTER_SHA256}")
    print(f"Total Vectors:     {len(results)}")
    print("-----------------------------------------------------------------------------------------")
    print(f"{'Fixture ID':<10} | {'Owner MUST':<12} | {'Master Line':<11} | {'Expected Output':<30} | {'Actual Output':<30} | {'Status'}")
    print("-----------------------------------------------------------------------------------------")
    for r in results:
        print(f"{r.fixture_id:<10} | {r.must_id:<12} | L{r.master_line:<10} | {r.expected:<30} | {r.actual:<30} | {r.status}")
    print("=========================================================================================")
    print("Execution Details:")
    for r in results:
        print(f"  {r.fixture_id} (L{r.master_line}): {r.notes}")
    print("=========================================================================================")

    mismatches = [r for r in results if r.status != "RAN-MATCH"]
    if mismatches:
        print(f"RAN-MISMATCH count: {len(mismatches)}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
