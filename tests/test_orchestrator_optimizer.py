"""
Unit Tests for S-Class State Optimizer & Reasoning Router.
Verifies:
1. Initial discovery/specification routing.
2. Dynamic mode selection based on decision frontier and claim reduction status.
3. Diagnostic & repair mode routing on refutations.
4. Fail-closed safety escalations (budget exhaustion, oscillation, max repair attempts).
5. Global convergence and task closure.
"""

import pytest
from orchestrator.models import (
    ReasoningMode,
    OrchestrationStateSnapshot,
    RoutingDecision,
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


def test_optimizer_initial_discovery_routing():
    """Verifies that an empty task routes to DISCOVER."""
    snap = OrchestrationStateSnapshot(
        task_id="TASK-EMPTY",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(),
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.DISCOVER
    assert "CAP_READ_CODE" in decision.required_capabilities


def test_optimizer_ready_frontier_routes_to_implement(sample_obligation, sample_claim):
    """Verifies that ready frontier with unsupported claims routes to IMPLEMENT."""
    snap = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(sample_obligation,),
        claims=(sample_claim,),
        ready_obligation_ids=("OBL-OPT-01",),
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.IMPLEMENT
    assert decision.active_frontier_ids == ("OBL-OPT-01",)
    assert decision.selected_skill is not None
    assert decision.selected_skill.skill_id == "skill-tdd-verification"


def test_optimizer_refutation_routes_to_diagnose_and_repair(sample_obligation, sample_claim):
    """Verifies that refuted obligations route to DIAGNOSE then REPAIR."""
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
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.DIAGNOSE
    assert decision.active_frontier_ids == ("OBL-OPT-01",)
    assert decision.selected_skill is not None
    assert decision.selected_skill.skill_id == "skill-systematic-debug"


def test_optimizer_budget_exhaustion_escalates():
    """Verifies that budget depletion triggers immediate ESCALATE."""
    snap = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        remaining_budget_units=0.0,
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.ESCALATE
    assert "budget" in decision.rationale.lower()


def test_optimizer_max_repair_attempts_escalates(sample_obligation):
    """Verifies that exceeding 3 repair attempts on an obligation triggers ESCALATE."""
    snap = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(sample_obligation,),
        failed_obligation_ids=("OBL-OPT-01",),
        repair_attempts_by_obligation={"OBL-OPT-01": 3},
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.ESCALATE
    assert "maximum repair attempts" in decision.reasoning_objective


def test_optimizer_oscillation_escalates():
    """Verifies that detected plan oscillation triggers ESCALATE."""
    snap = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        has_oscillation_detected=True,
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.ESCALATE
    assert "oscillation" in decision.rationale.lower()


def test_optimizer_all_satisfied_routes_to_close(sample_obligation):
    """Verifies that all satisfied obligations route to CLOSE."""
    snap = OrchestrationStateSnapshot(
        task_id="TASK-01",
        source_sha="a" * 40,
        policy_version=1,
        obligations=(sample_obligation,),
        satisfied_obligation_ids=("OBL-OPT-01",),
    )
    decision = StateOptimizerRouter.derive_next_decision(snap)
    assert decision.mode == ReasoningMode.CLOSE
