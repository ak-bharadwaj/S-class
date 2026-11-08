#!/usr/bin/env python3
"""Master-driven fixture runner for Block 6 Lane A (PD-CH6-007..PD-CH6-012).

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
from sclass.product.knowledge_package_quarantine import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_PACKAGE_METADATA_FIELDS,
    evaluate_pd_ch6_007_package_metadata,
    evaluate_pd_ch6_008_precedence_and_conflicts,
    evaluate_pd_ch6_009_lifecycle_projection,
    evaluate_pd_ch6_010_quarantine_conditions,
    evaluate_pd_ch6_011_license_provenance_verification,
    evaluate_pd_ch6_012_steppack_digest_pinning,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B6AFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b6_a_fixtures(master_path: Path) -> List[B6AFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B6AFixtureExecution] = []

    valid_meta = {f: "valid_val" for f in REQUIRED_PACKAGE_METADATA_FIELDS}

    cases: List[Tuple[str, str, Callable[[], GateOutput], str, int]] = [
        # CH6-T7 -> PD-CH6-007
        (
            "CH6-T7", "PD-CH6-007",
            lambda: evaluate_pd_ch6_007_package_metadata(
                {"closed_schema": "schema.json"},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Knowledge package missing required metadata fields",
            0,
        ),
        # CH6-T8 -> PD-CH6-007
        (
            "CH6-T8", "PD-CH6-007",
            lambda: evaluate_pd_ch6_007_package_metadata(
                valid_meta,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Knowledge package with all closed schema and signature bindings satisfied",
            0,
        ),
        # CH6-T9 -> PD-CH6-008
        (
            "CH6-T9", "PD-CH6-008",
            lambda: evaluate_pd_ch6_008_precedence_and_conflicts(
                precedence_deterministic=True,
                lower_tier_removes_mandatory=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Lower-tier content removes mandatory checks",
            0,
        ),
        # CH6-T10 -> PD-CH6-008
        (
            "CH6-T10", "PD-CH6-008",
            lambda: evaluate_pd_ch6_008_precedence_and_conflicts(
                precedence_deterministic=True,
                lower_tier_removes_mandatory=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Deterministic precedence without removing mandatory checks",
            0,
        ),
        # CH6-T11 -> PD-CH6-009
        (
            "CH6-T11", "PD-CH6-009",
            lambda: evaluate_pd_ch6_009_lifecycle_projection(
                is_evidence_projection=True,
                independent_state_machine=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Lifecycle label operating as an independent state machine",
            0,
        ),
        # CH6-T12 -> PD-CH6-009
        (
            "CH6-T12", "PD-CH6-009",
            lambda: evaluate_pd_ch6_009_lifecycle_projection(
                is_evidence_projection=True,
                independent_state_machine=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Lifecycle label projected from qualification/revocation evidence",
            0,
        ),
        # CH6-T13 -> PD-CH6-010
        (
            "CH6-T13", "PD-CH6-010",
            lambda: evaluate_pd_ch6_010_quarantine_conditions(
                unknown_checks=True,
                quarantined=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Unknown checks present in package without quarantine",
            0,
        ),
        # CH6-T14 -> PD-CH6-010
        (
            "CH6-T14", "PD-CH6-010",
            lambda: evaluate_pd_ch6_010_quarantine_conditions(
                unknown_checks=False,
                weakened_floors=False,
                invalid_signature=False,
                unsupported_compatibility=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Package clean of unknown checks, weakened floors, and valid signature",
            0,
        ),
        # CH6-T15 -> PD-CH6-011
        (
            "CH6-T15", "PD-CH6-011",
            lambda: evaluate_pd_ch6_011_license_provenance_verification(
                license_verified=True,
                provenance_verified=False,
                public_url_only=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Unclear provenance with public URL only",
            0,
        ),
        # CH6-T16 -> PD-CH6-011
        (
            "CH6-T16", "PD-CH6-011",
            lambda: evaluate_pd_ch6_011_license_provenance_verification(
                license_verified=True,
                provenance_verified=True,
                public_url_only=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Explicit verified license and provenance",
            0,
        ),
        # CH6-T17 -> PD-CH6-012
        (
            "CH6-T17", "PD-CH6-012",
            lambda: evaluate_pd_ch6_012_steppack_digest_pinning(
                in_flight=True,
                content_digest_pinned=False,
                compiler_digest_pinned=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "In-flight StepPack without content digest pin",
            0,
        ),
        # CH6-T18 -> PD-CH6-012
        (
            "CH6-T18", "PD-CH6-012",
            lambda: evaluate_pd_ch6_012_steppack_digest_pinning(
                in_flight=True,
                content_digest_pinned=True,
                compiler_digest_pinned=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "In-flight StepPack with pinned content and compiler digests",
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
            B6AFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 6 Lane A fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b6_a_fixtures(master_path)

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
