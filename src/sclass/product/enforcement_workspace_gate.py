"""Authoritative Enforcement Boundary & Workspace Concurrency Gate Engine.

Implements normative requirements for Chapter 8 Enforcement & Workspace Management (Block 5, Lane B5):
- PD-CH8-008 (Line 4102): Prevention MUST be claimed only inside a launched and qualified enforcement boundary; native IDE activity is detection/containment, not prevention.
- PD-CH8-009 (Line 4126): Workspace promotion MUST require the current target and kernel release authority after verification and preserve rollback evidence.
- PD-CH8-010 (Line 4150): Out-of-band/concurrent edits MUST trigger re-snapshot and digest comparison before continuing; invalidation is owned by PD-CH2-055.
- PD-CH8-011 (Line 4174): Parallel work MUST follow dependencies and canonical delta order, serialize overlapping write sets and merge only when target identity and each task verification pass.
- PD-CH8-012 (Line 4198): Repository intelligence MUST disclose index coverage/freshness and unresolved symbols remain MISSING.
- PD-CH8-013 (Line 4222): Budget exhaustion MUST stop or route to an authorized repair path; retry decisions use the frozen RetryBudget with no second ledger.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 5 evaluation."""

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "evaluate_pd_ch8_008_prevention_boundary",
    "evaluate_pd_ch8_009_workspace_promotion",
    "evaluate_pd_ch8_010_out_of_band_edits",
    "evaluate_pd_ch8_011_parallel_work_serialization",
    "evaluate_pd_ch8_012_repository_intelligence",
    "evaluate_pd_ch8_013_budget_exhaustion_ledger",
    "evaluate_b5_gate",
]


def evaluate_pd_ch8_008_prevention_boundary(
    prevention_claimed: Optional[bool] = None,
    inside_qualified_enforcement_boundary: Optional[bool] = None,
    *,
    is_native_ide_activity: Optional[bool] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH8-008 (Line 4102): Prevention MUST be claimed only inside a launched and qualified enforcement boundary."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-008",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(prevention_claimed) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-008",
            detail="prevention_claimed must be an exact boolean",
        )

    if prevention_claimed is True:
        if type(inside_qualified_enforcement_boundary) is not bool or not inside_qualified_enforcement_boundary or is_native_ide_activity:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH8-008",
                detail="Prevention claimed outside qualified enforcement boundary or on native IDE activity (action_result: BLOCKED)",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH8-008",
        detail="Enforcement boundary verified or no unqualified prevention claimed",
    )

def evaluate_pd_ch8_009_workspace_promotion(
    target_verified: bool,
    kernel_release_authority: bool,
    rollback_evidence_preserved: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH8-009 (Line 4126): Workspace promotion MUST require target, kernel release authority, and rollback evidence."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-009",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(target_verified) is not bool or type(kernel_release_authority) is not bool or type(rollback_evidence_preserved) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-009",
            detail="Workspace promotion requires exact boolean evidence inputs",
        )

    if not target_verified or not kernel_release_authority or not rollback_evidence_preserved:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-009",
            detail="Workspace promotion requires target verification, kernel release authority, and rollback evidence",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH8-009",
        detail="Workspace promotion authorized with target verification and rollback evidence preserved",
    )


def evaluate_pd_ch8_010_out_of_band_edits(
    out_of_band_edits_detected: Optional[bool] = None,
    re_snapshot_taken: Optional[bool] = None,
    digest_comparison_passed: Optional[bool] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH8-010 (Line 4150): Out-of-band edits MUST trigger re-snapshot and digest comparison before continuing."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-010",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(out_of_band_edits_detected) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-010",
            detail="out_of_band_edits_detected must be an exact boolean",
        )

    if out_of_band_edits_detected is True:
        if not re_snapshot_taken or not digest_comparison_passed:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH8-010",
                detail="Out-of-band edits require re-snapshot and successful digest comparison before continuing",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH8-010",
        detail="Workspace snapshot consistency verified against out-of-band edits",
    )

def evaluate_pd_ch8_011_parallel_work_serialization(
    dependencies_satisfied: bool,
    canonical_delta_order: bool,
    overlapping_writes_serialized: bool,
    target_identity_match: bool,
    all_task_verification_pass: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH8-011 (Line 4174): Parallel work MUST follow dependencies/delta order, serialize writes, and verify tasks."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-011",
            detail="Caller lacks qualified evaluator authority",
        )

    if any(type(x) is not bool for x in (dependencies_satisfied, canonical_delta_order, overlapping_writes_serialized, target_identity_match, all_task_verification_pass)):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-011",
            detail="Parallel work serialization requires exact boolean evidence inputs",
        )

    if (
        not dependencies_satisfied
        or not canonical_delta_order
        or not overlapping_writes_serialized
        or not target_identity_match
        or not all_task_verification_pass
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-011",
            detail="Parallel merge requires canonical delta order, serialized overlapping writes, matching target identity, and all task verification pass",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH8-011",
        detail="Parallel execution following canonical delta order and task verification satisfied",
    )


def evaluate_pd_ch8_012_repository_intelligence(
    discloses_coverage: bool,
    discloses_freshness: bool,
    *,
    unresolved_symbol_present: Optional[bool] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH8-012 (Line 4198): Repository intelligence MUST disclose index coverage/freshness; unresolved symbols remain MISSING."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-012",
            detail="Caller lacks qualified evaluator authority",
        )

    if not discloses_coverage or not discloses_freshness or unresolved_symbol_present:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-012",
            detail="Repository intelligence omits coverage/freshness disclosure or contains unresolved symbols",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH8-012",
        detail="Repository intelligence discloses index coverage and freshness with zero unresolved symbols",
    )


def evaluate_pd_ch8_013_budget_exhaustion_ledger(
    budget_exhausted: Optional[bool] = None,
    routed_to_authorized_repair: Optional[bool] = None,
    *,
    second_ledger_active: Optional[bool] = None,
    model_reported_only_cost: Optional[bool] = None,
    authoritative_host_cost: bool = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH8-013 (Line 4222): Budget exhaustion MUST stop/route to repair; retry uses frozen RetryBudget with no second ledger."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-013",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(budget_exhausted) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-013",
            detail="budget_exhausted must be an exact boolean",
        )

    if second_ledger_active or model_reported_only_cost or not authoritative_host_cost:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-013",
            detail="Hard budget gate rejects model-reported-only cost or second ledger; must use frozen RetryBudget and authoritative cost",
        )

    if budget_exhausted is True and not routed_to_authorized_repair:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-013",
            detail="Budget exhaustion must stop or route to authorized repair path",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH8-013",
        detail="Budget controls enforced using frozen RetryBudget and authoritative host cost metrics",
    )

def evaluate_b5_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 5 (PD-CH8-008..013)."""
    if not isinstance(payload, Mapping):
        payload = {}

    res: Dict[str, GateOutput] = {}

    if "prevention_claimed" in payload:
        res["PD-CH8-008"] = evaluate_pd_ch8_008_prevention_boundary(
            payload.get("prevention_claimed"),
            payload.get("inside_qualified_enforcement_boundary", False),
            is_native_ide_activity=payload.get("is_native_ide_activity", False),
            authority=authority,
        )
    else:
        res["PD-CH8-008"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-008",
            detail="Payload missing required key: prevention_claimed",
        )

    if "target_verified" in payload or "kernel_release_authority" in payload:
        res["PD-CH8-009"] = evaluate_pd_ch8_009_workspace_promotion(
            payload.get("target_verified", False),
            payload.get("kernel_release_authority", False),
            payload.get("rollback_evidence_preserved", False),
            authority=authority,
        )
    else:
        res["PD-CH8-009"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-009",
            detail="Payload missing workspace promotion keys",
        )

    if "out_of_band_edits_detected" in payload:
        res["PD-CH8-010"] = evaluate_pd_ch8_010_out_of_band_edits(
            payload.get("out_of_band_edits_detected"),
            payload.get("re_snapshot_taken", False),
            payload.get("digest_comparison_passed", False),
            authority=authority,
        )
    else:
        res["PD-CH8-010"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-010",
            detail="Payload missing required key: out_of_band_edits_detected",
        )

    if "dependencies_satisfied" in payload or "canonical_delta_order" in payload:
        res["PD-CH8-011"] = evaluate_pd_ch8_011_parallel_work_serialization(
            payload.get("dependencies_satisfied", False),
            payload.get("canonical_delta_order", False),
            payload.get("overlapping_writes_serialized", False),
            payload.get("target_identity_match", False),
            payload.get("all_task_verification_pass", False),
            authority=authority,
        )
    else:
        res["PD-CH8-011"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-011",
            detail="Payload missing parallel work serialization keys",
        )

    if "discloses_coverage" in payload or "discloses_freshness" in payload:
        res["PD-CH8-012"] = evaluate_pd_ch8_012_repository_intelligence(
            payload.get("discloses_coverage", False),
            payload.get("discloses_freshness", False),
            unresolved_symbol_present=payload.get("unresolved_symbol_present", False),
            authority=authority,
        )
    else:
        res["PD-CH8-012"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-012",
            detail="Payload missing repository intelligence keys",
        )

    if "budget_exhausted" in payload:
        res["PD-CH8-013"] = evaluate_pd_ch8_013_budget_exhaustion_ledger(
            payload.get("budget_exhausted"),
            payload.get("routed_to_authorized_repair", False),
            second_ledger_active=payload.get("second_ledger_active", False),
            model_reported_only_cost=payload.get("model_reported_only_cost", False),
            authoritative_host_cost=payload.get("authoritative_host_cost", True),
            authority=authority,
        )
    else:
        res["PD-CH8-013"] = GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH8-013",
            detail="Payload missing required key: budget_exhausted",
        )

    return res
