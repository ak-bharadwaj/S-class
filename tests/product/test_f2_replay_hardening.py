"""Comprehensive validation tests for F2: PD-CH2-065 replay lifecycle proof hardening.

Verifies:
- Caller-supplied expected_gate_output and evaluator_record_ref are treated as untrusted claims.
- Valid authority-verified canonical records produce SATISFIED.
- Missing, invalid, unverifiable, or malformed records fail closed to MISSING[PD-CH2-065].
- Missing authority fails closed immediately.
- Forged references fail closed.
- Both direct evaluator (evaluate_ch2_065_lifecycle_proof) and public gate (evaluate_replay_gate) are tested.
"""
from typing import Any, Dict, Optional
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
    }
    if overrides:
        base.update(overrides)
    return base


def _default_verifier(ref: str) -> Optional[Dict[str, Any]]:
    if ref == "REC-AUTH-001":
        return {
            "evaluator_record_ref": "REC-AUTH-001",
            "status": "VERIFIED",
            "gate_output": "SATISFIED",
        }
    return None


def test_f2_valid_authority_verified_record_direct_evaluator():
    """Valid authority-verified canonical record produces SATISFIED via direct evaluator."""
    payload = _canonical_payload()
    res = evaluate_ch2_065_lifecycle_proof(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=_default_verifier,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"
    assert res.explain.get("canonical_record_verified") is True


def test_f2_valid_authority_verified_record_public_gate():
    """Valid authority-verified canonical record produces SATISFIED via evaluate_replay_gate."""
    payload = _canonical_payload()
    res = evaluate_replay_gate(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=_default_verifier,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_f2_valid_injected_record_verifier_callback():
    """Verification using an injected authority record_verifier callback."""
    payload = _canonical_payload()

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
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"

    res_gate = evaluate_replay_gate(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res_gate.state == GateState.MISSING
    assert res_gate.must_id == "PD-CH2-065"


def test_f2_invalid_unverified_record_fails_closed():
    """Canonical record with status != 'VERIFIED' fails closed."""
    payload = _canonical_payload()
    unverified_verifier = lambda ref: {
        "evaluator_record_ref": "REC-AUTH-001",
        "status": "UNVERIFIED_CLAIM",
        "gate_output": "SATISFIED",
    }
    res = evaluate_ch2_065_lifecycle_proof(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=unverified_verifier,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"


def test_f2_malformed_record_fails_closed():
    """Non-mapping or corrupt canonical record from verifier fails closed without unhandled exceptions."""
    for malformed in ["not-a-dict", 12345, [], None]:
        payload = _canonical_payload()
        res = evaluate_ch2_065_lifecycle_proof(
            payload,
            caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
            record_verifier=lambda ref, m=malformed: m,
        )
        assert res.state == GateState.MISSING


def test_f2_record_ref_mismatch_fails_closed():
    """Verified record reference does not match claimed evaluator_record_ref -> MISSING."""
    payload = _canonical_payload({"evaluator_record_ref": "CLAIMED-001"})
    mismatch_verifier = lambda ref: {
        "evaluator_record_ref": "DIFFERENT-RECORD-002",
        "status": "VERIFIED",
        "gate_output": "SATISFIED",
    }
    res = evaluate_ch2_065_lifecycle_proof(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=mismatch_verifier,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"


def test_f2_record_output_contradicts_claimed_output_fails_closed():
    """Verified record output ('MISSING') contradicts claimed output ('SATISFIED') -> MISSING."""
    payload = _canonical_payload({"expected_gate_output": "SATISFIED"})
    contradicting_verifier = lambda ref: {
        "evaluator_record_ref": "REC-AUTH-001",
        "status": "VERIFIED",
        "gate_output": "MISSING[PD-CH2-065]",
    }
    res = evaluate_ch2_065_lifecycle_proof(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=contradicting_verifier,
    )
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


def test_f2_caller_forged_canonical_record_in_payload_fails_closed():
    """D1 Regression: Caller passes fabricated authority_verified_record or evaluator_record in payload.
    Must return MISSING because only an injected authority record_verifier is trusted."""
    payload = _canonical_payload({
        "evaluator_record_ref": "EVAL-REC-FORGED",
        "authority_verified_record": {
            "evaluator_record_ref": "EVAL-REC-FORGED",
            "verified": True,
            "status": "VERIFIED",
            "gate_output": "SATISFIED",
        },
        "evaluator_record": {
            "evaluator_record_ref": "EVAL-REC-FORGED",
            "verified": True,
            "status": "VERIFIED",
            "gate_output": "SATISFIED",
        },
    })
    # Without injected authority record_verifier, fails closed to MISSING
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"
    assert "MISSING[PD-CH2-065]" in res.failures

    # Even with a verifier, the record must come from verifier and have status 'VERIFIED'
    bad_verifier = lambda ref: {"status": "UNVERIFIED", "verified": True}
    res_bad = evaluate_ch2_065_lifecycle_proof(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=bad_verifier,
    )
    assert res_bad.state == GateState.MISSING
    assert res_bad.must_id == "PD-CH2-065"


def test_f2_verified_record_omitting_evaluator_record_ref_fails_closed():
    """R3-1 / F-7: A VERIFIED canonical record omitting evaluator_record_ref must fail closed to MISSING[PD-CH2-065]."""
    payload = _canonical_payload()
    no_ref_verifier = lambda ref: {
        "status": "VERIFIED",
        "gate_output": "SATISFIED",
    }
    # Direct evaluator
    res = evaluate_ch2_065_lifecycle_proof(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=no_ref_verifier,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"
    assert "MISSING[PD-CH2-065]" in res.failures

    # Public gate
    res_gate = evaluate_replay_gate(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=no_ref_verifier,
    )
    assert res_gate.state == GateState.MISSING
    assert res_gate.must_id == "PD-CH2-065"


def test_f2_verified_record_omitting_gate_output_fails_closed():
    """R3-1 / F-7: A VERIFIED canonical record omitting gate_output must fail closed to MISSING[PD-CH2-065]."""
    payload = _canonical_payload()
    no_out_verifier = lambda ref: {
        "evaluator_record_ref": "REC-AUTH-001",
        "status": "VERIFIED",
    }
    # Direct evaluator
    res = evaluate_ch2_065_lifecycle_proof(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=no_out_verifier,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"
    assert "MISSING[PD-CH2-065]" in res.failures

    # Public gate
    res_gate = evaluate_replay_gate(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=no_out_verifier,
    )
    assert res_gate.state == GateState.MISSING
    assert res_gate.must_id == "PD-CH2-065"


def test_f2_verified_record_omitting_both_ref_and_output_fails_closed():
    """R3-1 / F-7: A VERIFIED canonical record omitting BOTH fields must fail closed to MISSING[PD-CH2-065]."""
    payload = _canonical_payload()
    bare_verified = lambda ref: {"status": "VERIFIED"}
    # Direct evaluator
    res = evaluate_ch2_065_lifecycle_proof(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=bare_verified,
    )
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"
    assert "MISSING[PD-CH2-065]" in res.failures

    # Public gate
    res_gate = evaluate_replay_gate(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=bare_verified,
    )
    assert res_gate.state == GateState.MISSING
    assert res_gate.must_id == "PD-CH2-065"


def test_f2_verified_record_empty_or_whitespace_fields_fail_closed():
    """R3-1 / F-7: Empty or whitespace-only record_ref or gate_output in verified record fails closed."""
    payload = _canonical_payload()
    for empty_val in ["", "   ", "\t\n", None]:
        v1 = lambda ref, e=empty_val: {"status": "VERIFIED", "evaluator_record_ref": e, "gate_output": "SATISFIED"}
        res1 = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY, record_verifier=v1)
        assert res1.state == GateState.MISSING
        assert res1.must_id == "PD-CH2-065"

        v2 = lambda ref, e=empty_val: {"status": "VERIFIED", "evaluator_record_ref": "REC-AUTH-001", "gate_output": e}
        res2 = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY, record_verifier=v2)
        assert res2.state == GateState.MISSING
        assert res2.must_id == "PD-CH2-065"

