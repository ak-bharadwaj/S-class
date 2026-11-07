"""Tests for S-Class F5 Gate Evaluator Architecture and Projection Engine.

Validates normative requirements PD-F5-001 through PD-F5-005 and Appendix F
concrete test fixtures F5-T1 through F5-T7 under Master Section 5.1 (F5) and
R2-8 / WAVE1-FIX authority hardening.
"""

from __future__ import annotations

import copy
import pytest
from typing import Any, Dict, List, Optional, Tuple

from sclass.product.gate import GateOutput, GateState
from sclass.product.gate_evaluator import (
    FailureEntry,
    F5Result,
    QUALIFIED_EVALUATOR_BOUNDARY,
    compute_f5_cache_key,
    evaluate_f5_gate,
)
from sclass_semantics_v6_0_1 import AuthorizationState


# =============================================================================
# 1. Normative Appendix F Concrete Test Fixtures (F5-T1 through F5-T7)
# =============================================================================

def test_f5_t1_deterministic_replay_input() -> None:
    """F5-T1 / F5-FT1: Identical phase/state/guidance tuple evaluated twice.

    Expected: SATISFIED both times; canonical state unchanged; byte-identical digest.
    """
    tuple_args = {
        "phase": "P2",
        "canonical_state_binding": "SB-1",
        "pinned_guidance": "G-1",
        "policy_version": "P-7",
        "evaluator_version": "EV-3",
        "evaluation_instant": "2026-01-01T00:00:00Z",
        "relevant_input_digests": ["R-1", "AC-1"],
        "caller_authority": QUALIFIED_EVALUATOR_BOUNDARY,
        "kernel_decision": AuthorizationState.ALLOW,
    }
    state_before = copy.deepcopy(tuple_args)

    res1 = evaluate_f5_gate(**tuple_args)
    res2 = evaluate_f5_gate(**tuple_args)

    # Both must be SATISFIED
    assert res1.state == GateState.SATISFIED
    assert res2.state == GateState.SATISFIED
    assert res1.product_gate.state == GateState.SATISFIED
    assert res2.product_gate.state == GateState.SATISFIED
    assert res1.combined == "SATISFIED"
    assert res1.action_result == "ALLOWED"

    # Byte-identical digests
    assert res1.digest() == res2.digest()
    assert res1.cache_key == res2.cache_key
    assert res1.cache_key != ""

    # Canonical state unchanged
    assert tuple_args == state_before


def test_f5_t2_structured_gate_output_and_precedence() -> None:
    """F5-T2 / F5-FT2: Missing checks C-01, C-02 and blocked check C-09.

    Expected:
      state: MISSING
      failures: [{must_id: PD-F5-002, check_id: C-01, inputs_digest: D1},
                 {must_id: PD-F5-002, check_id: C-02, inputs_digest: D2}]
      explain: {blocked: [C-09]}
    """
    checks = [
        {"check_id": "C-02", "status": "MISSING", "must_id": "PD-F5-002", "inputs_digest": "D2"},
        {"check_id": "C-09", "status": "BLOCKED_ON_HUMAN", "inputs_digest": "D9"},
        {"check_id": "C-01", "status": "MISSING", "must_id": "PD-F5-002", "inputs_digest": "D1"},
    ]

    res = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB-2",
        pinned_guidance="G-2",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        checks=checks,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        kernel_decision=AuthorizationState.ALLOW,
    )

    assert res.state == GateState.MISSING
    assert res.product_gate.state == GateState.MISSING
    assert res.product_gate.must_id == "PD-F5-002"

    # Precedence: MISSING over BLOCKED_ON_HUMAN
    # Canonical sort: C-01 before C-02
    assert len(res.failures) == 2
    assert res.failures[0].check_id == "C-01"
    assert res.failures[0].inputs_digest == "D1"
    assert res.failures[1].check_id == "C-02"
    assert res.failures[1].inputs_digest == "D2"

    # explain.blocked lists C-09
    assert res.explain.get("blocked") == ["C-09"]

    # Serialized schema shape matches Appendix A GateOutput
    f5_dict = res.to_f5_dict()
    assert f5_dict["state"] == "MISSING"
    assert len(f5_dict["failures"]) == 2
    assert f5_dict["failures"][0] == {"must_id": "PD-F5-002", "check_id": "C-01", "inputs_digest": "D1"}
    assert f5_dict["failures"][1] == {"must_id": "PD-F5-002", "check_id": "C-02", "inputs_digest": "D2"}
    assert f5_dict["explain"]["blocked"] == ["C-09"]


def test_f5_t3_evaluator_timeout_and_version_mismatch() -> None:
    """F5-T3 / F5-FT3: Evaluator timeout and unpinned evaluator version.

    Case 1: executing_version='v6' differs from pinned_evaluator_version='v7'
            -> MISSING[PD-F5-003]
    Case 2: elapsed_ms=101 exceeds timeout_ms=100
            -> MISSING[PD-F5-003]
    """
    # Version mismatch
    res_version = evaluate_f5_gate(
        phase="P3",
        canonical_state_binding="SB-3",
        pinned_guidance="G-3",
        policy_version="P-7",
        evaluator_version="v6",
        pinned_evaluator_version="v7",
        evaluation_instant="2026-01-01T00:00:00Z",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert res_version.state == GateState.MISSING
    assert res_version.product_gate.must_id == "PD-F5-003"
    assert "PD-F5-003" in res_version.product_gate.failures

    # Timeout
    res_timeout = evaluate_f5_gate(
        phase="P3",
        canonical_state_binding="SB-3",
        pinned_guidance="G-3",
        policy_version="P-7",
        evaluator_version="v7",
        pinned_evaluator_version="v7",
        evaluation_instant="2026-01-01T00:00:00Z",
        timeout_ms=100,
        elapsed_ms=101,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert res_timeout.state == GateState.MISSING
    assert res_timeout.product_gate.must_id == "PD-F5-003"
    assert "PD-F5-003" in res_timeout.product_gate.failures


def test_f5_t4_cache_and_replay_identity() -> None:
    """F5-T4 / F5-FT4: Same digest tuple produces cache hit and replayed result."""
    tuple_args = {
        "phase": "P7",
        "canonical_state_binding": "SB-2",
        "pinned_guidance": "G-4",
        "policy_version": "P-7",
        "evaluator_version": "EV-3",
        "evaluation_instant": "2026-01-01T00:00:00Z",
        "relevant_input_digests": ["VS-2", "T-2", "E-2"],
        "caller_authority": QUALIFIED_EVALUATOR_BOUNDARY,
        "kernel_decision": AuthorizationState.ALLOW,
    }

    res1 = evaluate_f5_gate(**tuple_args)
    res2 = evaluate_f5_gate(**tuple_args)

    assert res1.state == GateState.SATISFIED
    assert res2.state == GateState.SATISFIED
    assert res1.cache_key == res2.cache_key
    assert res1.explanation_inputs_digest == res2.explanation_inputs_digest
    assert res1.digest() == res2.digest()


def test_f5_t5a_kernel_denial_wins_conflict_f1_preservation() -> None:
    """F5-T5a / F5-FT5a: Kernel ExecutionGate=DENIED, product check SATISFIED.

    Normative expectation from Appendix F fixture F5-T5a:
      expected_combined_result: DENIED
      action_result: BLOCKED
    Product gate preserves SATISFIED separately from combined DENIED under R2-8.
    """
    res = evaluate_f5_gate(
        phase="P5",
        canonical_state_binding="SB-5",
        pinned_guidance="G-5",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        kernel_decision=AuthorizationState.DENY,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )

    # Combined result is DENIED, action is BLOCKED
    assert res.combined == "DENIED"
    assert res.combined_result == "DENIED"
    assert res.action_result == "BLOCKED"

    # Product gate preserves pure product state (SATISFIED)
    assert res.product_gate.state == GateState.SATISFIED
    assert res.state == GateState.SATISFIED


def test_f5_t5b_product_block_applies_when_kernel_allows() -> None:
    """F5-T5b / F5-FT5b: Kernel ExecutionGate=ALLOWED, product check MISSING.

    Expected: combined MISSING[PD-F5-005], action BLOCKED.
    """
    checks = [
        {"check_id": "PROD_CHK_1", "status": "MISSING", "must_id": "PD-F5-005", "inputs_digest": "D_P1"}
    ]
    res = evaluate_f5_gate(
        phase="P5",
        canonical_state_binding="SB-5",
        pinned_guidance="G-5",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        checks=checks,
        kernel_decision=AuthorizationState.ALLOW,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )

    assert res.product_gate.state == GateState.MISSING
    assert res.combined == "MISSING[PD-F5-005]"
    assert res.action_result == "BLOCKED"
    assert res.product_gate.must_id == "PD-F5-005"


def test_f5_t5c_skill_added_check_cannot_remove_blocking() -> None:
    """F5-T5c / F5-FT5c: Skill-added check cannot turn BLOCKED_ON_HUMAN into SATISFIED.

    kernel_decision: ALLOW
    product_base_checks: BLOCKED_ON_HUMAN[PD-F5-005]
    skill_added_check: SATISFIED
    expected_combined_result: BLOCKED_ON_HUMAN[PD-F5-005]
    forbidden_result: SATISFIED
    """
    base_checks = [
        {"check_id": "HUMAN_APPROVAL_1", "status": "BLOCKED_ON_HUMAN", "must_id": "PD-F5-005"}
    ]
    skill_checks = [
        {"check_id": "SKILL_CHECK_1", "status": "SATISFIED", "must_id": "PD-F5-005"}
    ]

    res = evaluate_f5_gate(
        phase="P6",
        canonical_state_binding="SB-6",
        pinned_guidance="G-6",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        checks=base_checks,
        skill_added_checks=skill_checks,
        kernel_decision=AuthorizationState.ALLOW,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )

    assert res.state == GateState.BLOCKED_ON_HUMAN
    assert res.combined == "BLOCKED_ON_HUMAN[PD-F5-005]"
    assert res.action_result == "BLOCKED"
    assert res.state != GateState.SATISFIED


def test_f5_t6_replay_at_different_wall_time() -> None:
    """F5-T6 / F5-FT6: Replay at different wall-clock times with identical recorded tuple.

    Expected: byte-identical output; SATISFIED both times.
    """
    tuple_args = {
        "phase": "P7",
        "canonical_state_binding": "SB-2",
        "pinned_guidance": "G-4",
        "policy_version": "P-7",
        "evaluator_version": "EV-3",
        "evaluation_instant": "2026-01-01T00:00:00Z",
        "caller_authority": QUALIFIED_EVALUATOR_BOUNDARY,
        "kernel_decision": AuthorizationState.ALLOW,
    }

    res_at_wall_time_1 = evaluate_f5_gate(**tuple_args)
    res_at_wall_time_2 = evaluate_f5_gate(**tuple_args)

    assert res_at_wall_time_1.state == GateState.SATISFIED
    assert res_at_wall_time_2.state == GateState.SATISFIED
    assert res_at_wall_time_1.digest() == res_at_wall_time_2.digest()
    assert res_at_wall_time_1.to_f5_dict() == res_at_wall_time_2.to_f5_dict()


def test_f5_t7_triggering_record_carries_no_evaluation_instant() -> None:
    """F5-T7 / F5-FT7: Triggering record carries no evaluation_instant.

    Expected: MISSING[PD-F5-001].
    """
    res = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB-1",
        pinned_guidance="G-1",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant=None,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )

    assert res.state == GateState.MISSING
    assert res.product_gate.state == GateState.MISSING
    assert res.product_gate.must_id == "PD-F5-001"
    assert "PD-F5-001" in res.product_gate.failures


# =============================================================================
# 2. Authority, Frozen Kernel Enum Guard, and Replay Integrity Tests
# =============================================================================

def test_frozen_kernel_authorization_state_enum_members_present() -> None:
    """Guard test: validates named frozen kernel enum and members exist verbatim in sclass_semantics_v6_0_1."""
    import sclass_semantics_v6_0_1 as sem
    assert hasattr(sem, "AuthorizationState"), "Frozen kernel AuthorizationState enum is missing"
    AuthState = getattr(sem, "AuthorizationState")
    assert hasattr(AuthState, "ALLOW"), "AuthorizationState.ALLOW is missing"
    assert hasattr(AuthState, "DENY"), "AuthorizationState.DENY is missing"
    assert not hasattr(AuthState, "DENIED"), "AuthorizationState.DENIED must not exist in frozen kernel"


def test_caller_authority_omitted_returns_missing() -> None:
    """Binding authority rule: omitted caller_authority argument fails closed to MISSING."""
    res = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB-1",
        pinned_guidance="G-1",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
    )
    assert res.state == GateState.MISSING
    assert res.product_gate.must_id == "PD-F5-001"
    assert res.combined == "MISSING[PD-F5-001]"
    assert res.action_result == "BLOCKED"


def test_caller_authority_agent_and_unrecognized_rejected() -> None:
    """Binding authority rule: 'AGENT' and unrecognized strings fail closed to MISSING."""
    for bad_auth in ["AGENT", "UNKNOWN", "caller", "admin", ""]:
        res = evaluate_f5_gate(
            phase="P2",
            canonical_state_binding="SB-1",
            pinned_guidance="G-1",
            policy_version="P-7",
            evaluator_version="EV-3",
            evaluation_instant="2026-01-01T00:00:00Z",
            caller_authority=bad_auth,
        )
        assert res.state == GateState.MISSING
        assert res.product_gate.must_id == "PD-F5-001"


def test_kernel_decision_enum_composition() -> None:
    """Tests composition of injected frozen kernel decision enum with product result."""
    # Kernel DENY overrides product SATISFIED -> combined DENIED, action BLOCKED
    res_deny = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB-1",
        pinned_guidance="G-1",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        kernel_decision=AuthorizationState.DENY,
    )
    assert res_deny.product_gate.state == GateState.SATISFIED
    assert res_deny.combined == "DENIED"
    assert res_deny.action_result == "BLOCKED"

    # Kernel ALLOW adopts product SATISFIED -> combined SATISFIED, action ALLOWED
    res_allow = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB-1",
        pinned_guidance="G-1",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        kernel_decision=AuthorizationState.ALLOW,
    )
    assert res_allow.product_gate.state == GateState.SATISFIED
    assert res_allow.combined == "SATISFIED"
    assert res_allow.action_result == "ALLOWED"

    # Missing kernel decision -> combined MISSING[PD-F5-005], action BLOCKED
    res_none = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB-1",
        pinned_guidance="G-1",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
        kernel_decision=None,
    )
    assert res_none.product_gate.state == GateState.SATISFIED
    assert res_none.combined == "MISSING[PD-F5-005]"
    assert res_none.action_result == "BLOCKED"


# =============================================================================
# 3. Non-Normative Security, Adversarial, and Mutation Hardening Tests
# =============================================================================

@pytest.mark.parametrize(
    "instant_val",
    [None, "", "   "],
)
def test_non_normative_empty_or_whitespace_evaluation_instant_fails_closed(instant_val: Optional[str]) -> None:
    """Non-normative test: None, empty or whitespace evaluation_instant returns MISSING[PD-F5-001]."""
    res = evaluate_f5_gate(
        phase="P1",
        canonical_state_binding="SB-0",
        pinned_guidance="G-0",
        policy_version="P-1",
        evaluator_version="EV-1",
        evaluation_instant=instant_val,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert res.state == GateState.MISSING
    assert res.product_gate.must_id == "PD-F5-001"


def test_non_normative_no_injected_authority_negative_test() -> None:
    """Non-normative test: no-injected-authority negative test must never return SATISFIED."""
    # When missing authority / checks are signaled or missing instant
    res = evaluate_f5_gate(
        phase="P0",
        canonical_state_binding=None,
        pinned_guidance=None,
        policy_version="P-0",
        evaluator_version="EV-0",
        evaluation_instant=None,
        caller_authority=None,
    )
    assert res.state != GateState.SATISFIED
    assert res.state == GateState.MISSING


@pytest.mark.parametrize(
    "malformed_check",
    [
        "not_a_dict",
        123,
        None,
        {"status": "MISSING"},  # missing check_id
        {"check_id": "", "status": "MISSING"},  # empty check_id
        {"check_id": "C-1", "must_id": "", "status": "MISSING"},  # empty must_id
        {"check_id": "C-1", "inputs_digest": "", "status": "MISSING"},  # empty inputs_digest
    ],
)
def test_non_normative_malformed_checks_fail_closed_pd_f5_003(malformed_check: Any) -> None:
    """Non-normative test: malformed check inputs must fail closed with MISSING[PD-F5-003]."""
    res = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB",
        pinned_guidance="G",
        policy_version="P",
        evaluator_version="EV",
        evaluation_instant="2026-01-01T00:00:00Z",
        checks=[malformed_check],
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert res.state == GateState.MISSING
    assert res.product_gate.must_id == "PD-F5-003"


def test_non_normative_budget_exhaustion_fails_closed() -> None:
    """Non-normative test: budget_exhausted flag fails closed with MISSING[PD-F5-003]."""
    res = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB",
        pinned_guidance="G",
        policy_version="P",
        evaluator_version="EV",
        evaluation_instant="2026-01-01T00:00:00Z",
        budget_exhausted=True,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert res.state == GateState.MISSING
    assert res.product_gate.must_id == "PD-F5-003"


@pytest.mark.parametrize(
    "shuffled_order",
    [
        [("C-03", "MISSING"), ("C-01", "MISSING"), ("C-02", "MISSING"), ("C-09", "BLOCKED")],
        [("C-09", "BLOCKED"), ("C-02", "MISSING"), ("C-03", "MISSING"), ("C-01", "MISSING")],
        [("C-01", "MISSING"), ("C-09", "BLOCKED"), ("C-02", "MISSING"), ("C-03", "MISSING")],
    ],
)
def test_non_normative_shuffled_checks_produce_identical_canonical_sort(
    shuffled_order: List[Tuple[str, str]]
) -> None:
    """Non-normative test: Missing-over-blocked precedence and canonical sorting are independent of input order."""
    checks = [
        {"check_id": cid, "status": stat, "must_id": "PD-F5-002", "inputs_digest": f"D_{cid}"}
        for cid, stat in shuffled_order
    ]
    res = evaluate_f5_gate(
        phase="P4",
        canonical_state_binding="SB-4",
        pinned_guidance="G-4",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        checks=checks,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert res.state == GateState.MISSING
    assert [f.check_id for f in res.failures] == ["C-01", "C-02", "C-03"]
    assert res.explain.get("blocked") == ["C-09"]


def test_non_normative_failure_entry_immutability_and_validation() -> None:
    """Non-normative test: FailureEntry is immutable and validates field types."""
    fe = FailureEntry(must_id="PD-F5-002", check_id="C-01", inputs_digest="D1")
    assert fe.must_id == "PD-F5-002"
    assert fe.check_id == "C-01"
    assert fe.inputs_digest == "D1"

    with pytest.raises(Exception):
        fe.must_id = "OTHER"  # type: ignore

    with pytest.raises(ValueError):
        FailureEntry(must_id="", check_id="C-01", inputs_digest="D1")

    with pytest.raises(ValueError):
        FailureEntry(must_id="PD-F5-002", check_id="", inputs_digest="D1")

    with pytest.raises(ValueError):
        FailureEntry(must_id="PD-F5-002", check_id="C-01", inputs_digest="")


def test_non_normative_unknown_kernel_gate_value_fails_closed() -> None:
    """Non-normative test: non-standard kernel execution gate value fails closed."""
    res = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB",
        pinned_guidance="G",
        policy_version="P",
        evaluator_version="EV",
        evaluation_instant="2026-01-01T00:00:00Z",
        kernel_execution_gate="UNKNOWN_STATUS",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert res.product_gate.state == GateState.SATISFIED
    assert res.combined == "MISSING[PD-F5-005]"
    assert res.action_result == "BLOCKED"
