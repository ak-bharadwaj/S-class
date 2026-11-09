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
    absence_of_findings_as_pass: Optional[bool] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-008 (Line 4321): Threat coverage: attack, boundary, prevention/detection, containment, mapped fixture."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-008",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

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
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-008",
            detail=f"Adversarial input rejected: {type(e).__name__}",
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
    try:

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
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-009",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch9_010_promotion_blockers(
    critical_regression: Optional[bool] = None,
    unqualified_data_handling: Optional[bool] = None,
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

    if critical_regression is True or unqualified_data_handling is True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-010",
            detail="Promotion blocked due to critical regression or unqualified data handling",
        )

    if (
        type(critical_regression) is not bool
        or type(unqualified_data_handling) is not bool
        or critical_regression is not False
        or unqualified_data_handling is not False
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-010",
            detail="Promotion blocker evidence omitted, incomplete, or invalid type",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH9-010",
        detail="Zero critical regressions and qualified data handling confirmed",
    )


def evaluate_pd_ch9_003_security_promotion_gate(
    failed_security_scan: Optional[bool] = None,
    environment_mismatch: Optional[bool] = None,
    sandbox_trust_root_failure: Optional[bool] = None,
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

    if failed_security_scan is True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-003",
            detail="Security critical regression detected on promotion (action_result: BLOCKED)",
        )

    if environment_mismatch is True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-003",
            detail="Mismatched environment/runner identity receipt",
        )

    if sandbox_trust_root_failure is True:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-003",
            detail="Sandbox or trust-root verification failure (action_result: BLOCKED)",
        )

    if (
        type(failed_security_scan) is not bool
        or type(environment_mismatch) is not bool
        or type(sandbox_trust_root_failure) is not bool
        or failed_security_scan is not False
        or environment_mismatch is not False
        or sandbox_trust_root_failure is not False
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-003",
            detail="Security promotion evidence omitted, incomplete, or invalid type",
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
    try:

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
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-004",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch9_005_data_retention_policy(
    within_retention_limit: Optional[bool] = None,
    has_policy_reference: Optional[bool] = None,
    *,
    recorded_action: Optional[bool] = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH9-005 (Line 4400): Retention and data access MUST follow policy values with explicit units and version."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-005",
            detail="Caller lacks qualified evaluator authority",
        )

    if (
        type(within_retention_limit) is not bool
        or within_retention_limit is not True
        or type(has_policy_reference) is not bool
        or has_policy_reference is not True
        or type(recorded_action) is not bool
        or recorded_action is not True
    ):
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
    if not isinstance(payload, Mapping):
        payload = {}

    res: Dict[str, GateOutput] = {}

    if "threat_record" in payload:
        res["PD-CH9-008"] = evaluate_pd_ch9_008_threat_coverage(
            payload.get("threat_record"),
            absence_of_findings_as_pass=payload.get("absence_of_findings_as_pass", False),
            authority=authority,
        )
    else:
        res["PD-CH9-008"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-008",
            detail="Payload missing required key: threat_record",
        )

    if "eval_run" in payload:
        res["PD-CH9-009"] = evaluate_pd_ch9_009_eval_run_bindings(
            payload.get("eval_run"),
            authority=authority,
        )
    else:
        res["PD-CH9-009"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-009",
            detail="Payload missing required key: eval_run",
        )

    if "critical_regression" in payload or "unqualified_data_handling" in payload:
        res["PD-CH9-010"] = evaluate_pd_ch9_010_promotion_blockers(
            payload.get("critical_regression"),
            payload.get("unqualified_data_handling"),
            authority=authority,
        )
    else:
        res["PD-CH9-010"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-010",
            detail="Payload missing required keys: critical_regression / unqualified_data_handling",
        )

    if "failed_security_scan" in payload or "environment_mismatch" in payload or "sandbox_trust_root_failure" in payload:
        res["PD-CH9-003"] = evaluate_pd_ch9_003_security_promotion_gate(
            failed_security_scan=payload.get("failed_security_scan"),
            environment_mismatch=payload.get("environment_mismatch"),
            sandbox_trust_root_failure=payload.get("sandbox_trust_root_failure"),
            authority=authority,
        )
    else:
        res["PD-CH9-003"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-003",
            detail="Payload missing required security promotion gate keys",
        )

    if "metric_report" in payload:
        res["PD-CH9-004"] = evaluate_pd_ch9_004_metric_reporting_integrity(
            payload.get("metric_report"),
            authority=authority,
        )
    else:
        res["PD-CH9-004"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-004",
            detail="Payload missing required key: metric_report",
        )

    if "within_retention_limit" in payload or "has_policy_reference" in payload:
        res["PD-CH9-005"] = evaluate_pd_ch9_005_data_retention_policy(
            payload.get("within_retention_limit"),
            payload.get("has_policy_reference"),
            recorded_action=payload.get("recorded_action", True),
            authority=authority,
        )
    else:
        res["PD-CH9-005"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH9-005",
            detail="Payload missing required data retention keys",
        )

    return res
