"""Tests for Block 4 Lane A (F10 Adapter Qualification Contract & Verification).

Test matrix: MUST x {gaming, happy, no-authority, malformed/None fail-closed, mutation per decision branch}.
MUSTs covered:
- PD-F10-001: Executable-spec tooling MUST be invoked only through declared F10 adapter contract and category.
- PD-F10-002: A usable adapter MUST bind immutable identity, schemas, qualification and frozen evidence-binding fields.
- PD-F10-003: Only authorized non-agent authority may register/change adapters; changed digest stales evidence.
- PD-F10-004: Adapter execution MUST pass through ExecutionGate with lease, budget, and fence.
- PD-F10-005: Qualification MUST pass all 14 frozen adapter tests, A1, A2, and A3.
- PD-F10-006: CRITICAL-lane independent verification MUST use qualified independent verifier.
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.adapter_qualification_contract import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    FROZEN_EVIDENCE_BINDING_FIELDS,
    FROZEN_ADAPTER_TESTS,
    ADDITIONAL_PRODUCT_TESTS,
    DECLARED_ADAPTER_CATEGORIES,
    evaluate_pd_f10_001_contract_invocation,
    evaluate_pd_f10_002_usable_adapter_binding,
    evaluate_pd_f10_003_adapter_registration_authority,
    evaluate_pd_f10_004_execution_gate_enforcement,
    evaluate_pd_f10_005_qualification_matrix,
    evaluate_pd_f10_006_independent_verification,
    evaluate_b4_a_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -----------------------------------------------------------------------------
# PD-F10-001
# -----------------------------------------------------------------------------
def test_f10_001_happy_path():
    out = evaluate_pd_f10_001_contract_invocation(
        tool_call={"tool_identity": "validator-x", "version": "1.2.3"},
        adapter_record={"declared_contract": True, "category": "syntax-validator"},
        category="syntax-validator",
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-F10-001"


def test_f10_001_gaming_undeclared_direct_call():
    out = evaluate_pd_f10_001_contract_invocation(
        tool_call={"tool_identity": "validator-x", "version": "1.2.3"},
        adapter_record=None,
        category="syntax-validator",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F10-001"


def test_f10_001_no_authority_fails_closed():
    out = evaluate_pd_f10_001_contract_invocation(
        tool_call={"tool_identity": "validator-x"},
        adapter_record={"declared_contract": True},
        category="syntax-validator",
        authority=None,
    )
    assert out.state == GateState.MISSING
    assert "Caller lacks qualified evaluator authority" in out.detail


def test_f10_001_malformed_and_unknown_category():
    out_none = evaluate_pd_f10_001_contract_invocation(None, None, authority=AUTH)
    assert out_none.state == GateState.MISSING

    out_cat = evaluate_pd_f10_001_contract_invocation(
        tool_call={"tool_identity": "x"},
        adapter_record={"declared": True},
        category="unregistered-hack-category",
        authority=AUTH,
    )
    assert out_cat.state == GateState.MISSING
    assert "Undeclared adapter category" in out_cat.detail


# -----------------------------------------------------------------------------
# PD-F10-002
# -----------------------------------------------------------------------------
def test_f10_002_happy_path():
    out = evaluate_pd_f10_002_usable_adapter_binding(
        {
            "adapter_id": "A-1",
            "tool_identity": "validator-x@1.2.3",
            "qualification_record_ref": "QR-99",
            "evidence_binding_fields": list(FROZEN_EVIDENCE_BINDING_FIELDS),
        },
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-F10-002"


def test_f10_002_gaming_missing_qualification_and_fields():
    out = evaluate_pd_f10_002_usable_adapter_binding(
        {
            "adapter_id": "A-1",
            "tool_identity": "validator-x@1.2.3",
            "qualification_record_ref": None,
            "evidence_binding_fields": ["obligation_id", "target_snapshot"],
        },
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F10-002"


def test_f10_002_no_authority_fails_closed():
    out = evaluate_pd_f10_002_usable_adapter_binding(
        {"qualification_record_ref": "QR-1", "evidence_binding_fields": list(FROZEN_EVIDENCE_BINDING_FIELDS)},
        authority="INVALID",
    )
    assert out.state == GateState.MISSING
    assert "Caller lacks qualified evaluator authority" in out.detail


def test_f10_002_malformed_and_partial_fields():
    assert evaluate_pd_f10_002_usable_adapter_binding(None, authority=AUTH).state == GateState.MISSING
    out = evaluate_pd_f10_002_usable_adapter_binding(
        {"qualification_record_ref": "QR-1", "evidence_binding_fields": ["raw_result_digest"]},
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Adapter omits frozen evidence-binding fields" in out.detail


# -----------------------------------------------------------------------------
# PD-F10-003
# -----------------------------------------------------------------------------
def test_f10_003_happy_path():
    out = evaluate_pd_f10_003_adapter_registration_authority(
        actor="lead-architect",
        operation="REGISTER_ADAPTER",
        canonical_write_authorized=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-F10-003"


def test_f10_003_gaming_agent_attempt():
    out = evaluate_pd_f10_003_adapter_registration_authority(
        actor="agent",
        operation="REGISTER_ADAPTER",
        canonical_write_authorized=False,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F10-003"


def test_f10_003_gaming_changed_digest_stales_evidence():
    out = evaluate_pd_f10_003_adapter_registration_authority(
        actor="admin",
        operation="VERIFY_ADAPTER",
        canonical_write_authorized=True,
        evidence_adapter_digest="sha256:11111111",
        current_adapter_digest="sha256:22222222",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Adapter digest changed after evidence receipt" in out.detail


def test_f10_003_no_authority_and_unauthorized_write():
    out_noauth = evaluate_pd_f10_003_adapter_registration_authority("admin", "REG", True, authority=None)
    assert out_noauth.state == GateState.MISSING
    assert "Caller lacks qualified evaluator authority" in out_noauth.detail

    out_unauth = evaluate_pd_f10_003_adapter_registration_authority("user", "REG", False, authority=AUTH)
    assert out_unauth.state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-F10-004
# -----------------------------------------------------------------------------
def test_f10_004_happy_path():
    out = evaluate_pd_f10_004_execution_gate_enforcement(
        authorized_request={"id": "REQ-1"},
        execution_lease={"lease_id": "L-1"},
        budget_reservation={"cost": 10},
        fence={"fence_id": "F-1"},
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-F10-004"


def test_f10_004_gaming_execution_gate_bypass():
    out = evaluate_pd_f10_004_execution_gate_enforcement(
        authorized_request=None,
        execution_lease=None,
        budget_reservation=None,
        fence=None,
        worker_execute_attempt=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F10-004"


def test_f10_004_timeout_failure():
    out = evaluate_pd_f10_004_execution_gate_enforcement(
        authorized_request={"id": "REQ-1"},
        execution_lease={"lease_id": "L-1"},
        budget_reservation={"cost": 10},
        fence={"fence_id": "F-1"},
        execution_timeout=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Adapter execution timed out" in out.detail


def test_f10_004_no_authority():
    out = evaluate_pd_f10_004_execution_gate_enforcement({"id": "1"}, {"id": "1"}, {"id": "1"}, {"id": "1"}, authority=None)
    assert out.state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-F10-005
# -----------------------------------------------------------------------------
def _all_pass_tests():
    frozen = {t: {"result": "PASS"} for t in FROZEN_ADAPTER_TESTS}
    additional = {t: {"result": "PASS"} for t in ADDITIONAL_PRODUCT_TESTS}
    return frozen, additional


def test_f10_005_happy_path():
    frozen, additional = _all_pass_tests()
    out = evaluate_pd_f10_005_qualification_matrix(frozen, additional, authority=AUTH)
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-F10-005"


def test_f10_005_gaming_differential_detection_failure():
    frozen, additional = _all_pass_tests()
    additional["A2_differential_result_detection"] = {"result": "FAIL"}
    out = evaluate_pd_f10_005_qualification_matrix(frozen, additional, authority=AUTH)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F10-005"
    assert "A2_differential_result_detection" in out.detail


def test_f10_005_frozen_test_missing_or_failed():
    frozen, additional = _all_pass_tests()
    frozen["timeout"] = {"result": "FAIL"}
    out = evaluate_pd_f10_005_qualification_matrix(frozen, additional, authority=AUTH)
    assert out.state == GateState.MISSING
    assert "timeout" in out.detail


def test_f10_005_no_authority_and_none_payload():
    assert evaluate_pd_f10_005_qualification_matrix(None, None, authority=None).state == GateState.MISSING
    assert evaluate_pd_f10_005_qualification_matrix(None, None, authority=AUTH).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-F10-006
# -----------------------------------------------------------------------------
def test_f10_006_happy_path_critical():
    out = evaluate_pd_f10_006_independent_verification(
        is_critical_lane=True,
        qualified_independent_verifier="verifier-b@4.2",
        primary_result="PASS",
        independent_result="PASS",
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-F10-006"


def test_f10_006_gaming_no_verifier_blocks_on_human():
    out = evaluate_pd_f10_006_independent_verification(
        is_critical_lane=True,
        qualified_independent_verifier=None,
        primary_result="PASS",
        independent_result=None,
        authority=AUTH,
    )
    assert out.state == GateState.BLOCKED_ON_HUMAN
    assert out.must_id == "PD-F10-006"


def test_f10_006_gaming_contradiction_missing():
    out = evaluate_pd_f10_006_independent_verification(
        is_critical_lane=True,
        qualified_independent_verifier="verifier-b@4.2",
        primary_result="PASS",
        independent_result="FAIL",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F10-006"
    assert "Contradiction" in out.detail


def test_f10_006_non_critical_lane_satisfied():
    out = evaluate_pd_f10_006_independent_verification(
        is_critical_lane=False,
        qualified_independent_verifier=None,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED


def test_f10_006_no_authority():
    out = evaluate_pd_f10_006_independent_verification(True, "verifier-b", "PASS", "PASS", authority=None)
    assert out.state == GateState.MISSING


# -----------------------------------------------------------------------------
# Aggregate Gate
# -----------------------------------------------------------------------------
def test_evaluate_b4_a_gate_aggregate():
    frozen, additional = _all_pass_tests()
    payload = {
        "tool_call": {"tool_identity": "val"},
        "adapter_record": {"declared_contract": True},
        "category": "syntax-validator",
        "adapter": {
            "qualification_record_ref": "QR",
            "evidence_binding_fields": list(FROZEN_EVIDENCE_BINDING_FIELDS),
        },
        "actor": "admin",
        "operation": "REG",
        "canonical_write_authorized": True,
        "authorized_request": {"id": 1},
        "execution_lease": {"id": 1},
        "budget_reservation": {"id": 1},
        "fence": {"id": 1},
        "frozen_required_tests": frozen,
        "additional_product_tests": additional,
        "is_critical_lane": True,
        "qualified_independent_verifier": "ver",
        "primary_result": "PASS",
        "independent_result": "PASS",
    }
    gate_out = evaluate_b4_a_gate(payload, authority=AUTH)
    assert len(gate_out) == 6
    for m_id, res in gate_out.items():
        assert res.state == GateState.SATISFIED
