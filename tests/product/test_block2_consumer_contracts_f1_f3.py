"""Block 2 Consumer Contract tests for F1 (artifacts) and F3 (trust_model).

Mandated by GATE-B brief and Round 4 W4:
- F1 and F3 public consumer-contract verification
- No-source non-SATISFIED (all authority must be caller-injected)
- Payload claims (resolved / fresh / closed / approved / verified) cannot grant authority
- Public APIs only, including new F3 injected sources (protocols & in-memory implementations)
- GateOutput contract compliance (GateState closed vocabulary, to_dict schema)
- Strict fail-closed semantics on invalid, raising, or falsified inputs
"""

import hashlib
import pytest
from typing import Any, Dict, Mapping, Optional

from sclass import canonical_c1
from sclass.product.artifacts import (
    QUALIFIED_EVALUATOR_BOUNDARY as F1_BOUNDARY,
    evaluate_f1_representation,
    freeze_to_c1_compatible,
)
from sclass.product.gate import GateOutput, GateState
from sclass.product.trust_model import (
    ConfirmationEventSource,
    HostAttestationSource,
    InMemoryConfirmationEventSource,
    InMemoryHostAttestationSource,
    evaluate_f3_trust,
)


# =============================================================================
# 1. F1 Consumer Contracts: No-Source Non-SATISFIED & Anti-Payload-Granting
# =============================================================================

def test_f1_consumer_contract_empty_payload_fails_closed():
    """F1: Empty payload without injected sources fails closed to non-SATISFIED."""
    res = evaluate_f1_representation({})
    assert isinstance(res, GateOutput)
    assert res != GateState.SATISFIED
    assert res.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F1-003"
    assert str(res).startswith("MISSING")


def test_f1_consumer_contract_payload_claims_cannot_grant_authority():
    """F1: Payload claims (resolved/fresh/closed/approved/verified) cannot grant authority."""
    # Attempt 1: Payload claims self-approval
    spec_self_approved = {
        "proposed": {"predicate": "x <= 20"},
        "confirmed": {"predicate": "x <= 10"},
        "authoritative_approval": "DECISION-42",
        "approved": True,
        "approval_status": "APPROVED",
        "claim_status": "RESOLVED",
        "freshness": "FRESH",
        "lifecycle_state": "CLOSED",
    }
    res1 = evaluate_f1_representation(spec_self_approved)
    assert res1 != GateState.SATISFIED
    assert res1.state == GateState.BLOCKED_ON_HUMAN
    assert res1.must_id == "PD-F1-005"

    # Attempt 2: Payload claims independent verifier pass
    spec_verifier_claim = {
        "agent_result": "PASS",
        "independent_verifier_result": "PASS",
        "verifier_status": "PASS",
        "verified": True,
        "resolved": True,
        "closed": True,
    }
    res2 = evaluate_f1_representation(spec_verifier_claim)
    assert res2 != GateState.SATISFIED
    assert res2.state == GateState.MISSING
    assert res2.must_id == "PD-F1-002"

    # Attempt 3: Payload injects structural diff procedure string or function
    spec_proc_claim = {
        "proposed": {"predicate": "x <= 20"},
        "confirmed": {"predicate": "x <= 10"},
        "structural_diff_procedure": lambda c, p: False,
        "authoritative_approval": "DECISION-OVERRIDE",
    }
    res3 = evaluate_f1_representation(spec_proc_claim)
    assert res3 != GateState.SATISFIED
    assert res3.state == GateState.BLOCKED_ON_HUMAN
    assert res3.must_id == "PD-F1-005"


def test_f1_consumer_contract_injected_authority_grants_satisfied():
    """F1: Only genuine caller-injected dependencies grant SATISFIED."""
    # Injected independent verifier
    res_v = evaluate_f1_representation(
        {"agent_result": "PASS"},
        independent_verifier_result="PASS",
    )
    assert res_v == GateState.SATISFIED
    assert res_v.state == GateState.SATISFIED

    # Injected non-weakening structural diff procedure
    res_nw = evaluate_f1_representation(
        {"proposed": {"predicate": "x <= 10"}},
        confirmed_artifact={"predicate": "x <= 10"},
        structural_diff_procedure=lambda c, p: False,
    )
    assert res_nw == GateState.SATISFIED
    assert res_nw.state == GateState.SATISFIED

    # Injected weakening procedure WITH valid caller-injected approval
    res_w = evaluate_f1_representation(
        {"proposed": {"predicate": "x <= 20"}},
        confirmed_artifact={"predicate": "x <= 10"},
        structural_diff_procedure=lambda c, p: True,
        authoritative_approval="AUTH-DECISION-2026",
    )
    assert res_w == GateState.SATISFIED
    assert res_w.state == GateState.SATISFIED


def test_f1_consumer_contract_whitespace_approval_or_raising_diff_fails_closed():
    """F1: Whitespace-only approval or exception in diff procedure fails closed."""
    # Whitespace approval
    res_ws = evaluate_f1_representation(
        {"proposed": {"predicate": "x <= 20"}},
        confirmed_artifact={"predicate": "x <= 10"},
        structural_diff_procedure=lambda c, p: True,
        authoritative_approval="   \t\n  ",
    )
    assert res_ws != GateState.SATISFIED
    assert res_ws.state == GateState.BLOCKED_ON_HUMAN

    # Procedure exception
    def bad_proc(c: Any, p: Any) -> bool:
        raise ValueError("diff engine error")

    res_err = evaluate_f1_representation(
        {"proposed": {"predicate": "x <= 20"}},
        confirmed_artifact={"predicate": "x <= 10"},
        structural_diff_procedure=bad_proc,
        authoritative_approval="AUTH-DECISION-2026",
    )
    assert res_err != GateState.SATISFIED
    assert res_err.state == GateState.BLOCKED_ON_HUMAN


# =============================================================================
# 2. F3 Consumer Contracts: No-Source Non-SATISFIED & Anti-Payload-Granting
# =============================================================================

def test_f3_consumer_contract_empty_payload_fails_closed():
    """F3: Empty spec without injected sources fails closed to non-SATISFIED."""
    res = evaluate_f3_trust({})
    assert isinstance(res, GateOutput)
    assert res != GateState.SATISFIED
    assert res.state in (GateState.MISSING, GateState.BLOCKED_ON_HUMAN)


def test_f3_consumer_contract_payload_claims_cannot_grant_authority():
    """F3: Payload claims (resolved/fresh/closed/approved) cannot grant authority."""
    form = {"req_id": "REQ-GATE-B2", "body": "Audit log"}
    raw = canonical_c1(freeze_to_c1_compatible(form))
    digest = hashlib.sha256(raw).hexdigest()

    # Payload claims requirement confirmation event
    spec_conf = {
        "requirement_id": "REQ-GATE-B2",
        "requirement_confirmation": {
            "event_type": "REQUIREMENT_CONFIRMED",
            "authority": "USER",
            "source_provenance": digest,
        },
        "canonical_structured_form": form,
        "canonical_structured_form_digest": digest,
        "status": "APPROVED",
        "resolved": True,
        "fresh": True,
        "closed": True,
    }
    res1 = evaluate_f3_trust(spec_conf)
    assert res1 != GateState.SATISFIED
    assert res1.state == GateState.MISSING
    assert res1.must_id == "PD-F3-004"

    # Payload claims host custody facts
    spec_custody = {
        "confirmation_surface": "host_native",
        "principal_key_accessible_to_agent": False,
        "approval_forwarding_tool_available": False,
        "user_presence_required": True,
        "status": "APPROVED",
        "attestation_status": "VALID",
        "resolved": True,
        "fresh": True,
    }
    res2 = evaluate_f3_trust(spec_custody)
    assert res2 != GateState.SATISFIED
    assert res2.state == GateState.BLOCKED_ON_HUMAN
    assert res2.must_id == "PD-F3-006"


def test_f3_consumer_contract_injected_sources_grant_satisfied():
    """F3: Genuine caller-injected sources grant SATISFIED via public API."""
    # 1. Injected ConfirmationEventSource
    form = {"req_id": "REQ-GATE-B2-SUCCESS", "body": "Audit log verified"}
    raw = canonical_c1(freeze_to_c1_compatible(form))
    digest = hashlib.sha256(raw).hexdigest()

    event = {
        "event_type": "REQUIREMENT_CONFIRMED",
        "authority": "USER",
        "source_provenance": digest,
    }
    conf_source = InMemoryConfirmationEventSource(event=event, canonical_structured_form=form)

    res_conf = evaluate_f3_trust(
        {"requirement_id": "REQ-GATE-B2-SUCCESS"},
        confirmation_event_source=conf_source,
    )
    assert res_conf == GateState.SATISFIED
    assert res_conf.state == GateState.SATISFIED

    # 2. Injected HostAttestationSource
    attest_source = InMemoryHostAttestationSource(
        confirmation_surface="host_native",
        principal_key_accessible_to_agent=False,
        approval_forwarding_tool_available=False,
        user_presence_required=True,
    )
    res_attest = evaluate_f3_trust(
        {"confirmation_surface": "host_native"},
        host_attestation_source=attest_source,
    )
    assert res_attest == GateState.SATISFIED
    assert res_attest.state == GateState.SATISFIED


def test_f3_consumer_contract_failing_or_tampered_sources_fail_closed():
    """F3: Faulty, raising, or mismatching injected sources fail closed."""
    # Source raising exception
    class RaisingConfSource:
        def get_confirmation(self, requirement_id: Optional[str] = None) -> Any:
            raise RuntimeError("Database unavailable")

    res_raise = evaluate_f3_trust(
        {"requirement_id": "REQ-FAULTY"},
        confirmation_event_source=RaisingConfSource(),  # type: ignore[arg-type]
    )
    assert res_raise != GateState.SATISFIED
    assert res_raise.state == GateState.MISSING
    assert res_raise.must_id == "PD-F3-004"

    # Host source returning agent-accessible key
    bad_attest = InMemoryHostAttestationSource(
        confirmation_surface="host_native",
        principal_key_accessible_to_agent=True,  # Inadmissible
        approval_forwarding_tool_available=False,
        user_presence_required=True,
    )
    res_bad_host = evaluate_f3_trust(
        {"confirmation_surface": "host_native"},
        host_attestation_source=bad_attest,
    )
    assert res_bad_host != GateState.SATISFIED
    assert res_bad_host.state == GateState.BLOCKED_ON_HUMAN
    assert res_bad_host.must_id == "PD-F3-006"


# =============================================================================
# 3. GateOutput Schema & Invariant Contracts
# =============================================================================

def test_consumer_contract_gate_output_shape_and_invariants():
    """F1 and F3 public evaluators always return conforming GateOutput objects."""
    # Evaluators never return raw bool or None
    res_f1 = evaluate_f1_representation({})
    res_f3 = evaluate_f3_trust({})

    for r in (res_f1, res_f3):
        assert isinstance(r, GateOutput)
        assert r.state in (GateState.SATISFIED, GateState.MISSING, GateState.BLOCKED_ON_HUMAN)
        assert hasattr(r, "must_id")
        assert hasattr(r, "failures")
        assert hasattr(r, "explain")

        d = r.to_dict()
        assert isinstance(d, dict)
        assert "state" in d
        assert "failures" in d
        assert "explain" in d
        assert d["state"] in ("SATISFIED", "MISSING", "BLOCKED_ON_HUMAN")
        # DENIED is NEVER a GateState
        assert d["state"] != "DENIED"
