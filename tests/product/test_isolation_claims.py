"""Tests for Block 4 Lane E (Test Isolation Write Protection & Evidence Claim Verification).

Test matrix: MUST x {gaming, happy, no-authority, malformed/None fail-closed, mutation per decision branch}.
MUSTs covered:
- PD-CH4-010: P6 MUST exclude bound TestInputSet from writes; P7 evidence uses same manifest.
- PD-CH4-014: Observed delta outside authorized scope returns BLOCKED; cannot accept by green test.
- PD-CH4-016: Independence claims MUST name distinct evidence producers; self-review prohibited.
- PD-CH4-002: Execution claims MUST bind structured results and raw result digest.
- PD-CH4-005: Evidence freshness and independence evaluated from bound identity; old evidence staled.
- PD-CH4-006: False-completion recorded only from canonical events; prose has no closure authority.
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.isolation_claims import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch4_010_test_input_write_isolation,
    evaluate_pd_ch4_014_authorized_delta_scope,
    evaluate_pd_ch4_016_independent_evidence_producers,
    evaluate_pd_ch4_002_execution_claim_receipt,
    evaluate_pd_ch4_005_evidence_freshness_identity,
    evaluate_pd_ch4_006_canonical_closure_vs_prose,
    evaluate_b4_e_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -----------------------------------------------------------------------------
# PD-CH4-010
# -----------------------------------------------------------------------------
def test_ch4_010_happy_path():
    out = evaluate_pd_ch4_010_test_input_write_isolation(
        implementation_write_paths=["src/feature.py"],
        test_input_paths=["tests/test_feature.py", "conftest.py"],
        manifest_unchanged=True,
        environment_digest_match=True,
        test_is_green=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-010"


def test_ch4_010_gaming_write_overlap_test_inputs():
    out = evaluate_pd_ch4_010_test_input_write_isolation(
        implementation_write_paths=["src/feature.py", "tests/test_feature.py"],
        test_input_paths=["tests/test_feature.py"],
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-010"
    assert "implementation writes touch paths in bound TestInputSet" in out.detail


def test_ch4_010_gaming_altered_manifest():
    out = evaluate_pd_ch4_010_test_input_write_isolation(
        implementation_write_paths=["src/feature.py"],
        test_input_paths=["tests/test_feature.py"],
        manifest_unchanged=False,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "altered manifest" in out.detail


def test_ch4_010_no_authority():
    assert evaluate_pd_ch4_010_test_input_write_isolation([], [], authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH4-014
# -----------------------------------------------------------------------------
def test_ch4_014_happy_path():
    out = evaluate_pd_ch4_014_authorized_delta_scope(
        observed_delta_paths=["src/feature.py"],
        authorized_write_paths=["src/feature.py", "src/helper.py"],
        green_test_run=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-014"


def test_ch4_014_gaming_unauthorized_scope_delta():
    out = evaluate_pd_ch4_014_authorized_delta_scope(
        observed_delta_paths=["src/feature.py", "config/security.json"],
        authorized_write_paths=["src/feature.py"],
        green_test_run=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-014"
    assert "action_result: BLOCKED" in out.detail


def test_ch4_014_no_authority():
    assert evaluate_pd_ch4_014_authorized_delta_scope([], [], authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH4-016
# -----------------------------------------------------------------------------
def test_ch4_016_happy_path():
    out = evaluate_pd_ch4_016_independent_evidence_producers(
        primary_producer="producer-primary@1.0",
        independent_producer="verifier-indep@2.0",
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-016"


def test_ch4_016_gaming_self_review():
    out = evaluate_pd_ch4_016_independent_evidence_producers(
        primary_producer="worker-1",
        independent_producer="worker-1",
        is_self_review=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-016"
    assert "Self-review prohibited" in out.detail


def test_ch4_016_gaming_shared_unqualified_adapter():
    out = evaluate_pd_ch4_016_independent_evidence_producers(
        primary_producer="worker-1",
        independent_producer="worker-2",
        shared_unqualified_adapter=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Shared unqualified adapter" in out.detail


def test_ch4_016_no_authority_and_none():
    assert evaluate_pd_ch4_016_independent_evidence_producers("p1", "p2", authority=None).state == GateState.MISSING
    assert evaluate_pd_ch4_016_independent_evidence_producers(None, None, authority=AUTH).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH4-002
# -----------------------------------------------------------------------------
def test_ch4_002_happy_path():
    out = evaluate_pd_ch4_002_execution_claim_receipt(
        has_execution_claim=True,
        has_structured_results=True,
        raw_result_digest="sha256:raw123",
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-002"


def test_ch4_002_gaming_agent_says_pass_without_receipt():
    out = evaluate_pd_ch4_002_execution_claim_receipt(
        has_execution_claim=True,
        has_structured_results=False,
        raw_result_digest=None,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-002"
    assert "without structured results receipt" in out.detail


def test_ch4_002_no_claim_and_no_authority():
    assert evaluate_pd_ch4_002_execution_claim_receipt(False, False, None, authority=AUTH).state == GateState.SATISFIED
    assert evaluate_pd_ch4_002_execution_claim_receipt(True, True, "sha", authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH4-005
# -----------------------------------------------------------------------------
def test_ch4_005_happy_path():
    out = evaluate_pd_ch4_005_evidence_freshness_identity(
        requirement_revision_digest="sha256:req_v1",
        evidence_requirement_digest="sha256:req_v1",
        target_identity_match=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-005"


def test_ch4_005_gaming_changed_requirement_old_evidence():
    out = evaluate_pd_ch4_005_evidence_freshness_identity(
        requirement_revision_digest="sha256:req_v2",
        evidence_requirement_digest="sha256:req_v1_stale",
        target_identity_match=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-005"
    assert "evidence stale" in out.detail


def test_ch4_005_target_mismatch_and_no_authority():
    assert evaluate_pd_ch4_005_evidence_freshness_identity("d", "d", target_identity_match=False, authority=AUTH).state == GateState.MISSING
    assert evaluate_pd_ch4_005_evidence_freshness_identity("d", "d", authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH4-006
# -----------------------------------------------------------------------------
def test_ch4_006_happy_path():
    out = evaluate_pd_ch4_006_canonical_closure_vs_prose(
        agent_prose_done_claim=True,
        kernel_obligation_closure=True,
        has_admissible_evidence=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-006"


def test_ch4_006_gaming_agent_says_done_closure_absent():
    out = evaluate_pd_ch4_006_canonical_closure_vs_prose(
        agent_prose_done_claim=True,
        kernel_obligation_closure=False,
        has_admissible_evidence=False,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-006"
    assert "Agent says done but closure absent" in out.detail


def test_ch4_006_no_claim_and_no_authority():
    assert evaluate_pd_ch4_006_canonical_closure_vs_prose(False, False, False, authority=AUTH).state == GateState.SATISFIED
    assert evaluate_pd_ch4_006_canonical_closure_vs_prose(True, True, True, authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# Aggregate Gate
# -----------------------------------------------------------------------------
def test_evaluate_b4_e_gate_aggregate():
    payload = {
        "implementation_write_paths": ["src/f.py"],
        "test_input_paths": ["tests/t.py"],
        "observed_delta_paths": ["src/f.py"],
        "authorized_write_paths": ["src/f.py"],
        "primary_producer": "p1",
        "independent_producer": "p2",
        "has_execution_claim": True,
        "has_structured_results": True,
        "raw_result_digest": "sha256:raw",
        "requirement_revision_digest": "sha256:r1",
        "evidence_requirement_digest": "sha256:r1",
        "agent_prose_done_claim": True,
        "kernel_obligation_closure": True,
        "has_admissible_evidence": True,
    }
    gate_out = evaluate_b4_e_gate(payload, authority=AUTH)
    assert len(gate_out) == 6
    for m_id, res in gate_out.items():
        assert res.state == GateState.SATISFIED
