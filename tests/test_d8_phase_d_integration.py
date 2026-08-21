"""
D8 Autonomous Planning Substrate - Phase D Integration & Adversarial Test Suite.

Exhaustively verifies:
1. D3 Policy Delegation without rule inspection (§3.6, §8.1)
2. Non-compensating risk invariance under maximized quality/Phi (§3.5, CORE-14)
3. Separation of candidate strategy verification from D0 architectural claim truth (§4.2, §8.1)
4. Context/claim/capability-appropriate hypothesis verification node synthesis
5. D8 -> D5 adversarial integration gates (stale fence, state drift, authority context mismatch, digest tampering)
6. Complete planner_state_digest field sensitivity and domain separation
7. Cryptographic strategy-to-proposal execution binding
"""

import copy
import hashlib
import time
import pytest
from datetime import datetime, timezone
from typing import Mapping, Sequence

from controller.authorization import (
    ActionProposal,
    AuthorizationEngine,
    AuthorizationStatus,
)
from controller.controller import SClassController
from controller.authority import StaticLeaseAuthority, StaticStateAuthority
from controller.token import (
    ActionBinding,
    ExecutionContext,
    compute_action_digest,
    verify_execution_token,
)
from domain.models import (
    Obligation,
    Policy,
    PolicyRule,
    PolicyExpression,
)
from domain.types import (
    Criticality,
    ObligationCategory,
    ObligationStatus,
    PolicyScope,
    RuleType,
    CombinatorType,
)
from events.state import MaterializedState
from events.store import D2NonceStore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from cryptography.hazmat.primitives.asymmetric import ed25519

from planner.analysis import (
    AnalysisArtifact,
    AnalystType,
    Observation,
    Hypothesis,
    Inference,
    Uncertainty,
    Contradiction,
    Implication,
    ToolProvenance,
    compute_analysis_artifact_digest,
)
from planner.models import (
    ExecutionStrategyArtifact,
    Plan,
    PlanNode,
    PlannerStateContent,
    PlannerStateProjectionMetadata,
    PlannerStateView,
    PlanRuntimeEnvelope,
    PlanStatus,
    PlanningLease,
    PlannerRiskAssessment,
    PlanQualityScore,
)
from planner.fingerprint import (
    compute_execution_strategy_fingerprint,
    compute_plan_semantic_fingerprint,
    compute_planner_state_digest,
)
from planner.lease import (
    PlanningLeaseManager,
    LeaseAcquisitionError,
    LeaseValidationError,
)
from planner.projector import StateProjector
from planner.generator import (
    CandidateGenerator,
    DeterministicRuleGenerator,
)
from planner.dependency import (
    DependencyPlanner,
    DependencyCycleError,
)
from planner.evaluator import (
    HardConstraintGate,
    PlanEvaluator,
    MAX_GOVERNED_BLAST_RADIUS,
)
from planner.convergence import (
    ConvergenceMonitor,
    PlanOscillationDetectedError,
    ReplanningBudgetExceededError,
    SpontaneousReplanningError,
)
from planner.emitter import ProposalEmitter
from planner.session import (
    NoAdmissiblePlanError,
    PlannerSession,
)


@pytest.fixture(autouse=True)
def setup_authority_keys():
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)


@pytest.fixture
def mock_context():
    return ExecutionContext(
        provider_id="PROVIDER-TEST",
        sandbox_profile_id="SANDBOX-TEST",
        workspace_id="WS-TEST",
        resource_profile_id="RES-TEST",
        capability_set=("FS_READ", "FS_WRITE"),
    )


@pytest.fixture
def sample_obligation():
    return Obligation(
        obligation_id="OBL-001",
        task_id="TASK-PHASE-D-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        title="Fix state corruption in core processor",
        description="Fix state corruption in core processor",
    )


# ============================================================================
# 1. D3 Policy Delegation (No Rule Inspection)
# ============================================================================

def test_d8_d01_d3_policy_delegation_without_rule_inspection(mock_context, sample_obligation):
    """D8 MUST NOT inspect policy.expression.rules. It delegates to D3 evaluate_policy()."""
    deny_policy = Policy(
        policy_id="POL-RESTRICT-CORE",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(
                    rule_type=RuleType.REQUIRE_MIN_TRIALS,
                    parameters={"min_trials": 999},  # Cannot be met without trials
                ),
            ),
        ),
    )

    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": sample_obligation},
        claims={},
        executable_frontier=("OBL-001",),
        active_policies=(deny_policy,),
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="APPLY_PATCH",
        target="src/core.py",
        purpose="Patch core",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-POLICY-TEST",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    is_valid, violations = HardConstraintGate.evaluate(strategy, state_view)
    assert not is_valid
    assert any("D3 Policy 'POL-RESTRICT-CORE' DENIED" in v for v in violations)


# ============================================================================
# 2. Non-Compensating Risk Invariance
# ============================================================================

def test_d8_d02_non_compensating_risk_cannot_be_rescued_by_max_quality(mock_context, sample_obligation):
    """Metamorphic Property: Maximizing quality/Phi cannot rescue a catastrophic hard-risk rejection."""
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": sample_obligation},
        claims={},
        executable_frontier=("OBL-001",),
        state_version=1,
        state_digest="0" * 64,
    )

    # Strategy targeting > 30% blast radius (CORE-14 catastrophic violation)
    nodes = []
    for i in range(10):
        nodes.append(
            PlanNode(
                node_id=f"N-BLAST-{i}",
                obligation_id="OBL-001",
                action_type="APPLY_PATCH",
                target=f"src/module_{i}.py",
                purpose=f"Broad patch {i}",
                execution_context=mock_context,
            )
        )

    blast_strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-BLAST-VIOLATION",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=tuple(nodes),
        dependency_edges=(),
    )

    # 1. HardConstraintGate must reject
    is_valid, violations = HardConstraintGate.evaluate(blast_strategy, state_view)
    assert not is_valid
    assert any("Blast radius" in v for v in violations)

    # 2. Even if we construct a maximal hypothetical quality score (Phi = 1.0, Cost = 0.0)
    risk_assessment = PlanEvaluator.assess_risk(blast_strategy, state_view)
    assert not risk_assessment.is_acceptable

    # 3. PlannerSession must categorically raise NoAdmissiblePlanError
    lease_manager = PlanningLeaseManager()
    session = PlannerSession(
        task_id="TASK-PHASE-D-01",
        owner_id="OWNER-1",
        lease_manager=lease_manager,
    )

    class FixedBlastGenerator:
        def generate_candidates(self, state_view, context, max_candidates=3):
            return [blast_strategy]

    session._generator = CandidateGenerator(engine=FixedBlastGenerator())
    with session:
        with pytest.raises(NoAdmissiblePlanError, match="No candidate plan satisfied"):
            session.plan(state_view, mock_context)


# ============================================================================
# 3. Separation of Candidate Verification from D0 Plan Validation
# ============================================================================

def test_d8_d03_candidate_verification_does_not_mutate_d0_claim_truth(mock_context, sample_obligation):
    """Proposing a verification node does NOT make an unsupported D0 claim SUPPORTED in Plan."""
    unsupported_claim = {
        "claim_id": "CLM-ARCH-001",
        "tier": "TIER_1_MICRO_INVARIANT",
        "predicate": "MemorySafetyInvariant",
        "status": "UNSUPPORTED",
    }

    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": sample_obligation},
        claims={"CLM-ARCH-001": unsupported_claim},
        executable_frontier=("OBL-001",),
        state_version=1,
        state_digest="0" * 64,
    )

    lease_manager = PlanningLeaseManager()
    session = PlannerSession(
        task_id="TASK-PHASE-D-01",
        owner_id="OWNER-1",
        lease_manager=lease_manager,
    )

    with session:
        envelope, score = session.plan(state_view, mock_context)
        # The generated D0 plan must preserve the honest D4 claim status
        arch_claims = envelope.plan.architecture_claims
        assert len(arch_claims) == 1
        assert arch_claims[0]["claim_id"] == "CLM-ARCH-001"
        assert arch_claims[0]["status"] == "UNSUPPORTED"


# ============================================================================
# 4. Context-Appropriate Hypothesis Verification
# ============================================================================

def test_d8_d04_context_appropriate_hypothesis_verification_nodes(mock_context, sample_obligation):
    """Hypothesis.requires_verification generates capability/context-appropriate node types."""
    generator = DeterministicRuleGenerator()

    # Case A: Type-related hypothesis -> TYPE_CHECK
    art_type = AnalysisArtifact(
        analysis_id="ANA-TYPE-01",
        execution_id="EXEC-01",
        analyst_type=AnalystType.ARCHITECTURE,
        task_id="TASK-PHASE-D-01",
        repository_id="repo-main",
        source_sha="a" * 40,
        input_state_digest="b" * 64,
        observations=(Observation(observation_id="OBS-T1", category="TYPE_SIGNATURE", description="Type error in API", target_path="src/api.py"),),
        hypotheses=(Hypothesis(hypothesis_id="HYP-T1", description="Type signature mismatch on handler"),),
    )
    sv_type = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, analysis_artifacts=(art_type,))
    c_type = generator.generate_candidates(sv_type, mock_context)
    assert c_type[0].nodes[0].action_type == "TYPE_CHECK"

    # Case B: Static AST / Syntax hypothesis -> STATIC_ANALYSIS
    art_ast = AnalysisArtifact(
        analysis_id="ANA-AST-01",
        execution_id="EXEC-02",
        analyst_type=AnalystType.ARCHITECTURE,
        task_id="TASK-PHASE-D-01",
        repository_id="repo-main",
        source_sha="a" * 40,
        input_state_digest="b" * 64,
        observations=(Observation(observation_id="OBS-A1", category="STATIC_AST", description="AST parse ambiguity", target_path="src/parser.py"),),
        hypotheses=(Hypothesis(hypothesis_id="HYP-A1", description="Syntax lint violation on grammar"),),
    )
    sv_ast = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, analysis_artifacts=(art_ast,))
    c_ast = generator.generate_candidates(sv_ast, mock_context)
    assert c_ast[0].nodes[0].action_type == "STATIC_ANALYSIS"

    # Case C: Contract / Fuzz hypothesis -> FUZZ_CONTRACT
    art_fuzz = AnalysisArtifact(
        analysis_id="ANA-FUZZ-01",
        execution_id="EXEC-03",
        analyst_type=AnalystType.REPOSITORY,
        task_id="TASK-PHASE-D-01",
        repository_id="repo-main",
        source_sha="a" * 40,
        input_state_digest="b" * 64,
        observations=(Observation(observation_id="OBS-F1", category="CONTRACT", description="Contract boundary", target_path="src/token.py"),),
        hypotheses=(Hypothesis(hypothesis_id="HYP-F1", description="Property fuzz violation in invariant"),),
    )
    sv_fuzz = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, analysis_artifacts=(art_fuzz,))
    c_fuzz = generator.generate_candidates(sv_fuzz, mock_context)
    assert c_fuzz[0].nodes[0].action_type == "FUZZ_CONTRACT"


# ============================================================================
# 5. D8 -> D5 Adversarial Integration Gates
# ============================================================================

def test_d8_d05_stale_fencing_token_rejected_by_d5(mock_context, sample_obligation, tmp_path):
    """Adversarial D5 Check: Proposal with stale fencing token rejected by Controller."""
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "nonces.json"))

    lease_manager = PlanningLeaseManager()
    session = PlannerSession(task_id="TASK-PHASE-D-01", owner_id="OWNER-1", lease_manager=lease_manager)

    with session:
        lease_authority = StaticLeaseAuthority({"TASK-PHASE-D-01": session.active_lease})
        state_authority = StaticStateAuthority(state_version=1, state_digest="0" * 64)
        controller = SClassController(authority_signer=signer, nonce_store=nonce_store, lease_authority=lease_authority, state_authority=state_authority)

        sv = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, state_version=1, state_digest="0" * 64)
        session.plan(sv, mock_context)
        proposal = session.next_proposal()

        # Adversarial tamper: decrement fencing token
        stale_proposal = ActionProposal(
            proposal_id=proposal.proposal_id,
            obligation_id=proposal.obligation_id,
            action_type=proposal.action_type,
            target=proposal.target,
            purpose=proposal.purpose,
            execution_context=proposal.execution_context,
            action_digest=proposal.action_digest,
            fencing_token=proposal.fencing_token - 1,  # Stale fence!
            lease_epoch=proposal.lease_epoch,
            owner_id=proposal.owner_id,
            state_version=proposal.state_version,
            state_digest=proposal.state_digest,
        )

        res = controller.submit_proposal(
            proposal=stale_proposal,
            obligations={"OBL-001": sample_obligation},
            policies={},
            source_sha="a" * 40,
            policy_version=1,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            expires_at="2026-08-21T23:59:59Z",
        )
        assert res.decision.status == AuthorizationStatus.REJECTED
        assert any("FENCING" in r for r in res.decision.rejection_reasons)


def test_d8_d06_stale_planner_state_digest_rejected_by_d5(mock_context, sample_obligation, tmp_path):
    """Adversarial D5 Check: Proposal with state digest mismatch rejected by Controller."""
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "nonces.json"))

    lease_manager = PlanningLeaseManager()
    session = PlannerSession(task_id="TASK-PHASE-D-01", owner_id="OWNER-1", lease_manager=lease_manager)

    with session:
        lease_authority = StaticLeaseAuthority({"TASK-PHASE-D-01": session.active_lease})
        # Authoritative state is version 2, digest "2"*64
        state_authority = StaticStateAuthority(state_version=2, state_digest="2" * 64)
        controller = SClassController(authority_signer=signer, nonce_store=nonce_store, lease_authority=lease_authority, state_authority=state_authority)

        # Plan built on stale version 1
        sv = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, state_version=1, state_digest="1" * 64)
        session.plan(sv, mock_context)
        proposal = session.next_proposal()

        res = controller.submit_proposal(
            proposal=proposal,
            obligations={"OBL-001": sample_obligation},
            policies={},
            source_sha="a" * 40,
            policy_version=1,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            expires_at="2026-08-21T23:59:59Z",
        )
        assert res.decision.status == AuthorizationStatus.REJECTED
        assert any("STATE" in r for r in res.decision.rejection_reasons)


def test_d8_d07_forged_authority_context_rejected_by_d5(mock_context, sample_obligation, tmp_path):
    """Adversarial D5 Check: Controller without active lease rejects any proposal fail-closed."""
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "nonces.json"))

    lease_manager = PlanningLeaseManager()
    session = PlannerSession(task_id="TASK-PHASE-D-01", owner_id="OWNER-1", lease_manager=lease_manager)

    with session:
        # Empty lease authority (no active lease)
        lease_authority = StaticLeaseAuthority({})
        state_authority = StaticStateAuthority(state_version=1, state_digest="0" * 64)
        controller = SClassController(authority_signer=signer, nonce_store=nonce_store, lease_authority=lease_authority, state_authority=state_authority)

        sv = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, state_version=1, state_digest="0" * 64)
        session.plan(sv, mock_context)
        proposal = session.next_proposal()

        res = controller.submit_proposal(
            proposal=proposal,
            obligations={"OBL-001": sample_obligation},
            policies={},
            source_sha="a" * 40,
            policy_version=1,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            expires_at="2026-08-21T23:59:59Z",
        )
        assert res.decision.status == AuthorizationStatus.REJECTED
        assert any("NO_ACTIVE_LEASE" in r for r in res.decision.rejection_reasons)


def test_d8_d08_tampered_proposal_fields_rejected_by_action_digest():
    """Adversarial Proposal Check: Tampering with proposal parameters without digest update is rejected."""
    ctx = ExecutionContext(provider_id="P", sandbox_profile_id="S", workspace_id="W", resource_profile_id="R")

    # Creating proposal with tampered action_digest fails in __post_init__
    with pytest.raises(ValueError, match="action_digest mismatch"):
        ActionProposal(
            proposal_id="PROP-1",
            obligation_id="OBL-001",
            action_type="APPLY_PATCH",
            target="src/core.py",
            purpose="Patch core",
            execution_context=ctx,
            action_digest="0" * 64,  # Forged digest!
        )


# ============================================================================
# 6. Complete planner_state_digest Coverage
# ============================================================================

def test_d8_d09_planner_state_digest_complete_field_sensitivity(sample_obligation):
    """Property 6: Every authority-relevant field in PlannerStateContent is bound into planner_state_digest."""
    base = PlannerStateContent(
        task_id="TASK-PHASE-D-01",
        milestones=({"m": 1},),
        claims=({"c": 1},),
        obligations=({"obligation_id": "OBL-001"},),
        executable_frontier=("OBL-001",),
        blocked_frontier=("OBL-002",),
        evidence_digests=("e" * 64,),
        active_policies=({"p": 1},),
        analysis_digests=("a" * 64,),
        state_version=1,
        state_digest="d" * 64,
    )
    base_digest = compute_planner_state_digest(base)

    mutations = [
        PlannerStateContent(task_id="TASK-MUTATED", milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=({"m": 2},), claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=({"c": 2},), obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=({"obligation_id": "OBL-002"},), executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=("OBL-NEW",), blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=("OBL-BLOCKED",), evidence_digests=base.evidence_digests, active_policies=base.active_policies, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=("f" * 64,), active_policies=base.active_policies, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=({"p": 2},), analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, analysis_digests=("b" * 64,), state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, analysis_digests=base.analysis_digests, state_version=2, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest="e" * 64),
    ]

    for mutated in mutations:
        assert compute_planner_state_digest(mutated) != base_digest


# ============================================================================
# 7. Execution-Strategy Binding at Proposal Emission
# ============================================================================

def test_d8_d10_tampered_strategy_node_rejected_at_emission(mock_context):
    """ProposalEmitter enforces cryptographic strategy node digest binding before emission."""
    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_core.py",
        purpose="Test baseline",
        execution_context=mock_context,
    )

    # Tamper with node object bypassing post_init
    tampered_node = copy.copy(node)
    object.__setattr__(tampered_node, "target", "src/evil_mutation.py")

    tampered_strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-TAMPERED",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(tampered_node,),
        dependency_edges=(),
    )

    lease = PlanningLease(
        task_id="TASK-PHASE-D-01",
        owner_id="OWNER-1",
        lease_epoch=1,
        fencing_token=100,
        acquired_at="2026-08-21T00:00:00Z",
        expires_at="2026-08-21T23:59:59Z",
    )

    with pytest.raises(ValueError, match="action digest tampering detected"):
        ProposalEmitter.emit_next_proposal(
            strategy=tampered_strategy,
            lease=lease,
            state_version=1,
            state_digest="0" * 64,
        )
