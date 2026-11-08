"""Authoritative Execution Flow Adaptation & TestInputSet Binding Engine.

Implements normative requirements for Chapters 3 and 4 (Block 4, Lane D):
- PD-CH3-010 (Line 3185): Upgrade, migration, performance, CI, and PR-review flows MUST bind relevant baselines and rollback/verification inputs before closure.
- PD-CH3-011 (Line 3186): Project-class adaptation MUST preserve common gates and mark each unqualified adapter/pack as an open qualification, not as supported.
- PD-CH3-012 (Line 3187): UX adaptation MUST preserve mandatory gates/anchors; interruption budgets MUST NOT suppress an authority-required human decision.
- PD-CH3-014 (Line 3188): Canonical lifecycle examples MUST exercise real gate outputs and at least one adversarial claim and test-integrity failure.
- PD-CH4-012 (Line 3257): Every path/symbol/line reference MUST resolve exactly against the pinned target snapshot and indexed source; any unresolved or ambiguous reference is MISSING.
- PD-CH4-009 (Line 3288): P5 MUST bind a qualified adapter-declared complete TestInputSet before red.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 4 evaluation."""

FLOWS_REQUIRING_BASELINE: FrozenSet[str] = frozenset({
    "UPGRADE",
    "MIGRATION",
    "PERFORMANCE",
    "CI",
    "PR_REVIEW",
})

REQUIRED_TEST_INPUT_KEYS: FrozenSet[str] = frozenset({
    "tests",
    "conftest",
    "fixtures",
    "test_data",
    "runner_configuration",
    "markers",
    "plugins",
    "discovery_inputs",
    "environment_identity",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "FLOWS_REQUIRING_BASELINE",
    "REQUIRED_TEST_INPUT_KEYS",
    "evaluate_pd_ch3_010_flow_baseline_binding",
    "evaluate_pd_ch3_011_adapter_qualification_disclosure",
    "evaluate_pd_ch3_012_ux_interruption_budget_authority",
    "evaluate_pd_ch3_014_lifecycle_example_adversarial_failure",
    "evaluate_pd_ch4_012_reference_exact_resolution",
    "evaluate_pd_ch4_009_test_input_set_binding",
    "evaluate_b4_d_gate",
]


def evaluate_pd_ch3_010_flow_baseline_binding(
    flow_type: str,
    baseline_digest: Optional[str],
    *,
    rollback_inputs_bound: bool = True,
    verification_inputs_bound: bool = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-010 (Line 3185): Upgrade/migration flows MUST bind baselines and rollback/verification inputs."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-010",
            detail="Caller lacks qualified evaluator authority",
        )

    norm_type = flow_type.upper()
    if norm_type in FLOWS_REQUIRING_BASELINE:
        if not baseline_digest or not rollback_inputs_bound or not verification_inputs_bound:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH3-010",
                detail=f"{norm_type} flow missing baseline binding or rollback/verification inputs",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-010",
        detail=f"{norm_type} flow baseline and rollback/verification inputs bound",
    )


def evaluate_pd_ch3_011_adapter_qualification_disclosure(
    adapter_identity: str,
    is_qualified: bool,
    marked_supported: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-011 (Line 3186): Project-class adaptation MUST mark unqualified adapter as open qualification."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-011",
            detail="Caller lacks qualified evaluator authority",
        )

    if not is_qualified and marked_supported:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-011",
            detail=f"Unqualified adapter '{adapter_identity}' presented as supported rather than open qualification",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-011",
        detail=f"Adapter '{adapter_identity}' correctly classified as qualified or open qualification",
    )


def evaluate_pd_ch3_012_ux_interruption_budget_authority(
    human_decision_required: bool,
    decision_suppressed_by_cap: bool = False,
    interruption_budget_exceeded: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-012 (Line 3187): UX adaptation interruption budgets MUST NOT suppress required human decision."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-012",
            detail="Caller lacks qualified evaluator authority",
        )

    if human_decision_required:
        if decision_suppressed_by_cap or interruption_budget_exceeded:
            return GateOutput(
                state=GateState.BLOCKED_ON_HUMAN,
                must_id="PD-CH3-012",
                detail="Interruption budget cap cannot suppress authority-required human decision",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-012",
        detail="Mandatory gates preserved without budget suppression of human decisions",
    )


def evaluate_pd_ch3_014_lifecycle_example_adversarial_failure(
    exercises_real_gate_outputs: bool,
    has_adversarial_claim_failure: bool,
    has_test_integrity_failure: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH3-014 (Line 3188): Canonical lifecycle examples MUST exercise real gate outputs and adversarial failure."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-014",
            detail="Caller lacks qualified evaluator authority",
        )

    if not exercises_real_gate_outputs or not has_adversarial_claim_failure or not has_test_integrity_failure:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH3-014",
            detail="Lifecycle example omits real gate outputs, adversarial claim, or test-integrity failure",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH3-014",
        detail="Canonical lifecycle examples exercise real gates, adversarial claim, and test-integrity failure",
    )


def evaluate_pd_ch4_012_reference_exact_resolution(
    path_reference: Optional[str],
    symbol_reference: Optional[str],
    target_snapshot_pinned: bool,
    *,
    is_unresolved: bool = False,
    is_ambiguous: bool = False,
    is_fuzzy_match: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-012 (Line 3257): Path/symbol/line reference MUST resolve exactly against pinned snapshot."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-012",
            detail="Caller lacks qualified evaluator authority",
        )

    if not path_reference or not symbol_reference or not target_snapshot_pinned or is_unresolved:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-012",
            detail="Unresolved reference or unpinned target snapshot",
        )

    if is_ambiguous:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-012",
            detail="Ambiguous reference cannot resolve to single exact target",
        )

    if is_fuzzy_match:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-012",
            detail="Fuzzy-match reference resolution prohibited; exact match required",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-012",
        detail="Reference resolved exactly against pinned target snapshot",
    )


def evaluate_pd_ch4_009_test_input_set_binding(
    test_input_set: Optional[Mapping[str, Any]],
    *,
    is_before_red: bool = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH4-009 (Line 3288): P5 MUST bind qualified adapter-declared complete TestInputSet before red."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-009",
            detail="Caller lacks qualified evaluator authority",
        )

    if not test_input_set or not is_before_red:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-009",
            detail="TestInputSet omitted or not bound before red phase",
        )

    missing = REQUIRED_TEST_INPUT_KEYS - set(test_input_set.keys())
    if missing:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH4-009",
            detail=f"TestInputSet omits declared complete inputs: {sorted(missing)}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH4-009",
        detail="Complete TestInputSet bound before red phase with all declared components",
    )


def evaluate_b4_d_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 4 Lane D (PD-CH3-010..012, PD-CH3-014, PD-CH4-012, PD-CH4-009)."""
    return {
        "PD-CH3-010": evaluate_pd_ch3_010_flow_baseline_binding(
            payload.get("flow_type", ""),
            payload.get("baseline_digest"),
            rollback_inputs_bound=payload.get("rollback_inputs_bound", True),
            verification_inputs_bound=payload.get("verification_inputs_bound", True),
            authority=authority,
        ),
        "PD-CH3-011": evaluate_pd_ch3_011_adapter_qualification_disclosure(
            payload.get("adapter_identity", ""),
            payload.get("is_qualified", False),
            payload.get("marked_supported", False),
            authority=authority,
        ),
        "PD-CH3-012": evaluate_pd_ch3_012_ux_interruption_budget_authority(
            payload.get("human_decision_required", False),
            decision_suppressed_by_cap=payload.get("decision_suppressed_by_cap", False),
            interruption_budget_exceeded=payload.get("interruption_budget_exceeded", False),
            authority=authority,
        ),
        "PD-CH3-014": evaluate_pd_ch3_014_lifecycle_example_adversarial_failure(
            payload.get("exercises_real_gate_outputs", False),
            payload.get("has_adversarial_claim_failure", False),
            payload.get("has_test_integrity_failure", False),
            authority=authority,
        ),
        "PD-CH4-012": evaluate_pd_ch4_012_reference_exact_resolution(
            payload.get("path_reference"),
            payload.get("symbol_reference"),
            payload.get("target_snapshot_pinned", False),
            is_unresolved=payload.get("is_unresolved", False),
            is_ambiguous=payload.get("is_ambiguous", False),
            is_fuzzy_match=payload.get("is_fuzzy_match", False),
            authority=authority,
        ),
        "PD-CH4-009": evaluate_pd_ch4_009_test_input_set_binding(
            payload.get("test_input_set"),
            is_before_red=payload.get("is_before_red", True),
            authority=authority,
        ),
    }
