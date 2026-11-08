#!/usr/bin/env python3
"""Master-driven fixture runner for Block 6 Lane B (PD-CH6-013, 014, 003, 006).

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
from sclass.product.oss_qualification_playbook import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    OSS_QUALIFICATION_FIELDS,
    REQUIRED_PLAYBOOK_PHASES,
    evaluate_pd_ch6_013_stack_pack_adapters,
    evaluate_pd_ch6_014_oss_qualification_record,
    evaluate_pd_ch6_003_pack_activation,
    evaluate_pd_ch6_006_playbook_content,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B6BFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b6_b_fixtures(master_path: Path) -> List[B6BFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B6BFixtureExecution] = []

    valid_16_fields = {f: f"evidence_ref_{f}" for f in OSS_QUALIFICATION_FIELDS}
    missing_reviewer = {f: f"evidence_ref_{f}" for f in OSS_QUALIFICATION_FIELDS}
    del missing_reviewer["reviewer_reference"]

    cases: List[Tuple[str, str, Callable[[], GateOutput], str, int]] = [
        # CH6-T19 -> PD-CH6-013
        (
            "CH6-T19", "PD-CH6-013",
            lambda: evaluate_pd_ch6_013_stack_pack_adapters(
                {
                    "adapter_capability_families": {
                        "unqualified_family": {"qualified": False, "applicable_checks": ["CHECK_1"]}
                    },
                    "explicitly_blocked_checks": [],
                },
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Stack pack references unqualified adapter without explicit check block",
            0,
        ),
        # CH6-T20 -> PD-CH6-013
        (
            "CH6-T20", "PD-CH6-013",
            lambda: evaluate_pd_ch6_013_stack_pack_adapters(
                {
                    "adapter_capability_families": {
                        "qualified_family": {"qualified": True, "applicable_checks": ["CHECK_1"]}
                    },
                    "explicitly_blocked_checks": [],
                },
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Stack pack references qualified adapter capability families",
            0,
        ),
        # CH6-T21 -> PD-CH6-014
        (
            "CH6-T21", "PD-CH6-014",
            lambda: evaluate_pd_ch6_014_oss_qualification_record(
                missing_reviewer,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "OSS qualification record omits reviewer reference",
            0,
        ),
        # CH6-T22 -> PD-CH6-014
        (
            "CH6-T22", "PD-CH6-014",
            lambda: evaluate_pd_ch6_014_oss_qualification_record(
                valid_16_fields,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "OSS qualification record supplies all 16 evidence references",
            0,
        ),
        # CH6-T3 -> PD-CH6-003
        (
            "CH6-T3", "PD-CH6-003",
            lambda: evaluate_pd_ch6_003_pack_activation(
                scope_specific_qualification=False,
                effective_revocation_present=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Candidate unqualified pack activation attempt",
            0,
        ),
        # CH6-T6 -> PD-CH6-006
        (
            "CH6-T6", "PD-CH6-006",
            lambda: evaluate_pd_ch6_006_playbook_content(
                {
                    "phases": ["P0", "P1", "P2"],
                    "unqualified_adapter_claimed_usable": False,
                },
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Playbook checklist missing required phases",
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
            B6BFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 6 Lane B fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b6_b_fixtures(master_path)

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
