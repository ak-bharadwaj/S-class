"""Permanent regression tests for F3 authority model hardening (Task 4 / F3-FIX).

Verifies that authority for requirement confirmation (PD-F3-004) and host attestation
(PD-F3-006) derives strictly from caller-injected dependencies (ConfirmationEventSource,
HostAttestationSource), never from untrusted specification payloads or candidate claims.
"""

import hashlib
import pytest
from typing import Any, Mapping, Optional

from sclass import canonical_c1
from sclass.product.artifacts import freeze_to_c1_compatible
from sclass.product.trust_model import (
    ConfirmationEventSource,
    HostAttestationSource,
    InMemoryConfirmationEventSource,
    InMemoryHostAttestationSource,
    GateOutput,
    GateState,
    evaluate_f3_trust,
)


class RaisingConfirmationSource:
    """Mock source that raises an exception during confirmation lookup."""

    def get_confirmation(self, requirement_id: Optional[str] = None) -> Any:
        raise RuntimeError("Injected confirmation source connection timeout")


class RaisingHostAttestationSource:
    """Mock source that raises an exception during attestation lookup."""

    def get_host_attestation(self) -> Any:
        raise RuntimeError("Injected host attestation hardware failure")


class NonMappingHostAttestationSource:
    """Mock source that returns non-mapping object."""

    def get_host_attestation(self) -> Any:
        return "not_a_mapping"


class TruthyNonExactHostAttestationSource:
    """Mock source that returns truthy non-boolean facts."""

    def get_host_attestation(self) -> Mapping[str, Any]:
        return {
            "confirmation_surface": "host_native",
            "principal_key_accessible_to_agent": 0,  # int 0 instead of False
            "approval_forwarding_tool_available": False,
            "user_presence_required": 1,  # int 1 instead of True
        }


def test_probe_f3_d_payload_custody_facts_without_host_attestation_fails_closed():
    """F3-D probe: payload confirmation custody facts with no injected host source must NOT be SATISFIED."""
    spec_f3_d = {
        "confirmation_surface": "host_native",
        "principal_key_accessible_to_agent": False,
        "approval_forwarding_tool_available": False,
        "user_presence_required": True,
    }
    result = evaluate_f3_trust(spec_f3_d, host_attestation_source=None)
    assert result != GateState.SATISFIED
    assert result == "BLOCKED_ON_HUMAN[PD-F3-006]"
    assert result.state == GateState.BLOCKED_ON_HUMAN
    assert result.must_id == "PD-F3-006"


def test_probe_f3_e_payload_requirement_confirmation_without_event_source_fails_closed():
    """F3-E probe: payload REQUIREMENT_CONFIRMED event with matching provenance without injected source must NOT be SATISFIED."""
    form_f3_e = {"req_id": "REQ-101", "text": "Audited requirement"}
    raw_form = canonical_c1(freeze_to_c1_compatible(form_f3_e))
    digest_f3_e = hashlib.sha256(raw_form).hexdigest()
    spec_f3_e = {
        "requirement_confirmation": {
            "event_type": "REQUIREMENT_CONFIRMED",
            "authority": "USER",
            "source_provenance": digest_f3_e,
        },
        "canonical_structured_form": form_f3_e,
        "canonical_structured_form_digest": digest_f3_e,
    }
    result = evaluate_f3_trust(spec_f3_e, confirmation_event_source=None)
    assert result != GateState.SATISFIED
    assert result == "MISSING[PD-F3-004]"
    assert result.state == GateState.MISSING
    assert result.must_id == "PD-F3-004"


def test_omitted_authority_arguments_never_produce_satisfied():
    """Omitted keyword-only authority arguments default to None and fail closed."""
    spec_custody = {
        "confirmation_surface": "host_native",
        "principal_key_accessible_to_agent": False,
        "approval_forwarding_tool_available": False,
        "user_presence_required": True,
    }
    out_custody = evaluate_f3_trust(spec_custody)
    assert out_custody == "BLOCKED_ON_HUMAN[PD-F3-006]"

    form = {"req_id": "REQ-omitted"}
    raw = canonical_c1(freeze_to_c1_compatible(form))
    digest = hashlib.sha256(raw).hexdigest()
    spec_conf = {
        "requirement_confirmation": {
            "event_type": "REQUIREMENT_CONFIRMED",
            "authority": "USER",
            "source_provenance": digest,
        },
        "canonical_structured_form": form,
        "canonical_structured_form_digest": digest,
    }
    out_conf = evaluate_f3_trust(spec_conf)
    assert out_conf == "MISSING[PD-F3-004]"


def test_injected_host_attestation_source_valid_produces_satisfied():
    """Valid injected host attestation source produces SATISFIED."""
    source = InMemoryHostAttestationSource(
        confirmation_surface="host_native",
        principal_key_accessible_to_agent=False,
        approval_forwarding_tool_available=False,
        user_presence_required=True,
    )
    spec = {"confirmation_surface": "host_native"}
    result = evaluate_f3_trust(spec, host_attestation_source=source)
    assert result == GateState.SATISFIED
    assert result.state == GateState.SATISFIED


def test_injected_host_attestation_source_raising_fails_closed():
    """Host attestation source raising exception fails closed to BLOCKED_ON_HUMAN[PD-F3-006]."""
    source = RaisingHostAttestationSource()
    spec = {"confirmation_surface": "host_native"}
    result = evaluate_f3_trust(spec, host_attestation_source=source)
    assert result == "BLOCKED_ON_HUMAN[PD-F3-006]"
    assert result.state == GateState.BLOCKED_ON_HUMAN
    assert result.must_id == "PD-F3-006"


def test_injected_host_attestation_source_returning_none_fails_closed():
    """Host attestation source returning None fails closed to BLOCKED_ON_HUMAN[PD-F3-006]."""
    class NoneSource:
        def get_host_attestation(self):
            return None

    spec = {"confirmation_surface": "host_native"}
    result = evaluate_f3_trust(spec, host_attestation_source=NoneSource())
    assert result == "BLOCKED_ON_HUMAN[PD-F3-006]"


def test_injected_host_attestation_source_non_mapping_fails_closed():
    """Host attestation source returning non-mapping fails closed to BLOCKED_ON_HUMAN[PD-F3-006]."""
    source = NonMappingHostAttestationSource()
    spec = {"confirmation_surface": "host_native"}
    result = evaluate_f3_trust(spec, host_attestation_source=source)
    assert result == "BLOCKED_ON_HUMAN[PD-F3-006]"


def test_injected_host_attestation_source_truthy_non_exact_fails_closed():
    """Host attestation source returning truthy non-boolean values fails closed."""
    source = TruthyNonExactHostAttestationSource()
    spec = {"confirmation_surface": "host_native"}
    result = evaluate_f3_trust(spec, host_attestation_source=source)
    assert result == "BLOCKED_ON_HUMAN[PD-F3-006]"


def test_source_supplied_but_payload_contradicts_with_untrusted_surface_stays_blocked():
    """Valid host attestation source cannot grant authority if payload specifies untrusted surface."""
    source = InMemoryHostAttestationSource(
        confirmation_surface="host_native",
        principal_key_accessible_to_agent=False,
        approval_forwarding_tool_available=False,
        user_presence_required=True,
    )
    spec = {
        "confirmation_surface": "untrusted_web_agent",
        "principal_key_accessible_to_agent": True,
    }
    result = evaluate_f3_trust(spec, host_attestation_source=source)
    assert result == "BLOCKED_ON_HUMAN[PD-F3-006]"
    assert result.state == GateState.BLOCKED_ON_HUMAN


def test_injected_confirmation_event_source_valid_produces_satisfied():
    """Valid injected confirmation event source produces SATISFIED."""
    form = {"req_id": "REQ-200", "description": "Critical requirement"}
    raw = canonical_c1(freeze_to_c1_compatible(form))
    digest = hashlib.sha256(raw).hexdigest()

    event = {
        "event_type": "REQUIREMENT_CONFIRMED",
        "authority": "USER",
        "source_provenance": digest,
    }
    source = InMemoryConfirmationEventSource(event=event, canonical_structured_form=form)

    spec = {"requirement_id": "REQ-200"}
    result = evaluate_f3_trust(spec, confirmation_event_source=source)
    assert result == GateState.SATISFIED
    assert result.state == GateState.SATISFIED


def test_injected_confirmation_event_source_raising_fails_closed():
    """Confirmation event source raising exception fails closed to MISSING[PD-F3-004]."""
    source = RaisingConfirmationSource()
    spec = {"requirement_id": "REQ-200"}
    result = evaluate_f3_trust(spec, confirmation_event_source=source)
    assert result == "MISSING[PD-F3-004]"
    assert result.state == GateState.MISSING
    assert result.must_id == "PD-F3-004"


def test_injected_confirmation_event_source_returning_none_fails_closed():
    """Confirmation event source returning None fails closed to MISSING[PD-F3-004]."""
    source = InMemoryConfirmationEventSource(event=None)
    spec = {"requirement_id": "REQ-200"}
    result = evaluate_f3_trust(spec, confirmation_event_source=source)
    assert result == "MISSING[PD-F3-004]"


def test_injected_confirmation_event_source_non_exact_type_or_authority_fails_closed():
    """Injected event with non-exact event_type or authority (e.g. AGENT) fails closed."""
    form = {"req_id": "REQ-200"}
    raw = canonical_c1(freeze_to_c1_compatible(form))
    digest = hashlib.sha256(raw).hexdigest()

    # Agent authority
    agent_evt = {
        "event_type": "REQUIREMENT_CONFIRMED",
        "authority": "AGENT",
        "source_provenance": digest,
    }
    src_agent = InMemoryConfirmationEventSource(event=agent_evt, canonical_structured_form=form)
    res_agent = evaluate_f3_trust({"requirement_id": "REQ-200"}, confirmation_event_source=src_agent)
    assert res_agent == "MISSING[PD-F3-004]"

    # Wrong event type
    wrong_type_evt = {
        "event_type": "REQUIREMENT_UPDATED",
        "authority": "USER",
        "source_provenance": digest,
    }
    src_type = InMemoryConfirmationEventSource(event=wrong_type_evt, canonical_structured_form=form)
    res_type = evaluate_f3_trust({"requirement_id": "REQ-200"}, confirmation_event_source=src_type)
    assert res_type == "MISSING[PD-F3-004]"


def test_injected_confirmation_event_source_digest_mismatch_blocks():
    """Injected event where digest changed after confirmation fails to BLOCKED_ON_HUMAN[PD-F3-004]."""
    form = {"req_id": "REQ-200", "version": "v2"}
    raw = canonical_c1(freeze_to_c1_compatible(form))
    digest = hashlib.sha256(raw).hexdigest()

    event = {
        "event_type": "REQUIREMENT_CONFIRMED",
        "authority": "USER",
        "source_provenance": "sha256_old_digest_prior_to_change",
    }
    source = InMemoryConfirmationEventSource(event=event, canonical_structured_form=form)
    result = evaluate_f3_trust({"requirement_id": "REQ-200"}, confirmation_event_source=source)
    assert result == "BLOCKED_ON_HUMAN[PD-F3-004]"
    assert result.state == GateState.BLOCKED_ON_HUMAN
    assert result.must_id == "PD-F3-004"


def test_injected_confirmation_valid_but_payload_conflicting_digest_stays_blocked():
    """Injected confirmation is valid but payload specifies conflicting digest -> stays blocked."""
    form = {"req_id": "REQ-200"}
    raw = canonical_c1(freeze_to_c1_compatible(form))
    digest = hashlib.sha256(raw).hexdigest()

    event = {
        "event_type": "REQUIREMENT_CONFIRMED",
        "authority": "USER",
        "source_provenance": digest,
    }
    source = InMemoryConfirmationEventSource(event=event, canonical_structured_form=form)
    spec = {
        "requirement_id": "REQ-200",
        "canonical_structured_form_digest": "conflicting_tampered_digest",
    }
    result = evaluate_f3_trust(spec, confirmation_event_source=source)
    assert result == "BLOCKED_ON_HUMAN[PD-F3-004]"
    assert result.state == GateState.BLOCKED_ON_HUMAN
