"""Authoritative Objective Lifecycle Phase Flow & Admission Engine.

Implements normative requirements for Section Chapter 3 Phase Admission (Block 4, Lane C):
- PD-CH3-001 (Line 3179): Every phase artifact MUST bind the objective revision and canonical SpecAnchor digests.
- PD-CH3-002 (Line 3180): Normative requirements MUST have testable acceptance links, explicit non-goals, and no unresolved normative placeholders.
- PD-CH3-003 (Line 3181): Clarification answers changing scope MUST enter canonical Decision/Requirement mechanisms; absent human confirmation blocks.
- PD-CH3-006 (Line 3182): External process tools MUST remain untrusted candidates until adapter/content qualification is recorded.
- PD-CH3-007 (Line 3183): Work type MUST be projected from an existing canonical Decision scope/outcome without a product-owned state machine.
- PD-CH3-009 (Line 3184): Each default user-facing flow MUST preserve its required gates/evidence and compute lane from canonical profile/policy.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 4 evaluation."""

VALID_WORK_TYPES: FrozenSet[str] = frozenset({
    "FEATURE",
    "BUGFIX",
    "REFACTOR",
    "MIGRATION",
    "INVESTIGATION",
})

CANONICAL_LANES: FrozenSet[str] = frozenset({
    "FAST_LANE",
    "STANDARD_LANE",
    "CRITICAL_LANE",
    "REPLAY_LANE",
    "MIGRATION_LANE",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "VALID_WORK_TYPES",
    "CANONICAL_LANES",
    "evaluate_pd_ch3_001_phase_artifact_anchors",
    "evaluate_pd_ch3_002_normative_requirements_completeness",
    "evaluate_pd_ch3_003_clarification_scope_entry",
    "evaluate_pd_ch3_006_external_tool_candidate_trust",
    "evaluate_pd_ch3_007_work_type_decision_projection",
    "evaluate_pd_ch3_009_flow_gates_and_lane_computation",
    "evaluate_b4_c_gate",
]


def evaluate_pd_ch3_001_phase_artifact_anchors(
    objective_revision: Optional[str],
    spec_anchor_digests: Optional[Sequence[str]],
    *,
    expected_objective_revision: Optional[str] = None,
    expected_anchor_digests: Optional[Sequence[str]] = None,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-001 (Line 3179): Every phase artifact MUST bind objective revision and canonical SpecAnchor digests."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-001",
            detail="Caller lacks qualified evaluator authority",
        )

    if not objective_revision or not spec_anchor_digests:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-001",
            detail="Missing objective revision or canonical spec anchor digests",
        )

    if expected_objective_revision is not None and objective_revision != expected_objective_revision:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-001",
            detail=f"Mismatched objective revision: {objective_revision} != {expected_objective_revision}",
        )

    if expected_anchor_digests is not None and set(spec_anchor_digests) != set(expected_anchor_digests):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-001",
            detail="Mismatched spec anchor digests",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-001",
        detail="Phase artifact bound to valid objective revision and canonical SpecAnchor digests",
    )


def evaluate_pd_ch3_002_normative_requirements_completeness(
    requirements: Optional[Sequence[Mapping[str, Any]]],
    non_goals: Optional[Sequence[str]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-002 (Line 3180): Normative requirements MUST have testable acceptance links, non-goals, and no placeholders."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-002",
            detail="Caller lacks qualified evaluator authority",
        )

    if not requirements or not non_goals:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-002",
            detail="Missing requirements or explicit non-goals list",
        )

    for req in requirements:
        if not req.get("acceptance_links"):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH3-002",
                detail=f"Requirement {req.get('id', 'UNKNOWN')} missing testable acceptance links",
            )
        text = str(req.get("text", ""))
        if any(ph in text.upper() for ph in ("TODO", "TBD", "PLACEHOLDER", "UNRESOLVED")):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH3-002",
                detail=f"Requirement {req.get('id', 'UNKNOWN')} contains unresolved normative placeholder",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-002",
        detail="Normative requirements complete with testable acceptance links and explicit non-goals",
    )


def evaluate_pd_ch3_003_clarification_scope_entry(
    scope_changed: bool,
    canonical_decision_recorded: bool,
    human_confirmed: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-003 (Line 3181): Clarification answers changing scope MUST enter canonical mechanisms; absent human blocks."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-003",
            detail="Caller lacks qualified evaluator authority",
        )

    if scope_changed:
        if not human_confirmed:
            return GateOutput(
                state=GateState.BLOCKED_ON_HUMAN,
                must_id="PD-CH3-003",
                detail="Clarification answer changing scope requires authorized human confirmation",
            )
        if not canonical_decision_recorded:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH3-003",
                detail="Scope change has human confirmation but not entered in canonical Decision/Requirement mechanisms",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-003",
        detail="Clarification scope entry verified or no scope change",
    )


def evaluate_pd_ch3_006_external_tool_candidate_trust(
    tool_identity: str,
    qualification_recorded: bool,
    claimed_authoritative: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-006 (Line 3182): External process tools MUST remain untrusted candidates until qualification is recorded."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-006",
            detail="Caller lacks qualified evaluator authority",
        )

    if claimed_authoritative and not qualification_recorded:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-006",
            detail=f"Unqualified process tool '{tool_identity}' claimed authoritative without recorded qualification",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-006",
        detail=f"Tool '{tool_identity}' correctly scoped as candidate or qualified authoritative",
    )


def evaluate_pd_ch3_007_work_type_decision_projection(
    canonical_decision_outcome: Optional[str],
    projected_work_type: Optional[str],
    agent_override_attempted: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-007 (Line 3183): Work type MUST be projected from canonical Decision outcome without product state machine."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-007",
            detail="Caller lacks qualified evaluator authority",
        )

    if agent_override_attempted:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-007",
            detail="Agent-only work-type label change rejected; must project from canonical Decision",
        )

    if not canonical_decision_outcome or not projected_work_type:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-007",
            detail="Missing canonical decision outcome or projected work type",
        )

    if projected_work_type not in VALID_WORK_TYPES:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-007",
            detail=f"Invalid projected work type: {projected_work_type}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-007",
        detail=f"Work type '{projected_work_type}' projected from canonical Decision outcome '{canonical_decision_outcome}'",
    )


def evaluate_pd_ch3_009_flow_gates_and_lane_computation(
    flow_identity: str,
    contract_tests_present: bool,
    computed_lane: Optional[str],
    agent_selected_lane: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-009 (Line 3184): Default user-facing flow MUST preserve required gates/evidence and compute lane from policy."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-009",
            detail="Caller lacks qualified evaluator authority",
        )

    if not contract_tests_present:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-009",
            detail=f"User-facing flow '{flow_identity}' omits required contract test",
        )

    if agent_selected_lane:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-009",
            detail=f"User-facing flow '{flow_identity}' uses agent-selected lane rather than policy-computed lane",
        )

    if not computed_lane or computed_lane not in CANONICAL_LANES:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-009",
            detail=f"Invalid or uncomputed execution lane: {computed_lane}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-009",
        detail=f"User-facing flow '{flow_identity}' preserves gates with computed lane '{computed_lane}'",
    )


def evaluate_b4_c_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 4 Lane C (PD-CH3-001..003, PD-CH3-006..007, PD-CH3-009)."""
    return {
        "PD-CH3-001": evaluate_pd_ch3_001_phase_artifact_anchors(
            payload.get("objective_revision"),
            payload.get("spec_anchor_digests"),
            expected_objective_revision=payload.get("expected_objective_revision"),
            expected_anchor_digests=payload.get("expected_anchor_digests"),
            authority=authority,
        ),
        "PD-CH3-002": evaluate_pd_ch3_002_normative_requirements_completeness(
            payload.get("requirements"),
            payload.get("non_goals"),
            authority=authority,
        ),
        "PD-CH3-003": evaluate_pd_ch3_003_clarification_scope_entry(
            payload.get("scope_changed", False),
            payload.get("canonical_decision_recorded", False),
            payload.get("human_confirmed", False),
            authority=authority,
        ),
        "PD-CH3-006": evaluate_pd_ch3_006_external_tool_candidate_trust(
            payload.get("tool_identity", ""),
            payload.get("qualification_recorded", False),
            payload.get("claimed_authoritative", False),
            authority=authority,
        ),
        "PD-CH3-007": evaluate_pd_ch3_007_work_type_decision_projection(
            payload.get("canonical_decision_outcome"),
            payload.get("projected_work_type"),
            agent_override_attempted=payload.get("agent_override_attempted", False),
            authority=authority,
        ),
        "PD-CH3-009": evaluate_pd_ch3_009_flow_gates_and_lane_computation(
            payload.get("flow_identity", ""),
            payload.get("contract_tests_present", False),
            payload.get("computed_lane"),
            agent_selected_lane=payload.get("agent_selected_lane", False),
            authority=authority,
        ),
    }
