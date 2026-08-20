"""
S-Class EOS V11.2 - D5 Controller Test Suite.
Exhaustive verification of:
1. Ready / Blocked / Executable Frontier Calculus (READY != EXECUTABLE distinction, CORE-22).
2. Topological dependency ordering & cycle rejection (CORE-23).
3. Precondition evaluation & immutable AuthorizationDecision creation (CORE-05).
4. Real D3 Policy evaluation integration during PRE_AUTHORIZE.
5. Exact Action Binding & action_digest Domain Separator SCLASS_ACTION_BINDING_V1:.
6. Ed25519-signed single-use ExecutionToken with domain separator SCLASS_EXECUTION_TOKEN_V1:.
7. ExecutionToken admission/consumption strictly BEFORE D6 execution.
8. Immutable, Authority-signed ExecutionAdmissionResult bound to:
   token_id, execution_nonce, obligation_id, action_digest, source_sha, policy_version, decision_id, admitted_at.
9. Explicit D2 Durable Completion Lifecycle:
   COMPLETION_STARTED -> POST_EXECUTE -> POST_OBSERVE -> COMPLETION_FINALIZED (or COMPLETION_FAILED).
10. Full Adversarial Red-Team Suite:
    - Same proposal + altered target -> REJECT
    - Same proposal + altered action_type -> REJECT
    - Same proposal + altered parameters -> REJECT
    - Same proposal + altered purpose -> REJECT
    - Altered action_digest -> REJECT
    - Valid exact action -> ACCEPT
    - Post-hook failure records COMPLETION_FAILED in D2 store
    - Valid admission + same token -> ACCEPT
    - Admission A + token B -> REJECT
    - Token mutated after admission -> REJECT
    - Obligation mismatch -> REJECT
    - Source SHA mismatch -> REJECT
    - Policy version mismatch -> REJECT
    - Fabricated admission -> REJECT
    - Repeated completion -> REJECT
    - Controller restart -> no false authorization (D2 durable authority)
    - Concurrent completion -> exactly one valid path
    - Replay token before completion -> REJECT
    - Concurrent execution admission -> exactly one succeeds
    - Future-issued token -> REJECT
    - Expired token -> REJECT
    - Arbitrary caller attempts token mint -> REJECT (no public mint function)
    - Policy denial -> no token
    - Policy mutation after authorization -> existing immutable decision remains bound
    - Planner direct execution -> REJECT
    - READY but non-EXECUTABLE obligation -> proposal REJECTED
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
    ExecutionToken,
    ExecutionAdmissionResult,
    compute_action_digest,
    _mint_execution_token,
    verify_and_consume_execution_token,
    verify_execution_token_signature,
    verify_admission_signature,
    SCLASS_ACTION_BINDING_DOMAIN_SEPARATOR,
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


def test_authorization_rejected_budget_exceeded():
    """Estimated cost exceeding remaining budget -> REJECTED."""
    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal(estimated_cost=25.0)

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        budget_remaining=10.0,
    )
    assert decision.status == AuthorizationStatus.REJECTED
    assert any("budget" in r for r in decision.rejection_reasons)


def test_authorization_rejected_unsatisfied_prerequisites():
    """Proposal with unsatisfied prerequisites -> REJECTED."""
    obls = {
        "OBL-001": make_test_obligation(obligation_id="OBL-001"),
        "OBL-PREREQ": make_test_obligation(obligation_id="OBL-PREREQ", status=ObligationStatus.OPEN),
    }
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal(prerequisites=("OBL-PREREQ",))

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
    )
    assert decision.status == AuthorizationStatus.REJECTED
    assert any("Prerequisite obligation" in r for r in decision.rejection_reasons)


def test_authorization_rejected_nonexistent_obligation():
    """Proposal targeting nonexistent obligation ID -> REJECTED."""
    proposal = make_test_proposal(obligation_id="OBL-NONEXISTENT")
    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations={},
        policies={},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
    )
    assert decision.status == AuthorizationStatus.REJECTED
    assert any("not found" in r for r in decision.rejection_reasons)


# ============================================================================
# 3. Action Binding & Exact Action Adversarial Tests
# ============================================================================

def test_action_binding_valid_exact_action_accepted(fresh_nonce_store):
    """Valid exact action binding matches token and completes execution successfully."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal(
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify authentication",
        parameters={"flags": ["-v", "--tb=short"]},
    )

    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    token = dispatch.execution_token
    assert token is not None

    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission.is_admitted is True

    # Complete execution with identical action binding
    exact_binding = proposal.binding
    comp = controller.complete_execution(
        token=token,
        admission=admission,
        action_binding=exact_binding,
        execution_result={"status": "PASS"},
    )
    assert comp.is_valid_execution is True


def test_adversarial_altered_target_rejected(fresh_nonce_store):
    """Adversarial: Same proposal with altered target is rejected during completion."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal(action_type="EXECUTE_TEST", target="tests/test_auth.py", purpose="Verify auth")
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": make_test_obligation()},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)

    # Altered target in ActionBinding
    altered_binding = ActionBinding(
        action_type="EXECUTE_TEST",
        target="tests/test_unauthorized_target.py",
        purpose="Verify auth",
    )
    comp = controller.complete_execution(token=token, admission=admission, action_binding=altered_binding)
    assert comp.is_valid_execution is False
    assert "digest does not match" in comp.error_message


def test_adversarial_altered_action_type_rejected(fresh_nonce_store):
    """Adversarial: Same proposal with altered action_type is rejected during completion."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal(action_type="EXECUTE_TEST", target="tests/test_auth.py", purpose="Verify auth")
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": make_test_obligation()},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)

    # Altered action_type
    altered_binding = ActionBinding(
        action_type="STATIC_ANALYSIS",
        target="tests/test_auth.py",
        purpose="Verify auth",
    )
    comp = controller.complete_execution(token=token, admission=admission, action_binding=altered_binding)
    assert comp.is_valid_execution is False
    assert "digest does not match" in comp.error_message


def test_adversarial_altered_parameters_rejected(fresh_nonce_store):
    """Adversarial: Same proposal with altered parameters is rejected during completion."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal(parameters={"mode": "safe"})
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": make_test_obligation()},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)

    # Altered parameters in ActionBinding
    altered_binding = ActionBinding(
        action_type=proposal.action_type,
        target=proposal.target,
        purpose=proposal.purpose,
        parameters={"mode": "unsafe_root"},
    )
    comp = controller.complete_execution(token=token, admission=admission, action_binding=altered_binding)
    assert comp.is_valid_execution is False
    assert "digest does not match" in comp.error_message


def test_adversarial_altered_purpose_rejected(fresh_nonce_store):
    """Adversarial: Same proposal with altered purpose string is rejected during completion."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal(purpose="Original Purpose")
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": make_test_obligation()},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)

    altered_binding = ActionBinding(
        action_type=proposal.action_type,
        target=proposal.target,
        purpose="Altered Malicious Purpose",
        parameters=proposal.parameters,
    )
    comp = controller.complete_execution(token=token, admission=admission, action_binding=altered_binding)
    assert comp.is_valid_execution is False
    assert "digest does not match" in comp.error_message


def test_adversarial_altered_action_digest_rejected(fresh_nonce_store):
    """Adversarial: Forging action_digest in ActionProposal raises ValueError or fails closed."""
    with pytest.raises(ValueError, match="action_digest mismatch"):
        ActionProposal(
            proposal_id="ACT-BAD-DIGEST",
            obligation_id="OBL-001",
            action_type="EXECUTE_TEST",
            target="tests/test_auth.py",
            purpose="Verify auth",
            action_digest="f" * 64,  # Fake digest
        )


# ============================================================================
# 4. Explicit D2 Durable Completion Lifecycle Tests
# ============================================================================

def test_durable_completion_post_hook_failure_records_failed_state(fresh_nonce_store):
    """D2 Durable Lifecycle: A post-hook failure records COMPLETION_FAILED and halts completion."""
    class AbortPostObserveHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=False, error_message="Observation gateway rejected digest.")

    pipeline = LifecyclePipeline()
    pipeline.register_hook(LifecycleStage.POST_OBSERVE, AbortPostObserveHook())

    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, pipeline=pipeline, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": make_test_obligation()},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission.is_admitted is True

    comp = controller.complete_execution(token=token, admission=admission)
    assert comp.is_valid_execution is False
    assert "Observation gateway" in comp.error_message

    # Verify D2 store recorded COMPLETION_FAILED
    assert fresh_nonce_store.is_nonce_consumed(f"COMPLETION_FAILED:{token.execution_nonce}") is True


def test_adversarial_repeated_completion_rejected(fresh_nonce_store):
    """Adversarial: Attempting to complete the same admission twice is rejected via D2 durable lifecycle."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": make_test_obligation()},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission.is_admitted is True

    # First completion succeeds
    comp1 = controller.complete_execution(token=token, admission=admission)
    assert comp1.is_valid_execution is True

    # Second completion of same token fails closed (COMPLETION_STARTED already reserved in D2)
    comp2 = controller.complete_execution(token=token, admission=admission)
    assert comp2.is_valid_execution is False
    assert "already started or consumed" in comp2.error_message


def test_adversarial_controller_restart_preserves_durable_authority(tmp_path):
    """Adversarial: Controller restart maintains single-use state via D2 durable store."""
    signer = Gate3AuthoritySigner()
    log_file = str(tmp_path / "persistent_d5_nonces.log")

    store1 = D2NonceStore(file_path=log_file)
    ctrl1 = SClassController(authority_signer=signer, nonce_store=store1)

    proposal = make_test_proposal()
    dispatch = ctrl1.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": make_test_obligation()},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    token = dispatch.execution_token
    admission = ctrl1.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission.is_admitted is True

    comp = ctrl1.complete_execution(token, admission)
    assert comp.is_valid_execution is True

    # Simulated Controller Restart
    store2 = D2NonceStore(file_path=log_file)
    ctrl2 = SClassController(authority_signer=signer, nonce_store=store2)

    # Re-admission fails closed
    re_admit = ctrl2.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert re_admit.is_admitted is False

    # Re-completion fails closed
    re_comp = ctrl2.complete_execution(token, admission)
    assert re_comp.is_valid_execution is False


def test_adversarial_concurrent_completion_race(fresh_nonce_store):
    """Adversarial: 20 concurrent threads attempt to complete the same admission.
    Exactly ONE succeeds; 19 fail closed.
    """
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": make_test_obligation()},
        policies={"POL-001": make_test_policy()},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission.is_admitted is True

    results: List[bool] = []

    def try_complete():
        res = controller.complete_execution(token, admission)
        return res.is_valid_execution

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_complete) for _ in range(20)]
        for f in futures:
            results.append(f.result())

    assert results.count(True) == 1
    assert results.count(False) == 19


# ============================================================================
# 5. Admission Mismatch & Attack Vector Tests
# ============================================================================

def test_adversarial_admission_a_with_token_b_rejected(fresh_nonce_store):
    """Adversarial: Valid admission for Token A paired with Token B during completion is REJECTED."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal_a = make_test_proposal(proposal_id="ACT-001")
    proposal_b = make_test_proposal(proposal_id="ACT-002")

    obls = {"OBL-001": make_test_obligation()}
    pols = {"POL-001": make_test_policy()}

    dispatch_a = controller.submit_proposal(proposal_a, obls, pols, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    dispatch_b = controller.submit_proposal(proposal_b, obls, pols, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)

    token_a = dispatch_a.execution_token
    token_b = dispatch_b.execution_token

    admission_a = controller.admit_execution(token_a, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission_a.is_admitted is True

    comp = controller.complete_execution(token=token_b, admission=admission_a)
    assert comp.is_valid_execution is False
    assert "mismatch" in comp.error_message


def test_adversarial_token_mutated_after_admission_rejected(fresh_nonce_store):
    """Adversarial: Tampering with token fields after admission causes completion rejection."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission.is_admitted is True

    tampered_token = ExecutionToken(
        token_id=token.token_id,
        decision_id=token.decision_id,
        obligation_id=token.obligation_id,
        proposal_id=token.proposal_id,
        action_digest=token.action_digest,
        source_sha=ALT_SHA,
        policy_version=token.policy_version,
        execution_nonce=token.execution_nonce,
        issued_at=token.issued_at,
        expires_at=token.expires_at,
        signature=token.signature,
    )
    comp = controller.complete_execution(token=tampered_token, admission=admission)
    assert comp.is_valid_execution is False


def test_adversarial_obligation_mismatch_rejected(fresh_nonce_store):
    """Adversarial: Admission obligation_id differing from token obligation_id is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)

    mismatched_admission = ExecutionAdmissionResult(
        token_id=token.token_id,
        execution_nonce=token.execution_nonce,
        obligation_id="OBL-OTHER-999",
        action_digest=token.action_digest,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        decision_id=token.decision_id,
        admitted_at=TIMESTAMP_NOW,
        is_admitted=True,
        signature=admission.signature,
    )
    comp = controller.complete_execution(token=token, admission=mismatched_admission)
    assert comp.is_valid_execution is False
    assert "obligation_id mismatch" in comp.error_message


def test_adversarial_source_sha_mismatch_rejected(fresh_nonce_store):
    """Adversarial: Admission source_sha differing from token source_sha is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)

    mismatched_admission = ExecutionAdmissionResult(
        token_id=token.token_id,
        execution_nonce=token.execution_nonce,
        obligation_id=token.obligation_id,
        action_digest=token.action_digest,
        source_sha=ALT_SHA,
        policy_version=token.policy_version,
        decision_id=token.decision_id,
        admitted_at=TIMESTAMP_NOW,
        is_admitted=True,
        signature=admission.signature,
    )
    comp = controller.complete_execution(token=token, admission=mismatched_admission)
    assert comp.is_valid_execution is False
    assert "source_sha mismatch" in comp.error_message


def test_adversarial_policy_version_mismatch_rejected(fresh_nonce_store):
    """Adversarial: Admission policy_version differing from token policy_version is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)

    mismatched_admission = ExecutionAdmissionResult(
        token_id=token.token_id,
        execution_nonce=token.execution_nonce,
        obligation_id=token.obligation_id,
        action_digest=token.action_digest,
        source_sha=token.source_sha,
        policy_version=2,
        decision_id=token.decision_id,
        admitted_at=TIMESTAMP_NOW,
        is_admitted=True,
        signature=admission.signature,
    )
    comp = controller.complete_execution(token=token, admission=mismatched_admission)
    assert comp.is_valid_execution is False
    assert "policy_version mismatch" in comp.error_message


def test_adversarial_fabricated_admission_rejected(fresh_nonce_store):
    """Adversarial: Caller-fabricated admission with fake authority signature fails closed."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token

    fake_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="RogueActor",
        public_key_fingerprint="0" * 64,
        payload_digest="0" * 64,
        signature_hex="0" * 128,
        timestamp=TIMESTAMP_NOW,
    )
    fabricated_admission = ExecutionAdmissionResult(
        token_id=token.token_id,
        execution_nonce=token.execution_nonce,
        obligation_id=token.obligation_id,
        action_digest=token.action_digest,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        decision_id=token.decision_id,
        admitted_at=TIMESTAMP_NOW,
        is_admitted=True,
        signature=fake_sig,
    )
    comp = controller.complete_execution(token=token, admission=fabricated_admission)
    assert comp.is_valid_execution is False
    assert "Admission signature invalid" in comp.error_message


def test_adversarial_replay_token_before_completion_rejected(fresh_nonce_store):
    """Adversarial: Replaying token during admission (before completion) is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token

    admit1 = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admit1.is_admitted is True

    admit2 = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admit2.is_admitted is False


def test_adversarial_concurrent_execution_admission_race(fresh_nonce_store):
    """Adversarial: 20 concurrent workers attempt to admit the same ExecutionToken.
    Exactly ONE succeeds; 19 fail closed.
    """
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    proposal = make_test_proposal()
    dispatch = controller.submit_proposal(proposal, {"OBL-001": make_test_obligation()}, {"POL-001": make_test_policy()}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token

    results: List[bool] = []

    def try_admit():
        res = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
        return res.is_admitted

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_admit) for _ in range(20)]
        for f in futures:
            results.append(f.result())

    assert results.count(True) == 1
    assert results.count(False) == 19


def test_adversarial_future_issued_token_rejected(fresh_nonce_store):
    """Adversarial: Token evaluated before its issued_at timestamp (future-issued) is rejected."""
    signer = Gate3AuthoritySigner()
    token = _mint_execution_token(
        token_id="TOK-FUTURE-001",
        decision_id="DEC-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        action_digest="0" * 64,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_FUTURE,
        expires_at="2026-08-20T16:00:00Z",
        authority_signer=signer,
    )
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission.is_admitted is False


def test_adversarial_expired_token_rejected(fresh_nonce_store):
    """Adversarial: Token evaluated past expires_at timestamp -> rejected."""
    signer = Gate3AuthoritySigner()
    token = _mint_execution_token(
        token_id="TOK-EXPIRED-001",
        decision_id="DEC-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        action_digest="0" * 64,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        authority_signer=signer,
    )
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_LATE)
    assert admission.is_admitted is False


def test_adversarial_arbitrary_caller_cannot_import_public_mint():
    """The controller module does NOT expose mint_execution_token in public __all__."""
    import controller as cpkg
    assert "mint_execution_token" not in cpkg.__all__
    assert not hasattr(cpkg, "mint_execution_token")


def test_adversarial_planner_direct_execution_rejected(fresh_nonce_store):
    """CORE-05: Planner directly attempting execution without Controller token is rejected."""
    controller = SClassController(authority_signer=Gate3AuthoritySigner(), nonce_store=fresh_nonce_store)
    comp = controller.complete_execution(
        token=None,  # type: ignore
        admission=None,  # type: ignore
    )
    assert comp.is_valid_execution is False


def test_adversarial_ready_but_non_executable_rejected(fresh_nonce_store):
    """Target obligation is READY (all prereqs satisfied) but not EXECUTABLE (missing policy / zero budget)."""
    obls = {"OBL-001": make_test_obligation(status=ObligationStatus.OPEN, policy_id="POL-NONEXISTENT")}
    policies = {}
    proposal = make_test_proposal()

    controller = SClassController(authority_signer=Gate3AuthoritySigner(), nonce_store=fresh_nonce_store)
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    assert dispatch.decision.status == AuthorizationStatus.REJECTED
    assert dispatch.execution_token is None
    assert any("not in EXECUTABLE frontier" in r or "not EXECUTABLE" in r for r in dispatch.decision.rejection_reasons)


# ============================================================================
# 6. Type and Validation Edge Cases
# ============================================================================

def test_action_binding_validation_errors():
    """ActionBinding raises ValueError on missing or empty fields."""
    with pytest.raises(ValueError, match="action_type cannot be empty"):
        ActionBinding("", "target", "purpose")
    with pytest.raises(ValueError, match="target cannot be empty"):
        ActionBinding("TEST", "", "purpose")
    with pytest.raises(ValueError, match="purpose cannot be empty"):
        ActionBinding("TEST", "target", "")
    with pytest.raises(ValueError, match="action_type cannot be empty"):
        compute_action_digest("", "target", "purpose")
    with pytest.raises(ValueError, match="target cannot be empty"):
        compute_action_digest("TEST", "", "purpose")
    with pytest.raises(ValueError, match="purpose cannot be empty"):
        compute_action_digest("TEST", "target", "")


def test_execution_admission_result_validation_errors():
    """ExecutionAdmissionResult validation fails closed on invalid fields."""
    with pytest.raises(ValueError, match="token_id cannot be empty"):
        ExecutionAdmissionResult("", "NONCE-1", "OBL-1", "0"*64, DEFAULT_SHA, 1, "DEC-1", TIMESTAMP_NOW, True, None)
    with pytest.raises(ValueError, match="execution_nonce cannot be empty"):
        ExecutionAdmissionResult("TOK-1", "", "OBL-1", "0"*64, DEFAULT_SHA, 1, "DEC-1", TIMESTAMP_NOW, True, None)
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        ExecutionAdmissionResult("TOK-1", "NONCE-1", "", "0"*64, DEFAULT_SHA, 1, "DEC-1", TIMESTAMP_NOW, True, None)
    with pytest.raises(ValueError, match="policy_version must be an integer >= 1"):
        ExecutionAdmissionResult("TOK-1", "NONCE-1", "OBL-1", "0"*64, DEFAULT_SHA, 0, "DEC-1", TIMESTAMP_NOW, True, None)
    with pytest.raises(ValueError, match="decision_id cannot be empty"):
        ExecutionAdmissionResult("TOK-1", "NONCE-1", "OBL-1", "0"*64, DEFAULT_SHA, 1, "", TIMESTAMP_NOW, True, None)
    with pytest.raises(TypeError, match="signature must be an AsymmetricAuthoritySignature"):
        ExecutionAdmissionResult("TOK-1", "NONCE-1", "OBL-1", "0"*64, DEFAULT_SHA, 1, "DEC-1", TIMESTAMP_NOW, True, None)


def test_signature_helpers_type_checking():
    """verify_execution_token_signature and verify_admission_signature return False on invalid types."""
    assert verify_execution_token_signature(None, Gate3AuthoritySigner()) is False  # type: ignore
    assert verify_execution_token_signature("not_a_token", Gate3AuthoritySigner()) is False  # type: ignore
    assert verify_admission_signature(None, Gate3AuthoritySigner()) is False  # type: ignore
    assert verify_admission_signature("not_an_admission", Gate3AuthoritySigner()) is False  # type: ignore


def test_action_proposal_and_decision_validation_errors():
    """ActionProposal and AuthorizationDecision validate arguments fail-closed."""
    with pytest.raises(ValueError, match="proposal_id cannot be empty"):
        ActionProposal("", "OBL-1", "TEST", "target", "purpose")
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        ActionProposal("ACT-1", "", "TEST", "target", "purpose")
    with pytest.raises(ValueError, match="action_type cannot be empty"):
        ActionProposal("ACT-1", "OBL-1", "", "target", "purpose")
    with pytest.raises(ValueError, match="target cannot be empty"):
        ActionProposal("ACT-1", "OBL-1", "TEST", "", "purpose")
    with pytest.raises(ValueError, match="purpose cannot be empty"):
        ActionProposal("ACT-1", "OBL-1", "TEST", "target", "")
    with pytest.raises(ValueError, match="cannot be negative"):
        ActionProposal("ACT-1", "OBL-1", "TEST", "target", "purpose", estimated_cost_usd=-1.0)
    with pytest.raises(ValueError, match="timeout_seconds must be >= 1"):
        ActionProposal("ACT-1", "OBL-1", "TEST", "target", "purpose", timeout_seconds=0)

    with pytest.raises(ValueError, match="decision_id cannot be empty"):
        AuthorizationDecision("", "ACT-1", "OBL-1", "0"*64, AuthorizationStatus.AUTHORIZED, evaluated_at=TIMESTAMP_NOW)
    with pytest.raises(ValueError, match="proposal_id cannot be empty"):
        AuthorizationDecision("DEC-1", "", "OBL-1", "0"*64, AuthorizationStatus.AUTHORIZED, evaluated_at=TIMESTAMP_NOW)
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        AuthorizationDecision("DEC-1", "ACT-1", "", "0"*64, AuthorizationStatus.AUTHORIZED, evaluated_at=TIMESTAMP_NOW)
    with pytest.raises(TypeError, match="Invalid status"):
        AuthorizationDecision("DEC-1", "ACT-1", "OBL-1", "0"*64, "BAD_STATUS", evaluated_at=TIMESTAMP_NOW)  # type: ignore


def test_token_and_controller_type_validation():
    """ExecutionToken dataclass and Controller validate types fail-closed."""
    with pytest.raises(ValueError, match="must start with 'TOK-'"):
        ExecutionToken("BAD-ID", "DEC-1", "OBL-1", "ACT-1", "0"*64, DEFAULT_SHA, 1, "NONCE-1", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore
    with pytest.raises(ValueError, match="decision_id cannot be empty"):
        ExecutionToken("TOK-1", "", "OBL-1", "ACT-1", "0"*64, DEFAULT_SHA, 1, "NONCE-1", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        ExecutionToken("TOK-1", "DEC-1", "", "ACT-1", "0"*64, DEFAULT_SHA, 1, "NONCE-1", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore
    with pytest.raises(ValueError, match="proposal_id cannot be empty"):
        ExecutionToken("TOK-1", "DEC-1", "OBL-1", "", "0"*64, DEFAULT_SHA, 1, "NONCE-1", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore

    with pytest.raises(TypeError, match="authority_signer must implement AuthoritySignerProtocol"):
        _mint_execution_token("TOK-1", "DEC-1", "OBL-1", "ACT-1", "0"*64, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, "bad_signer")  # type: ignore

    with pytest.raises(ValueError, match="timestamps are required"):
        _mint_execution_token("TOK-1", "DEC-1", "OBL-1", "ACT-1", "0"*64, DEFAULT_SHA, 1, "", "", Gate3AuthoritySigner())

    with pytest.raises(TypeError, match="authority_signer must implement AuthoritySignerProtocol"):
        SClassController(authority_signer="bad_signer")  # type: ignore

    ctrl = SClassController(authority_signer=Gate3AuthoritySigner())
    with pytest.raises(TypeError, match="proposal must be an ActionProposal instance"):
        ctrl.submit_proposal("not_a_proposal", {}, {}, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)  # type: ignore
    with pytest.raises(ValueError, match="timestamps are required"):
        ctrl.submit_proposal(make_test_proposal(), {}, {}, DEFAULT_SHA, 1, "", TIMESTAMP_EXPIRY)


def test_hook_pipeline_stage_mismatch_and_exceptions():
    """Hook pipeline rejects context stage mismatch and handles hook exceptions fail-closed."""
    pipeline = LifecyclePipeline()
    ctx = HookContext(stage=LifecycleStage.PRE_VALIDATE, proposal_id="ACT-1", obligation_id="OBL-1", action_type="TEST", target="t", source_sha=DEFAULT_SHA)
    res = pipeline.run_stage(LifecycleStage.PRE_AUTHORIZE, ctx)
    assert res.proceed is False
    assert "stage mismatch" in res.error_message

    class ErrorHook:
        def execute_hook(self, context: HookContext) -> HookResult:
            raise RuntimeError("Unexpected hook failure")

    pipeline.register_hook(LifecycleStage.PRE_VALIDATE, ErrorHook())
    res2 = pipeline.run_stage(LifecycleStage.PRE_VALIDATE, ctx)
    assert res2.proceed is False
    assert "Unexpected hook failure" in res2.error_message
