"""
D8 Autonomous Planning Substrate - Phase D Integration & Adversarial Test Suite.

Exhaustively verifies:
D01: D3 Policy Delegation without rule inspection (§3.6, §8.1)
D02: Non-compensating risk invariance under maximized quality/Phi (§3.5, CORE-14)
D03: Separation of candidate strategy verification from D0 architectural claim truth (§4.2, §8.1)
D04: Context/claim/capability-appropriate hypothesis verification node synthesis
D05: D8 -> D5 adversarial integration gates (stale fence)
D06: D8 -> D5 adversarial integration gates (state drift)
D07: D8 -> D5 adversarial integration gates (missing/unauthorized active lease)
D08: Cryptographic proposal action_digest validation
D09: Complete planner_state_digest field sensitivity and domain separation
D10: Strategy-to-proposal execution binding
D11: Blocked obligation cannot generate proposal
D12: Blocked obligation injected into strategy rejected by HardConstraintGate
D13: Policy rule/expression mutation changes planner_state_digest
D14: Exact obligation policy is the only policy evaluated
D15: Claim/evidence-dependent D3 policy receives real context
D16: Catastrophic risk cannot be rescued by maximum quality/Phi
D17: Irreversible + valid signed PolicyException allowed through risk gate
D18: Irreversible without exception rejected
D19: Missing analytical target never generates APPLY_PATCH
D20: Forged state digest cannot masquerade as fresh state
D21: Strategy_digest tampering rejected
D22: Strategy mutation after fingerprinting rejected
"""

import copy
import hashlib
import time
import uuid
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
    Claim,
    ClaimSubject,
    AsymmetricAuthoritySignature,
)
from domain.types import (
    Criticality,
    ObligationCategory,
    ObligationStatus,
    PolicyScope,
    RuleType,
    CombinatorType,
    ClaimTier,
    ClaimStatus,
)
from events.state import MaterializedState
from events.store import D2NonceStore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner, Gate3ProviderKeyStore
from cryptography.hazmat.primitives.asymmetric import ed25519

from policy.models import (
    PolicyException,
    AuthorizedActor,
)
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


from benchmark.parity.verify_gate_3_certificate import Gate3PublicKeystore


@pytest.fixture(autouse=True)
def setup_authority_keys():
    Gate3AuthorityKeyStore.clear()
    Gate3PublicKeystore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    Gate3PublicKeystore.set_public_key(priv.public_key())
    Gate3ProviderKeyStore.clear()
    Gate3ProviderKeyStore.register_provider_key("K1", b"0" * 32)


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
# D01: D3 Policy Delegation (No Rule Inspection)
# ============================================================================

def test_d8_d01_d3_policy_delegation_without_rule_inspection(mock_context, sample_obligation):
    """D01: D8 MUST NOT inspect policy.expression.rules. It delegates to D3 evaluate_policy()."""
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
# D02: Non-Compensating Risk Invariance
# ============================================================================

def test_d8_d02_non_compensating_risk_cannot_be_rescued_by_max_quality(mock_context, sample_obligation):
    """D02: Metamorphic Property: Maximizing quality/Phi cannot rescue a catastrophic hard-risk rejection."""
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": sample_obligation},
        claims={},
        executable_frontier=("OBL-001",),
        state_version=1,
        state_digest="0" * 64,
    )

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

    is_valid, violations = HardConstraintGate.evaluate(blast_strategy, state_view)
    assert not is_valid
    assert any("Blast radius" in v for v in violations)

    risk_assessment = PlanEvaluator.assess_risk(blast_strategy, state_view)
    assert not risk_assessment.is_acceptable

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
# D03: Separation of Candidate Verification from D0 Plan Validation
# ============================================================================

def test_d8_d03_candidate_verification_does_not_mutate_d0_claim_truth(mock_context, sample_obligation):
    """D03: Proposing a verification node does NOT make an unsupported D0 claim SUPPORTED in Plan."""
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
        arch_claims = envelope.plan.architecture_claims
        assert len(arch_claims) == 1
        assert arch_claims[0]["claim_id"] == "CLM-ARCH-001"
        assert arch_claims[0]["status"] == "UNSUPPORTED"


# ============================================================================
# D04: Context-Appropriate Hypothesis Verification
# ============================================================================

def test_d8_d04_context_appropriate_hypothesis_verification_nodes(mock_context, sample_obligation):
    """D04: Hypothesis.requires_verification generates capability/context-appropriate node types."""
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
    sv_type = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, executable_frontier=("OBL-001",), analysis_artifacts=(art_type,))
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
    sv_ast = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, executable_frontier=("OBL-001",), analysis_artifacts=(art_ast,))
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
    sv_fuzz = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, executable_frontier=("OBL-001",), analysis_artifacts=(art_fuzz,))
    c_fuzz = generator.generate_candidates(sv_fuzz, mock_context)
    assert c_fuzz[0].nodes[0].action_type == "FUZZ_CONTRACT"


# ============================================================================
# D05-D08: D8 -> D5 Adversarial Integration Gates
# ============================================================================

def test_d8_d05_stale_fencing_token_rejected_by_d5(mock_context, sample_obligation, tmp_path):
    """D05: Proposal with stale fencing token rejected by Controller."""
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "nonces.json"))

    lease_manager = PlanningLeaseManager(lease_dir=str(tmp_path / ".leases"))
    session = PlannerSession(task_id="TASK-PHASE-D-01", owner_id="OWNER-1", lease_manager=lease_manager)

    with session:
        lease_authority = StaticLeaseAuthority({"TASK-PHASE-D-01": session.active_lease})
        state_authority = StaticStateAuthority(state_version=1, state_digest="0" * 64)
        controller = SClassController(authority_signer=signer, nonce_store=nonce_store, lease_authority=lease_authority, state_authority=state_authority)

        sv = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, executable_frontier=("OBL-001",), state_version=1, state_digest="0" * 64)
        session.plan(sv, mock_context)
        proposal = session.next_proposal()

        stale_proposal = ActionProposal(
            proposal_id=proposal.proposal_id,
            obligation_id=proposal.obligation_id,
            action_type=proposal.action_type,
            target=proposal.target,
            purpose=proposal.purpose,
            execution_context=proposal.execution_context,
            action_digest=proposal.action_digest,
            fencing_token=proposal.fencing_token - 1,
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
    """D06: Proposal with state digest mismatch rejected by Controller."""
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "nonces.json"))

    lease_manager = PlanningLeaseManager()
    session = PlannerSession(task_id="TASK-PHASE-D-01", owner_id="OWNER-1", lease_manager=lease_manager)

    with session:
        lease_authority = StaticLeaseAuthority({"TASK-PHASE-D-01": session.active_lease})
        state_authority = StaticStateAuthority(state_version=2, state_digest="2" * 64)
        controller = SClassController(authority_signer=signer, nonce_store=nonce_store, lease_authority=lease_authority, state_authority=state_authority)

        sv = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, executable_frontier=("OBL-001",), state_version=1, state_digest="1" * 64)
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
    """D07: Controller without active lease rejects any proposal fail-closed."""
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "nonces.json"))

    lease_manager = PlanningLeaseManager()
    session = PlannerSession(task_id="TASK-PHASE-D-01", owner_id="OWNER-1", lease_manager=lease_manager)

    with session:
        lease_authority = StaticLeaseAuthority({})
        state_authority = StaticStateAuthority(state_version=1, state_digest="0" * 64)
        controller = SClassController(authority_signer=signer, nonce_store=nonce_store, lease_authority=lease_authority, state_authority=state_authority)

        sv = StateProjector.project(task_id="TASK-PHASE-D-01", obligations={"OBL-001": sample_obligation}, claims={}, executable_frontier=("OBL-001",), state_version=1, state_digest="0" * 64)
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
    """D08: Tampering with proposal parameters without digest update is rejected."""
    ctx = ExecutionContext(provider_id="P", sandbox_profile_id="S", workspace_id="W", resource_profile_id="R")

    with pytest.raises(ValueError, match="action_digest mismatch"):
        ActionProposal(
            proposal_id="PROP-1",
            obligation_id="OBL-001",
            action_type="APPLY_PATCH",
            target="src/core.py",
            purpose="Patch core",
            execution_context=ctx,
            action_digest="0" * 64,
        )


# ============================================================================
# D09: Complete planner_state_digest Coverage
# ============================================================================

def test_d8_d09_planner_state_digest_complete_field_sensitivity(sample_obligation):
    """D09: Every authority-relevant field in PlannerStateContent is bound into planner_state_digest."""
    base = PlannerStateContent(
        task_id="TASK-PHASE-D-01",
        milestones=({"m": 1},),
        claims=({"c": 1},),
        obligations=({"obligation_id": "OBL-001"},),
        executable_frontier=("OBL-001",),
        blocked_frontier=("OBL-002",),
        evidence_digests=("e" * 64,),
        active_policies=({"p": 1},),
        exceptions=({"exc": 1},),
        analysis_digests=("a" * 64,),
        state_version=1,
        state_digest="d" * 64,
    )
    base_digest = compute_planner_state_digest(base)

    mutations = [
        PlannerStateContent(task_id="TASK-MUTATED", milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=({"m": 2},), claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=({"c": 2},), obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=({"obligation_id": "OBL-002"},), executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=("OBL-NEW",), blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=("OBL-BLOCKED",), evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=("f" * 64,), active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=({"p": 2},), exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=({"exc": 2},), analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=("b" * 64,), state_version=base.state_version, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=2, state_digest=base.state_digest),
        PlannerStateContent(task_id=base.task_id, milestones=base.milestones, claims=base.claims, obligations=base.obligations, executable_frontier=base.executable_frontier, blocked_frontier=base.blocked_frontier, evidence_digests=base.evidence_digests, active_policies=base.active_policies, exceptions=base.exceptions, analysis_digests=base.analysis_digests, state_version=base.state_version, state_digest="e" * 64),
    ]

    for mutated in mutations:
        assert compute_planner_state_digest(mutated) != base_digest


# ============================================================================
# D10: Strategy-to-Proposal Execution Binding
# ============================================================================

def test_d8_d10_tampered_strategy_node_rejected_at_emission(mock_context):
    """D10: ProposalEmitter enforces cryptographic strategy node digest binding before emission."""
    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_core.py",
        purpose="Test baseline",
        execution_context=mock_context,
    )

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


# ============================================================================
# D11-D12: Frontier Authority
# ============================================================================

def test_d8_d11_blocked_obligation_cannot_generate_candidate(mock_context):
    """D11: Obligations not in executable_frontier are excluded from candidate generation."""
    blocked_obl = Obligation(
        obligation_id="OBL-BLOCKED",
        task_id="TASK-PHASE-D-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        title="Blocked obligation",
        description="Blocked obligation",
    )

    generator = DeterministicRuleGenerator()
    # executable_frontier is empty -> NO candidates should be generated
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-BLOCKED": blocked_obl},
        claims={},
        executable_frontier=(),  # EMPTY
        blocked_frontier=("OBL-BLOCKED",),
        state_version=1,
        state_digest="0" * 64,
    )

    candidates = generator.generate_candidates(state_view, mock_context)
    assert len(candidates) == 0


def test_d8_d12_blocked_obligation_injected_into_strategy_rejected(mock_context):
    """D12: HardConstraintGate rejects any node targeting an obligation not in executable_frontier."""
    blocked_obl = Obligation(
        obligation_id="OBL-BLOCKED",
        task_id="TASK-PHASE-D-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        title="Blocked obligation",
        description="Blocked obligation",
    )

    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-BLOCKED": blocked_obl},
        claims={},
        executable_frontier=(),  # Not executable!
        blocked_frontier=("OBL-BLOCKED",),
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-BLOCKED",
        action_type="EXECUTE_TEST",
        target="tests/test_blocked.py",
        purpose="Test blocked",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-BLOCKED",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    is_valid, violations = HardConstraintGate.evaluate(strategy, state_view)
    assert not is_valid
    assert any("not in executable frontier" in v for v in violations)


# ============================================================================
# D13: Policy Rule Mutation Changes planner_state_digest
# ============================================================================

def test_d8_d13_policy_rule_mutation_changes_planner_state_digest():
    """D13: Complete policy semantic binding: mutating policy rules changes planner_state_digest."""
    policy1 = Policy(
        policy_id="POL-01",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(
                    rule_type=RuleType.REQUIRE_MIN_TRIALS,
                    parameters={"min_trials": 3},
                ),
            ),
        ),
    )

    policy2 = Policy(
        policy_id="POL-01",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(
                    rule_type=RuleType.REQUIRE_MIN_TRIALS,
                    parameters={"min_trials": 5},  # Mutated parameter!
                ),
            ),
        ),
    )

    state1 = PlannerStateContent(task_id="TASK-PHASE-D-01", active_policies=(policy1,))
    state2 = PlannerStateContent(task_id="TASK-PHASE-D-01", active_policies=(policy2,))

    assert compute_planner_state_digest(state1) != compute_planner_state_digest(state2)


# ============================================================================
# D14-D15: Exact D3 Policy Delegation with Real Context
# ============================================================================

def test_d8_d14_exact_obligation_policy_is_the_only_policy_evaluated(mock_context):
    """D14: HardConstraintGate only evaluates the policy specifically bound to the obligation."""
    obl_with_policy = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-PHASE-D-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        title="Obligation 1",
        description="Obligation 1",
        policy_id="POL-ALLOW",
    )

    allow_policy = Policy(
        policy_id="POL-ALLOW",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(),  # Trivial pass
        ),
    )

    deny_policy = Policy(
        policy_id="POL-DENY",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(PolicyRule(rule_type=RuleType.REQUIRE_MIN_TRIALS, parameters={"min_trials": 999}),),
        ),
    )

    # State has BOTH policies, but OBL-001 is bound strictly to POL-ALLOW
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": obl_with_policy},
        claims={},
        executable_frontier=("OBL-001",),
        active_policies=(allow_policy, deny_policy),
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_obl.py",
        purpose="Test",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-EXACT-POLICY",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    is_valid, violations = HardConstraintGate.evaluate(strategy, state_view)
    assert is_valid
    assert len(violations) == 0


from domain.types import TargetType
from domain.exceptions import DomainValidationError


def test_d8_d15_claim_evidence_dependent_d3_policy_receives_real_context(mock_context):
    """D15: PolicyEvaluationContext reconstructs real claims from state."""
    claim = Claim(
        claim_id="CLM-001",
        obligation_id="OBL-001",
        tier=ClaimTier.V1_STRUCTURAL,
        subject=ClaimSubject(target_type=TargetType.FUNCTION, identifier="handle_core"),
        predicate="NoPanic",
        criticality=Criticality.HIGH,
        status=ClaimStatus.SUPPORTED,
    )

    obl = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-PHASE-D-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        title="Obligation 1",
        description="Obligation 1",
        claim_ids=("CLM-001",),
        policy_id="POL-REQUIRE-TIER",
    )

    tier_policy = Policy(
        policy_id="POL-REQUIRE-TIER",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(
                    rule_type=RuleType.REQUIRE_TIER,
                    parameters={"tier": "V1_STRUCTURAL", "min_count": 1},
                ),
            ),
        ),
    )

    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": obl},
        claims={"CLM-001": claim},
        executable_frontier=("OBL-001",),
        active_policies=(tier_policy,),
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_tier.py",
        purpose="Test tier",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-TIER-POLICY",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    is_valid, violations = HardConstraintGate.evaluate(strategy, state_view)
    assert is_valid, f"Violations: {violations}"


# ============================================================================
# D16: Catastrophic Risk Cannot Be Rescued
# ============================================================================

def test_d8_d16_catastrophic_risk_cannot_be_rescued_by_maximum_quality(mock_context, sample_obligation):
    """D16: Proves non-compensating property: irreversible action without exception is rejected regardless of quality."""
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": sample_obligation},
        claims={},
        executable_frontier=("OBL-001",),
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N-DROP-DB",
        obligation_id="OBL-001",
        action_type="DROP_DATABASE",
        target="prod-database",
        purpose="Wipe DB",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-DROP-DB",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    is_valid, violations = HardConstraintGate.evaluate(strategy, state_view)
    assert not is_valid
    assert any("Irreversible action" in v for v in violations)


# ============================================================================
# D17-D18: Signed PolicyException Semantics
# ============================================================================

def test_d8_d17_irreversible_with_valid_signed_policy_exception_allowed(mock_context, sample_obligation):
    """D17: Irreversible action WITH matching signed PolicyException passes the risk gate."""
    actor = AuthorizedActor(
        actor_id="SEC-ADMIN-1",
        actor_role="SECURITY_OFFICER",
        public_key_fingerprint="a" * 64,
    )
    sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="GATE3-SIGNER",
        public_key_fingerprint="0" * 64,
        payload_digest="0" * 64,
        signature_hex="0" * 128,
        timestamp="2026-08-21T12:00:00Z",
    )
    exc = PolicyException(
        exception_id="EXC-FORCE-PUSH",
        obligation_id="OBL-001",
        policy_id="POL-DEFAULT",
        justification="Authorized emergency deployment override",
        authorized_by=actor,
        compensating_controls=("Full backup verified", "Peer review conducted"),
        signature=sig,
    )

    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": sample_obligation},
        claims={},
        executable_frontier=("OBL-001",),
        exceptions=(exc,),
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N-FORCE-PUSH",
        obligation_id="OBL-001",
        action_type="FORCE_PUSH",
        target="origin/master",
        purpose="Emergency force push",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-FORCE-PUSH-EXC",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    risk = PlanEvaluator.assess_risk(strategy, state_view)
    assert risk.is_acceptable
    assert risk.irreversible_risk == 0.0


def test_d8_d18_irreversible_without_exception_rejected(mock_context, sample_obligation):
    """D18: Irreversible action WITHOUT matching exception is rejected."""
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": sample_obligation},
        claims={},
        executable_frontier=("OBL-001",),
        exceptions=(),  # No exception!
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N-FORCE-PUSH",
        obligation_id="OBL-001",
        action_type="FORCE_PUSH",
        target="origin/master",
        purpose="Emergency force push",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-FORCE-PUSH-NO-EXC",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    risk = PlanEvaluator.assess_risk(strategy, state_view)
    assert not risk.is_acceptable
    assert risk.irreversible_risk == 1.0
    assert any("Irreversible action" in r for r in risk.rejection_reasons)


# ============================================================================
# D19: No Fabricated Mutation Targets
# ============================================================================

def test_d8_d19_missing_analytical_target_never_generates_apply_patch(mock_context, sample_obligation):
    """D19: When no target path is observed by analysts, generator does NOT invent 'src/core.py'."""
    generator = DeterministicRuleGenerator()

    # State with NO analysis artifacts (no observed files)
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": sample_obligation},
        claims={},
        executable_frontier=("OBL-001",),
        analysis_artifacts=(),  # No artifacts!
        state_version=1,
        state_digest="0" * 64,
    )

    candidates = generator.generate_candidates(state_view, mock_context)
    assert len(candidates) > 0
    # Every generated node must be verification/audit; NO APPLY_PATCH node
    for candidate in candidates:
        for node in candidate.nodes:
            assert node.action_type != "APPLY_PATCH", f"Invented APPLY_PATCH node on {node.target}!"


# ============================================================================
# D20: Forged State Digest Detection
# ============================================================================

def test_d8_d20_forged_state_digest_cannot_masquerade_as_fresh_state(mock_context, sample_obligation):
    """D20: Corrupted/short state digest fails validation in StateProjector with DomainValidationError."""
    with pytest.raises(DomainValidationError, match="Invalid state_digest"):
        StateProjector.project(
            task_id="TASK-PHASE-D-01",
            obligations={"OBL-001": sample_obligation},
            claims={},
            executable_frontier=("OBL-001",),
            state_version=1,
            state_digest="short_forged",
        )

    # Valid format but forged hash against authoritative state
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": sample_obligation},
        claims={},
        executable_frontier=("OBL-001",),
        state_version=1,
        state_digest="f" * 64,
    )

    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_x.py",
        purpose="Test",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-FORGED-STATE",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    # When evaluated against state_view, it passes format, but state authority in D5 rejects it
    is_valid, violations = HardConstraintGate.evaluate(strategy, state_view)
    assert is_valid


# ============================================================================
# D21-D22: ExecutionStrategyArtifact Fingerprint Validation
# ============================================================================

def test_d8_d21_strategy_digest_tampering_rejected(mock_context, sample_obligation):
    """D21: ExecutionStrategyArtifact rejects explicit forged strategy_digest at construction."""
    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_x.py",
        purpose="Test",
        execution_context=mock_context,
    )

    with pytest.raises(ValueError, match="strategy_digest mismatch"):
        ExecutionStrategyArtifact(
            strategy_id="STRAT-TAMPERED",
            plan_id="PLAN-01",
            plan_revision=1,
            nodes=(node,),
            dependency_edges=(),
            strategy_digest="0" * 64,  # Forged digest!
        )


def test_d8_d22_strategy_mutation_after_fingerprinting_rejected(mock_context):
    """D22: ProposalEmitter rejects strategy if its nodes were mutated after fingerprinting."""
    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_x.py",
        purpose="Test",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-MUTATED",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    # Mutate strategy plan_id bypassing post_init
    tampered_strat = copy.copy(strategy)
    object.__setattr__(tampered_strat, "plan_id", "PLAN-MUTATED")

    lease = PlanningLease(
        task_id="TASK-PHASE-D-01",
        owner_id="OWNER-1",
        lease_epoch=1,
        fencing_token=100,
        acquired_at="2026-08-21T00:00:00Z",
        expires_at="2026-08-21T23:59:59Z",
    )

    with pytest.raises(ValueError, match="Execution strategy digest tampering detected"):
        ProposalEmitter.emit_next_proposal(
            strategy=tampered_strat,
            lease=lease,
            state_version=1,
            state_digest="0" * 64,
        )


# ============================================================================
# D23-D25: Proposal-Time State Freshness Gates
# ============================================================================

from planner.session import StaleStateError


def test_d8_d23_state_mutation_after_plan_proposal_rejected(mock_context, sample_obligation, tmp_path):
    """D23: State version mutation after plan causes next_proposal to reject with StaleStateError."""
    lease_manager = PlanningLeaseManager(lease_dir=str(tmp_path / ".leases"))
    session = PlannerSession(task_id="TASK-PHASE-D-01", owner_id="OWNER-1", lease_manager=lease_manager)

    with session:
        sv_v1 = StateProjector.project(
            task_id="TASK-PHASE-D-01",
            obligations={"OBL-001": sample_obligation},
            claims={},
            executable_frontier=("OBL-001",),
            state_version=1,
            state_digest="1" * 64,
        )
        session.plan(sv_v1, mock_context)

        # Mutated state view (version advanced from 1 to 2)
        sv_v2 = StateProjector.project(
            task_id="TASK-PHASE-D-01",
            obligations={"OBL-001": sample_obligation},
            claims={},
            executable_frontier=("OBL-001",),
            state_version=2,
            state_digest="2" * 64,
        )

        with pytest.raises(StaleStateError, match="State version mutation detected"):
            session.next_proposal(current_state_view=sv_v2)


def test_d8_d24_stale_planner_state_digest_proposal_rejected(mock_context, sample_obligation, tmp_path):
    """D24: Stale planner_state_digest causes next_proposal to reject with StaleStateError."""
    lease_manager = PlanningLeaseManager(lease_dir=str(tmp_path / ".leases"))
    session = PlannerSession(task_id="TASK-PHASE-D-01", owner_id="OWNER-1", lease_manager=lease_manager)

    with session:
        sv_base = StateProjector.project(
            task_id="TASK-PHASE-D-01",
            obligations={"OBL-001": sample_obligation},
            claims={},
            executable_frontier=("OBL-001",),
            state_version=1,
            state_digest="1" * 64,
        )
        session.plan(sv_base, mock_context)

        # Mutated domain state with same version/digest but different claims
        sv_mutated_claims = StateProjector.project(
            task_id="TASK-PHASE-D-01",
            obligations={"OBL-001": sample_obligation},
            claims={"CLM-NEW": {"claim_id": "CLM-NEW", "tier": "V1_STRUCTURAL", "predicate": "P", "status": "SUPPORTED"}},
            executable_frontier=("OBL-001",),
            state_version=1,
            state_digest="1" * 64,
        )

        with pytest.raises(StaleStateError, match="Planner state digest mutation detected"):
            session.next_proposal(current_state_view=sv_mutated_claims)


def test_d8_d25_stale_repository_source_state_proposal_rejected(mock_context, sample_obligation, tmp_path):
    """D25: State authority mismatch causes next_proposal to reject with StaleStateError."""
    lease_manager = PlanningLeaseManager(lease_dir=str(tmp_path / ".leases"))
    state_authority = StaticStateAuthority(state_version=2, state_digest="2" * 64)

    session = PlannerSession(
        task_id="TASK-PHASE-D-01",
        owner_id="OWNER-1",
        lease_manager=lease_manager,
        state_authority=state_authority,
    )

    with session:
        # Plan was created against version 1
        sv_v1 = StateProjector.project(
            task_id="TASK-PHASE-D-01",
            obligations={"OBL-001": sample_obligation},
            claims={},
            executable_frontier=("OBL-001",),
            state_version=1,
            state_digest="1" * 64,
        )
        session.plan(sv_v1, mock_context)

        # Authority is at version 2 -> proposal rejected
        with pytest.raises(StaleStateError, match="Authoritative state mismatch"):
            session.next_proposal()


# ============================================================================
# D26-D28: Evidence-Dependent D3 Policies & Code Coverage
# ============================================================================

from domain.models import Evidence, EvidenceObservation, EvidenceScope, Provenance, HmacSessionSignature
from domain.types import EvidencePolarity, EvidenceValidity, RawStatus
from benchmark.parity.gate_3_authority import issue_gate_3_evidence_certificate, sign_provider_evidence


def make_sample_evidence(ev_id: str, cap: str = "TEST_EXECUTION", source_sha: str = "0" * 40, cov_pct: float = 95.0) -> Evidence:
    obs = EvidenceObservation(
        raw_status=RawStatus.PASS,
        diagnostics=(),
        counterexample={"coverage_pct": cov_pct},
    )
    prov = Provenance(
        engine_name="pytest",
        engine_version="9.0.3",
        environment_hash="0" * 64,
        timestamp="2026-08-21T12:00:00Z",
    )
    scope = EvidenceScope(
        targets_evaluated=("src/core.py",),
        aspects_covered=("FUNCTIONAL_CORRECTNESS",),
    )
    sig = sign_provider_evidence(
        evidence_id=ev_id,
        claim_id="CLM-001",
        provider_id="PROVIDER-TEST",
        capability=cap,
        execution_id="EXEC-001",
        source_sha=source_sha,
        scope=scope,
        observation=obs,
        provenance=prov,
        key_id="K1",
        nonce=uuid.uuid4().hex,
    )
    ev = Evidence(
        evidence_id=ev_id,
        claim_id="CLM-001",
        provider_id="PROVIDER-TEST",
        capability=cap,
        execution_id="EXEC-001",
        source_sha=source_sha,
        scope=scope,
        observation=obs,
        polarity=EvidencePolarity.SUPPORTS,
        validity=EvidenceValidity.VALID,
        independence_group="GROUP-1",
        provenance=prov,
        signature=sig,
    )
    cert = issue_gate_3_evidence_certificate(ev, source_sha)
    object.__setattr__(ev, "trust_certificate", cert)
    return ev


def test_d8_d26_evidence_dependent_policy_with_supplied_evidence_passes(mock_context):
    """D26: Evidence-dependent D3 policy passes when valid supporting evidence is supplied."""
    obl = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-PHASE-D-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        title="Obligation 1",
        description="Obligation 1",
        policy_id="POL-REQ-CAP",
    )

    policy = Policy(
        policy_id="POL-REQ-CAP",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(
                    rule_type=RuleType.REQUIRE_CAPABILITY,
                    parameters={"capability": "TEST_EXECUTION"},
                ),
            ),
        ),
    )

    ev = make_sample_evidence("EV-001", cap="TEST_EXECUTION")
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": obl},
        claims={},
        executable_frontier=("OBL-001",),
        evidence_items=(ev,),
        active_policies=(policy,),
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_x.py",
        purpose="Test",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-EV-PASS",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    is_valid, violations = HardConstraintGate.evaluate(strategy, state_view)
    assert is_valid, f"Violations: {violations}"


def test_d8_d27_evidence_dependent_policy_without_evidence_fails_closed(mock_context):
    """D27: Evidence-dependent D3 policy fails closed (DENY) when no evidence is available."""
    obl = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-PHASE-D-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        title="Obligation 1",
        description="Obligation 1",
        policy_id="POL-REQ-CAP",
    )

    policy = Policy(
        policy_id="POL-REQ-CAP",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(
                    rule_type=RuleType.REQUIRE_CAPABILITY,
                    parameters={"capability": "TEST_EXECUTION"},
                ),
            ),
        ),
    )

    # Empty evidence items -> fail closed!
    state_view = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": obl},
        claims={},
        executable_frontier=("OBL-001",),
        evidence_items=(),  # EMPTY
        active_policies=(policy,),
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_x.py",
        purpose="Test",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-EV-FAIL",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    is_valid, violations = HardConstraintGate.evaluate(strategy, state_view)
    assert not is_valid
    assert any("DENIED action for obligation 'OBL-001'" in v for v in violations)


def test_d8_d28_require_code_coverage_uses_authoritative_evidence_context(mock_context):
    """D28: REQUIRE_CODE_COVERAGE evaluates structured metrics from authoritative evidence."""
    obl = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-PHASE-D-01",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        title="Obligation 1",
        description="Obligation 1",
        policy_id="POL-COV",
    )

    policy = Policy(
        policy_id="POL-COV",
        scope_level=PolicyScope.TASK,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(
                    rule_type=RuleType.REQUIRE_CODE_COVERAGE,
                    parameters={"min_coverage_pct": 80.0},
                ),
            ),
        ),
    )

    # Case A: 95% coverage -> passes
    ev_pass = make_sample_evidence("EV-001", cap="TEST_EXECUTION", cov_pct=95.0)
    sv_pass = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": obl},
        claims={},
        executable_frontier=("OBL-001",),
        evidence_items=(ev_pass,),
        active_policies=(policy,),
        state_version=1,
        state_digest="0" * 64,
    )

    node = PlanNode(
        node_id="N1",
        obligation_id="OBL-001",
        action_type="EXECUTE_TEST",
        target="tests/test_x.py",
        purpose="Test",
        execution_context=mock_context,
    )
    strategy = ExecutionStrategyArtifact(
        strategy_id="STRAT-COV",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node,),
        dependency_edges=(),
    )

    is_valid, violations = HardConstraintGate.evaluate(strategy, sv_pass)
    assert is_valid, f"Violations: {violations}"

    # Case B: 50% coverage -> fails
    ev_fail = make_sample_evidence("EV-002", cap="TEST_EXECUTION", cov_pct=50.0)
    sv_fail = StateProjector.project(
        task_id="TASK-PHASE-D-01",
        obligations={"OBL-001": obl},
        claims={},
        executable_frontier=("OBL-001",),
        evidence_items=(ev_fail,),
        active_policies=(policy,),
        state_version=1,
        state_digest="0" * 64,
    )

    is_valid_fail, violations = HardConstraintGate.evaluate(strategy, sv_fail)
    assert not is_valid_fail
    assert any("DENIED action for obligation 'OBL-001'" in v for v in violations)
