"""Authoritative Notification Projections & Skill Normalization Gate Engine.

Implements normative requirements for Chapter 7 Integrations & Developer Experience (Block 7, Lane B7-B):
- PD-CH7-014 (Line 4041): Notifications MUST be derived from gate projections and must not imply
  approval/closure on a model-generated message.
- PD-CH7-015 (Line 4244): External skill/playbook content MUST be normalized into S-Class-owned checks
  and cannot create an alternate lifecycle or agent loop.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 7 Lane B evaluation."""

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "evaluate_pd_ch7_014_notification_projections",
    "evaluate_pd_ch7_015_external_skill_normalization",
    "evaluate_b7_b_gate",
]


def evaluate_pd_ch7_014_notification_projections(
    derived_from_gate_projection: bool,
    *,
    implies_approval_on_model_message: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH7-014 (Line 4041): Notifications MUST be derived from gate projections and not imply approval on model message."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-014",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(derived_from_gate_projection) is not bool or type(implies_approval_on_model_message) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-014",
            detail="Arguments must be exact bool",
        )

    if not derived_from_gate_projection or implies_approval_on_model_message:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-014",
            detail="Notification is not derived from gate projections or improperly implies approval/closure on model-generated message",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH7-014",
        detail="Notification derived strictly from gate projection without model message approval implication",
    )


def evaluate_pd_ch7_015_external_skill_normalization(
    normalized_into_sclass_owned_checks: bool,
    *,
    creates_alternate_lifecycle_or_loop: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH7-015 (Line 4244): External skill content normalized into S-Class-owned checks; no alternate lifecycle."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-015",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(normalized_into_sclass_owned_checks) is not bool or type(creates_alternate_lifecycle_or_loop) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-015",
            detail="Arguments must be exact bool",
        )

    if not normalized_into_sclass_owned_checks or creates_alternate_lifecycle_or_loop:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-015",
            detail="External skill/playbook content not normalized into S-Class-owned checks or creates alternate lifecycle/agent loop",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH7-015",
        detail="External skill content successfully normalized into S-Class checks with zero alternate loops",
    )


def evaluate_b7_b_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 7 Lane B (PD-CH7-014, 015)."""
    return {
        "PD-CH7-014": evaluate_pd_ch7_014_notification_projections(
            payload.get("derived_from_gate_projection", False),
            implies_approval_on_model_message=payload.get("implies_approval_on_model_message", False),
            authority=authority,
        ),
        "PD-CH7-015": evaluate_pd_ch7_015_external_skill_normalization(
            payload.get("normalized_into_sclass_owned_checks", False),
            creates_alternate_lifecycle_or_loop=payload.get("creates_alternate_lifecycle_or_loop", False),
            authority=authority,
        ),
    }
