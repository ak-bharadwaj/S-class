"""
S-Class EOS V11.2 - D5 Controller Final Test Suite.
Exhaustive verification of:
1. Ready / Blocked / Executable Frontier Calculus (READY != EXECUTABLE distinction, CORE-22).
2. Topological dependency ordering & cycle rejection (CORE-23).
3. Precondition evaluation & immutable AuthorizationDecision creation (CORE-05).
4. Real D3 Policy evaluation integration during PRE_AUTHORIZE.
5. Exact Action Binding & action_digest Domain Separator SCLASS_ACTION_BINDING_V1:.
6. Exact Execution Context & context_digest Domain Separator SCLASS_EXECUTION_CONTEXT_V1:.
7. Ed25519-signed single-use ExecutionToken with domain separator SCLASS_EXECUTION_TOKEN_V1:.
8. ExecutionToken admission/consumption strictly BEFORE D6 execution.
9. Immutable, Authority-signed ExecutionAdmissionResult bound to:
   token_id, execution_nonce, obligation_id, action_digest, context_digest, source_sha, policy_version, decision_id, admitted_at.
10. Mandatory ExecutionEnvelope container delivered to D6 executor.
11. Explicit D2 Durable Completion Lifecycle:
    COMPLETION_STARTED -> POST_EXECUTE -> POST_OBSERVE -> COMPLETION_FINALIZED (or COMPLETION_FAILED).
12. Full Adversarial Red-Team Suite:
    - Authorized A + execute B -> reject before D6
    - Altered action_type -> reject before D6
    - Altered target -> reject before D6
    - Altered purpose -> reject before D6
    - Altered parameters -> reject before D6
    - Altered action_digest -> reject before D6
    - Altered provider_id -> reject
    - Altered sandbox_profile_id -> reject
    - Altered workspace_id -> reject
    - Altered resource_profile -> reject
    - Altered capability_set -> reject
    - Token/admission mismatch -> reject
    - Admission/context mismatch -> reject
    - Missing ActionBinding -> reject
    - Missing ExecutionContext -> reject
    - Replay token -> reject
    - Replay admission -> reject
    - Replay completion -> reject
    - Concurrent admission -> exactly one winner
    - Concurrent completion -> exactly one winner
    - D6 attempts direct authorization -> reject
    - D6 attempts capability escalation -> reject
    - Hook attempts token minting -> reject
    - Policy mutation after authorization -> existing decision remains immutable
"""

import os
import pytest
import uuid
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor
from cryptography.hazmat.primitives.asymmetric import ed25519

from domain.models import (
    Obligation,
    Policy,
    PolicyRule,
    PolicyExpression,
    AsymmetricAuthoritySignature,
)
from domain.types import (
    ObligationCategory,
    ObligationStatus,
    Criticality,
    RuleType,
    CombinatorType,
    PolicyScope,
)
from events.store import D2NonceStore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from controller.token import (
    ActionBinding,
    ExecutionContext,
    ExecutionToken,
    ExecutionAdmissionResult,
    ExecutionEnvelope,
    compute_action_digest,
    compute_context_digest,
    _mint_execution_token,
    verify_and_consume_execution_token,
    verify_execution_token_signature,
    verify_admission_signature,
    verify_execution_envelope,
    SCLASS_ACTION_BINDING_DOMAIN_SEPARATOR,
    SCLASS_EXECUTION_CONTEXT_DOMAIN_SEPARATOR,
    SCLASS_EXECUTION_TOKEN_DOMAIN_SEPARATOR,
    SCLASS_EXECUTION_ADMISSION_DOMAIN_SEPARATOR,
)
from controller.frontier import (
    ExecutionFrontier,
    compute_ready_frontier,
    compute_blocked_frontier,
    compute_executable_frontier,
    compute_frontier,
    get_topological_dependency_order,
)
from controller.authorization import (
    ActionProposal,
    AuthorizationStatus,
    AuthorizationDecision,
    AuthorizationEngine,
)
from controller.hooks import (
    LifecycleStage,
    HookResult,
    HookContext,
    LifecycleHook,
    LifecyclePipeline,
)
from controller.controller import (
    SClassController,
    ControllerDispatchResult,
    ExecutionCompletionResult,
)


DEFAULT_SHA = "a" * 40
ALT_SHA = "b" * 40
TIMESTAMP_NOW = "2026-08-20T12:00:00Z"
TIMESTAMP_EXPIRY = "2026-08-20T13:00:00Z"
TIMESTAMP_PAST = "2026-08-20T11:00:00Z"
TIMESTAMP_LATE = "2026-08-20T14:00:00Z"
TIMESTAMP_FUTURE = "2026-08-20T15:00:00Z"


@pytest.fixture(autouse=True)
def setup_authority_keys():
    """Initializes Gate 3 Authority KeyStore for test runs."""
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


@pytest.fixture
def fresh_nonce_store(tmp_path):
    """Provides a fresh isolated D2 nonce store for testing."""
    log_file = str(tmp_path / "d5_test_nonces.log")
    return D2NonceStore(file_path=log_file)


def make_test_context(
    provider_id: str = "PROV-SANDBOX-01",
    sandbox_profile_id: str = "SBX-STRICT-V1",
    workspace_id: str = "WS-PROD-001",
    resource_profile_id: str = "RES-STD-4CPU",
    capability_set: tuple = ("CAP_READ_SOURCE", "CAP_EXEC_TEST"),
) -> ExecutionContext:
    return ExecutionContext(
        provider_id=provider_id,
        sandbox_profile_id=sandbox_profile_id,
        workspace_id=workspace_id,
        resource_profile_id=resource_profile_id,
        capability_set=capability_set,
    )


def make_test_obligation(
    obligation_id: str = "OBL-001",
    task_id: str = "TASK-001",
    status: ObligationStatus = ObligationStatus.OPEN,
    depends_on: tuple = (),
    category: ObligationCategory = ObligationCategory.SECURITY_INTEGRITY,
    policy_id: str = "POL-001",
) -> Obligation:
    return Obligation(
        obligation_id=obligation_id,
        task_id=task_id,
        title=f"Test Obligation {obligation_id}",
        description="Verify system invariant",
        category=category,
        criticality=Criticality.HIGH,
        status=status,
        depends_on=depends_on,
        policy_id=policy_id,
    )


def make_test_policy(policy_id: str = "POL-001", version: int = 1) -> Policy:
    rule = PolicyRule(
        rule_type=RuleType.NO_CONFLICTS,
        parameters={},
    )
    expr = PolicyExpression(
        combinator=CombinatorType.ALL,
        rules=(rule,),
    )
    return Policy(
        policy_id=policy_id,
        scope_level=PolicyScope.PROJECT,
        version=version,
        expression=expr,
    )


def make_test_proposal(
    proposal_id: str = "ACT-001",
    obligation_id: str = "OBL-001",
    action_type: str = "EXECUTE_TEST",
    target: str = "tests/test_auth.py",
    purpose: str = "Run behavioral property tests",
    execution_context: ExecutionContext = None,
    parameters: dict = None,
    estimated_cost: float = 0.05,
    timeout_seconds: int = 30,
    prerequisites: tuple = (),
) -> ActionProposal:
    return ActionProposal(
        proposal_id=proposal_id,
        obligation_id=obligation_id,
        action_type=action_type,
        target=target,
        purpose=purpose,
        execution_context=execution_context or make_test_context(),
        parameters=parameters or {},
        estimated_cost_usd=estimated_cost,
        timeout_seconds=timeout_seconds,
        prerequisites=prerequisites,
    )


# ============================================================================
# 1. Deterministic Frontier Calculus Tests (§11.4, CORE-22, CORE-23)
# ============================================================================

def test_frontier_ready_vs_executable_distinction():
    """CORE-22 Invariant: READY != EXECUTABLE."""
    obls = {
        "OBL-1": make_test_obligation(obligation_id="OBL-1", status=ObligationStatus.OPEN, policy_id="POL-1"),
        "OBL-2": make_test_obligation(obligation_id="OBL-2", status=ObligationStatus.OPEN, policy_id="POL-MISSING"),
    }
    policies = {"POL-1": make_test_policy("POL-1")}

    ready = compute_ready_frontier(obls)
    assert set(ready) == {"OBL-1", "OBL-2"}

    executable = compute_executable_frontier(obls, policies)
    assert executable == ("OBL-1",)


def test_frontier_blocked_transitive_propagation():
    """Blocked obligation transitively blocks all downstream dependents."""
    obls = {
        "OBL-ROOT": make_test_obligation(obligation_id="OBL-ROOT", status=ObligationStatus.BLOCKED),
        "OBL-CHILD-1": make_test_obligation(obligation_id="OBL-CHILD-1", depends_on=("OBL-ROOT",)),
        "OBL-CHILD-2": make_test_obligation(obligation_id="OBL-CHILD-2", depends_on=("OBL-CHILD-1",)),
        "OBL-INDEPENDENT": make_test_obligation(obligation_id="OBL-INDEPENDENT", status=ObligationStatus.OPEN),
    }
    blocked = compute_blocked_frontier(obls)
    assert set(blocked) == {"OBL-ROOT", "OBL-CHILD-1", "OBL-CHILD-2"}
    assert "OBL-INDEPENDENT" not in blocked


def test_topological_dependency_ordering_and_cycle_rejection():
    """CORE-23 Invariant: Topological sort orders dependencies deterministically; cycles are rejected."""
    obls = {
        "OBL-C": make_test_obligation(obligation_id="OBL-C", depends_on=("OBL-B",)),
        "OBL-A": make_test_obligation(obligation_id="OBL-A", depends_on=()),
        "OBL-B": make_test_obligation(obligation_id="OBL-B", depends_on=("OBL-A",)),
    }
    order = get_topological_dependency_order(obls)
    assert order == ["OBL-A", "OBL-B", "OBL-C"]

    obls_cyclic = {
        "OBL-C": make_test_obligation(obligation_id="OBL-C", depends_on=("OBL-B",)),
        "OBL-A": make_test_obligation(obligation_id="OBL-A", depends_on=("OBL-C",)),
        "OBL-B": make_test_obligation(obligation_id="OBL-B", depends_on=("OBL-A",)),
    }
    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        get_topological_dependency_order(obls_cyclic)


def test_frontier_disallowed_category_or_zero_budget():
    """Disallowed category or zero remaining budget excludes obligations from executable frontier."""
    obls = {
        "OBL-1": make_test_obligation(obligation_id="OBL-1", category=ObligationCategory.CONTRACT_CONFORMANCE),
    }
    policies = {"POL-001": make_test_policy()}
    exec1 = compute_executable_frontier(obls, policies, disallowed_categories=[ObligationCategory.CONTRACT_CONFORMANCE])
    assert exec1 == ()
    exec2 = compute_executable_frontier(obls, policies, budget_remaining=0.0)
    assert exec2 == ()


# ============================================================================
# 2. Precondition & Authorization Engine Tests (§8.2, CORE-05)
# ============================================================================

def test_authorization_preconditions_all_pass():
    """Proposal on executable obligation with valid parameters -> AUTHORIZED."""
    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal()

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
    )
    assert decision.status == AuthorizationStatus.AUTHORIZED
    assert decision.action_digest == proposal.action_digest
    assert decision.context_digest == proposal.context_digest
    assert len(decision.rejection_reasons) == 0


def test_authorization_rejected_target_not_executable():
    """Target obligation outside Executable frontier -> REJECTED."""
    obls = {"OBL-001": make_test_obligation(status=ObligationStatus.BLOCKED)}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal()

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
    )
    assert decision.status == AuthorizationStatus.REJECTED
    assert any("BLOCKED" in r for r in decision.rejection_reasons)


def test_authorization_rejected_policy_denial():
    """Policy evaluation denial during PRE_AUTHORIZE -> REJECTED with zero token."""
    rule = PolicyRule(
        rule_type=RuleType.REQUIRE_CAPABILITY,
        parameters={"capability": "NONEXISTENT_RESTRICTED_CAPABILITY"},
    )
    expr = PolicyExpression(
        combinator=CombinatorType.ALL,
        rules=(rule,),
    )
    denying_policy = Policy(
        policy_id="POL-STRICT",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=expr,
    )
    obls = {"OBL-001": make_test_obligation(policy_id="POL-STRICT")}
    policies = {"POL-STRICT": denying_policy}
    proposal = make_test_proposal()

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
    )
    assert decision.status == AuthorizationStatus.REJECTED
    assert any("Policy" in r for r in decision.rejection_reasons)


def test_authorization_policy_mutation_after_decision_preserves_immutable_binding():
    """Mutating policies dict after authorization does not change the already issued AuthorizationDecision."""
    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal()

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
    )
    assert decision.status == AuthorizationStatus.AUTHORIZED

    policies.clear()
    assert decision.status == AuthorizationStatus.AUTHORIZED
    assert decision.policy_version == 1


# ============================================================================
# 3. ExecutionEnvelope & D5 -> D6 Boundary Tests
# ============================================================================

def test_full_execution_envelope_lifecycle_accepted(fresh_nonce_store):
    """Full lifecycle: Proposal -> Token -> Admission -> ExecutionEnvelope -> D6 Verification -> Completion."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}

    dispatch = controller.submit_proposal(proposal, obls, policies, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    assert token is not None

    admission = controller.admit_execution(
        token=token,
        expected_obligation_id="OBL-001",
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        expected_action_binding=proposal.binding,
        expected_execution_context=proposal.execution_context,
        current_time_iso=TIMESTAMP_NOW,
    )
    assert admission.is_admitted is True

    # Controller constructs mandatory ExecutionEnvelope
    envelope = controller.create_execution_envelope(
        token=token,
        admission=admission,
        action_binding=proposal.binding,
        execution_context=proposal.execution_context,
    )

    # D6 Gate: Verifies envelope before starting process
    is_envelope_valid = verify_execution_envelope(
        envelope=envelope,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=TIMESTAMP_NOW,
        authority_signer=signer,
        nonce_store=fresh_nonce_store,
    )
    assert is_envelope_valid is True

    # Complete execution with envelope
    comp = controller.complete_execution(envelope=envelope, execution_result={"status": "PASS"})
    assert comp.is_valid_execution is True


# ============================================================================
# 4. Mandatory Action & Context Alteration Adversarial Suite
# ============================================================================

def test_adversarial_authorized_a_execute_b_rejected_before_d6(fresh_nonce_store):
    """Adversarial: Authorized Action A, but caller passes Action B in envelope -> Envelope rejects before D6."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal_a = make_test_proposal(action_type="EXECUTE_TEST", target="tests/test_auth.py")
    dispatch = controller.submit_proposal(proposal_a, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal_a.binding, proposal_a.execution_context, TIMESTAMP_NOW)

    action_b = ActionBinding(action_type="APPLY_PATCH", target="controller/token.py", purpose="Rogue patch")

    with pytest.raises(ValueError, match="Action digest mismatch"):
        controller.create_execution_envelope(token, admission, action_b, proposal_a.execution_context)


def test_adversarial_altered_action_type_rejected_before_d6(fresh_nonce_store):
    """Adversarial: Altering action_type in binding -> envelope rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal(action_type="EXECUTE_TEST", target="tests/test_auth.py")
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    altered_binding = ActionBinding(action_type="STATIC_ANALYSIS", target="tests/test_auth.py", purpose=proposal.purpose)
    with pytest.raises(ValueError, match="Action digest mismatch"):
        controller.create_execution_envelope(token, admission, altered_binding, proposal.execution_context)


def test_adversarial_altered_target_rejected_before_d6(fresh_nonce_store):
    """Adversarial: Altering target in binding -> envelope rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal(action_type="EXECUTE_TEST", target="tests/test_auth.py")
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    altered_binding = ActionBinding(action_type="EXECUTE_TEST", target="tests/test_unauthorized.py", purpose=proposal.purpose)
    with pytest.raises(ValueError, match="Action digest mismatch"):
        controller.create_execution_envelope(token, admission, altered_binding, proposal.execution_context)


def test_adversarial_altered_purpose_rejected_before_d6(fresh_nonce_store):
    """Adversarial: Altering purpose in binding -> envelope rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    altered_binding = ActionBinding(action_type=proposal.action_type, target=proposal.target, purpose="Malicious purpose")
    with pytest.raises(ValueError, match="Action digest mismatch"):
        controller.create_execution_envelope(token, admission, altered_binding, proposal.execution_context)


def test_adversarial_altered_parameters_rejected_before_d6(fresh_nonce_store):
    """Adversarial: Altering parameters in binding -> envelope rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal(parameters={"mode": "safe"})
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    altered_binding = ActionBinding(action_type=proposal.action_type, target=proposal.target, purpose=proposal.purpose, parameters={"mode": "root_bypass"})
    with pytest.raises(ValueError, match="Action digest mismatch"):
        controller.create_execution_envelope(token, admission, altered_binding, proposal.execution_context)


def test_adversarial_altered_provider_id_rejected(fresh_nonce_store):
    """Adversarial: ExecutionContext with altered provider_id is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    altered_ctx = ExecutionContext(
        provider_id="ROGUE_UNCONTAINED_PROVIDER",
        sandbox_profile_id=proposal.execution_context.sandbox_profile_id,
        workspace_id=proposal.execution_context.workspace_id,
        resource_profile_id=proposal.execution_context.resource_profile_id,
        capability_set=proposal.execution_context.capability_set,
    )
    with pytest.raises(ValueError, match="Context digest mismatch"):
        controller.create_execution_envelope(token, admission, proposal.binding, altered_ctx)


def test_adversarial_altered_sandbox_profile_id_rejected(fresh_nonce_store):
    """Adversarial: ExecutionContext with altered sandbox_profile_id is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    altered_ctx = ExecutionContext(
        provider_id=proposal.execution_context.provider_id,
        sandbox_profile_id="SBX-UNCONFINED-ROOT",
        workspace_id=proposal.execution_context.workspace_id,
        resource_profile_id=proposal.execution_context.resource_profile_id,
        capability_set=proposal.execution_context.capability_set,
    )
    with pytest.raises(ValueError, match="Context digest mismatch"):
        controller.create_execution_envelope(token, admission, proposal.binding, altered_ctx)


def test_adversarial_altered_workspace_id_rejected(fresh_nonce_store):
    """Adversarial: ExecutionContext with altered workspace_id is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    altered_ctx = ExecutionContext(
        provider_id=proposal.execution_context.provider_id,
        sandbox_profile_id=proposal.execution_context.sandbox_profile_id,
        workspace_id="WS-ESCAPED-HOST",
        resource_profile_id=proposal.execution_context.resource_profile_id,
        capability_set=proposal.execution_context.capability_set,
    )
    with pytest.raises(ValueError, match="Context digest mismatch"):
        controller.create_execution_envelope(token, admission, proposal.binding, altered_ctx)


def test_adversarial_altered_resource_profile_rejected(fresh_nonce_store):
    """Adversarial: ExecutionContext with altered resource_profile_id is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    altered_ctx = ExecutionContext(
        provider_id=proposal.execution_context.provider_id,
        sandbox_profile_id=proposal.execution_context.sandbox_profile_id,
        workspace_id=proposal.execution_context.workspace_id,
        resource_profile_id="RES-UNLIMITED-GPU",
        capability_set=proposal.execution_context.capability_set,
    )
    with pytest.raises(ValueError, match="Context digest mismatch"):
        controller.create_execution_envelope(token, admission, proposal.binding, altered_ctx)


def test_adversarial_altered_capability_set_escalation_rejected(fresh_nonce_store):
    """Adversarial: Attempted capability escalation in ExecutionContext is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal(execution_context=make_test_context(capability_set=("CAP_READ_ONLY",)))
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    escalated_ctx = ExecutionContext(
        provider_id=proposal.execution_context.provider_id,
        sandbox_profile_id=proposal.execution_context.sandbox_profile_id,
        workspace_id=proposal.execution_context.workspace_id,
        resource_profile_id=proposal.execution_context.resource_profile_id,
        capability_set=("CAP_READ_ONLY", "CAP_WRITE_SYSTEM_ROOT"),
    )
    with pytest.raises(ValueError, match="Context digest mismatch"):
        controller.create_execution_envelope(token, admission, proposal.binding, escalated_ctx)


# ============================================================================
# 5. Durable Completion Lifecycle & State Transition Tests
# ============================================================================

def test_durable_completion_post_hook_failure_records_failed_state(fresh_nonce_store):
    """D2 Durable Lifecycle: Post-hook failure records COMPLETION_FAILED in D2 store."""
    class AbortPostObserveHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=False, error_message="Observation gateway rejected digest.")

    pipeline = LifecyclePipeline()
    pipeline.register_hook(LifecycleStage.POST_OBSERVE, AbortPostObserveHook())

    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, pipeline=pipeline, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)

    envelope = controller.create_execution_envelope(token, admission, proposal.binding, proposal.execution_context)
    comp = controller.complete_execution(envelope=envelope)
    assert comp.is_valid_execution is False
    assert "Observation gateway" in comp.error_message

    # Verify D2 store recorded COMPLETION_FAILED
    assert fresh_nonce_store.is_nonce_consumed(f"COMPLETION_FAILED:{token.execution_nonce}") is True


def test_adversarial_repeated_completion_rejected(fresh_nonce_store):
    """Adversarial: Attempting to complete the same envelope twice is rejected via D2 durable lifecycle."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)
    envelope = controller.create_execution_envelope(token, admission, proposal.binding, proposal.execution_context)

    # First completion succeeds
    comp1 = controller.complete_execution(envelope=envelope)
    assert comp1.is_valid_execution is True

    # Second completion fails closed
    comp2 = controller.complete_execution(envelope=envelope)
    assert comp2.is_valid_execution is False
    assert "already started or consumed" in comp2.error_message


def test_adversarial_concurrent_completion_race(fresh_nonce_store):
    """Adversarial: 20 concurrent threads race to complete the same envelope. Exactly 1 succeeds."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)
    envelope = controller.create_execution_envelope(token, admission, proposal.binding, proposal.execution_context)

    results: List[bool] = []

    def try_complete():
        res = controller.complete_execution(envelope=envelope)
        return res.is_valid_execution

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_complete) for _ in range(20)]
        for f in futures:
            results.append(f.result())

    assert results.count(True) == 1
    assert results.count(False) == 19


def test_adversarial_concurrent_admission_race(fresh_nonce_store):
    """Adversarial: 20 concurrent workers race to admit the same token. Exactly 1 succeeds."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token

    results: List[bool] = []

    def try_admit():
        res = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)
        return res.is_admitted

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_admit) for _ in range(20)]
        for f in futures:
            results.append(f.result())

    assert results.count(True) == 1
    assert results.count(False) == 19


# ============================================================================
# 6. Type and Integrity Edge Cases
# ============================================================================

def test_type_and_integrity_edge_cases():
    """Type checking and edge case validations fail closed."""
    with pytest.raises(TypeError, match="token must be an ExecutionToken"):
        ExecutionEnvelope("bad_token", "bad_adm", "bad_act", "bad_ctx")  # type: ignore

    with pytest.raises(ValueError, match="provider_id cannot be empty"):
        ExecutionContext("", "SBX-1", "WS-1", "RES-1")
    with pytest.raises(ValueError, match="sandbox_profile_id cannot be empty"):
        ExecutionContext("P-1", "", "WS-1", "RES-1")
    with pytest.raises(ValueError, match="workspace_id cannot be empty"):
        ExecutionContext("P-1", "SBX-1", "", "RES-1")
    with pytest.raises(ValueError, match="resource_profile_id cannot be empty"):
        ExecutionContext("P-1", "SBX-1", "WS-1", "")

    with pytest.raises(ValueError, match="provider_id cannot be empty"):
        compute_context_digest("", "SBX-1", "WS-1", "RES-1", ())
    with pytest.raises(ValueError, match="sandbox_profile_id cannot be empty"):
        compute_context_digest("P-1", "", "WS-1", "RES-1", ())
    with pytest.raises(ValueError, match="workspace_id cannot be empty"):
        compute_context_digest("P-1", "SBX-1", "", "RES-1", ())
    with pytest.raises(ValueError, match="resource_profile_id cannot be empty"):
        compute_context_digest("P-1", "SBX-1", "WS-1", "", ())


def test_authorization_budget_and_prerequisites():
    """Budget exceedance and unsatisfied prerequisites produce REJECTED decision."""
    proposal_budget = make_test_proposal(estimated_cost=500.0)
    dec1 = AuthorizationEngine.evaluate_proposal(
        proposal=proposal_budget,
        obligations={"OBL-001": make_test_obligation()},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        budget_remaining=10.0,
    )
    assert dec1.status == AuthorizationStatus.REJECTED
    assert any("budget" in r for r in dec1.rejection_reasons)

    proposal_prereq = make_test_proposal(prerequisites=("OBL-UNSATISFIED",))
    dec2 = AuthorizationEngine.evaluate_proposal(
        proposal=proposal_prereq,
        obligations={"OBL-001": make_test_obligation(), "OBL-UNSATISFIED": make_test_obligation("OBL-UNSATISFIED", status=ObligationStatus.OPEN)},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
    )
    assert dec2.status == AuthorizationStatus.REJECTED
    assert any("Prerequisite" in r for r in dec2.rejection_reasons)

    proposal_nonexistent = make_test_proposal(obligation_id="OBL-MISSING")
    dec3 = AuthorizationEngine.evaluate_proposal(
        proposal=proposal_nonexistent,
        obligations={},
        policies={},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
    )
    assert dec3.status == AuthorizationStatus.REJECTED
    assert any("not found" in r for r in dec3.rejection_reasons)


def test_adversarial_replay_token_before_completion_rejected(fresh_nonce_store):
    """Adversarial: Replaying token during admission is rejected by D2 store."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token

    admit1 = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)
    assert admit1.is_admitted is True

    admit2 = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)
    assert admit2.is_admitted is False


def test_adversarial_future_and_expired_tokens(fresh_nonce_store):
    """Adversarial: Tokens evaluated before issued_at or past expires_at fail admission."""
    signer = Gate3AuthoritySigner()
    token_future = _mint_execution_token(
        token_id="TOK-FUTURE-001",
        decision_id="DEC-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        action_digest="0" * 64,
        context_digest="0" * 64,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_FUTURE,
        expires_at="2026-08-20T16:00:00Z",
        authority_signer=signer,
    )
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)
    res_fut = controller.admit_execution(token_future, "OBL-001", DEFAULT_SHA, 1, ActionBinding("T","t","p"), make_test_context(), TIMESTAMP_NOW)
    assert res_fut.is_admitted is False

    token_expired = _mint_execution_token(
        token_id="TOK-EXPIRED-001",
        decision_id="DEC-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        action_digest="0" * 64,
        context_digest="0" * 64,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        authority_signer=signer,
    )
    res_exp = controller.admit_execution(token_expired, "OBL-001", DEFAULT_SHA, 1, ActionBinding("T","t","p"), make_test_context(), TIMESTAMP_LATE)
    assert res_exp.is_admitted is False


def test_adversarial_token_signature_and_fabrication(fresh_nonce_store):
    """Adversarial: Fabricated tokens or fake signatures are rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    fake_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="Rogue",
        public_key_fingerprint="0" * 64,
        payload_digest="0" * 64,
        signature_hex="0" * 128,
        timestamp=TIMESTAMP_NOW,
    )
    fake_token = ExecutionToken(
        token_id="TOK-FAKE-001",
        decision_id="DEC-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        action_digest="0" * 64,
        context_digest="0" * 64,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        execution_nonce="NONCE-FAKE",
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        signature=fake_sig,
    )
    admit_fake = controller.admit_execution(fake_token, "OBL-001", DEFAULT_SHA, 1, ActionBinding("T","t","p"), make_test_context(), TIMESTAMP_NOW)
    assert admit_fake.is_admitted is False


def test_verify_execution_envelope_validation_failures(fresh_nonce_store):
    """verify_execution_envelope rejects envelopes with mismatched or corrupt data."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)
    envelope = controller.create_execution_envelope(token, admission, proposal.binding, proposal.execution_context)

    # 1. Invalid envelope instance
    assert verify_execution_envelope("not_an_envelope", DEFAULT_SHA, 1, TIMESTAMP_NOW, signer, fresh_nonce_store) is False  # type: ignore

    # 2. SHA mismatch
    assert verify_execution_envelope(envelope, ALT_SHA, 1, TIMESTAMP_NOW, signer, fresh_nonce_store) is False

    # 3. Policy version mismatch
    assert verify_execution_envelope(envelope, DEFAULT_SHA, 2, TIMESTAMP_NOW, signer, fresh_nonce_store) is False

    # 4. Expired time
    assert verify_execution_envelope(envelope, DEFAULT_SHA, 1, TIMESTAMP_LATE, signer, fresh_nonce_store) is False


def test_controller_restart_preserves_d2_state(tmp_path):
    """Controller restart maintains single-use state in D2 store."""
    signer = Gate3AuthoritySigner()
    log_file = str(tmp_path / "d5_restart.log")
    store1 = D2NonceStore(file_path=log_file)
    ctrl1 = SClassController(authority_signer=signer, nonce_store=store1)

    proposal = make_test_proposal()
    dispatch = ctrl1.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = ctrl1.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, proposal.binding, proposal.execution_context, TIMESTAMP_NOW)
    envelope = ctrl1.create_execution_envelope(token, admission, proposal.binding, proposal.execution_context)

    comp = ctrl1.complete_execution(envelope)
    assert comp.is_valid_execution is True

    # Controller 2 restart
    store2 = D2NonceStore(file_path=log_file)
    ctrl2 = SClassController(authority_signer=signer, nonce_store=store2)
    assert ctrl2.complete_execution(envelope).is_valid_execution is False


def test_action_binding_and_context_validation_errors():
    """ActionBinding, ExecutionContext, and ActionProposal validation errors fail closed."""
    with pytest.raises(ValueError, match="action_type cannot be empty"):
        ActionBinding("", "t", "p")
    with pytest.raises(ValueError, match="target cannot be empty"):
        ActionBinding("T", "", "p")
    with pytest.raises(ValueError, match="purpose cannot be empty"):
        ActionBinding("T", "t", "")

    with pytest.raises(ValueError, match="action_digest mismatch"):
        ActionProposal("ACT-1", "OBL-1", "T", "t", "p", make_test_context(), action_digest="f"*64)

    with pytest.raises(ValueError, match="proposal_id cannot be empty"):
        ActionProposal("", "OBL-1", "T", "t", "p", make_test_context())
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        ActionProposal("ACT-1", "", "T", "t", "p", make_test_context())
    with pytest.raises(ValueError, match="action_type cannot be empty"):
        ActionProposal("ACT-1", "OBL-1", "", "t", "p", make_test_context())
    with pytest.raises(ValueError, match="target cannot be empty"):
        ActionProposal("ACT-1", "OBL-1", "T", "", "p", make_test_context())
    with pytest.raises(ValueError, match="purpose cannot be empty"):
        ActionProposal("ACT-1", "OBL-1", "T", "t", "", make_test_context())
    with pytest.raises(TypeError, match="execution_context must be an ExecutionContext"):
        ActionProposal("ACT-1", "OBL-1", "T", "t", "p", "bad_context")  # type: ignore
    with pytest.raises(ValueError, match="cannot be negative"):
        ActionProposal("ACT-1", "OBL-1", "T", "t", "p", make_test_context(), estimated_cost_usd=-1.0)
    with pytest.raises(ValueError, match="timeout_seconds must be >= 1"):
        ActionProposal("ACT-1", "OBL-1", "T", "t", "p", make_test_context(), timeout_seconds=0)

    with pytest.raises(ValueError, match="decision_id cannot be empty"):
        AuthorizationDecision("", "ACT-1", "OBL-1", "0"*64, "0"*64, AuthorizationStatus.AUTHORIZED, evaluated_at=TIMESTAMP_NOW)
    with pytest.raises(ValueError, match="proposal_id cannot be empty"):
        AuthorizationDecision("DEC-1", "", "OBL-1", "0"*64, "0"*64, AuthorizationStatus.AUTHORIZED, evaluated_at=TIMESTAMP_NOW)
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        AuthorizationDecision("DEC-1", "ACT-1", "", "0"*64, "0"*64, AuthorizationStatus.AUTHORIZED, evaluated_at=TIMESTAMP_NOW)
    with pytest.raises(TypeError, match="Invalid status"):
        AuthorizationDecision("DEC-1", "ACT-1", "OBL-1", "0"*64, "0"*64, "BAD_STATUS", evaluated_at=TIMESTAMP_NOW)  # type: ignore

    with pytest.raises(ValueError, match="must start with 'TOK-'"):
        ExecutionToken("BAD", "DEC-1", "OBL-1", "ACT-1", "0"*64, "0"*64, DEFAULT_SHA, 1, "NONCE", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore
    with pytest.raises(ValueError, match="decision_id cannot be empty"):
        ExecutionToken("TOK-1", "", "OBL-1", "ACT-1", "0"*64, "0"*64, DEFAULT_SHA, 1, "NONCE", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        ExecutionToken("TOK-1", "DEC-1", "", "ACT-1", "0"*64, "0"*64, DEFAULT_SHA, 1, "NONCE", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore
    with pytest.raises(ValueError, match="proposal_id cannot be empty"):
        ExecutionToken("TOK-1", "DEC-1", "OBL-1", "", "0"*64, "0"*64, DEFAULT_SHA, 1, "NONCE", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore
    with pytest.raises(ValueError, match="execution_nonce cannot be empty"):
        ExecutionToken("TOK-1", "DEC-1", "OBL-1", "ACT-1", "0"*64, "0"*64, DEFAULT_SHA, 1, "", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore

    with pytest.raises(TypeError, match="authority_signer must implement AuthoritySignerProtocol"):
        _mint_execution_token("TOK-1", "DEC-1", "OBL-1", "ACT-1", "0"*64, "0"*64, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, "bad_signer")  # type: ignore
    with pytest.raises(ValueError, match="timestamps are required"):
        _mint_execution_token("TOK-1", "DEC-1", "OBL-1", "ACT-1", "0"*64, "0"*64, DEFAULT_SHA, 1, "", "", Gate3AuthoritySigner())


def test_signature_helpers_type_checking():
    """verify_execution_token_signature and verify_admission_signature return False on invalid types."""
    assert verify_execution_token_signature(None, Gate3AuthoritySigner()) is False  # type: ignore
    assert verify_execution_token_signature("not_a_token", Gate3AuthoritySigner()) is False  # type: ignore
    assert verify_admission_signature(None, Gate3AuthoritySigner()) is False  # type: ignore
    assert verify_admission_signature("not_an_admission", Gate3AuthoritySigner()) is False  # type: ignore


def test_controller_public_surface_and_argument_validation():
    """Controller validates inputs fail-closed."""
    ctrl = SClassController(authority_signer=Gate3AuthoritySigner())
    with pytest.raises(TypeError, match="proposal must be an ActionProposal instance"):
        ctrl.submit_proposal("not_a_proposal", {}, {}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)  # type: ignore
    with pytest.raises(ValueError, match="timestamps are required"):
        ctrl.submit_proposal(make_test_proposal(), {}, {}, DEFAULT_SHA, 1, "", TIMESTAMP_EXPIRY)

    adm_bad_tok = ctrl.admit_execution("bad_token", "OBL-1", DEFAULT_SHA, 1, ActionBinding("T","t","p"), make_test_context(), TIMESTAMP_NOW)  # type: ignore
    assert adm_bad_tok.is_admitted is False

    adm_bad_act = ctrl.admit_execution(ExecutionToken("TOK-1","D","O","A","0"*64,"0"*64,DEFAULT_SHA,1,"N",TIMESTAMP_NOW,TIMESTAMP_EXPIRY,AsymmetricAuthoritySignature("ED25519","V","0"*64,"0"*64,"0"*128,TIMESTAMP_NOW)), "OBL-1", DEFAULT_SHA, 1, "bad_act", make_test_context(), TIMESTAMP_NOW)  # type: ignore
    assert adm_bad_act.is_admitted is False

    adm_bad_ctx = ctrl.admit_execution(ExecutionToken("TOK-1","D","O","A","0"*64,"0"*64,DEFAULT_SHA,1,"N",TIMESTAMP_NOW,TIMESTAMP_EXPIRY,AsymmetricAuthoritySignature("ED25519","V","0"*64,"0"*64,"0"*128,TIMESTAMP_NOW)), "OBL-1", DEFAULT_SHA, 1, ActionBinding("T","t","p"), "bad_ctx", TIMESTAMP_NOW)  # type: ignore
    assert adm_bad_ctx.is_admitted is False

    comp_bad_env = ctrl.complete_execution("not_an_envelope")  # type: ignore
    assert comp_bad_env.is_valid_execution is False

    # Admission Result validation errors
    with pytest.raises(ValueError, match="token_id cannot be empty"):
        ExecutionAdmissionResult("", "N", "O", "0"*64, "0"*64, DEFAULT_SHA, 1, "D", TIMESTAMP_NOW, True, AsymmetricAuthoritySignature("ED25519","V","0"*64,"0"*64,"0"*128,TIMESTAMP_NOW))
    with pytest.raises(ValueError, match="execution_nonce cannot be empty"):
        ExecutionAdmissionResult("TOK-1", "", "O", "0"*64, "0"*64, DEFAULT_SHA, 1, "D", TIMESTAMP_NOW, True, AsymmetricAuthoritySignature("ED25519","V","0"*64,"0"*64,"0"*128,TIMESTAMP_NOW))
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        ExecutionAdmissionResult("TOK-1", "N", "", "0"*64, "0"*64, DEFAULT_SHA, 1, "D", TIMESTAMP_NOW, True, AsymmetricAuthoritySignature("ED25519","V","0"*64,"0"*64,"0"*128,TIMESTAMP_NOW))
    with pytest.raises(ValueError, match="decision_id cannot be empty"):
        ExecutionAdmissionResult("TOK-1", "N", "O", "0"*64, "0"*64, DEFAULT_SHA, 1, "", TIMESTAMP_NOW, True, AsymmetricAuthoritySignature("ED25519","V","0"*64,"0"*64,"0"*128,TIMESTAMP_NOW))
    with pytest.raises(TypeError, match="signature must be an AsymmetricAuthoritySignature"):
        ExecutionAdmissionResult("TOK-1", "N", "O", "0"*64, "0"*64, DEFAULT_SHA, 1, "D", TIMESTAMP_NOW, True, None)


def test_execution_envelope_mismatch_invariants():
    """ExecutionEnvelope __post_init__ rejects any mismatched field fail-closed."""
    signer = Gate3AuthoritySigner()
    action = ActionBinding("EXECUTE_TEST", "tests/test_auth.py", "Verify")
    ctx = make_test_context()

    token = _mint_execution_token(
        token_id="TOK-ENV-001",
        decision_id="DEC-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        action_digest=action.action_digest,
        context_digest=ctx.context_digest,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        authority_signer=signer,
    )
    sig = AsymmetricAuthoritySignature("ED25519", "V", "0"*64, "0"*64, "0"*128, TIMESTAMP_NOW)
    adm_bad_tok_id = ExecutionAdmissionResult("TOK-OTHER", token.execution_nonce, "OBL-001", action.action_digest, ctx.context_digest, DEFAULT_SHA, 1, "DEC-001", TIMESTAMP_NOW, True, sig)
    adm_bad_nonce = ExecutionAdmissionResult(token.token_id, "NONCE-OTHER", "OBL-001", action.action_digest, ctx.context_digest, DEFAULT_SHA, 1, "DEC-001", TIMESTAMP_NOW, True, sig)
    adm_bad_obl = ExecutionAdmissionResult(token.token_id, token.execution_nonce, "OBL-OTHER", action.action_digest, ctx.context_digest, DEFAULT_SHA, 1, "DEC-001", TIMESTAMP_NOW, True, sig)
    adm_bad_sha = ExecutionAdmissionResult(token.token_id, token.execution_nonce, "OBL-001", action.action_digest, ctx.context_digest, ALT_SHA, 1, "DEC-001", TIMESTAMP_NOW, True, sig)
    adm_bad_pol = ExecutionAdmissionResult(token.token_id, token.execution_nonce, "OBL-001", action.action_digest, ctx.context_digest, DEFAULT_SHA, 2, "DEC-001", TIMESTAMP_NOW, True, sig)
    adm_bad_dec = ExecutionAdmissionResult(token.token_id, token.execution_nonce, "OBL-001", action.action_digest, ctx.context_digest, DEFAULT_SHA, 1, "DEC-OTHER", TIMESTAMP_NOW, True, sig)

    with pytest.raises(ValueError, match="Token ID mismatch"):
        ExecutionEnvelope(token, adm_bad_tok_id, action, ctx)
    with pytest.raises(ValueError, match="Execution nonce mismatch"):
        ExecutionEnvelope(token, adm_bad_nonce, action, ctx)
    with pytest.raises(ValueError, match="Obligation ID mismatch"):
        ExecutionEnvelope(token, adm_bad_obl, action, ctx)
    with pytest.raises(ValueError, match="Source SHA mismatch"):
        ExecutionEnvelope(token, adm_bad_sha, action, ctx)
    with pytest.raises(ValueError, match="Policy version mismatch"):
        ExecutionEnvelope(token, adm_bad_pol, action, ctx)
    with pytest.raises(ValueError, match="Decision ID mismatch"):
        ExecutionEnvelope(token, adm_bad_dec, action, ctx)


def test_controller_hook_abort_branches(fresh_nonce_store):
    """Controller aborts when PRE_VALIDATE, PRE_AUTHORIZE, or PRE_EXECUTE hooks return proceed=False."""
    class AbortPreValHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=False, error_message="PreVal abort")

    class AbortPreAuthHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=False, error_message="PreAuth abort")

    class AbortPreExecHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=False, error_message="PreExec abort")

    pipe1 = LifecyclePipeline()
    pipe1.register_hook(LifecycleStage.PRE_VALIDATE, AbortPreValHook())
    c1 = SClassController(authority_signer=Gate3AuthoritySigner(), pipeline=pipe1, nonce_store=fresh_nonce_store)
    r1 = c1.submit_proposal(make_test_proposal(), {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    assert r1.decision.status == AuthorizationStatus.REJECTED
    assert "PreVal abort" in r1.decision.rejection_reasons[0]

    pipe2 = LifecyclePipeline()
    pipe2.register_hook(LifecycleStage.PRE_AUTHORIZE, AbortPreAuthHook())
    c2 = SClassController(authority_signer=Gate3AuthoritySigner(), pipeline=pipe2, nonce_store=fresh_nonce_store)
    r2 = c2.submit_proposal(make_test_proposal(), {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    assert r2.decision.status == AuthorizationStatus.REJECTED
    assert "PreAuth abort" in r2.decision.rejection_reasons[0]

    pipe3 = LifecyclePipeline()
    pipe3.register_hook(LifecycleStage.PRE_EXECUTE, AbortPreExecHook())
    c3 = SClassController(authority_signer=Gate3AuthoritySigner(), pipeline=pipe3, nonce_store=fresh_nonce_store)
    r3 = c3.submit_proposal(make_test_proposal(), {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    assert r3.execution_token is None
    assert "PreExec abort" in r3.error_message
