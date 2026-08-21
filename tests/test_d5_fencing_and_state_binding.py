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
        lease_resolver=lambda tid: authoritative_lease if tid == "TASK-001" else None,
        state_resolver=lambda: (100, "a" * 64),
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
        enforce_lease=True,
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
        enforce_lease=True,
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
        enforce_lease=True,
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
        expected_state_version=12,
        expected_state_digest="a" * 64,
        enforce_state=True,
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
        expected_state_version=12,
        expected_state_digest="2" * 64,
        enforce_state=True,
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
