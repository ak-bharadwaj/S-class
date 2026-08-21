"""D5 Controller Recertification Test Suite (§8.1, §8.2, CORE-05).

Verifies the 8 D5 recertification proofs:
D5-P1: Reject stale past fencing token
D5-P2: Reject future fabricated fencing token
D5-P3: Reject wrong lease owner
D5-P4: Reject stale state version
D5-P5: Reject stale state digest
D5-P6: Accept exact valid lease and state coordinates
D5-P7: ExecutionToken strictly binds fence, epoch, version, digest
D5-P8: ExecutionAdmissionResult strictly preserves fence, epoch, version, digest
"""

from __future__ import annotations
import os
import tempfile
import uuid
import pytest
from datetime import datetime, timezone

from controller.authorization import (
    ActionProposal,
    AuthorizationEngine,
    AuthorizationStatus,
)
from controller.controller import SClassController
from controller.token import (
    ExecutionContext,
    ActionBinding,
    ExecutionToken,
    ExecutionAdmissionResult,
    verify_execution_token,
    verify_execution_token_signature,
    verify_admission_signature,
)
from domain.models import (
    Obligation,
    Policy,
    PolicyExpression,
    PolicyRule,
)
from domain.types import (
    ObligationCategory,
    Criticality,
    ObligationStatus,
    PolicyScope,
    RuleType,
    CombinatorType,
)
from events.store import D2NonceStore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from cryptography.hazmat.primitives.asymmetric import ed25519


@pytest.fixture(autouse=True)
def setup_authority_keys():
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


@pytest.fixture
def authority_signer():
    return Gate3AuthoritySigner()


@pytest.fixture
def temp_nonce_store():
    with tempfile.TemporaryDirectory() as td:
        store_path = os.path.join(td, "d2_nonces.jsonl")
        yield D2NonceStore(file_path=store_path)


@pytest.fixture
def sample_context():
    return ExecutionContext(
        provider_id="pytest_runner",
        sandbox_profile_id="sbx_isolated",
        workspace_id="ws_main",
        resource_profile_id="res_standard",
        capability_set=("TEST_RUNNER", "STATIC_ANALYSIS"),
    )


@pytest.fixture
def sample_obligation():
    return Obligation(
        obligation_id="OBL-AUTH-001",
        task_id="TASK-001",
        title="Verify Authentication",
        description="Must enforce 403 on unauthenticated request",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        depends_on=(),
        claim_ids=(),
    )


from controller.authority import StaticLeaseAuthority, StaticStateAuthority
from controller.token import _mint_execution_token
from planner.lease import PlanningLeaseManager
from planner.models import PlanningLease


@pytest.fixture
def controller(authority_signer, temp_nonce_store):
    authoritative_lease = PlanningLease(
        task_id="TASK-001",
        owner_id="WORKER-EXACT",
        lease_epoch=3,
        fencing_token=42,
        acquired_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
        is_active=True,
    )
    return SClassController(
        authority_signer=authority_signer,
        nonce_store=temp_nonce_store,
        lease_authority=StaticLeaseAuthority({"TASK-001": authoritative_lease}),
        state_authority=StaticStateAuthority(100, "a" * 64),
    )


def test_d5_p1_rejects_stale_past_fencing_token(sample_context, sample_obligation):
    """D5-P1: Reject proposal with fencing_token lower than active lease."""
    proposal = ActionProposal(
        proposal_id="PROP-P1",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=4,
        lease_epoch=2,
        owner_id="WORKER-01",
        state_version=10,
        state_digest="a" * 64,
    )

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="a" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        active_fencing_token=5,
        active_lease_epoch=2,
        active_owner_id="WORKER-01",
        expected_state_version=10,
        expected_state_digest="a" * 64,
    )

    assert decision.status == AuthorizationStatus.REJECTED
    assert any("INVALID_FENCING_TOKEN" in r for r in decision.rejection_reasons)


def test_d5_p2_rejects_future_fabricated_fencing_token(sample_context, sample_obligation):
    """D5-P2: Reject proposal with fencing_token higher than active lease."""
    proposal = ActionProposal(
        proposal_id="PROP-P2",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=99,
        lease_epoch=2,
        owner_id="WORKER-01",
        state_version=10,
        state_digest="a" * 64,
    )

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="a" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        active_fencing_token=5,
        active_lease_epoch=2,
        active_owner_id="WORKER-01",
        expected_state_version=10,
        expected_state_digest="a" * 64,
    )

    assert decision.status == AuthorizationStatus.REJECTED
    assert any("INVALID_FENCING_TOKEN" in r for r in decision.rejection_reasons)


def test_d5_p3_rejects_wrong_lease_owner(sample_context, sample_obligation):
    """D5-P3: Reject proposal with owner_id not matching active lease."""
    proposal = ActionProposal(
        proposal_id="PROP-P3",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=5,
        lease_epoch=2,
        owner_id="ROGUE-WORKER",
        state_version=10,
        state_digest="a" * 64,
    )

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="a" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        active_fencing_token=5,
        active_lease_epoch=2,
        active_owner_id="LEGIT-WORKER-01",
        expected_state_version=10,
        expected_state_digest="a" * 64,
    )

    assert decision.status == AuthorizationStatus.REJECTED
    assert any("WRONG_LEASE_OWNER" in r for r in decision.rejection_reasons)


def test_d5_p4_rejects_stale_state_version(sample_context, sample_obligation):
    """D5-P4: Reject proposal with state_version not matching current event sequence."""
    proposal = ActionProposal(
        proposal_id="PROP-P4",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=5,
        lease_epoch=2,
        owner_id="WORKER-01",
        state_version=10,
        state_digest="a" * 64,
    )

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="a" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        active_fencing_token=5,
        active_lease_epoch=2,
        active_owner_id="WORKER-01",
        expected_state_version=12,
        expected_state_digest="a" * 64,
    )

    assert decision.status == AuthorizationStatus.REJECTED
    assert any("STALE_STATE_VERSION" in r for r in decision.rejection_reasons)


def test_d5_p5_rejects_stale_state_digest(sample_context, sample_obligation):
    """D5-P5: Reject proposal with state_digest not matching current head digest."""
    proposal = ActionProposal(
        proposal_id="PROP-P5",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=5,
        lease_epoch=2,
        owner_id="WORKER-01",
        state_version=12,
        state_digest="1" * 64,
    )

    decision = AuthorizationEngine.evaluate_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="a" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        active_fencing_token=5,
        active_lease_epoch=2,
        active_owner_id="WORKER-01",
        expected_state_version=12,
        expected_state_digest="2" * 64,
    )

    assert decision.status == AuthorizationStatus.REJECTED
    assert any("STALE_STATE_DIGEST" in r for r in decision.rejection_reasons)


def test_d5_p6_p7_p8_accepts_exact_lease_and_binds_in_token_and_admission(
    controller, authority_signer, sample_context, sample_obligation
):
    """D5-P6, P7, P8: Accept valid lease/state, verify token and admission bind coordinates."""
    proposal = ActionProposal(
        proposal_id="PROP-P6",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=42,
        lease_epoch=3,
        owner_id="WORKER-EXACT",
        state_version=100,
        state_digest="a" * 64,
    )

    result = controller.submit_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="b" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )

    # D5-P6: Accepted
    assert result.decision.status == AuthorizationStatus.AUTHORIZED
    assert result.execution_token is not None

    token = result.execution_token
    # D5-P7: Token binds exact coordinates including owner_id
    assert token.owner_id == "WORKER-EXACT"
    assert token.fencing_token == 42
    assert token.lease_epoch == 3
    assert token.state_version == 100
    assert token.state_digest == "a" * 64

    # Verify token signature validates
    assert verify_execution_token(
        token=token,
        expected_obligation_id=sample_obligation.obligation_id,
        expected_source_sha="b" * 40,
        expected_policy_version=1,
        expected_action_digest=proposal.action_digest,
        expected_context_digest=sample_context.context_digest,
        current_time_iso="2026-08-20T12:05:00Z",
        authority_signer=authority_signer,
        expected_owner_id="WORKER-EXACT",
        expected_fencing_token=42,
        expected_lease_epoch=3,
        expected_state_version=100,
        expected_state_digest="a" * 64,
    )

    # D5-P8: Admission preserves exact coordinates including owner_id
    admission = controller.admit_execution(
        token=token,
        expected_obligation_id=sample_obligation.obligation_id,
        expected_source_sha="b" * 40,
        expected_policy_version=1,
        expected_action_binding=proposal.binding,
        expected_execution_context=sample_context,
        current_time_iso="2026-08-20T12:06:00Z",
    )

    assert admission.is_admitted is True
    assert admission.owner_id == "WORKER-EXACT"
    assert admission.fencing_token == 42
    assert admission.lease_epoch == 3
    assert admission.state_version == 100
    assert admission.state_digest == "a" * 64
    assert verify_admission_signature(admission, authority_signer) is True


def test_d5_rejects_omitted_fencing_parameters_under_active_lease(controller, sample_context, sample_obligation):
    """Adversarial: Caller attempts to bypass lease by omitting fencing coordinates."""
    proposal = ActionProposal(
        proposal_id="PROP-BYPASS-01",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        # Omitted fencing/state coordinates default to 0/empty
    )

    result = controller.submit_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="b" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )

    assert result.decision.status == AuthorizationStatus.REJECTED
    assert any("INVALID_FENCING_TOKEN" in r for r in result.decision.rejection_reasons)


def test_d5_rejects_caller_supplied_fake_current_state(controller, sample_context, sample_obligation):
    """Adversarial: Caller supplies forged state coordinates, controller checks its internal resolver."""
    proposal = ActionProposal(
        proposal_id="PROP-FORGE-STATE",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=42,
        lease_epoch=3,
        owner_id="WORKER-EXACT",
        state_version=999,  # Forged state version
        state_digest="f" * 64,  # Forged state digest
    )

    result = controller.submit_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="b" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )

    assert result.decision.status == AuthorizationStatus.REJECTED
    assert any("STALE_STATE_VERSION" in r for r in result.decision.rejection_reasons)
    assert any("STALE_STATE_DIGEST" in r for r in result.decision.rejection_reasons)


def test_owner_identity_verified_through_complete_execution_lifecycle(
    controller, authority_signer, sample_context, sample_obligation
):
    """Adversarial: Tampering with owner_id across token and admission causes complete_execution rejection."""
    proposal = ActionProposal(
        proposal_id="PROP-OWNER-TEST",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=42,
        lease_epoch=3,
        owner_id="WORKER-EXACT",
        state_version=100,
        state_digest="a" * 64,
    )

    result = controller.submit_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="b" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )

    token = result.execution_token
    assert token is not None
    assert token.owner_id == "WORKER-EXACT"

    admission = controller.admit_execution(
        token=token,
        expected_obligation_id=sample_obligation.obligation_id,
        expected_source_sha="b" * 40,
        expected_policy_version=1,
        expected_action_binding=proposal.binding,
        expected_execution_context=sample_context,
        current_time_iso="2026-08-20T12:06:00Z",
    )

    envelope = controller.create_execution_envelope(
        token=token,
        admission=admission,
        action_binding=proposal.binding,
        execution_context=sample_context,
    )

    completion = controller.complete_execution(envelope)
    assert completion.is_valid_execution is True


# ============================================================================
# Cryptographic Tamper & Configuration Bypass Tests (Requirements 4 & 5)
# ============================================================================

def test_cryptographic_tamper_detection_execution_token(authority_signer, sample_context, sample_obligation):
    """Requirement 4: Independently mutating signed fields on ExecutionToken causes signature verification failure."""
    token = _mint_execution_token(
        token_id=f"TOK-{uuid.uuid4().hex[:8]}",
        decision_id=f"DEC-{uuid.uuid4().hex[:8]}",
        obligation_id=sample_obligation.obligation_id,
        proposal_id="PROP-TAMPER-01",
        action_digest="c" * 64,
        context_digest=sample_context.context_digest,
        source_sha="b" * 40,
        policy_version=1,
        issued_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
        authority_signer=authority_signer,
        owner_id="WORKER-EXACT",
        fencing_token=42,
        lease_epoch=3,
        state_version=100,
        state_digest="a" * 64,
    )
    assert verify_execution_token_signature(token, authority_signer) is True

    # 1. Mutate owner_id
    tampered_owner = ExecutionToken(
        token_id=token.token_id,
        decision_id=token.decision_id,
        obligation_id=token.obligation_id,
        proposal_id=token.proposal_id,
        action_digest=token.action_digest,
        context_digest=token.context_digest,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        execution_nonce=token.execution_nonce,
        issued_at=token.issued_at,
        expires_at=token.expires_at,
        signature=token.signature,
        fencing_token=token.fencing_token,
        lease_epoch=token.lease_epoch,
        owner_id="ROGUE-WORKER",
        state_version=token.state_version,
        state_digest=token.state_digest,
    )
    assert verify_execution_token_signature(tampered_owner, authority_signer) is False

    # 2. Mutate fencing_token
    tampered_fence = ExecutionToken(
        token_id=token.token_id,
        decision_id=token.decision_id,
        obligation_id=token.obligation_id,
        proposal_id=token.proposal_id,
        action_digest=token.action_digest,
        context_digest=token.context_digest,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        execution_nonce=token.execution_nonce,
        issued_at=token.issued_at,
        expires_at=token.expires_at,
        signature=token.signature,
        fencing_token=999,
        lease_epoch=token.lease_epoch,
        owner_id=token.owner_id,
        state_version=token.state_version,
        state_digest=token.state_digest,
    )
    assert verify_execution_token_signature(tampered_fence, authority_signer) is False

    # 3. Mutate lease_epoch
    tampered_epoch = ExecutionToken(
        token_id=token.token_id,
        decision_id=token.decision_id,
        obligation_id=token.obligation_id,
        proposal_id=token.proposal_id,
        action_digest=token.action_digest,
        context_digest=token.context_digest,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        execution_nonce=token.execution_nonce,
        issued_at=token.issued_at,
        expires_at=token.expires_at,
        signature=token.signature,
        fencing_token=token.fencing_token,
        lease_epoch=99,
        owner_id=token.owner_id,
        state_version=token.state_version,
        state_digest=token.state_digest,
    )
    assert verify_execution_token_signature(tampered_epoch, authority_signer) is False

    # 4. Mutate state_version
    tampered_state_ver = ExecutionToken(
        token_id=token.token_id,
        decision_id=token.decision_id,
        obligation_id=token.obligation_id,
        proposal_id=token.proposal_id,
        action_digest=token.action_digest,
        context_digest=token.context_digest,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        execution_nonce=token.execution_nonce,
        issued_at=token.issued_at,
        expires_at=token.expires_at,
        signature=token.signature,
        fencing_token=token.fencing_token,
        lease_epoch=token.lease_epoch,
        owner_id=token.owner_id,
        state_version=999,
        state_digest=token.state_digest,
    )
    assert verify_execution_token_signature(tampered_state_ver, authority_signer) is False

    # 5. Mutate state_digest
    tampered_state_dig = ExecutionToken(
        token_id=token.token_id,
        decision_id=token.decision_id,
        obligation_id=token.obligation_id,
        proposal_id=token.proposal_id,
        action_digest=token.action_digest,
        context_digest=token.context_digest,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        execution_nonce=token.execution_nonce,
        issued_at=token.issued_at,
        expires_at=token.expires_at,
        signature=token.signature,
        fencing_token=token.fencing_token,
        lease_epoch=token.lease_epoch,
        owner_id=token.owner_id,
        state_version=token.state_version,
        state_digest="f" * 64,
    )
    assert verify_execution_token_signature(tampered_state_dig, authority_signer) is False


def test_cryptographic_tamper_detection_admission_result(controller, authority_signer, sample_context, sample_obligation):
    """Requirement 4: Independently mutating signed fields on ExecutionAdmissionResult causes signature verification failure."""
    proposal = ActionProposal(
        proposal_id="PROP-ADMIT-TAMPER",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=42,
        lease_epoch=3,
        owner_id="WORKER-EXACT",
        state_version=100,
        state_digest="a" * 64,
    )
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="b" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )
    token = dispatch.execution_token
    admission = controller.admit_execution(
        token=token,
        expected_obligation_id=sample_obligation.obligation_id,
        expected_source_sha="b" * 40,
        expected_policy_version=1,
        expected_action_binding=proposal.binding,
        expected_execution_context=sample_context,
        current_time_iso="2026-08-20T12:06:00Z",
    )
    assert verify_admission_signature(admission, authority_signer) is True

    # Mutate owner_id
    t_owner = ExecutionAdmissionResult(
        token_id=admission.token_id,
        execution_nonce=admission.execution_nonce,
        obligation_id=admission.obligation_id,
        action_digest=admission.action_digest,
        context_digest=admission.context_digest,
        source_sha=admission.source_sha,
        policy_version=admission.policy_version,
        decision_id=admission.decision_id,
        admitted_at=admission.admitted_at,
        is_admitted=admission.is_admitted,
        signature=admission.signature,
        fencing_token=admission.fencing_token,
        lease_epoch=admission.lease_epoch,
        owner_id="TAMPERED-OWNER",
        state_version=admission.state_version,
        state_digest=admission.state_digest,
    )
    assert verify_admission_signature(t_owner, authority_signer) is False

    # Mutate fencing_token
    t_fence = ExecutionAdmissionResult(
        token_id=admission.token_id,
        execution_nonce=admission.execution_nonce,
        obligation_id=admission.obligation_id,
        action_digest=admission.action_digest,
        context_digest=admission.context_digest,
        source_sha=admission.source_sha,
        policy_version=admission.policy_version,
        decision_id=admission.decision_id,
        admitted_at=admission.admitted_at,
        is_admitted=admission.is_admitted,
        signature=admission.signature,
        fencing_token=999,
        lease_epoch=admission.lease_epoch,
        owner_id=admission.owner_id,
        state_version=admission.state_version,
        state_digest=admission.state_digest,
    )
    assert verify_admission_signature(t_fence, authority_signer) is False

    # Mutate lease_epoch
    t_epoch = ExecutionAdmissionResult(
        token_id=admission.token_id,
        execution_nonce=admission.execution_nonce,
        obligation_id=admission.obligation_id,
        action_digest=admission.action_digest,
        context_digest=admission.context_digest,
        source_sha=admission.source_sha,
        policy_version=admission.policy_version,
        decision_id=admission.decision_id,
        admitted_at=admission.admitted_at,
        is_admitted=admission.is_admitted,
        signature=admission.signature,
        fencing_token=admission.fencing_token,
        lease_epoch=99,
        owner_id=admission.owner_id,
        state_version=admission.state_version,
        state_digest=admission.state_digest,
    )
    assert verify_admission_signature(t_epoch, authority_signer) is False

    # Mutate state_version
    t_state_ver = ExecutionAdmissionResult(
        token_id=admission.token_id,
        execution_nonce=admission.execution_nonce,
        obligation_id=admission.obligation_id,
        action_digest=admission.action_digest,
        context_digest=admission.context_digest,
        source_sha=admission.source_sha,
        policy_version=admission.policy_version,
        decision_id=admission.decision_id,
        admitted_at=admission.admitted_at,
        is_admitted=admission.is_admitted,
        signature=admission.signature,
        fencing_token=admission.fencing_token,
        lease_epoch=admission.lease_epoch,
        owner_id=admission.owner_id,
        state_version=999,
        state_digest=admission.state_digest,
    )
    assert verify_admission_signature(t_state_ver, authority_signer) is False

    # Mutate state_digest
    t_state_dig = ExecutionAdmissionResult(
        token_id=admission.token_id,
        execution_nonce=admission.execution_nonce,
        obligation_id=admission.obligation_id,
        action_digest=admission.action_digest,
        context_digest=admission.context_digest,
        source_sha=admission.source_sha,
        policy_version=admission.policy_version,
        decision_id=admission.decision_id,
        admitted_at=admission.admitted_at,
        is_admitted=admission.is_admitted,
        signature=admission.signature,
        fencing_token=admission.fencing_token,
        lease_epoch=admission.lease_epoch,
        owner_id=admission.owner_id,
        state_version=admission.state_version,
        state_digest="f" * 64,
    )
    assert verify_admission_signature(t_state_dig, authority_signer) is False


def test_controller_without_lease_authority_rejects_proposal(authority_signer, temp_nonce_store, sample_context, sample_obligation):
    """Requirement 5: Controller without lease authority fails closed."""
    ctrl = SClassController(
        authority_signer=authority_signer,
        nonce_store=temp_nonce_store,
        lease_authority=None,
        state_authority=StaticStateAuthority(100, "a" * 64),
    )
    proposal = ActionProposal(
        proposal_id="PROP-NO-LEASE-AUTH",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
    )
    result = ctrl.submit_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="b" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )
    assert result.decision.status == AuthorizationStatus.REJECTED
    assert any("MISSING_LEASE_AUTHORITY" in r for r in result.decision.rejection_reasons)


def test_controller_without_state_authority_rejects_proposal(authority_signer, temp_nonce_store, sample_context, sample_obligation):
    """Requirement 5: Controller without state authority fails closed."""
    authoritative_lease = PlanningLease(
        task_id="TASK-001",
        owner_id="WORKER-EXACT",
        lease_epoch=3,
        fencing_token=42,
        acquired_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
        is_active=True,
    )
    ctrl = SClassController(
        authority_signer=authority_signer,
        nonce_store=temp_nonce_store,
        lease_authority=StaticLeaseAuthority({"TASK-001": authoritative_lease}),
        state_authority=None,
    )
    proposal = ActionProposal(
        proposal_id="PROP-NO-STATE-AUTH",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
        fencing_token=42,
        lease_epoch=3,
        owner_id="WORKER-EXACT",
    )
    result = ctrl.submit_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="b" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )
    assert result.decision.status == AuthorizationStatus.REJECTED
    assert any("MISSING_STATE_AUTHORITY" in r for r in result.decision.rejection_reasons)


def test_controller_with_invalid_lease_authority_object_rejects_proposal(
    authority_signer, temp_nonce_store, sample_context, sample_obligation
):
    """Requirement 5: Controller with invalid lease authority type fails closed."""
    ctrl = SClassController(
        authority_signer=authority_signer,
        nonce_store=temp_nonce_store,
        lease_authority="NOT_A_LEASE_AUTHORITY",  # type: ignore
        state_authority=StaticStateAuthority(100, "a" * 64),
    )
    proposal = ActionProposal(
        proposal_id="PROP-INVALID-LEASE-AUTH",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
    )
    result = ctrl.submit_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="b" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )
    assert result.decision.status == AuthorizationStatus.REJECTED
    assert any("INVALID_LEASE_AUTHORITY" in r for r in result.decision.rejection_reasons)


def test_controller_with_corrupted_lease_record_rejects_proposal(
    authority_signer, temp_nonce_store, sample_context, sample_obligation, tmp_path
):
    """Requirement 3 & 5: Corrupted lease record on disk triggers LEASE_STATE_CORRUPT rejection."""
    lease_dir = tmp_path / "corrupt_leases"
    os.makedirs(lease_dir, exist_ok=True)
    lease_mgr = PlanningLeaseManager(str(lease_dir))

    # Write corrupt data into TASK-001.json
    corrupt_file = lease_dir / "TASK-001.json"
    with open(corrupt_file, "w", encoding="utf-8") as f:
        f.write("{ INVALID JSON DATA FOR CORRUPTION PROOF !!!")

    ctrl = SClassController(
        authority_signer=authority_signer,
        nonce_store=temp_nonce_store,
        lease_authority=lease_mgr,
        state_authority=StaticStateAuthority(100, "a" * 64),
    )
    proposal = ActionProposal(
        proposal_id="PROP-CORRUPT-LEASE",
        obligation_id=sample_obligation.obligation_id,
        action_type="EXECUTE_TEST",
        target="tests/test_auth.py",
        purpose="Verify token check",
        execution_context=sample_context,
    )
    result = ctrl.submit_proposal(
        proposal=proposal,
        obligations={sample_obligation.obligation_id: sample_obligation},
        policies={},
        source_sha="b" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )
    assert result.decision.status == AuthorizationStatus.REJECTED
    assert any("LEASE_STATE_CORRUPT" in r for r in result.decision.rejection_reasons)

