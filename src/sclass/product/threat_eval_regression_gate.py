"""Authoritative Threat Evaluation, Security Gate & Promotion Blocker Engine.

Implements normative requirements for Chapter 9 Threat Evaluation & Benchmarks (Block 9, Lane B9-A):
- PD-CH9-008 (Line 4321): Every listed threat MUST have an attack, boundary, prevention/detection,
  containment, and mapped fixture; absence of findings is not a pass.
- PD-CH9-009 (Line 4347): Evaluation runs MUST bind benchmark/task revision, target, policy,
  model/worker/runtime, and ground-truth audit label.
- PD-CH9-010 (Line 4371): Promotion MUST block on critical regression or unqualified data handling.
- PD-CH9-003 (Line 4398): Security critical regressions, mismatched environment/runner identity,
  or sandbox/trust-root failures MUST block promotion.
- PD-CH9-004 (Line 4399): Metric reports MUST include denominator, observation window, stratum,
  exclusions, and uncertainty.
- PD-CH9-005 (Line 4400): Retention and data access MUST follow policy values with explicit units
  and version.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 9 Lane A evaluation."""

REQUIRED_THREAT_FIELDS: FrozenSet[str] = frozenset({
    "attack",
    "boundary",
    "prevention_or_detection",
    "containment",
    "mapped_fixture",
})

REQUIRED_EVAL_RUN_BINDINGS: FrozenSet[str] = frozenset({
    "benchmark_task_revision",
    "target",
    "policy",
    "model_worker_runtime",
    "ground_truth_audit_label",
})

REQUIRED_METRIC_REPORT_FIELDS: FrozenSet[str] = frozenset({
    "denominator",
    "observation_window",
    "stratum",
    "exclusions",
    "uncertainty",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "REQUIRED_THREAT_FIELDS",
    "REQUIRED_EVAL_RUN_BINDINGS",
    "REQUIRED_METRIC_REPORT_FIELDS",
    "evaluate_pd_ch9_008_threat_coverage",
    "evaluate_pd_ch9_009_eval_run_bindings",
    "evaluate_pd_ch9_010_promotion_blockers",
    "evaluate_pd_ch9_003_security_promotion_gate",
    "evaluate_pd_ch9_004_metric_reporting_integrity",
    "evaluate_pd_ch9_005_data_retention_policy",
    "evaluate_b9_a_gate",
]


def evaluate_pd_ch9_008_threat_coverage(
    threat_record: Optional[Mapping[str, Any]],
    *,
    absence_of_findings_as_pass: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-008 (Line 4321): Threat coverage: attack, boundary, prevention/detection, containment, mapped fixture."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-008",
            detail="Caller lacks qualified evaluator authority",
        )

    if not threat_record or absence_of_findings_as_pass:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-008",
            detail="Threat record missing or improperly treating absence of findings as pass",
        )

    for field in REQUIRED_THREAT_FIELDS:
        val = threat_record.get(field)
        if val is None or (isinstance(val, (str, list, dict, set)) and len(val) == 0):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH9-008",
                detail=f"Threat record missing required field: {field}",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH9-008",
        detail="Threat coverage verified with attack, boundary, containment, and mapped fixture",
    )


def evaluate_pd_ch9_009_eval_run_bindings(
    eval_run: Optional[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-009 (Line 4347): Evaluation run binds benchmark, target, policy, runtime, and audit label."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-009",
            detail="Caller lacks qualified evaluator authority",
        )

    if not eval_run:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-009",
            detail="Evaluation run record missing entirely",
        )

    for field in REQUIRED_EVAL_RUN_BINDINGS:
        val = eval_run.get(field)
        if val is None or (isinstance(val, (str, list, dict, set)) and len(val) == 0):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH9-009",
                detail=f"Evaluation run missing required binding: {field}",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH9-009",
        detail="Evaluation run fully binds revision, target, policy, runtime, and audit label",
    )


def evaluate_pd_ch9_010_promotion_blockers(
    critical_regression: bool,
    unqualified_data_handling: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-010 (Line 4371): Promotion blocks on critical regression or unqualified data handling."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-010",
            detail="Caller lacks qualified evaluator authority",
        )

    if critical_regression or unqualified_data_handling:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-010",
            detail="Promotion blocked due to critical regression or unqualified data handling",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH9-010",
        detail="Zero critical regressions and qualified data handling confirmed",
    )


def evaluate_pd_ch9_003_security_promotion_gate(
    failed_security_scan: bool = False,
    environment_mismatch: bool = False,
    sandbox_trust_root_failure: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-003 (Line 4398): Security scan failure, environment mismatch, or sandbox/trust-root failure blocks promotion."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-003",
            detail="Caller lacks qualified evaluator authority",
        )

    if failed_security_scan:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-003",
            detail="Security critical regression detected on promotion (action_result: BLOCKED)",
        )

    if environment_mismatch:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-003",
            detail="Mismatched environment/runner identity receipt",
        )

    if sandbox_trust_root_failure:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-003",
            detail="Sandbox or trust-root verification failure (action_result: BLOCKED)",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH9-003",
        detail="Security scan, runner environment, and sandbox trust-root verified clean",
    )


def evaluate_pd_ch9_004_metric_reporting_integrity(
    metric_report: Optional[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-004 (Line 4399): Metric reports MUST include denominator, observation window, stratum, exclusions, uncertainty."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-004",
            detail="Caller lacks qualified evaluator authority",
        )

    if not metric_report:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-004",
            detail="Metric report missing entirely",
        )

    denom = metric_report.get("denominator")
    if denom is None or denom == 0:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-004",
            detail="Zero sample or omitted denominator in metric report",
        )

    for field in REQUIRED_METRIC_REPORT_FIELDS:
        if field not in metric_report or metric_report[field] is None:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH9-004",
                detail=f"Metric report missing required field: {field}",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH9-004",
        detail="Metric report contains denominator, window, stratum, exclusions, and uncertainty",
    )


def evaluate_pd_ch9_005_data_retention_policy(
    within_retention_limit: bool,
    has_policy_reference: bool,
    *,
    recorded_action: bool = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-005 (Line 4400): Retention and data access MUST follow policy values with explicit units and version."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-005",
            detail="Caller lacks qualified evaluator authority",
        )

    if not within_retention_limit or not has_policy_reference or not recorded_action:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-005",
            detail="Artifact beyond retention limit or data access without policy reference or unrecorded action",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH9-005",
        detail="Data access within versioned retention limit with recorded action",
    )


def evaluate_b9_a_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 9 Lane A (PD-CH9-008..010, PD-CH9-003..005)."""
    return {
        "PD-CH9-008": evaluate_pd_ch9_008_threat_coverage(
            payload.get("threat_record"),
            absence_of_findings_as_pass=payload.get("absence_of_findings_as_pass", False),
            authority=authority,
        ),
        "PD-CH9-009": evaluate_pd_ch9_009_eval_run_bindings(
            payload.get("eval_run"),
            authority=authority,
        ),
        "PD-CH9-010": evaluate_pd_ch9_010_promotion_blockers(
            payload.get("critical_regression", False),
            payload.get("unqualified_data_handling", False),
            authority=authority,
        ),
        "PD-CH9-003": evaluate_pd_ch9_003_security_promotion_gate(
            failed_security_scan=payload.get("failed_security_scan", False),
            environment_mismatch=payload.get("environment_mismatch", False),
            sandbox_trust_root_failure=payload.get("sandbox_trust_root_failure", False),
            authority=authority,
        ),
        "PD-CH9-004": evaluate_pd_ch9_004_metric_reporting_integrity(
            payload.get("metric_report"),
            authority=authority,
        ),
        "PD-CH9-005": evaluate_pd_ch9_005_data_retention_policy(
            payload.get("within_retention_limit", False),
            payload.get("has_policy_reference", False),
            recorded_action=payload.get("recorded_action", True),
            authority=authority,
        ),
    }
