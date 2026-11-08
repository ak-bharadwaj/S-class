#!/usr/bin/env python3
"""Master-driven fixture runner for Block 9 Lane B (PD-CH9-006..007, PD-CH10-008..011).

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
from sclass.product.stratum_sampling_compatibility import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_AUDIT_EXPORT_FIELDS,
    REQUIRED_COMPATIBILITY_FIELDS,
    evaluate_pd_ch9_006_stratum_sampling_promotion,
    evaluate_pd_ch9_007_secret_egress_claims,
    evaluate_pd_ch10_008_explicit_compatibility,
    evaluate_pd_ch10_009_audit_export_bindings,
    evaluate_pd_ch10_010_roadmap_integrity,
    evaluate_pd_ch10_011_fact_classification,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B9BFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b9_b_fixtures(master_path: Path) -> List[B9BFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B9BFixtureExecution] = []

    valid_matrix = {f: "1.0" for f in REQUIRED_COMPATIBILITY_FIELDS}
    valid_audit = {f: f"val_{f}" for f in REQUIRED_AUDIT_EXPORT_FIELDS}
    valid_caps = [{"id": "C1", "horizon": "H1", "dependency": "DEP1", "exit_test": "TEST1"}]
    valid_facts = [{"id": "F1", "classification": "keep", "evidence_ref": "REF1"}]

    cases: List[Tuple[str, str, Callable[[], GateOutput], str, int]] = [
        # CH9-T6 -> PD-CH9-006
        (
            "CH9-T6", "PD-CH9-006",
            lambda: evaluate_pd_ch9_006_stratum_sampling_promotion(
                false_completion_worsened=True,
                stratum_counts={"stratum_a": 50},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Worse false-completion or stratum below minimum",
            0,
        ),
        # CH9-T23 -> PD-CH9-006
        (
            "CH9-T23", "PD-CH9-006",
            lambda: evaluate_pd_ch9_006_stratum_sampling_promotion(
                false_completion_worsened=False,
                stratum_counts={"stratum_a": 120, "stratum_b": 150},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "False-completion not worsened and every stratum at minimum",
            0,
        ),
        # CH9-T12 -> PD-CH9-007
        (
            "CH9-T12", "PD-CH9-007",
            lambda: evaluate_pd_ch9_007_secret_egress_claims(
                qualified_receipt_on_launched_worker=False,
                unqualified_scanner_or_native_host_write=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Unqualified egress scanner or host-native write",
            0,
        ),
        # CH9-T24 -> PD-CH9-007
        (
            "CH9-T24", "PD-CH9-007",
            lambda: evaluate_pd_ch9_007_secret_egress_claims(
                qualified_receipt_on_launched_worker=True,
                unqualified_scanner_or_native_host_write=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Qualified receipt on launched worker",
            0,
        ),
        # CH10-T8 -> PD-CH10-008
        (
            "CH10-T8", "PD-CH10-008",
            lambda: evaluate_pd_ch10_008_explicit_compatibility(
                valid_matrix,
                unsupported_pair_present=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Unsupported subsystem pair in compatibility matrix",
            0,
        ),
        # CH10-T9 -> PD-CH10-008
        (
            "CH10-T9", "PD-CH10-008",
            lambda: evaluate_pd_ch10_008_explicit_compatibility(
                valid_matrix,
                unsupported_pair_present=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Explicit compatible pairs across kernel, protocol, schema, adapter, pack",
            0,
        ),
        # CH10-T10 -> PD-CH10-009
        (
            "CH10-T10", "PD-CH10-009",
            lambda: evaluate_pd_ch10_009_audit_export_bindings(
                {"digests": "D1"},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Audit export missing sequence range, gate I/O, or declarations",
            0,
        ),
        # CH10-T11 -> PD-CH10-009
        (
            "CH10-T11", "PD-CH10-009",
            lambda: evaluate_pd_ch10_009_audit_export_bindings(
                valid_audit,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Audit export fully binds sequence range, digests, gate I/O, declarations",
            0,
        ),
        # CH10-T12 -> PD-CH10-010
        (
            "CH10-T12", "PD-CH10-010",
            lambda: evaluate_pd_ch10_010_roadmap_integrity(
                [{"id": "C1", "horizon": "H8", "dependency": "DEP", "exit_test": "TEST"}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Roadmap uses invalid horizon outside H0-H7",
            0,
        ),
        # CH10-T13 -> PD-CH10-010
        (
            "CH10-T13", "PD-CH10-010",
            lambda: evaluate_pd_ch10_010_roadmap_integrity(
                valid_caps,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Roadmap uses H0-H7 with dependencies and exit tests",
            0,
        ),
        # CH10-T14 -> PD-CH10-011
        (
            "CH10-T14", "PD-CH10-011",
            lambda: evaluate_pd_ch10_011_fact_classification(
                [{"id": "F1", "classification": "invalid_status", "evidence_ref": "REF"}],
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Implementation fact unclassified or invalid status",
            0,
        ),
        # CH10-T15 -> PD-CH10-011
        (
            "CH10-T15", "PD-CH10-011",
            lambda: evaluate_pd_ch10_011_fact_classification(
                valid_facts,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Implementation facts classified and evidence-backed",
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
            B9BFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 9 Lane B fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b9_b_fixtures(master_path)

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
