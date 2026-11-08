#!/usr/bin/env python3
"""Master-driven fixture runner for Block 3 Wave 1 Lane E (PD-F8-001..004, PD-CH2-064..065).

Parses authoritative fixtures F8-T1..T4 and CH2-T73..T76 directly from the
hash-verified Master Product Design document using the shared parser
(tools/master_fixtures.py), executes real evaluators, and outputs an audited status table.
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

from sclass.product.f8_step_pack import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_f8_step_pack,
)
from sclass.product.gate import GateOutput, GateState
from sclass.product.replay import (
    evaluate_ch2_064_replay_invalidation,
    evaluate_ch2_065_lifecycle_proof,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    verify_master_sha256,
)


class EFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_e_fixtures(master_path: Path) -> List[EFixtureExecution]:
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    results: List[EFixtureExecution] = []

    cases: List[Tuple[str, str, Callable[[], Any], str]] = [
        # F8 Step-Pack Fixtures (Lines 864-867)
        (
            "F8-T1", "PD-F8-001",
            lambda: evaluate_f8_step_pack(
                {
                    "canonical_state_binding": "SB-10",
                    "pinned_skills": ["SK-1", "SK-2"],
                    "context_budget_bytes": 4096,
                    "compiler_version": "C1",
                    "repeat_1_digest": "D-F8-1",
                    "repeat_2_digest": "D-F8-1",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Deterministic step pack identity",
        ),
        (
            "F8-T2", "PD-F8-002",
            lambda: evaluate_f8_step_pack(
                {
                    "context_items": ["A", "B", "C", "D", "E", "F"],
                    "item_utf8_bytes": {"A": 8, "B": 8, "C": 8, "D": 8, "E": 8, "F": 8},
                    "precedence": ["C", "A", "F", "B", "D", "E"],
                    "context_budget_bytes": 24,
                    "selected_items": ["C", "A", "F"],
                    "repeat_selected_items": ["C", "A", "F"],
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Deterministic context truncation order",
        ),
        (
            "F8-T3", "PD-F8-003",
            lambda: evaluate_f8_step_pack(
                {
                    "canonical_state_binding": "SB-10",
                    "transcript_present": False,
                    "anchors": ["REQ-1", "OBL-1", "VS-1"],
                    "recomputed_anchors": ["REQ-1", "OBL-1", "VS-1"],
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Canonical resume after transcript removal",
        ),
        (
            "F8-T4", "PD-F8-004",
            lambda: evaluate_f8_step_pack(
                {
                    "input_tuple": ["SB-10", ["SK-1"], 4096, "C1"],
                    "golden_digest": "D-F8-4",
                    "computed_digest": "D-F8-4",
                    "bytes_equal": True,
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Golden byte and digest exact reproduction",
        ),
        # Replay and Invalidation Fixtures (Lines 2808, 2866)
        (
            "CH2-T73", "PD-CH2-064",
            lambda: evaluate_ch2_064_replay_invalidation(
                {
                    "must_id": "PD-CH2-064",
                    "dependency_set_digest": "DEP-SET-001",
                    "earliest_affected_phase": "P2",
                    "replay_start_phase": "P5",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: replay start phase skips earliest affected phase -> MISSING[PD-CH2-064]",
        ),
        (
            "CH2-T74", "PD-CH2-064",
            lambda: evaluate_ch2_064_replay_invalidation(
                {
                    "must_id": "PD-CH2-064",
                    "dependency_set_digest": "DEP-SET-001",
                    "earliest_affected_phase": "P2",
                    "replay_start_phase": "P2",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: replay restarts from earliest affected phase -> SATISFIED",
        ),
        (
            "CH2-T75", "PD-CH2-065",
            lambda: evaluate_ch2_065_lifecycle_proof(
                {
                    "must_id": "PD-CH2-065",
                    "example_preconditions": {"target": "rate_limiter"},
                    "bound_input_digests": ["DIGEST-PRE-01"],
                    "evaluator_record_ref": "EVAL-REC-001",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Gaming: prose-only proof example omits expected gate output -> MISSING[PD-CH2-065]",
        ),
        (
            "CH2-T76", "PD-CH2-065",
            lambda: evaluate_ch2_065_lifecycle_proof(
                {
                    "must_id": "PD-CH2-065",
                    "example_preconditions": {"target": "rate_limiter", "window_sec": 60},
                    "bound_input_digests": ["DIGEST-PRE-01", "DIGEST-IN-01"],
                    "expected_gate_output": "SATISFIED",
                    "failure_route": None,
                    "evaluator_record_ref": "EVAL-REC-001",
                },
                caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Happy: fully bound proof example with valid evaluator ref -> SATISFIED",
        ),
    ]

    for fid, must_id, eval_fn, notes in cases:
        mf = parse_master_fixture(master_path, fid)
        assert fid in lines[mf.line_number - 1], f"Line {mf.line_number} does not contain {fid}"

        out = eval_fn()
        actual = str(out)
        status = "RAN-MATCH" if actual in mf.expected_gate_strings else "RAN-MISMATCH"
        results.append(EFixtureExecution(fid, must_id, mf.line_number, mf.primary_expected, actual, status, notes))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Block 3 Wave 1 Lane E Fixtures")
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

    results = run_e_fixtures(master_path)

    print("=========================================================================================")
    print("BLOCK 3 WAVE 1 — LANE E FIXTURE CONFORMANCE TABLE")
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
        print(f"RAN-MISMATCH count: {len(mismatches)}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
