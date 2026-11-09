"""Authoritative Lifecycle P0B Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Lifecycle Execution and Completion Invariants:
- PD-CH2-007: P8 repair MUST consume the frozen RetryBudget and MUST NOT create an alternate retry path.
- PD-CH2-008: P11 MUST be non-terminal; new work MUST re-enter at P0.
- PD-CH2-009: A model DONE claim MUST NOT close work without admissible evidence and kernel-evaluated closure.
- PD-CH2-010: A green external run MUST be treated only as run evidence bound to its inputs, not as completion by itself.
- PD-CH2-011: Stack/skill changes MUST NOT create a lifecycle fork or remove core phases.
- PD-CH2-012: Human judgment MUST NOT waive mandatory mechanical/evidence floors except through existing authorized waiver paths.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary in S-Class execution."""

STANDARD_LIFECYCLE_PHASES: Tuple[str, ...] = (
    "P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"
)

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "STANDARD_LIFECYCLE_PHASES",
    "evaluate_pd_ch2_007_p8_retry_budget",
    "evaluate_pd_ch2_008_p11_non_terminal_reentry",
    "evaluate_pd_ch2_009_done_claim_evidence_closure",
    "evaluate_pd_ch2_010_green_external_run_evidence",
    "evaluate_pd_ch2_011_stack_pack_phase_topology",
    "evaluate_pd_ch2_012_mandatory_floor_human_waiver",
    "evaluate_p0b_gate",
]


def evaluate_pd_ch2_007_p8_retry_budget(
    retry_budget_allocated: int,
    retry_budget_consumed: int,
    alternate_retry_path_active: bool = False,
    is_p8_repair: bool = True,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-007: P8 repair MUST consume the frozen RetryBudget and MUST NOT create an alternate retry path."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-007",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(retry_budget_allocated) is not int or type(retry_budget_consumed) is not int or type(alternate_retry_path_active) is not bool or type(is_p8_repair) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-007",
            detail="Arguments must be exact int/bool types",
        )

    if alternate_retry_path_active:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-007",
            detail="Alternate retry path active in violation of frozen RetryBudget",
        )

    if is_p8_repair:
        if retry_budget_consumed <= 0:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-007",
                detail="P8 repair must consume frozen RetryBudget",
            )
        if retry_budget_consumed > retry_budget_allocated:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-007",
                detail="P8 repair consumed exceeds allocated RetryBudget",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="P8 repair conforms to frozen RetryBudget without alternate retry paths",
    )


def evaluate_pd_ch2_008_p11_non_terminal_reentry(
    trigger_type: str,
    target_phase: str,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-008: P11 MUST be non-terminal; new work MUST re-enter at P0."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-008",
            detail="Caller lacks qualified evaluator authority",
        )

    if not isinstance(trigger_type, str) or not trigger_type or not isinstance(target_phase, str) or not target_phase:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-008",
            detail="trigger_type and target_phase must be non-empty strings",
        )

    new_work_triggers = {
        "new_work",
        "post_release_regression",
        "enhancement",
        "incident_remediation",
        "maintenance_cycle",
    }

    if trigger_type.lower() in new_work_triggers:
        if target_phase != "P0":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-008",
                detail=f"Post-release work trigger {trigger_type} re-enters at {target_phase} instead of P0",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail=f"Work trigger {trigger_type} cleanly re-enters lifecycle at {target_phase}",
    )


def evaluate_pd_ch2_009_done_claim_evidence_closure(
    model_done_claimed: bool,
    admissible_evidence_present: bool,
    kernel_evaluated_closure: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-009: A model DONE claim MUST NOT close work without admissible evidence and kernel-evaluated closure."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-009",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(model_done_claimed) is not bool or type(admissible_evidence_present) is not bool or type(kernel_evaluated_closure) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-009",
            detail="All arguments must be exact booleans",
        )

    if model_done_claimed:
        if not admissible_evidence_present:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-009",
                detail="Model DONE claim lacks admissible evidence",
            )
        if not kernel_evaluated_closure:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-009",
                detail="Model DONE claim lacks kernel-evaluated closure",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Model DONE claim backed by admissible evidence and kernel-evaluated closure",
    )


def evaluate_pd_ch2_010_green_external_run_evidence(
    external_run_green: bool,
    bound_to_obligation_inputs: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-010: A green external run MUST be treated only as run evidence bound to its inputs, not as completion by itself."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-010",
            detail="Caller lacks qualified evaluator authority",
        )

    if not bound_to_obligation_inputs:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-010",
            detail="External run evidence is not bound to authoritative obligation inputs",
        )

    if not external_run_green:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-010",
            detail="External run did not succeed",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Green external run is bound to obligation inputs as admissible evidence",
    )


def evaluate_pd_ch2_011_stack_pack_phase_topology(
    stack_pack_topology: Sequence[str],
    standard_phases: Sequence[str] = STANDARD_LIFECYCLE_PHASES,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-011: Stack/skill changes MUST NOT create a lifecycle fork or remove core phases."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-011",
            detail="Caller lacks qualified evaluator authority",
        )

    # Topology must preserve the exact canonical sequence P0..P11
    if tuple(stack_pack_topology) != tuple(standard_phases):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-011",
            detail="Stack pack introduces alternate phase topology or alters core phases",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Stack pack preserves authoritative lifecycle topology P0..P11",
    )


def evaluate_pd_ch2_012_mandatory_floor_human_waiver(
    waiver_requested: bool,
    has_authorized_waiver_path: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-012: Human judgment MUST NOT waive mandatory mechanical/evidence floors except through existing authorized waiver paths."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.BLOCKED_ON_HUMAN,
            must_id="PD-CH2-012",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(waiver_requested) is not bool or type(has_authorized_waiver_path) is not bool:
        return GateOutput(
            state=GateState.BLOCKED_ON_HUMAN,
            must_id="PD-CH2-012",
            detail="Arguments must be exact booleans",
        )

    if waiver_requested:
        if not has_authorized_waiver_path:
            return GateOutput(
                state=GateState.BLOCKED_ON_HUMAN,
                must_id="PD-CH2-012",
                detail="Unsupported override with no frozen authorization",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Mechanical floors preserved; waivers conform to authorized paths",
    )


def evaluate_p0b_gate(
    manifest: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Composite gate evaluator for Lifecycle P0B obligations (PD-CH2-007..012)."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-007",
            detail="Caller lacks qualified evaluator authority",
            failures=[
                "MISSING[PD-CH2-007]", "MISSING[PD-CH2-008]", "MISSING[PD-CH2-009]",
                "MISSING[PD-CH2-010]", "MISSING[PD-CH2-011]", "BLOCKED_ON_HUMAN[PD-CH2-012]",
            ],
        )

    if not isinstance(manifest, Mapping) or not manifest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-007",
            detail="Manifest is empty or missing required fields",
        )

    # 1. PD-CH2-007
    r007 = evaluate_pd_ch2_007_p8_retry_budget(
        retry_budget_allocated=manifest.get("retry_budget_allocated"),
        retry_budget_consumed=manifest.get("retry_budget_consumed"),
        alternate_retry_path_active=manifest.get("alternate_retry_path_active", False),
        is_p8_repair=manifest.get("is_p8_repair", False),
        authority=authority,
    )
    if r007.state != GateState.SATISFIED:
        return r007

    # 2. PD-CH2-008
    r008 = evaluate_pd_ch2_008_p11_non_terminal_reentry(
        trigger_type=manifest.get("trigger_type"),
        target_phase=manifest.get("target_phase"),
        authority=authority,
    )
    if r008.state != GateState.SATISFIED:
        return r008

    # 3. PD-CH2-009
    r009 = evaluate_pd_ch2_009_done_claim_evidence_closure(
        model_done_claimed=manifest.get("model_done_claimed"),
        admissible_evidence_present=manifest.get("admissible_evidence_present"),
        kernel_evaluated_closure=manifest.get("kernel_evaluated_closure"),
        authority=authority,
    )
    if r009.state != GateState.SATISFIED:
        return r009

    # 4. PD-CH2-010
    r010 = evaluate_pd_ch2_010_green_external_run_evidence(
        external_run_green=manifest.get("external_run_green"),
        bound_to_obligation_inputs=manifest.get("bound_to_obligation_inputs"),
        authority=authority,
    )
    if r010.state != GateState.SATISFIED:
        return r010

    # 5. PD-CH2-011
    r011 = evaluate_pd_ch2_011_stack_pack_phase_topology(
        stack_pack_topology=manifest.get("stack_pack_topology"),
        authority=authority,
    )
    if r011.state != GateState.SATISFIED:
        return r011

    # 6. PD-CH2-012
    r012 = evaluate_pd_ch2_012_mandatory_floor_human_waiver(
        waiver_requested=manifest.get("waiver_requested"),
        has_authorized_waiver_path=manifest.get("has_authorized_waiver_path", False),
        authority=authority,
    )
    if r012.state != GateState.SATISFIED:
        return r012

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All P0B lifecycle execution invariants satisfied",
    )
