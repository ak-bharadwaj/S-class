#!/usr/bin/env python3
"""Master-driven fixture runner for Block 7 Lane A (PD-CH7-016, 008, 009, 011, 012, 013).

Parses authoritative fixtures directly from the hash-verified Master Product Design
document using the shared parser (tools/master_fixtures.py), executes real evaluators,
and verifies results against master expected outputs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from sclass.product.gate import GateOutput, GateState
from sclass.product.wire_session_consequential_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_SESSION_BINDINGS,
    evaluate_pd_ch7_016_wire_protocol_envelope,
    evaluate_pd_ch7_008_guidance_resources,
    evaluate_pd_ch7_009_protocol_idempotent_retries,
    evaluate_pd_ch7_011_ide_mode_capabilities,
    evaluate_pd_ch7_012_session_identity_bindings,
    evaluate_pd_ch7_013_consequential_developer_actions,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B7AFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b7_a_fixtures(master_path: Path) -> List[B7AFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B7AFixtureExecution] = []

    valid_bindings = {f: f"bound_{f}" for f in REQUIRED_SESSION_BINDINGS}

    cases: List[Tuple[str, str, Callable[[], GateOutput], str, int]] = [
        # CH7-T24 -> PD-CH7-016
        (
            "CH7-T24", "PD-CH7-016",
            lambda: evaluate_pd_ch7_016_wire_protocol_envelope(
                {"protocol_version": "99.0", "task_id": "T1"},
                {"request_id": "R1"},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Wire request with unsupported protocol version and missing response envelope",
            0,
        ),
        # CH7-T25 -> PD-CH7-016
        (
            "CH7-T25", "PD-CH7-016",
            lambda: evaluate_pd_ch7_016_wire_protocol_envelope(
                {"protocol_version": "1.0", "task_id": "T1", "session_id": "S1"},
                {"request_id": "R1", "result": "OK", "next_action": "NONE", "resource_refs": [], "error": None},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Conforming wire protocol request and response envelope",
            0,
        ),
        # CH7-T8 -> PD-CH7-008
        (
            "CH7-T8", "PD-CH7-008",
            lambda: evaluate_pd_ch7_008_guidance_resources(
                versioned=True,
                bounded=False,
                subordinate_to_policy_and_kernel=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Guidance resource unbounded or not subordinate to kernel policy",
            0,
        ),
        # CH7-T9 -> PD-CH7-008
        (
            "CH7-T9", "PD-CH7-008",
            lambda: evaluate_pd_ch7_008_guidance_resources(
                versioned=True,
                bounded=True,
                subordinate_to_policy_and_kernel=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Guidance resources versioned, bounded, and subordinate to policy/kernel",
            0,
        ),
        # CH7-T10 -> PD-CH7-009
        (
            "CH7-T10", "PD-CH7-009",
            lambda: evaluate_pd_ch7_009_protocol_idempotent_retries(
                idempotent_under_request_identity=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Protocol retry is not idempotent under request identity",
            0,
        ),
        # CH7-T11 -> PD-CH7-009
        (
            "CH7-T11", "PD-CH7-009",
            lambda: evaluate_pd_ch7_009_protocol_idempotent_retries(
                idempotent_under_request_identity=True,
                version_conflict_typed_error=True,
                conflict_detected=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Protocol retry idempotent under request identity",
            0,
        ),
        # CH7-T14 -> PD-CH7-011
        (
            "CH7-T14", "PD-CH7-011",
            lambda: evaluate_pd_ch7_011_ide_mode_capabilities(
                host_qualified=False,
                declared_tier="E0",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "IDE mode host not qualified",
            0,
        ),
        # CH7-T15 -> PD-CH7-011
        (
            "CH7-T15", "PD-CH7-011",
            lambda: evaluate_pd_ch7_011_ide_mode_capabilities(
                host_qualified=True,
                declared_tier="E1",
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "IDE mode host qualified with declared E1 tier",
            0,
        ),
        # CH7-T16 -> PD-CH7-012
        (
            "CH7-T16", "PD-CH7-012",
            lambda: evaluate_pd_ch7_012_session_identity_bindings(
                valid_bindings,
                transport_claims_canonical_authority=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Transport session metadata claims canonical approval authority",
            0,
        ),
        # CH7-T17 -> PD-CH7-012
        (
            "CH7-T17", "PD-CH7-012",
            lambda: evaluate_pd_ch7_012_session_identity_bindings(
                valid_bindings,
                transport_claims_canonical_authority=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Session identity binds task, snapshot, revision, and pins without transport usurpation",
            0,
        ),
        # CH7-T18 -> PD-CH7-013
        (
            "CH7-T18", "PD-CH7-013",
            lambda: evaluate_pd_ch7_013_consequential_developer_actions(
                authorization_scope_gate_passed=False,
                admissible_observation_emitted=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Consequential action fails scope gate",
            0,
        ),
        # CH7-T19 -> PD-CH7-013
        (
            "CH7-T19", "PD-CH7-013",
            lambda: evaluate_pd_ch7_013_consequential_developer_actions(
                authorization_scope_gate_passed=True,
                admissible_observation_emitted=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Consequential action authorized with observation emitted",
            0,
        ),
    ]

    for fid, mid, fn, notes, exp_idx in cases:
        fixture = parse_master_fixture(master_path, fid)
        expected_str = fixture.expected_gate_strings[exp_idx]
        out: GateOutput = fn()
        actual_str = f"{out.state.value}[{out.must_id}]" if out.state != GateState.SATISFIED else "SATISFIED"

        status = "RAN-MATCH" if actual_str == expected_str else "MISMATCH"
        results.append(
            B7AFixtureExecution(
                fixture_id=fid if exp_idx == 0 else f"{fid}_branch{exp_idx+1}",
                must_id=mid,
                master_line=fixture.line_number,
                expected=expected_str,
                actual=actual_str,
                status=status,
                notes=notes,
            )
        )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Block 7 Lane A fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b7_a_fixtures(master_path)

    print(f"{'Fixture ID':<16} | {'MUST ID':<12} | {'Line':<6} | {'Expected':<28} | {'Actual':<28} | {'Status':<10}")
    print("-" * 110)
    mismatches = 0
    for r in results:
        print(f"{r.fixture_id:<16} | {r.must_id:<12} | {r.master_line:<6} | {r.expected:<28} | {r.actual:<28} | {r.status:<10}")
        if r.status != "RAN-MATCH":
            mismatches += 1

    print("-" * 110)
    print(f"Total fixtures executed: {len(results)}, Mismatches: {mismatches}")
    return 1 if mismatches > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
