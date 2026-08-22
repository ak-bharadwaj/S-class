"""
Unit and Integration Tests for Bridge 3 and Evidence Adapter:
- claim/adapter.py: ObservationEvidenceAdapter
- agent/repair.py: RepairFeedbackBuilder
"""

import pytest
from datetime import datetime, timezone
from domain.models import (
    Claim,
    ClaimSubject,
    AssessmentReceipt,
    AsymmetricAuthoritySignature,
)
from domain.types import (
    ClaimTier,
    ClaimStatus,
    TargetType,
    Criticality,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
    AssessmentVerdict,
)
from execution.models import ExecutionObservation, ExecutionStatus, TerminationReason
from claim.adapter import ObservationEvidenceAdapter
from claim.reducer import ClaimReductionState, ClaimEpistemicState
from agent.repair import RepairFeedbackBuilder, RepairFeedbackPayload


@pytest.fixture
def sample_claim():
    return Claim(
        claim_id="CLM-001",
        obligation_id="OBL-001",
        tier=ClaimTier.V0_OBSERVABLE,
        subject=ClaimSubject(target_type=TargetType.FUNCTION, identifier="math_service.square"),
        predicate="SQUARE_INVARIANT_SATISFIED",
        context={"aspects": ["functional_correctness"]},
        expected={"status": "PASS"},
        criticality=Criticality.HIGH,
        status=ClaimStatus.UNSUPPORTED,
        required_provider_capabilities=("CAP_EXEC_TEST",),
    )


def test_observation_evidence_adapter_success_and_failure(sample_claim):
    """Verifies that ExecutionObservations map cleanly to Evidence instances with stdout digest binding."""
    # 1. Success Observation
    obs_pass = ExecutionObservation(
        execution_id="EXEC-PASS-01",
        token_id="TOK-001",
        provider_id="pytest_runner_engine",
        action_digest="a" * 64,
        context_digest="b" * 64,
        started_at="2026-08-20T12:00:00Z",
        ended_at="2026-08-20T12:00:01Z",
        exit_code=0,
        termination_reason=TerminationReason.EXIT_ZERO,
        stdout_digest="c" * 64,
        stderr_digest="d" * 64,
        stdout_bytes_len=100,
        stderr_bytes_len=0,
        execution_status=ExecutionStatus.SUCCESS,
        diagnostics=({"msg": "2 passed in 0.05s"},),
    )
    ev_pass = ObservationEvidenceAdapter.create_evidence(obs_pass, sample_claim, source_sha="a" * 40)
    assert ev_pass.polarity == EvidencePolarity.SUPPORTS
    assert ev_pass.observation.raw_status == RawStatus.PASS
    assert ev_pass.signature.raw_stdout_digest == "c" * 64
    assert ev_pass.claim_id == sample_claim.claim_id

    # 2. Failure Observation
    obs_fail = ExecutionObservation(
        execution_id="EXEC-FAIL-01",
        token_id="TOK-002",
        provider_id="pytest_runner_engine",
        action_digest="a" * 64,
        context_digest="b" * 64,
        started_at="2026-08-20T12:00:00Z",
        ended_at="2026-08-20T12:00:01Z",
        exit_code=1,
        termination_reason=TerminationReason.EXIT_NON_ZERO,
        stdout_digest="e" * 64,
        stderr_digest="f" * 64,
        stdout_bytes_len=120,
        stderr_bytes_len=50,
        execution_status=ExecutionStatus.FAILURE,
        diagnostics=({"msg": "assert square(3) == 9 failed: 5 != 9"},),
    )
    ev_fail = ObservationEvidenceAdapter.create_evidence(obs_fail, sample_claim, source_sha="a" * 40)
    assert ev_fail.polarity == EvidencePolarity.REFUTES
    assert ev_fail.observation.raw_status == RawStatus.FAIL
    assert ev_fail.signature.raw_stdout_digest == "e" * 64


def test_repair_feedback_builder_rejected_assessment():
    """Verifies that rejected assessment receipts and contradicted claims produce actionable repair context."""
    sig = AsymmetricAuthoritySignature(
        algorithm="ED25519",
        signer_identity="AuthorityRoot",
        public_key_fingerprint="0" * 64,
        payload_digest="1" * 64,
        signature_hex="2" * 128,
        timestamp="2026-08-20T12:00:00Z",
    )
    receipt_rej = AssessmentReceipt(
        receipt_id="RCPT-001",
        obligation_id="OBL-MATH-001",
        policy_version=1,
        repository_sha="a" * 40,
        verdict=AssessmentVerdict.REJECTED,
        evaluated_at="2026-08-20T12:00:00Z",
        signature=sig,
        claim_assessments=(),
    )

    reduction_state = ClaimReductionState(
        claim_id="CLM-001",
        epistemic_state=ClaimEpistemicState.CONTRADICTED,
        refuting_evidence_ids=("EV-TEST-001",),
    )

    from domain.models import Evidence, EvidenceScope, EvidenceObservation, Provenance, HmacSessionSignature
    ev = Evidence(
        evidence_id="EV-TEST-001",
        claim_id="CLM-001",
        provider_id="pytest_runner_engine",
        capability="UNIT_TEST_EXECUTION",
        execution_id="TOK-001",
        source_sha="a" * 40,
        scope=EvidenceScope(targets_evaluated=("math_service.square",), aspects_covered=("functional_correctness",)),
        observation=EvidenceObservation(
            raw_status=RawStatus.FAIL,
            diagnostics=("AssertionError: assert 5 == 9",),
        ),
        polarity=EvidencePolarity.REFUTES,
        validity=EvidenceValidity.VALID,
        independence_group="INDEP-1",
        provenance=Provenance(engine_name="pytest", engine_version="9.0.3", environment_hash="e"*64, timestamp="2026-08-20T12:00:00Z"),
        signature=HmacSessionSignature(algorithm="HMAC-SHA256", key_id="K", nonce="N", raw_stdout_digest="0"*64, signature_hex="0"*64, timestamp="2026-08-20T12:00:00Z"),
    )

    feedback: RepairFeedbackPayload = RepairFeedbackBuilder.build_repair_feedback(
        receipt=receipt_rej,
        claim_states={"CLM-001": reduction_state},
        evidence_items=[ev],
        current_code="def square(x):\n    return x + 2\n",
    )

    assert feedback.is_rejected is True
    assert "CLM-001" in feedback.refuted_claim_ids
    assert "AssertionError: assert 5 == 9" in feedback.failure_diagnostics
    assert "def square(x):" in feedback.suggested_repair_prompt
    assert "AssertionError: assert 5 == 9" in feedback.suggested_repair_prompt
