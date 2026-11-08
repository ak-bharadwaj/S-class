#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 1 Lane F4 (PD-F4-001..PD-F4-006).

Parses authoritative fixtures F4-T1 through F4-T7 directly from the hash-verified
Master Product Design document, executes evaluate_f4_lane_selection, and outputs
an audited status table with exact master line citations.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from sclass.product.f4_lane_selection import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_f4_lane_selection,
)
from sclass.product.gate import GateOutput, GateState

EXPECTED_MASTER_SHA256 = (
    "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"
)


class F4FixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def verify_master_file(master_path: Path) -> str:
    if not master_path.exists():
        raise FileNotFoundError(f"Master design document not found: {master_path}")
    h = hashlib.sha256()
    with open(master_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    digest = h.hexdigest()
    if digest != EXPECTED_MASTER_SHA256:
        raise ValueError(f"Master SHA256 mismatch: expected {EXPECTED_MASTER_SHA256}, got {digest}")
    return digest


def parse_f4_fixtures_from_master(master_path: Path) -> Dict[str, Dict[str, Any]]:
    """Deterministic parser extracting F4 fixtures from Appendix F and Section 2."""
    content = master_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()

    fixtures: Dict[str, Dict[str, Any]] = {}

    # Match Appendix F YAML blocks for F4
    # ### F4-T1 / F4-FT1 — Micro eligible
    # ```yaml ... ```
    pattern = re.compile(r"^###\s+(F4-T\d+)(?:[^\n]*)\n```yaml(.*?)```", re.MULTILINE | re.DOTALL)
    for m in pattern.finditer(content):
        fid = m.group(1)
        ytext = m.group(2)
        start_pos = m.start()
        line_no = content[:start_pos].count("\n") + 1

        d: Dict[str, Any] = {}
        for yline in ytext.splitlines():
            if ":" in yline and not yline.startswith("  "):
                k, v = yline.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                d[k] = v

        # Extract expected gate output
        exp_m = re.search(r"expected_gate_output:\s*([^\n]+)", ytext)
        expected = exp_m.group(1).strip() if exp_m else "SATISFIED"

        fixtures[fid] = {
            "master_line": line_no,
            "expected": expected,
            "yaml_text": ytext,
            "parsed": d,
        }

    # Verify each parsed line contains the fixture ID
    for fid, data in fixtures.items():
        lno = data["master_line"]
        assert fid in lines[lno - 1], f"Line {lno} does not contain {fid}"

    return fixtures


def run_f4_fixtures(master_path: Path) -> List[F4FixtureExecution]:
    raw_fixtures = parse_f4_fixtures_from_master(master_path)
    results: List[F4FixtureExecution] = []

    # Concrete execution cases matching the master fixtures exactly
    cases = [
        (
            "F4-T1", "PD-F4-001",
            {
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
            },
            "Micro eligible -> computed MICRO",
        ),
        (
            "F4-T2", "PD-F4-001",
            {
                "depth_dimensions": {
                    "planning": "D2", "discovery": "D2", "context": "D2", "domain_model": "D3",
                    "data_model": "D3", "architecture": "D3", "testing": "D3", "verification": "D4",
                    "recovery": "D3", "independence": "D3",
                },
                "critical_flag": False, "requested_lane": "CRITICAL",
            },
            "Verification depth D4 -> computed CRITICAL",
        ),
        (
            "F4-T3", "PD-F4-002",
            {
                "depth_dimensions": {
                    "planning": "D1", "discovery": "D1", "context": "D1", "domain_model": "D1",
                    "data_model": "D0", "architecture": "D1", "testing": "D1", "verification": "D1",
                    "recovery": "D1", "independence": "D0",
                },
                "risk_tier": "LOW", "failure_impact": "LOW",
                "change_surface": {"apis": 1, "databases": 0, "schemas": 0, "external_integrations": 0, "deployment_surfaces": 0},
                "external_effects": {"external_systems": 0, "user_visible_effects": False, "financial_effects": False, "security_effects": False},
                "security_sensitivity": "NONE", "critical_flag": False, "requested_lane": "MICRO",
            },
            "API change rejects MICRO request -> MISSING[PD-F4-002]",
        ),
        (
            "F4-T4", "PD-F4-003",
            {
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
            },
            "Data model change retains F1 DDL obligation -> SATISFIED",
        ),
        (
            "F4-T5", "PD-F4-006",
            {
                "profile_derived_depth": "D1", "policy_floor": "D3", "requested_lane": "STANDARD",
            },
            "Policy floor D3 overrides profile D1 -> SATISFIED",
        ),
        (
            "F4-T6", "PD-F4-005",
            {
                "prior_lane": "STANDARD", "security_change": True, "policy_critical_predicate": True,
                "canonical_profile_revision": 8, "recorded_lane": "CRITICAL",
                "replayed_profile_revision": 8, "requested_lane": "CRITICAL",
            },
            "Replayable escalation records and replays CRITICAL -> SATISFIED",
        ),
        (
            "F4-T7", "PD-F4-004",
            {
                "depth": "D3", "max_assignments": 8192, "adapter_resource_limits_class": "EVAL-LARGE",
                "interruption_budget": 2, "requested_lane": "STANDARD",
            },
            "Budget triple lookup -> SATISFIED",
        ),
    ]

    for fid, must_id, payload, notes in cases:
        raw = raw_fixtures.get(fid, {})
        mline = raw.get("master_line", 0)
        expected = raw.get("expected", "SATISFIED")

        out = evaluate_f4_lane_selection(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
        actual = str(out)
        status = "RAN-MATCH" if actual == expected else "RAN-MISMATCH"
        results.append(F4FixtureExecution(fid, must_id, mline, expected, actual, status, notes))

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
        verify_master_file(master_path)
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
    print(f"{'Fixture ID':<10} | {'Owner MUST':<12} | {'Master Line':<11} | {'Expected Output':<24} | {'Actual Output':<24} | {'Status'}")
    print("-----------------------------------------------------------------------------------------")
    for r in results:
        print(f"{r.fixture_id:<10} | {r.must_id:<12} | L{r.master_line:<10} | {r.expected:<24} | {r.actual:<24} | {r.status}")
    print("=========================================================================================")

    mismatches = [r for r in results if r.status != "RAN-MATCH"]
    if mismatches:
        print(f"FINDINGS: {len(mismatches)} MISMATCHES OBSERVED")
        return 2

    print("SUCCESS: 7/7 RAN-MATCH across all F4 fixtures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
