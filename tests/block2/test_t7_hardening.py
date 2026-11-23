"""Tests for T7: F0 hardening re-audit (fail-closed defaults and security field validation)."""
from __future__ import annotations

import pytest
from sclass.product.gate import GateState
from sclass.product.lifecycle_p5 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_036_adapter_qualification,
)
from sclass.product.traceability import LinkType, TraceLink, compute_link_id
from sclass.product.claim_ledger import ClaimRecord


def test_lifecycle_p5_is_f10_qualified_defaults_false() -> None:
    out = evaluate_pd_ch2_036_adapter_qualification(
        "pytest-sclass",
        authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH2-036"


@pytest.mark.parametrize("bad_link_id", [False, 0, "", "   "])
def test_trace_link_from_dict_rejects_falsy_or_blank_link_id(bad_link_id: object) -> None:
    raw = {
        "type": LinkType.REQUIREMENT_TO_ACCEPTANCE.value,
        "source": "REQ-001",
        "destination": "ACC-001",
        "link_id": bad_link_id,
    }
    with pytest.raises(ValueError, match="TraceLink link_id when provided must be a non-empty string"):
        TraceLink.from_dict(raw)


def test_trace_link_from_dict_accepts_valid_or_none_link_id() -> None:
    # None / omitted computes valid id
    raw_none = {
        "type": LinkType.REQUIREMENT_TO_ACCEPTANCE.value,
        "source": "REQ-001",
        "destination": "ACC-001",
    }
    link1 = TraceLink.from_dict(raw_none)
    expected_id = compute_link_id(LinkType.REQUIREMENT_TO_ACCEPTANCE, "REQ-001", "ACC-001")
    assert link1.link_id == expected_id

    # Matching link_id succeeds
    raw_valid = dict(raw_none, link_id=expected_id)
    link2 = TraceLink.from_dict(raw_valid)
    assert link2.link_id == expected_id

    # Tampered link_id raises ValueError
    raw_tampered = dict(raw_none, link_id="bad_digest_deadbeef")
    with pytest.raises(ValueError, match="Tampered or mismatched link_id"):
        TraceLink.from_dict(raw_tampered)


def test_claim_record_content_digest_guarantee() -> None:
    rec = ClaimRecord(
        claim_id="CLM-001",
        type="behavioral",
        subject="SUBJ-001",
        created_by_delta=True,
        evidence_refs=["EVID-001"],
    )
    d = rec.to_dict()
    assert isinstance(d["content_digest"], str)
    assert len(d["content_digest"]) == 64
    assert d["content_digest"] != ""


def test_enforcement_workspace_gate_authoritative_host_cost_omitted_returns_missing() -> None:
    from sclass.product.enforcement_workspace_gate import (
        QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B5,
        evaluate_pd_ch8_013_budget_exhaustion_ledger,
    )
    # Fix-before: previously this returned SATISFIED because authoritative_host_cost defaulted True.
    # Now it fails closed and returns MISSING.
    out = evaluate_pd_ch8_013_budget_exhaustion_ledger(
        budget_exhausted=False,
        routed_to_authorized_repair=False,
        authority=AUTH_B5,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH8-013"
    assert out.detail == "authoritative_host_cost must be an exact boolean and present"


@pytest.mark.parametrize("bad_val", ["True", 1, 0, None, [], {}, 1.0])
def test_enforcement_workspace_gate_authoritative_host_cost_non_bool_returns_missing(bad_val: object) -> None:
    from sclass.product.enforcement_workspace_gate import (
        QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B5,
        evaluate_pd_ch8_013_budget_exhaustion_ledger,
    )
    out = evaluate_pd_ch8_013_budget_exhaustion_ledger(
        budget_exhausted=False,
        routed_to_authorized_repair=False,
        authoritative_host_cost=bad_val,  # type: ignore[arg-type]
        authority=AUTH_B5,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH8-013"
    assert out.detail == "authoritative_host_cost must be an exact boolean and present"


def test_enforcement_workspace_gate_authoritative_host_cost_true_satisfied() -> None:
    from sclass.product.enforcement_workspace_gate import (
        QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B5,
        evaluate_pd_ch8_013_budget_exhaustion_ledger,
    )
    out = evaluate_pd_ch8_013_budget_exhaustion_ledger(
        budget_exhausted=False,
        routed_to_authorized_repair=False,
        authoritative_host_cost=True,
        authority=AUTH_B5,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH8-013"


def test_enforcement_workspace_gate_authoritative_host_cost_false_returns_missing() -> None:
    from sclass.product.enforcement_workspace_gate import (
        QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B5,
        evaluate_pd_ch8_013_budget_exhaustion_ledger,
    )
    out = evaluate_pd_ch8_013_budget_exhaustion_ledger(
        budget_exhausted=False,
        routed_to_authorized_repair=False,
        authoritative_host_cost=False,
        authority=AUTH_B5,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH8-013"

