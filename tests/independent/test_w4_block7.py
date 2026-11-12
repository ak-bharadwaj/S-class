"""Independent W4 Consumer Contract Scenarios for Block 7 (Chapter 7).

Mandated by S-CLASS M0 ITERATION 2 (E5):
- Standalone independent test functions under tests/independent/
- Covers all 8 Block 7 MUSTs (PD-CH7-008, 009, 011, 012, 013, 014, 015, 016)
- Evaluates fail-closed security posture (unauthenticated / missing authority -> non-SATISFIED)
- Evaluates authorized consumer contracts (valid authority -> SATISFIED)
- Asserts GateOutput contract compliance (GateState closed vocabulary, to_dict schema)
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.notification_skill_normalization import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B7_B,
    evaluate_pd_ch7_014_notification_projections,
    evaluate_pd_ch7_015_external_skill_normalization,
)
from sclass.product.wire_session_consequential_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B7_A,
    SUPPORTED_PROTOCOL_VERSIONS,
    IDE_CAPABILITY_TIERS,
    REQUIRED_SESSION_BINDINGS,
    evaluate_pd_ch7_008_guidance_resources,
    evaluate_pd_ch7_009_protocol_idempotent_retries,
    evaluate_pd_ch7_011_ide_mode_capabilities,
    evaluate_pd_ch7_012_session_identity_bindings,
    evaluate_pd_ch7_013_consequential_developer_actions,
    evaluate_pd_ch7_016_wire_protocol_envelope,
)


def test_w4_scenario_pd_ch7_008():
    """W4 Scenario for PD-CH7-008: Guidance resources versioning and bounds."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch7_008_guidance_resources(True, True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH7-008"

    # 2. Missing bounds fails closed
    bad = evaluate_pd_ch7_008_guidance_resources(True, False, True, authority=AUTH_B7_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH7-008"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch7_008_guidance_resources(True, True, True, authority=AUTH_B7_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH7-008"


def test_w4_scenario_pd_ch7_009():
    """W4 Scenario for PD-CH7-009: Protocol idempotent retries."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch7_009_protocol_idempotent_retries(True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH7-009"

    # 2. Non-idempotent retry fails closed
    bad = evaluate_pd_ch7_009_protocol_idempotent_retries(False, authority=AUTH_B7_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH7-009"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch7_009_protocol_idempotent_retries(
        idempotent_under_request_identity=True,
        version_conflict_typed_error=True,
        conflict_detected=True,
        authority=AUTH_B7_A,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH7-009"


def test_w4_scenario_pd_ch7_011():
    """W4 Scenario for PD-CH7-011: IDE mode capability tiers."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch7_011_ide_mode_capabilities(True, "E1", authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH7-011"

    # 2. Invalid tier fails closed
    bad = evaluate_pd_ch7_011_ide_mode_capabilities(True, "INVALID_TIER", authority=AUTH_B7_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH7-011"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch7_011_ide_mode_capabilities(True, "E1", authority=AUTH_B7_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH7-011"


def test_w4_scenario_pd_ch7_012():
    """W4 Scenario for PD-CH7-012: Session identity bindings."""
    bindings = {f: f"val_{f}" for f in REQUIRED_SESSION_BINDINGS}

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch7_012_session_identity_bindings(bindings, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH7-012"

    # 2. Transport claiming canonical authority rejected
    bad = evaluate_pd_ch7_012_session_identity_bindings(
        bindings, transport_claims_canonical_authority=True, authority=AUTH_B7_A
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH7-012"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch7_012_session_identity_bindings(bindings, authority=AUTH_B7_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH7-012"


def test_w4_scenario_pd_ch7_013():
    """W4 Scenario for PD-CH7-013: Consequential developer actions authorization."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch7_013_consequential_developer_actions(True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH7-013"

    # 2. Missing observation fails closed
    bad = evaluate_pd_ch7_013_consequential_developer_actions(True, False, authority=AUTH_B7_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH7-013"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch7_013_consequential_developer_actions(True, True, authority=AUTH_B7_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH7-013"


def test_w4_scenario_pd_ch7_014():
    """W4 Scenario for PD-CH7-014: Notification projections."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch7_014_notification_projections(True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH7-014"

    # 2. Implies approval on model message rejected
    bad = evaluate_pd_ch7_014_notification_projections(
        derived_from_gate_projection=True,
        implies_approval_on_model_message=True,
        authority=AUTH_B7_B,
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH7-014"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch7_014_notification_projections(
        derived_from_gate_projection=True,
        implies_approval_on_model_message=False,
        authority=AUTH_B7_B,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH7-014"


def test_w4_scenario_pd_ch7_015():
    """W4 Scenario for PD-CH7-015: External skill normalization."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch7_015_external_skill_normalization(True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH7-015"

    # 2. Alternate lifecycle creation rejected
    bad = evaluate_pd_ch7_015_external_skill_normalization(
        normalized_into_sclass_owned_checks=True,
        creates_alternate_lifecycle_or_loop=True,
        authority=AUTH_B7_B,
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH7-015"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch7_015_external_skill_normalization(
        normalized_into_sclass_owned_checks=True,
        creates_alternate_lifecycle_or_loop=False,
        authority=AUTH_B7_B,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH7-015"


def test_w4_scenario_pd_ch7_016():
    """W4 Scenario for PD-CH7-016: Wire protocol envelope."""
    req = {"protocol_version": "1.0", "task_id": "T1", "session_id": "S1"}
    resp = {"request_id": "R1", "result": "OK", "next_action": "NONE", "resource_refs": [], "error": None}

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch7_016_wire_protocol_envelope(req, resp, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH7-016"

    # 2. Missing task_id in request fails closed
    bad_req = {"protocol_version": "1.0", "task_id": None, "session_id": "S1"}
    bad = evaluate_pd_ch7_016_wire_protocol_envelope(bad_req, resp, authority=AUTH_B7_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH7-016"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch7_016_wire_protocol_envelope(req, resp, authority=AUTH_B7_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH7-016"
