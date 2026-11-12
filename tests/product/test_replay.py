"""Tests for Replay & Invalidation Gates (PD-CH2-064, PD-CH2-065).

Verifies:
- PD-CH2-064: CH2-T73 (gaming bypass attacks A1..A3) and CH2-T74 (happy conforming).
- PD-CH2-065: CH2-T75 (gaming prose/forgery attacks A1..A4) and CH2-T76 (happy conforming).
- Fail-closed authority enforcement and payload integrity.
"""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.replay import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_ch2_064_replay_invalidation,
    evaluate_ch2_065_lifecycle_proof,
    evaluate_replay_gate,
)


# =============================================================================
# 1. PD-CH2-064 Invalidation & Replay Restart Tests
# =============================================================================

def test_pd_ch2_064_happy_fixture_ch2_t74():
    """CH2-T74: Conforming case: replay starts at earliest affected phase -> SATISFIED."""
    payload = {
        "must_id": "PD-CH2-064",
        "dependency_set_digest": "DEP-SET-001",
        "earliest_affected_phase": "P2",
        "replay_start_phase": "P2",
    }
    res = evaluate_ch2_064_replay_invalidation(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_064_gaming_fixture_ch2_t73_variant_a1():
    """CH2-T73 A1: earliest_affected_phase=P2, replay_start_phase=P5 -> MISSING[PD-CH2-064]."""
    payload = {
        "must_id": "PD-CH2-064",
        "dependency_set_digest": "DEP-SET-001",
        "earliest_affected_phase": "P2",
        "replay_start_phase": "P5",
    }
    res = evaluate_ch2_064_replay_invalidation(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-064"
    assert str(res) == "MISSING[PD-CH2-064]"


def test_pd_ch2_064_gaming_fixture_ch2_t73_variant_a2():
    """CH2-T73 A2: replay_start_phase absent after invalidation -> MISSING[PD-CH2-064]."""
    payload = {
        "must_id": "PD-CH2-064",
        "dependency_set_digest": "DEP-SET-001",
        "earliest_affected_phase": "P2",
    }
    res = evaluate_ch2_064_replay_invalidation(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-064"


def test_pd_ch2_064_gaming_fixture_ch2_t73_variant_a3():
    """CH2-T73 A3: agent sets replay_start_phase=P7 to skip stale work -> MISSING[PD-CH2-064]."""
    payload = {
        "must_id": "PD-CH2-064",
        "dependency_set_digest": "DEP-SET-001",
        "earliest_affected_phase": "P1",
        "replay_start_phase": "P7",
    }
    res = evaluate_ch2_064_replay_invalidation(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-064"


# =============================================================================
# 2. PD-CH2-065 Lifecycle Proof Example Tests
# =============================================================================

def test_pd_ch2_065_happy_fixture_ch2_t76():
    """CH2-T76: Conforming case: fully bound proof example with verified canonical record -> SATISFIED."""
    payload = {
        "must_id": "PD-CH2-065",
        "example_preconditions": {"target": "rate_limiter", "window_sec": 60},
        "bound_input_digests": ["DIGEST-PRE-01", "DIGEST-IN-01"],
        "expected_gate_output": "SATISFIED",
        "failure_route": None,
        "evaluator_record_ref": "EVAL-REC-001",
    }
    verifier = lambda ref: {
        "evaluator_record_ref": "EVAL-REC-001",
        "status": "VERIFIED",
        "gate_output": "SATISFIED",
    } if ref == "EVAL-REC-001" else None

    res = evaluate_ch2_065_lifecycle_proof(
        payload,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=verifier,
    )
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


def test_pd_ch2_065_gaming_fixture_ch2_t75_variant_a1():
    """CH2-T75 A1: expected_gate_output absent (prose-only example) -> MISSING[PD-CH2-065]."""
    payload = {
        "must_id": "PD-CH2-065",
        "example_preconditions": {"target": "rate_limiter"},
        "bound_input_digests": ["DIGEST-PRE-01"],
        "evaluator_record_ref": "EVAL-REC-001",
    }
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"


def test_pd_ch2_065_gaming_fixture_ch2_t75_variant_a2():
    """CH2-T75 A2: bound_input_digests missing or empty -> MISSING[PD-CH2-065]."""
    payload = {
        "must_id": "PD-CH2-065",
        "example_preconditions": {"target": "rate_limiter"},
        "bound_input_digests": [],
        "expected_gate_output": "SATISFIED",
        "evaluator_record_ref": "EVAL-REC-001",
    }
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"


def test_pd_ch2_065_gaming_fixture_ch2_t75_variant_a3():
    """CH2-T75 A3: agent supplies example with forged/agent evaluator ref -> MISSING[PD-CH2-065]."""
    payload = {
        "must_id": "PD-CH2-065",
        "example_preconditions": {"target": "rate_limiter"},
        "bound_input_digests": ["DIGEST-PRE-01"],
        "expected_gate_output": "SATISFIED",
        "evaluator_record_ref": "forged",
    }
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"


def test_pd_ch2_065_gaming_fixture_ch2_t75_variant_a4():
    """CH2-T75 A4: failure_route absent or mismatch with expected failure -> MISSING[PD-CH2-065]."""
    payload = {
        "must_id": "PD-CH2-065",
        "example_preconditions": {"target": "rate_limiter"},
        "bound_input_digests": ["DIGEST-PRE-01"],
        "expected_gate_output": "MISSING[PD-CH2-065]",
        "failure_route": "WRONG_ROUTE",
        "evaluator_record_ref": "EVAL-REC-001",
    }
    res = evaluate_ch2_065_lifecycle_proof(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-065"


# =============================================================================
# 3. Security & Authority Negative Tests
# =============================================================================

def test_unauthorized_replay_caller_rejected():
    """Fails closed when caller_authority is omitted or incorrect."""
    payload = {"dependency_set_digest": "DEP-SET-001", "earliest_affected_phase": "P2", "replay_start_phase": "P2"}
    res_none = evaluate_ch2_064_replay_invalidation(payload, caller_authority=None)
    assert res_none.state == GateState.MISSING
    assert res_none.must_id == "PD-CH2-064"

    res_agent = evaluate_ch2_064_replay_invalidation(payload, caller_authority="AGENT")
    assert res_agent.state == GateState.MISSING
    assert res_agent.must_id == "PD-CH2-064"


def test_unified_evaluate_replay_gate_entrypoint():
    """Verifies evaluate_replay_gate dispatch."""
    p64 = {
        "must_id": "PD-CH2-064",
        "dependency_set_digest": "D1",
        "earliest_affected_phase": "P1",
        "replay_start_phase": "P1",
    }
    res64 = evaluate_replay_gate(p64, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res64.state == GateState.SATISFIED

    p65 = {
        "must_id": "PD-CH2-065",
        "example_preconditions": {"k": "v"},
        "bound_input_digests": ["D1"],
        "expected_gate_output": "SATISFIED",
        "evaluator_record_ref": "EVAL-1",
    }
    verifier65 = lambda ref: {
        "evaluator_record_ref": "EVAL-1",
        "status": "VERIFIED",
        "gate_output": "SATISFIED",
    } if ref == "EVAL-1" else None
    res65 = evaluate_replay_gate(
        p65,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        record_verifier=verifier65,
    )
    assert res65.state == GateState.SATISFIED
