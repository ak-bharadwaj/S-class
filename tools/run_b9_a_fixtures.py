#!/usr/bin/env python3
"""Master-driven fixture runner for Block 9 Lane A (PD-CH9-008..010, PD-CH9-003..005).

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
from sclass.product.threat_eval_regression_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_THREAT_FIELDS,
    REQUIRED_EVAL_RUN_BINDINGS,
    REQUIRED_METRIC_REPORT_FIELDS,
    evaluate_pd_ch9_008_threat_coverage,
    evaluate_pd_ch9_009_eval_run_bindings,
    evaluate_pd_ch9_010_promotion_blockers,
    evaluate_pd_ch9_003_security_promotion_gate,
    evaluate_pd_ch9_004_metric_reporting_integrity,
    evaluate_pd_ch9_005_data_retention_policy,
)
from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


class B9AFixtureExecution(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    notes: str


def run_b9_a_fixtures(master_path: Path) -> List[B9AFixtureExecution]:
    verify_master_sha256(master_path)
    results: List[B9AFixtureExecution] = []

    valid_threat = {f: f"val_{f}" for f in REQUIRED_THREAT_FIELDS}
    valid_eval = {f: f"val_{f}" for f in REQUIRED_EVAL_RUN_BINDINGS}
    valid_metric = dict({f: f"val_{f}" for f in REQUIRED_METRIC_REPORT_FIELDS}, denominator=100)

    cases: List[Tuple[str, str, Callable[[], GateOutput], str, int]] = [
        # CH9-T14 -> PD-CH9-008
        (
            "CH9-T14", "PD-CH9-008",
            lambda: evaluate_pd_ch9_008_threat_coverage(
                {"attack": "A1"},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Threat record missing required fields",
            0,
        ),
        # CH9-T15 -> PD-CH9-008
        (
            "CH9-T15", "PD-CH9-008",
            lambda: evaluate_pd_ch9_008_threat_coverage(
                valid_threat,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Threat record with attack, boundary, prevention, containment, fixture",
            0,
        ),
        # CH9-T16 -> PD-CH9-009
        (
            "CH9-T16", "PD-CH9-009",
            lambda: evaluate_pd_ch9_009_eval_run_bindings(
                {"target": "T1"},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Evaluation run missing required bindings",
            0,
        ),
        # CH9-T17 -> PD-CH9-009
        (
            "CH9-T17", "PD-CH9-009",
            lambda: evaluate_pd_ch9_009_eval_run_bindings(
                valid_eval,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Evaluation run fully binds revision, target, policy, runtime, audit label",
            0,
        ),
        # CH9-T18 -> PD-CH9-010
        (
            "CH9-T18", "PD-CH9-010",
            lambda: evaluate_pd_ch9_010_promotion_blockers(
                critical_regression=True,
                unqualified_data_handling=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Promotion blocked on critical regression",
            0,
        ),
        # CH9-T19 -> PD-CH9-010
        (
            "CH9-T19", "PD-CH9-010",
            lambda: evaluate_pd_ch9_010_promotion_blockers(
                critical_regression=False,
                unqualified_data_handling=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Promotion permitted with zero critical regressions and qualified handling",
            0,
        ),
        # CH9-T3 -> PD-CH9-003
        (
            "CH9-T3", "PD-CH9-003",
            lambda: evaluate_pd_ch9_003_security_promotion_gate(
                failed_security_scan=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Failed candidate security scan on promotion",
            0,
        ),
        # CH9-T8 -> PD-CH9-003
        (
            "CH9-T8", "PD-CH9-003",
            lambda: evaluate_pd_ch9_003_security_promotion_gate(
                environment_mismatch=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Environment/runner identity mismatch on promotion",
            0,
        ),
        # CH9-T9 -> PD-CH9-003
        (
            "CH9-T9", "PD-CH9-003",
            lambda: evaluate_pd_ch9_003_security_promotion_gate(
                sandbox_trust_root_failure=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Sandbox or trust-root failure on promotion",
            0,
        ),
        # CH9-T20 -> PD-CH9-003
        (
            "CH9-T20", "PD-CH9-003",
            lambda: evaluate_pd_ch9_003_security_promotion_gate(
                failed_security_scan=False,
                environment_mismatch=False,
                sandbox_trust_root_failure=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Security scan, runner identity, and trust root verified clean",
            0,
        ),
        # CH9-T4 -> PD-CH9-004
        (
            "CH9-T4", "PD-CH9-004",
            lambda: evaluate_pd_ch9_004_metric_reporting_integrity(
                {"denominator": 0},
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Metric report with zero sample or omitted denominator",
            0,
        ),
        # CH9-T21 -> PD-CH9-004
        (
            "CH9-T21", "PD-CH9-004",
            lambda: evaluate_pd_ch9_004_metric_reporting_integrity(
                valid_metric,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Complete metric report with denominator, window, stratum, uncertainty",
            0,
        ),
        # CH9-T5 -> PD-CH9-005
        (
            "CH9-T5", "PD-CH9-005",
            lambda: evaluate_pd_ch9_005_data_retention_policy(
                within_retention_limit=False,
                has_policy_reference=False,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Artifact beyond retention limit or access without policy reference",
            0,
        ),
        # CH9-T22 -> PD-CH9-005
        (
            "CH9-T22", "PD-CH9-005",
            lambda: evaluate_pd_ch9_005_data_retention_policy(
                within_retention_limit=True,
                has_policy_reference=True,
                recorded_action=True,
                authority=QUALIFIED_EVALUATOR_BOUNDARY,
            ),
            "Data access within versioned retention limit with recorded action",
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
            B9AFixtureExecution(
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
    parser = argparse.ArgumentParser(description="Run Block 9 Lane A fixtures")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_b9_a_fixtures(master_path)

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
