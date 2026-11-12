"""Comprehensive validation tests for F2: PD-CH2-065 replay lifecycle proof hardening.

Verifies:
- Caller-supplied expected_gate_output and evaluator_record_ref are treated as untrusted claims.
- Valid authority-verified canonical records produce SATISFIED.
- Missing, invalid, unverifiable, or malformed records fail closed to MISSING[PD-CH2-065].
- Missing authority fails closed immediately.
- Forged references fail closed.
- Both direct evaluator (evaluate_ch2_065_lifecycle_proof) and public gate (evaluate_replay_gate) are tested.
"""
from typing import Any, Dict
import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.replay import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_ch2_065_lifecycle_proof,
    evaluate_replay_gate,
)


def _canonical_payload(overrides: Dict[str, Any] = None) -> Dict[str, Any]:
    base = {
        "must_id": "PD-CH2-065",
        "example_preconditions": {"service": "auth", "env": "prod"},
        "bound_input_digests": ["sha256:precondition1", "sha256:input1"],
        "expected_gate_output": "SATISFIED",
        "evaluator_record_ref": "REC-AUTH-001",
        "authority_verified_record": {
            "evaluator_record_ref": "REC-AUTH-001",
            "status": "VERIFIED",
            "gate_output": "SATISFIED",
        },
    }
    if overrides:
        base.update(overrides)
    return base


def test_f2_valid_authority_verified_record_direct_evaluator():
    """Valid authority-verified canonical record produces SATISFIED via direct evaluator."""
    payload = _canonical_payload()
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"
    assert res.explain.get("canonical_record_verified") is True


def test_f2_valid_authority_verified_record_public_gate():
    """Valid authority-verified canonical record produces SATISFIED via evaluate_replay_gate."""
    payload = _canonical_payload()
    res = evaluate_replay_gate(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_f2_valid_injected_record_verifier_callback():
    """Verification using an injected authority record_verifier callback."""
    payload = _canonical_payload()
    del payload["authority_verified_record"]  # Remove embedded record

    def verifier(ref: str):
        if ref == "REC-AUTH-001":
            return {"evaluator_record_ref": ref, "status": "VERIFIED", "gate_output": "SATISFIED"}
        return None

    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY, record_verifier=verifier)
    assert res.state == GateState.SATISFIED

    res_gate = evaluate_replay_gate(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY, record_verifier=verifier)
    assert res_gate.state == GateState.SATISFIED


def test_f2_missing_authority_fails_closed():
    """Missing or unauthorized caller_authority returns MISSING[PD-CH2-065]."""
    payload = _canonical_payload()
    assert evaluate_ch2_065_lifecycle_proof(payload, caller_authority=None).state == GateState.MISSING
    assert evaluate_ch2_065_lifecycle_proof(payload, caller_authority="AGENT").state == GateState.MISSING
    assert evaluate_replay_gate(payload, caller_authority=None).state == GateState.MISSING


def test_f2_missing_canonical_record_fails_closed():
    """Caller supplies expected_gate_output='SATISFIED' and record ref, but record is missing -> MISSING."""
    payload = _canonical_payload()
    del payload["authority_verified_record"]  # No record provided
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"

    res_gate = evaluate_replay_gate(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res_gate.state == GateState.MISSING
    assert res_gate.must_id == "PD-CH2-065"


def test_f2_invalid_unverified_record_fails_closed():
    """Canonical record with status != 'VERIFIED' fails closed."""
    payload = _canonical_payload({
        "authority_verified_record": {
            "evaluator_record_ref": "REC-AUTH-001",
            "status": "UNVERIFIED_CLAIM",
            "gate_output": "SATISFIED",
        }
    })
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"


def test_f2_malformed_record_fails_closed():
    """Non-mapping or corrupt canonical record fails closed without unhandled exceptions."""
    for malformed in ["not-a-dict", 12345, [], None]:
        payload = _canonical_payload({"authority_verified_record": malformed})
        res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
        assert res.state == GateState.MISSING


def test_f2_record_ref_mismatch_fails_closed():
    """Verified record reference does not match claimed evaluator_record_ref -> MISSING."""
    payload = _canonical_payload({
        "evaluator_record_ref": "CLAIMED-001",
        "authority_verified_record": {
            "evaluator_record_ref": "DIFFERENT-RECORD-002",
            "status": "VERIFIED",
            "gate_output": "SATISFIED",
        }
    })
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"


def test_f2_record_output_contradicts_claimed_output_fails_closed():
    """Verified record output ('MISSING') contradicts claimed output ('SATISFIED') -> MISSING."""
    payload = _canonical_payload({
        "expected_gate_output": "SATISFIED",
        "authority_verified_record": {
            "evaluator_record_ref": "REC-AUTH-001",
            "status": "VERIFIED",
            "gate_output": "MISSING[PD-CH2-065]",
        }
    })
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"


def test_f2_forged_reference_fails_closed():
    """Forged reference or agent-asserted string fails closed."""
    for forged in ["forged", "agent-asserted-proof", "AGENT_RECORD"]:
        payload = _canonical_payload({"evaluator_record_ref": forged})
        res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH2-065"


def test_f2_caller_expected_output_alone_is_not_proof():
    """Caller-provided expected_gate_output alone is an untrusted claim and cannot produce SATISFIED."""
    claim_only = {
        "must_id": "PD-CH2-065",
        "expected_gate_output": "SATISFIED",
    }
    res = evaluate_ch2_065_lifecycle_proof(claim_only, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"
