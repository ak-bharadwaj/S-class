"""
Unit Tests for S-Class Multi-Factor State Optimizer & Reasoning Router.
"""

import pytest
from orchestrator.models import (
    ReasoningMode,
    ModelTier,
    ArtifactType,
    OrchestrationStateSnapshot,
    StrategicPlanArtifact,
    TaskRiskAssessment,
    RepositoryFacts,
    VerificationProfile,
)
from orchestrator.optimizer import StateOptimizerRouter
from domain.models import Obligation, Claim, ClaimSubject
from domain.types import (
    ObligationCategory,
    Criticality,
    ObligationStatus,
    ClaimTier,
    TargetType,
    ClaimStatus,
)
from claim.reducer import ClaimReductionState, ClaimEpistemicState


@pytest.fixture
def sample_obligation():
    return Obligation(
        obligation_id="OBL-OPT-01",
        task_id="TASK-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        title="Arithmetic square invariant",
        description="square(x) == x * x",
        depends_on=(),
        status=ObligationStatus.OPEN,
    )


@pytest.fixture
def sample_claim():
    return Claim(
        claim_id="CLM-OPT-01",
        obligation_id="OBL-OPT-01",
        tier=ClaimTier.V0_OBSERVABLE,
        subject=ClaimSubject(target_type=TargetType.FUNCTION, identifier="target.square"),
        predicate="SQUARE_CORRECT",
        context={},
        expected={"status": "PASS"},
        criticality=Criticality.HIGH,
        status=ClaimStatus.UNSUPPORTED,
        required_provider_capabilities=("CAP_EXEC_TEST",),
    )


@pytest.fixture
def sample_plan():
    return StrategicPlanArtifact(
        plan_id="PLAN-001",
        task_id="TASK-01",
        strategy_name="TDD_STRATEGY",
        rationale="Plan rationale",
        stages=(),
        estimated_risk_score=0.2,
        plan_digest="a" * 64,
        created_at_iso="2026-08-20T12:00:00Z",
    )


def test_optimizer_initial_discovery():
    """Verifies that an empty task routes to DISCOVER."""
    snap = OrchestrationStateSnapshot(
        task_id="TASK-EMPTY",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(),
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.DISCOVER
    assert decision.expected_artifact_type == ArtifactType.REPO_INVENTORY
    assert decision.target_model_tier == ModelTier.REASONING_PRO


def test_optimizer_unplanned_frontier_routes_to_plan(sample_obligation, sample_claim):
    """Verifies that an un-planned task with ready obligations routes to PLAN."""
    snap = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(sample_obligation,),
        claims=(sample_claim,),
        ready_obligation_ids=("OBL-OPT-01",),
        active_plan=None,
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.PLAN
    assert decision.expected_artifact_type == ArtifactType.STRATEGIC_PLAN
    assert decision.target_model_tier == ModelTier.REASONING_PRO


def test_optimizer_planned_frontier_routes_to_implement(sample_obligation, sample_claim, sample_plan):
    """Verifies that planned ready frontier routes to IMPLEMENT with skill composition."""
    snap = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(sample_obligation,),
        claims=(sample_claim,),
        ready_obligation_ids=("OBL-OPT-01",),
        active_plan=sample_plan,
        task_risk=TaskRiskAssessment(criticality_score=0.9, blast_radius="LOCAL", complexity_score=0.8),
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.IMPLEMENT
    assert decision.expected_artifact_type == ArtifactType.CODE_PATCH
    assert decision.target_model_tier == ModelTier.CODE_FAST
    assert len(decision.selected_skills) >= 1


def test_optimizer_repeated_failure_routes_to_replan(sample_obligation, sample_claim, sample_plan):
    """Verifies that 2 failed repair attempts triggers REPLAN before escalation."""
    refuted_state = ClaimReductionState(
        claim_id="CLM-OPT-01",
        epistemic_state=ClaimEpistemicState.CONTRADICTED,
        refuting_evidence_ids=("EV-01",),
    )
    snap = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(sample_obligation,),
        claims=(sample_claim,),
        claim_states={"CLM-OPT-01": refuted_state},
        failed_obligation_ids=("OBL-OPT-01",),
        active_plan=sample_plan,
        repair_attempts_by_obligation={"OBL-OPT-01": 2},
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.REPLAN
    assert decision.expected_artifact_type == ArtifactType.REVISED_PLAN
    assert decision.target_model_tier == ModelTier.REASONING_PRO


def test_optimizer_dynamic_provider_selection(sample_obligation, sample_claim, sample_plan):
    """Verifies that optimizer dynamically picks from available providers without hardcoding."""
    snap_anthropic = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(sample_obligation,),
        claims=(sample_claim,),
        ready_obligation_ids=("OBL-OPT-01",),
        active_plan=sample_plan,
        available_providers=("anthropic", "local"),
    )
    decision = StateOptimizerRouter.derive_next_decision(snap_anthropic)
    assert decision.target_provider_type == "anthropic"

    snap_openai = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(sample_obligation,),
        claims=(sample_claim,),
        ready_obligation_ids=("OBL-OPT-01",),
        active_plan=sample_plan,
        available_providers=("openai", "local"),
    )
    decision_oa = StateOptimizerRouter.derive_next_decision(snap_openai)
    assert decision_oa.target_provider_type == "openai"


def test_optimizer_safety_escalations():
    """Verifies safety escalations for budget, oscillation, and max repair attempts."""
    # 1. Budget exhausted
    snap_b = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        remaining_budget_units=0.0,
    )
    assert StateOptimizerRouter.derive_next_decision(snap_b).mode == ReasoningMode.ESCALATE

    # 2. Oscillation
    snap_o = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        has_oscillation_detected=True,
    )
    assert StateOptimizerRouter.derive_next_decision(snap_o).mode == ReasoningMode.ESCALATE

    # 3. 3 attempts
    snap_3 = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        failed_obligation_ids=("OBL-01",),
        repair_attempts_by_obligation={"OBL-01": 3},
    )
    assert StateOptimizerRouter.derive_next_decision(snap_3).mode == ReasoningMode.ESCALATE
