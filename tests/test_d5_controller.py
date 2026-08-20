"""
S-Class EOS V11.2 - D5 Controller Test Suite.
Exhaustive verification of:
1. Ready / Blocked / Executable Frontier Calculus (READY != EXECUTABLE distinction, CORE-22).
2. Topological dependency ordering & cycle rejection (CORE-23).
3. Precondition evaluation & immutable AuthorizationDecision creation (CORE-05).
4. Real D3 Policy evaluation integration during PRE_AUTHORIZE.
5. Ed25519-signed single-use ExecutionToken with domain separator SCLASS_EXECUTION_TOKEN_V1:.
6. ExecutionToken admission/consumption strictly BEFORE D6 execution.
7. Controller-only token minting (no public mint function).
8. 5-Stage Lifecycle Hooks pipeline (CORE-25 fail-closed invariant).
9. Immutable authorization boundary: PRE_AUTHORIZE decision cannot be overridden by later hooks.
10. Full Adversarial Red-Team Suite:
    - Replay token before completion -> rejected
    - Concurrent execution admission -> exactly one succeeds
    - Future-issued token -> rejected
    - Arbitrary caller attempts token mint -> rejected
    - Policy denial -> no token
    - Policy mutation after authorization -> existing immutable decision remains bound
    - Replayed execution token -> rejected
    - Token from wrong obligation -> rejected
    - Token for wrong repository SHA -> rejected
    - Expired token -> rejected
    - Policy version mismatch -> rejected
    - PRE_AUTHORIZE failure -> no token minted
    - Hook attempts to mint token -> rejected
    - POST_EXECUTE cannot grant authorization retroactively
    - Planner direct execution -> rejected
    - READY but non-EXECUTABLE obligation -> proposal rejected
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
    ExecutionToken,
    _mint_execution_token,
    verify_and_consume_execution_token,
    SCLASS_EXECUTION_TOKEN_DOMAIN_SEPARATOR,
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
    ExecutionAdmissionResult,
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
    estimated_cost: float = 0.05,
    timeout_seconds: int = 30,
    prerequisites: tuple = (),
) -> ActionProposal:
    return ActionProposal(
        proposal_id=proposal_id,
        obligation_id=obligation_id,
        action_type=action_type,
        target=target,
        purpose="Run behavioral property tests",
        estimated_cost_usd=estimated_cost,
        timeout_seconds=timeout_seconds,
        prerequisites=prerequisites,
    )


# ============================================================================
# 1. Deterministic Frontier Calculus Tests (§11.4, CORE-22, CORE-23)
# ============================================================================

def test_frontier_ready_vs_executable_distinction():
    """CORE-22 Invariant: READY != EXECUTABLE.
    An obligation is READY when prerequisites are satisfied, but only EXECUTABLE when policies/resources permit.
    """
    obls = {
        "OBL-1": make_test_obligation(obligation_id="OBL-1", status=ObligationStatus.OPEN, policy_id="POL-1"),
        "OBL-2": make_test_obligation(obligation_id="OBL-2", status=ObligationStatus.OPEN, policy_id="POL-MISSING"),
    }
    policies = {"POL-1": make_test_policy("POL-1")}

    ready = compute_ready_frontier(obls)
    assert set(ready) == {"OBL-1", "OBL-2"}

    # OBL-2 has missing policy -> fails closed, excluded from EXECUTABLE
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

    # Introduce cyclic dependency: A depends on C
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

    # Mutate policies map
    policies.clear()
    # Existing decision remains strictly immutable
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
# 3. 5-Stage Lifecycle Hooks & Admission-Before-Execution Workflow (§8.3, CORE-25)
# ============================================================================

def test_controller_full_workflow_admission_before_execution(fresh_nonce_store):
    """Full workflow: Submit Proposal -> Authorized -> Token Issued -> Admitted/Consumed -> D6 Executed -> Completed."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal()

    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    assert dispatch.decision.status == AuthorizationStatus.AUTHORIZED
    assert dispatch.execution_token is not None

    # Step 1: ADMISSION BEFORE EXECUTION (consumes D2 nonce)
    admission = controller.admit_execution(
        token=dispatch.execution_token,
        expected_obligation_id="OBL-001",
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=TIMESTAMP_NOW,
    )
    assert admission.is_admitted is True
    assert admission.admission_nonce == dispatch.execution_token.execution_nonce

    # Step 2: Replay attempt before completion is REJECTED
    replay_admission = controller.admit_execution(
        token=dispatch.execution_token,
        expected_obligation_id="OBL-001",
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=TIMESTAMP_NOW,
    )
    assert replay_admission.is_admitted is False

    # Step 3: D6 Execution happens in sandbox...

    # Step 4: Completion after execution
    comp = controller.complete_execution(
        token=dispatch.execution_token,
        admission=admission,
        execution_result={"status": "PASS", "raw_output": "All 10 tests passed"},
    )
    assert comp.is_valid_execution is True


def test_complete_execution_without_prior_admission_fails_closed(fresh_nonce_store):
    """Calling complete_execution without valid prior admission fails closed."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    token = _mint_execution_token(
        token_id="TOK-NO-ADMIT-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        authority_signer=signer,
    )
    fake_admission = ExecutionAdmissionResult(token_id="TOK-NO-ADMIT-001", is_admitted=False)
    comp = controller.complete_execution(token=token, admission=fake_admission)
    assert comp.is_valid_execution is False
    assert "not admitted" in comp.error_message


def test_hook_failure_in_pre_validate_halts_workflow(fresh_nonce_store):
    """CORE-25: PRE_VALIDATE hook failure halts pipeline; no authorization or token minted."""
    class AbortValidationHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=False, error_message="Malicious syntax detected.")

    pipeline = LifecyclePipeline()
    pipeline.register_hook(LifecycleStage.PRE_VALIDATE, AbortValidationHook())

    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, pipeline=pipeline, nonce_store=fresh_nonce_store)

    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal()

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
    assert "Malicious syntax" in dispatch.error_message


def test_hook_failure_in_pre_authorize_halts_workflow(fresh_nonce_store):
    """CORE-25: PRE_AUTHORIZE hook failure halts pipeline; token is never minted."""
    class AbortAuthHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=False, error_message="Security profile mismatch.")

    pipeline = LifecyclePipeline()
    pipeline.register_hook(LifecycleStage.PRE_AUTHORIZE, AbortAuthHook())

    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, pipeline=pipeline, nonce_store=fresh_nonce_store)

    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal()

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


def test_hook_failure_in_pre_execute_aborts_token(fresh_nonce_store):
    """CORE-25: PRE_EXECUTE hook failure aborts token minting even if authorized."""
    class AbortPreExecHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=False, error_message="Lock acquisition timed out.")

    pipeline = LifecyclePipeline()
    pipeline.register_hook(LifecycleStage.PRE_EXECUTE, AbortPreExecHook())

    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, pipeline=pipeline, nonce_store=fresh_nonce_store)

    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal()

    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    assert dispatch.decision.status == AuthorizationStatus.AUTHORIZED
    assert dispatch.execution_token is None
    assert "Lock acquisition" in dispatch.error_message


def test_hook_failure_in_post_execute_or_observe(fresh_nonce_store):
    """CORE-25: POST_EXECUTE / POST_OBSERVE failures mark execution invalid."""
    class AbortPostExecHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=False, error_message="Sandbox crash detected.")

    pipeline = LifecyclePipeline()
    pipeline.register_hook(LifecycleStage.POST_EXECUTE, AbortPostExecHook())

    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, pipeline=pipeline, nonce_store=fresh_nonce_store)

    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal()

    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
    )
    assert dispatch.execution_token is not None

    admit = controller.admit_execution(dispatch.execution_token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admit.is_admitted is True

    res = controller.complete_execution(
        token=dispatch.execution_token,
        admission=admit,
    )
    assert res.is_valid_execution is False
    assert "Sandbox crash" in res.error_message


# ============================================================================
# 4. Adversarial Red-Team Injection Vectors
# ============================================================================

def test_adversarial_replay_token_before_completion_rejected(fresh_nonce_store):
    """Adversarial: Replaying token during admission (before execution completes) is rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    obls = {"OBL-001": make_test_obligation()}
    policies = {"POL-001": make_test_policy()}
    proposal = make_test_proposal()

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

    # First admission succeeds
    admit1 = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admit1.is_admitted is True

    # Immediate second admission of same token is rejected
    admit2 = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admit2.is_admitted is False


def test_adversarial_concurrent_execution_admission_race(fresh_nonce_store):
    """Adversarial: 20 concurrent workers attempt to admit the same ExecutionToken.
    Exactly ONE succeeds; 19 fail closed.
    """
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    token = _mint_execution_token(
        token_id="TOK-CONCURRENT-ADMIT-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        authority_signer=signer,
    )

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
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    token = _mint_execution_token(
        token_id="TOK-FUTURE-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_FUTURE,
        expires_at="2026-08-20T16:00:00Z",
        authority_signer=signer,
    )
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission.is_admitted is False


def test_adversarial_expired_token_rejected(fresh_nonce_store):
    """Adversarial: Token evaluated past expires_at timestamp -> rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    token = _mint_execution_token(
        token_id="TOK-EXPIRED-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        authority_signer=signer,
    )
    admission = controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_LATE)
    assert admission.is_admitted is False


def test_adversarial_token_from_wrong_obligation_rejected(fresh_nonce_store):
    """Adversarial: Token minted for OBL-001 replayed on OBL-002 -> rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    token = _mint_execution_token(
        token_id="TOK-MISBIND-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        authority_signer=signer,
    )
    assert controller.admit_execution(token, "OBL-002", DEFAULT_SHA, 1, TIMESTAMP_NOW).is_admitted is False


def test_adversarial_token_for_wrong_repository_sha_rejected(fresh_nonce_store):
    """Adversarial: Token bound to commit SHA-A replayed on commit SHA-B -> rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    token = _mint_execution_token(
        token_id="TOK-SHA-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        authority_signer=signer,
    )
    assert controller.admit_execution(token, "OBL-001", ALT_SHA, 1, TIMESTAMP_NOW).is_admitted is False


def test_adversarial_policy_version_mismatch_rejected(fresh_nonce_store):
    """Adversarial: Token issued under policy v1 replayed under policy v2 -> rejected."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)

    token = _mint_execution_token(
        token_id="TOK-POL-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        source_sha=DEFAULT_SHA,
        policy_version=1,
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        authority_signer=signer,
    )
    assert controller.admit_execution(token, "OBL-001", DEFAULT_SHA, 2, TIMESTAMP_NOW).is_admitted is False


def test_adversarial_arbitrary_caller_cannot_import_public_mint():
    """The controller module does NOT expose mint_execution_token in public __all__."""
    import controller as cpkg
    assert "mint_execution_token" not in cpkg.__all__
    assert not hasattr(cpkg, "mint_execution_token")


def test_adversarial_hook_cannot_forge_execution_token(fresh_nonce_store):
    """Adversarial: Rogue hook attempts to mint fake token -> fails domain separator / signature check."""
    fake_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="RogueActor",
        public_key_fingerprint="0" * 64,
        payload_digest="0" * 64,
        signature_hex="0" * 128,
        timestamp=TIMESTAMP_NOW,
    )
    forged_token = ExecutionToken(
        token_id="TOK-FORGED-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        source_sha=DEFAULT_SHA,
        policy_version=1,
        execution_nonce="NONCE-FORGED",
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        signature=fake_sig,
    )
    controller = SClassController(authority_signer=Gate3AuthoritySigner(), nonce_store=fresh_nonce_store)
    admission = controller.admit_execution(forged_token, "OBL-001", DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert admission.is_admitted is False


def test_adversarial_post_execute_cannot_grant_authorization(fresh_nonce_store):
    """Adversarial: POST_EXECUTE hook cannot grant authorization retroactively."""
    class MutatingPostHook:
        def execute_hook(self, ctx: HookContext) -> HookResult:
            return HookResult(proceed=True)

    pipeline = LifecyclePipeline()
    pipeline.register_hook(LifecycleStage.POST_EXECUTE, MutatingPostHook())

    controller = SClassController(authority_signer=Gate3AuthoritySigner(), pipeline=pipeline, nonce_store=fresh_nonce_store)

    fake_sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="RogueActor",
        public_key_fingerprint="0" * 64,
        payload_digest="0" * 64,
        signature_hex="0" * 128,
        timestamp=TIMESTAMP_NOW,
    )
    fake_token = ExecutionToken(
        token_id="TOK-FAKE-001",
        obligation_id="OBL-001",
        proposal_id="ACT-001",
        source_sha=DEFAULT_SHA,
        policy_version=1,
        execution_nonce="NONCE-FAKE-1",
        issued_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        signature=fake_sig,
    )
    fake_admission = ExecutionAdmissionResult(token_id="TOK-FAKE-001", is_admitted=True, admission_nonce="NONCE-FAKE-1")
    res = controller.complete_execution(fake_token, fake_admission)
    assert res.is_valid_execution is False


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
# 5. Type and Edge Case Validation Tests
# ============================================================================

def test_action_proposal_and_decision_validation_errors():
    """ActionProposal and AuthorizationDecision raise ValueError on invalid arguments."""
    with pytest.raises(ValueError, match="proposal_id cannot be empty"):
        ActionProposal("", "OBL-1", "TEST", "target", "purpose")
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        ActionProposal("ACT-1", "", "TEST", "target", "purpose")
    with pytest.raises(ValueError, match="action_type cannot be empty"):
        ActionProposal("ACT-1", "OBL-1", "", "target", "purpose")
    with pytest.raises(ValueError, match="target cannot be empty"):
        ActionProposal("ACT-1", "OBL-1", "TEST", "", "purpose")
    with pytest.raises(ValueError, match="cannot be negative"):
        ActionProposal("ACT-1", "OBL-1", "TEST", "target", "purpose", estimated_cost_usd=-1.0)
    with pytest.raises(ValueError, match="timeout_seconds must be >= 1"):
        ActionProposal("ACT-1", "OBL-1", "TEST", "target", "purpose", timeout_seconds=0)

    with pytest.raises(ValueError, match="decision_id cannot be empty"):
        AuthorizationDecision("", "ACT-1", "OBL-1", AuthorizationStatus.AUTHORIZED, evaluated_at=TIMESTAMP_NOW)
    with pytest.raises(ValueError, match="proposal_id cannot be empty"):
        AuthorizationDecision("DEC-1", "", "OBL-1", AuthorizationStatus.AUTHORIZED, evaluated_at=TIMESTAMP_NOW)
    with pytest.raises(ValueError, match="obligation_id cannot be empty"):
        AuthorizationDecision("DEC-1", "ACT-1", "", AuthorizationStatus.AUTHORIZED, evaluated_at=TIMESTAMP_NOW)
    with pytest.raises(TypeError, match="Invalid status"):
        AuthorizationDecision("DEC-1", "ACT-1", "OBL-1", "BAD_STATUS", evaluated_at=TIMESTAMP_NOW)  # type: ignore


def test_token_and_controller_type_validation():
    """Token dataclass and Controller validate types fail-closed."""
    with pytest.raises(ValueError, match="must start with 'TOK-'"):
        ExecutionToken("BAD-ID", "OBL-1", "ACT-1", DEFAULT_SHA, 1, "NONCE-1", TIMESTAMP_NOW, TIMESTAMP_EXPIRY, None)  # type: ignore

    with pytest.raises(TypeError, match="authority_signer must implement AuthoritySignerProtocol"):
        _mint_execution_token("TOK-1", "OBL-1", "ACT-1", DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, "bad_signer")  # type: ignore

    with pytest.raises(ValueError, match="timestamps are required"):
        _mint_execution_token("TOK-1", "OBL-1", "ACT-1", DEFAULT_SHA, 1, "", "", Gate3AuthoritySigner())

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
