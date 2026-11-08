#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 1 Lane P11 (PD-CH2-054, 058, 060, 061, 062, 063).

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
from sclass.product.lifecycle_p11 import (
    ALL_PHASES,
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_054_signal,
    evaluate_pd_ch2_058_applicability,
    evaluate_pd_ch2_060_flow_order,
    evaluate_pd_ch2_061_delivery_flow,
    evaluate_pd_ch2_062_project_class,
    evaluate_pd_ch2_063_question_budget,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class P11FixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_p11_fixtures(master_path: Path) -> List[P11FixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[P11FixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # PD-CH2-054 (Line 2413)
        (
            "CH2-T54", "PD-CH2-054",
            lambda: evaluate_pd_ch2_054_signal(
                {
                    "source_event_ref": "absent",
                    "baseline_digest": "D1",
                    "observed_digest": "D2",
                    "proposed_action": "mutate_workspace",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: missing source event and workspace mutation -> MISSING[PD-CH2-054]",
        ),
        # PD-CH2-058 (Line 2473)
        (
            "CH2-T61", "PD-CH2-058",
            lambda: evaluate_pd_ch2_058_applicability(
                {
                    "must_id": "PD-CH2-058",
                    "work_type": "FEATURE",
                    "applicability_records[P0..P11]": [p for p in ALL_PHASES if p != "P7"],
                    "skip_reason": "none",
                    "evaluator_record_ref": "EVAL-01",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: applicability records missing P7 -> MISSING[PD-CH2-058]",
        ),
        (
            "CH2-T62", "PD-CH2-058",
            lambda: evaluate_pd_ch2_058_applicability(
                {
                    "must_id": "PD-CH2-058",
                    "work_type": "FEATURE",
                    "applicability_records[P0..P11]": list(ALL_PHASES),
                    "skip_reason": "none",
                    "evaluator_record_ref": "EVAL-01",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: all 12 phases declared with explicit skip reasons -> SATISFIED",
        ),
        # PD-CH2-060 (Line 2568)
        (
            "CH2-T65", "PD-CH2-060",
            lambda: evaluate_pd_ch2_060_flow_order(
                {
                    "must_id": "PD-CH2-060",
                    "phase_order": ["P0", "P1", "P2", "P3", "P5", "P4"],
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: phase order lists P5 before P4 -> MISSING[PD-CH2-060]",
        ),
        (
            "CH2-T66", "PD-CH2-060",
            lambda: evaluate_pd_ch2_060_flow_order(
                {
                    "must_id": "PD-CH2-060",
                    "flow_definition_digest": "FLOW-DEF-01",
                    "phase_order": ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"],
                    "defect_origin_phase": "P2",
                    "replay_start_phase": "P2",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: default flow preserves order & defect routing -> SATISFIED",
        ),
        # PD-CH2-061 (Line 2630)
        (
            "CH2-T67", "PD-CH2-061",
            lambda: evaluate_pd_ch2_061_delivery_flow(
                {
                    "must_id": "PD-CH2-061",
                    "entry_predicate_digest": "DIGEST-ENTRY-01",
                    "gate_output_digests": ["DIGEST-GATE-01"],
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: rollback condition digest absent -> MISSING[PD-CH2-061]",
        ),
        (
            "CH2-T68", "PD-CH2-061",
            lambda: evaluate_pd_ch2_061_delivery_flow(
                {
                    "must_id": "PD-CH2-061",
                    "entry_predicate_digest": "DIGEST-ENTRY-01",
                    "gate_output_digests": ["DIGEST-GATE-01", "DIGEST-GATE-02"],
                    "rollback_condition_digest": "DIGEST-ROLLBACK-01",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: entry predicate, gate outputs, and rollback bound -> SATISFIED",
        ),
        # PD-CH2-062 (Line 2694)
        (
            "CH2-T69", "PD-CH2-062",
            lambda: evaluate_pd_ch2_062_project_class(
                {
                    "must_id": "PD-CH2-062",
                    "project_class": "python_backend",
                    "qualification_record_digest": "DIGEST-QUAL-01",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: fit evidence absent (inferred from language) -> MISSING[PD-CH2-062]",
        ),
        (
            "CH2-T70", "PD-CH2-062",
            lambda: evaluate_pd_ch2_062_project_class(
                {
                    "must_id": "PD-CH2-062",
                    "project_class": "python_backend",
                    "fit_evidence_digest": "DIGEST-FIT-001",
                    "qualification_record_digest": "DIGEST-QUAL-001",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: explicit fit evidence and qualified record -> SATISFIED",
        ),
        # PD-CH2-063 (Line 2761)
        (
            "CH2-T71", "PD-CH2-063",
            lambda: evaluate_pd_ch2_063_question_budget(
                {
                    "must_id": "PD-CH2-063",
                    "questions_asked": -1,
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: non-integer / negative questions asked -> MISSING[PD-CH2-063]",
        ),
        (
            "CH2-T72", "PD-CH2-063",
            lambda: evaluate_pd_ch2_063_question_budget(
                {
                    "must_id": "PD-CH2-063",
                    "question_budget": 5,
                    "questions_asked": 3,
                    "open_blockers_digest": "DIGEST-BLOCKERS-01",
                    "treated_as_complete": False,
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: questions asked within integer budget, blockers open -> SATISFIED",
        ),
    ]

    for fid, must_id, eval_fn, notes in cases:
        mf = parse_master_fixture(master_path, fid)
        assert fid in lines[mf.line_number - 1], f"Line {mf.line_number} does not contain {fid}"

        out = eval_fn()
        actual = str(out)
        status = "RAN-MATCH" if actual in mf.expected_gate_strings else "RAN-MISMATCH"
        results.append(P11FixtureExecution(fid, must_id, mf.line_number, mf.primary_expected, actual, status, notes))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Block 3 Wave 1 Lane P11 Fixtures")
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

    results = run_p11_fixtures(master_path)

    print("=========================================================================================")
    print("BLOCK 3 WAVE 1 — LANE P11 FIXTURE CONFORMANCE TABLE")
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

    print(f"SUCCESS: {len(results)}/{len(results)} RAN-MATCH across all Lane P11 fixtures.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
