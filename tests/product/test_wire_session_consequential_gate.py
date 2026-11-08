"""Unit and regression tests for Chapter 7 Wire Session & Consequential Actions Gate (Block 7, Lane B7-A).

Covers:
- PD-CH7-016: Wire request/response protocol envelope
- PD-CH7-008: Guidance resources versioning, bounds, subordination
- PD-CH7-009: Protocol idempotent retries and typed version conflict error
- PD-CH7-011: IDE mode capability declaration (E0/E1/E2)
- PD-CH7-012: Session identity bindings and transport authority rejection
- PD-CH7-013: Consequential developer actions authorization and observations
"""
import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.wire_session_consequential_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    SUPPORTED_PROTOCOL_VERSIONS,
    IDE_CAPABILITY_TIERS,
    REQUIRED_SESSION_BINDINGS,
    evaluate_pd_ch7_016_wire_protocol_envelope,
    evaluate_pd_ch7_008_guidance_resources,
    evaluate_pd_ch7_009_protocol_idempotent_retries,
    evaluate_pd_ch7_011_ide_mode_capabilities,
    evaluate_pd_ch7_012_session_identity_bindings,
    evaluate_pd_ch7_013_consequential_developer_actions,
    evaluate_b7_a_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


class TestPDCH7016WireProtocolEnvelope:
    def test_authority_enforced(self):
        res = evaluate_pd_ch7_016_wire_protocol_envelope({}, {}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-016"

    def test_missing_request_or_response(self):
        res1 = evaluate_pd_ch7_016_wire_protocol_envelope(None, {}, authority=AUTH)
        assert res1.state == GateState.MISSING
        res2 = evaluate_pd_ch7_016_wire_protocol_envelope({}, None, authority=AUTH)
        assert res2.state == GateState.MISSING

    def test_unsupported_protocol_version(self):
        req = {"protocol_version": "99.0", "task_id": "T1", "session_id": "S1"}
        resp = {"request_id": "R1", "result": "OK", "next_action": "NONE", "resource_refs": [], "error": None}
        res = evaluate_pd_ch7_016_wire_protocol_envelope(req, resp, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-016"

    def test_missing_canonical_refs(self):
        req = {"protocol_version": "1.0", "task_id": None, "session_id": "S1"}
        resp = {"request_id": "R1", "result": "OK", "next_action": "NONE", "resource_refs": [], "error": None}
        res = evaluate_pd_ch7_016_wire_protocol_envelope(req, resp, authority=AUTH)
        assert res.state == GateState.MISSING

    def test_valid_wire_envelope(self):
        req = {"protocol_version": "1.0", "task_id": "T1", "session_id": "S1"}
        resp = {"request_id": "R1", "result": "OK", "next_action": "NONE", "resource_refs": [], "error": None}
        res = evaluate_pd_ch7_016_wire_protocol_envelope(req, resp, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH7008GuidanceResources:
    def test_authority_enforced(self):
        res = evaluate_pd_ch7_008_guidance_resources(True, True, True, authority=None)
        assert res.state == GateState.MISSING

    @pytest.mark.parametrize("v,b,s", [
        (False, True, True),
        (True, False, True),
        (True, True, False),
    ])
    def test_guidance_resource_failures(self, v, b, s):
        res = evaluate_pd_ch7_008_guidance_resources(v, b, s, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-008"

    def test_guidance_resource_satisfied(self):
        res = evaluate_pd_ch7_008_guidance_resources(True, True, True, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH7009ProtocolIdempotentRetries:
    def test_authority_enforced(self):
        res = evaluate_pd_ch7_009_protocol_idempotent_retries(True, authority=None)
        assert res.state == GateState.MISSING

    def test_non_idempotent_retry(self):
        res = evaluate_pd_ch7_009_protocol_idempotent_retries(False, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-009"

    def test_version_conflict_without_typed_error(self):
        res = evaluate_pd_ch7_009_protocol_idempotent_retries(
            idempotent_under_request_identity=True,
            version_conflict_typed_error=False,
            conflict_detected=True,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-009"

    def test_retry_satisfied(self):
        res = evaluate_pd_ch7_009_protocol_idempotent_retries(
            idempotent_under_request_identity=True,
            version_conflict_typed_error=True,
            conflict_detected=True,
            authority=AUTH,
        )
        assert res.state == GateState.SATISFIED


class TestPDCH7011IDEModeCapabilities:
    def test_authority_enforced(self):
        res = evaluate_pd_ch7_011_ide_mode_capabilities(True, "E1", authority=None)
        assert res.state == GateState.MISSING

    def test_unqualified_host(self):
        res = evaluate_pd_ch7_011_ide_mode_capabilities(False, "E1", authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-011"

    def test_invalid_tier(self):
        res = evaluate_pd_ch7_011_ide_mode_capabilities(True, "E3", authority=AUTH)
        assert res.state == GateState.MISSING

    @pytest.mark.parametrize("tier", list(IDE_CAPABILITY_TIERS))
    def test_valid_tiers_satisfied(self, tier):
        res = evaluate_pd_ch7_011_ide_mode_capabilities(True, tier, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH7012SessionIdentityBindings:
    def test_authority_enforced(self):
        res = evaluate_pd_ch7_012_session_identity_bindings({}, authority=None)
        assert res.state == GateState.MISSING

    def test_transport_claims_authority_rejected(self):
        bindings = {f: f"val_{f}" for f in REQUIRED_SESSION_BINDINGS}
        res = evaluate_pd_ch7_012_session_identity_bindings(
            bindings, transport_claims_canonical_authority=True, authority=AUTH
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-012"

    @pytest.mark.parametrize("missing_field", list(REQUIRED_SESSION_BINDINGS))
    def test_missing_session_bindings(self, missing_field):
        bindings = {f: f"val_{f}" for f in REQUIRED_SESSION_BINDINGS}
        del bindings[missing_field]
        res = evaluate_pd_ch7_012_session_identity_bindings(bindings, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-012"

    def test_session_bindings_satisfied(self):
        bindings = {f: f"val_{f}" for f in REQUIRED_SESSION_BINDINGS}
        res = evaluate_pd_ch7_012_session_identity_bindings(bindings, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH7013ConsequentialDeveloperActions:
    def test_authority_enforced(self):
        res = evaluate_pd_ch7_013_consequential_developer_actions(True, True, authority=None)
        assert res.state == GateState.MISSING

    @pytest.mark.parametrize("auth_gate,obs", [
        (False, True),
        (True, False),
        (False, False),
    ])
    def test_consequential_action_failures(self, auth_gate, obs):
        res = evaluate_pd_ch7_013_consequential_developer_actions(auth_gate, obs, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-013"

    def test_consequential_action_satisfied(self):
        res = evaluate_pd_ch7_013_consequential_developer_actions(True, True, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestAggregateB7AGate:
    def test_aggregate_satisfied(self):
        payload = {
            "request": {"protocol_version": "1.0", "task_id": "T1", "session_id": "S1"},
            "response": {"request_id": "R1", "result": "OK", "next_action": "NONE", "resource_refs": [], "error": None},
            "versioned": True,
            "bounded": True,
            "subordinate_to_policy_and_kernel": True,
            "idempotent_under_request_identity": True,
            "version_conflict_typed_error": True,
            "conflict_detected": False,
            "host_qualified": True,
            "declared_tier": "E1",
            "session_bindings": {f: f"val_{f}" for f in REQUIRED_SESSION_BINDINGS},
            "transport_claims_canonical_authority": False,
            "authorization_scope_gate_passed": True,
            "admissible_observation_emitted": True,
        }
        res = evaluate_b7_a_gate(payload, authority=AUTH)
        assert len(res) == 6
        assert all(out.state == GateState.SATISFIED for out in res.values())

    def test_aggregate_no_authority(self):
        res = evaluate_b7_a_gate({}, authority=None)
        assert len(res) == 6
        assert all(out.state == GateState.MISSING for out in res.values())
