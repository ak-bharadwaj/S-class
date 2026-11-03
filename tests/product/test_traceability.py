"""Authoritative Test Suite for Section F6 Traceability Links & Computed Coverage.

Normative Reference:
    R30 Master Product Design (FREEZE-CANDIDATE-v6.0.2), Section F6.
    Obligations: PD-F6-001 through PD-F6-006.
    Authoritative Fixtures: F6-T1 through F6-T6.
"""

import hashlib
import pytest
from typing import Any, Dict

from sclass.product.traceability import (
    LinkType,
    NodeKind,
    SourceRefResolver,
    InMemorySourceRefResolver,
    TraceLink,
    TraceNode,
    compute_chain_coverage,
    compute_link_id,
    detect_orphan_nodes,
    evaluate_f6_traceability,
)
from sclass.product.trust_model import GateOutput, GateState


# =============================================================================
# 1. Authoritative R30 Fixture Tests (F6-T1 through F6-T6)
# =============================================================================

def test_f6_t1_complete_typed_chain():
    """F6-T1 / F6-FT1 — complete typed chain:
    Resolves Requirement R1, AC1, VS1, TEST1, EV1, OBL1 with typed links in order -> SATISFIED.
    """
    resolver = InMemorySourceRefResolver({
        "REQ-1": {"kind": "Requirement", "id": "REQ-1"},
        "AC-1": {"kind": "AcceptanceCriterion", "id": "AC-1"},
        "VS-1": {"kind": "VerificationStep", "id": "VS-1"},
        "TEST-1": {"kind": "Test", "id": "TEST-1"},
        "EV-1": {"kind": "Evidence", "id": "EV-1"},
        "OBL-1": {"kind": "Obligation", "id": "OBL-1"},
    })

    fixture_spec: Dict[str, Any] = {
        "nodes": ["REQ-1", "AC-1", "VS-1", "TEST-1", "EV-1", "OBL-1"],
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
            {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "VS-1"},
            {"type": "VERIFICATION_TO_TEST", "source": "VS-1", "destination": "TEST-1"},
            {"type": "TEST_TO_EVIDENCE", "source": "TEST-1", "destination": "EV-1"},
            {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-1", "destination": "OBL-1"},
        ],
        "source_refs": ["REQ-1", "AC-1", "VS-1", "TEST-1", "EV-1", "OBL-1"],
        "source_refs_resolve": True,
    }

    output = evaluate_f6_traceability(fixture_spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert output.state == GateState.SATISFIED
    assert output.must_id == "PD-F6-001"
    assert "verified" in output.detail.lower()


def test_f6_t2_orphan_verification_step():
    """F6-T2 / F6-FT2 — orphan verification step:
    Resolves VS-2 but it has no valid incoming AC link -> MISSING[PD-F6-002].
    """
    resolver = InMemorySourceRefResolver({
        "REQ-2": {"id": "REQ-2"},
        "AC-2": {"id": "AC-2"},
        "VS-2": {"id": "VS-2"},
        "TEST-2": {"id": "TEST-2"},
        "EV-2": {"id": "EV-2"},
        "OBL-2": {"id": "OBL-2"},
    })

    fixture_spec: Dict[str, Any] = {
        "nodes": ["REQ-2", "AC-2", "VS-2", "TEST-2", "EV-2", "OBL-2"],
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-2", "destination": "AC-2"},
            # Missing ACCEPTANCE_TO_VERIFICATION from AC-2 to VS-2
            {"type": "VERIFICATION_TO_TEST", "source": "VS-2", "destination": "TEST-2"},
            {"type": "TEST_TO_EVIDENCE", "source": "TEST-2", "destination": "EV-2"},
            {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-2", "destination": "OBL-2"},
        ],
        "source_refs": ["REQ-2", "AC-2", "VS-2", "TEST-2", "EV-2", "OBL-2"],
        "source_refs_resolve": True,
        "orphan_nodes": ["VS-2"],
    }

    output = evaluate_f6_traceability(fixture_spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert output.state == GateState.MISSING
    assert output.must_id == "PD-F6-002"
    assert "orphan" in output.detail.lower()
    assert "VS-2" in output.detail


def test_f6_t3_stable_link_identity_across_revision():
    """F6-T3 / F6-FT3 — stable link identity across revision:
    Link identity is stable across revision when source/destination stable IDs
    and link type remain unchanged, even when descriptions and revisions change.
    """
    link_type = "ACCEPTANCE_TO_VERIFICATION"
    source_stable_id = "AC-3"
    destination_stable_id = "VS-3"

    link_rev1 = TraceLink(
        link_type=LinkType.ACCEPTANCE_TO_VERIFICATION,
        source=source_stable_id,
        destination=destination_stable_id,
        revision=1,
        description="Rate limit accepted.",
    )

    link_rev2 = TraceLink(
        link_type=LinkType.ACCEPTANCE_TO_VERIFICATION,
        source=source_stable_id,
        destination=destination_stable_id,
        revision=2,
        description="Rate limit accepted with clarified wording.",
    )

    # Both must compute the exact same link_id matching golden vector
    expected_hash = "336f05112d86059abf4c921b63b0e866cd7cba74c82a5176f37e3faf743df41d"
    assert link_rev1.link_id == link_rev2.link_id
    assert link_rev1.link_id == expected_hash
    assert link_rev1.link_id == compute_link_id(link_type, source_stable_id, destination_stable_id)


def test_f6_t4_asserted_coverage_ignored():
    """F6-T4 / F6-FT4 — asserted coverage ignored:
    Artifact claims coverage=100% but misses Test -> Evidence link -> MISSING[PD-F6-004].
    """
    resolver = InMemorySourceRefResolver({
        "REQ-4": {}, "AC-4": {}, "VS-4": {}, "TEST-4": {}, "EV-4": {}, "OBL-4": {}
    })

    fixture_spec: Dict[str, Any] = {
        "nodes": ["REQ-4", "AC-4", "VS-4", "TEST-4", "EV-4", "OBL-4"],
        "agent_claimed_coverage_percent": 100,
        "resolved_links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-4", "destination": "AC-4"},
            {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-4", "destination": "VS-4"},
            {"type": "VERIFICATION_TO_TEST", "source": "VS-4", "destination": "TEST-4"},
            {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-4", "destination": "OBL-4"},
        ],
        "missing_link": {"type": "TEST_TO_EVIDENCE", "source": "TEST-4", "destination": "EV-4"},
    }

    output = evaluate_f6_traceability(fixture_spec, resolver=resolver)
    assert output.state == GateState.MISSING
    assert output.must_id == "PD-F6-004"
    assert "coverage" in output.detail.lower() or "missing" in output.detail.lower()


def test_f6_t5_stale_endpoint_freshness():
    """F6-T5 / F6-FT5 — stale endpoint freshness:
    Destination evidence digest is stale under the frozen freshness predicate -> MISSING[PD-F6-005].
    """
    resolver = InMemorySourceRefResolver({"VS-5": {}, "EV-5": {}})

    fixture_spec: Dict[str, Any] = {
        "nodes": ["VS-5", "EV-5"],
        "source_digest": "VS-5",
        "destination_digest": "EV-5",
        "source_fresh": True,
        "destination_fresh": False,
        "links": [
            {"type": "VERIFICATION_TO_TEST", "source": "VS-5", "destination": "EV-5"},
        ],
    }

    output = evaluate_f6_traceability(fixture_spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert output.state == GateState.MISSING
    assert output.must_id == "PD-F6-005"
    assert "stale" in output.detail.lower()


def test_f6_t6_planned_versus_realized_coverage():
    """F6-T6 / F6-FT6 — planned versus realized coverage:
    Planned chain has Requirement/AC/VS/Test but no evidence -> planned coverage computed (1.0),
    realized coverage absent (0.0). Realized case adds admissible evidence -> SATISFIED.
    """
    resolver = InMemorySourceRefResolver({
        "REQ-1": {}, "AC-1": {}, "VS-1": {}, "TEST-1": {}, "EV-1": {}, "OBL-1": {}
    })

    # 1. Planned mode without evidence
    planned_spec = {
        "mode": "planned",
        "nodes": ["REQ-1", "AC-1", "VS-1", "TEST-1"],
        "evidence": [],
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
            {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "VS-1"},
            {"type": "VERIFICATION_TO_TEST", "source": "VS-1", "destination": "TEST-1"},
        ],
    }
    planned_out = evaluate_f6_traceability(planned_spec, resolver=resolver, freshness_predicate=lambda nid: True, mode="planned")
    assert planned_out.state == GateState.SATISFIED

    # 2. Realized mode without evidence -> fails closed
    realized_fail_spec = dict(planned_spec)
    realized_fail_spec["mode"] = "realized"
    realized_fail_out = evaluate_f6_traceability(realized_fail_spec, resolver=resolver, freshness_predicate=lambda nid: True, mode="realized")
    assert realized_fail_out.state == GateState.MISSING
    assert realized_fail_out.must_id in ("PD-F6-002", "PD-F6-006")

    # 3. Realized mode with evidence -> SATISFIED
    realized_spec = {
        "mode": "realized",
        "nodes": ["REQ-1", "AC-1", "VS-1", "TEST-1", "EV-1", "OBL-1"],
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
            {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "VS-1"},
            {"type": "VERIFICATION_TO_TEST", "source": "VS-1", "destination": "TEST-1"},
            {"type": "TEST_TO_EVIDENCE", "source": "TEST-1", "destination": "EV-1"},
            {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-1", "destination": "OBL-1"},
        ],
    }
    realized_out = evaluate_f6_traceability(realized_spec, resolver=resolver, freshness_predicate=lambda nid: True, mode="realized")
    assert realized_out.state == GateState.SATISFIED


# =============================================================================
# 2. Normative Requirement Tests (PD-F6-001 through PD-F6-006)
# =============================================================================

def test_pd_f6_001_missing_resolver_fails_closed():
    """PD-F6-001: Absence of caller-injected resolver fails closed."""
    spec = {"nodes": ["REQ-1"], "links": []}
    out = evaluate_f6_traceability(spec, resolver=None)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-001"
    assert "caller-injected" in out.detail


def test_pd_f6_001_embedded_resolver_in_spec_ignored():
    """PD-F6-001: Spec containing candidate-embedded resolver cannot confer authority."""
    spec = {
        "resolver": {"dummy": True},
        "nodes": ["REQ-1"],
        "links": [],
    }
    out = evaluate_f6_traceability(spec, resolver=None)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-001"


def test_pd_f6_001_unresolved_source_ref_fails_closed():
    """PD-F6-001: Unresolved reference in source_refs yields MISSING[PD-F6-001]."""
    resolver = InMemorySourceRefResolver({"REQ-1": {}})
    spec = {
        "nodes": ["REQ-1", "REQ-MISSING"],
        "source_refs": ["REQ-1", "REQ-MISSING"],
        "links": [],
    }
    out = evaluate_f6_traceability(spec, resolver=resolver)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-001"
    assert "REQ-MISSING" in out.detail


def test_pd_f6_001_invalid_link_type_fails_closed():
    """PD-F6-001: Unknown link type fails closed with MISSING[PD-F6-001]."""
    resolver = InMemorySourceRefResolver({"A": {}, "B": {}})
    spec = {
        "nodes": ["A", "B"],
        "links": [{"type": "INVALID_UNKNOWN_LINK", "source": "A", "destination": "B"}],
    }
    out = evaluate_f6_traceability(spec, resolver=resolver)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-001"


def test_pd_f6_001_anti_gaming_name_matching_forbidden():
    """PD-F6-001: Inferring links from similar node names is strictly forbidden."""
    resolver = InMemorySourceRefResolver({"REQ-1": {}, "REQ-1-AC": {}})
    # Spec provides nodes with similar names, but no explicit links
    spec = {
        "nodes": ["REQ-1", "REQ-1-AC"],
        "links": [],
    }
    out = evaluate_f6_traceability(spec, resolver=resolver)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-001"
    assert "name matching" in out.detail.lower()


def test_pd_f6_002_orphan_requirement_detected():
    """PD-F6-002: Requirement node lacking outgoing link detected as orphan."""
    resolver = InMemorySourceRefResolver({"REQ-1": {}, "REQ-2": {}, "AC-1": {}})
    spec = {
        "nodes": ["REQ-1", "REQ-2", "AC-1"],
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
            # REQ-2 has no outgoing link!
        ],
    }
    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-002"
    assert "REQ-2" in out.detail


def test_pd_f6_002_orphan_evidence_detected():
    """PD-F6-002: Evidence node lacking incoming link detected as orphan."""
    resolver = InMemorySourceRefResolver({"TEST-1": {}, "EV-1": {}, "EV-2": {}, "OBL-1": {}})
    spec = {
        "nodes": ["TEST-1", "EV-1", "EV-2", "OBL-1"],
        "links": [
            {"type": "TEST_TO_EVIDENCE", "source": "TEST-1", "destination": "EV-1"},
            {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-1", "destination": "OBL-1"},
            {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-2", "destination": "OBL-1"},
            # EV-2 has no incoming link from a Test!
        ],
    }
    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-002"
    assert "EV-2" in out.detail


def test_pd_f6_003_link_id_computation_c1_canonical():
    """PD-F6-003: compute_link_id produces deterministic RFC 8785 C1 SHA-256."""
    lid1 = compute_link_id("REQUIREMENT_TO_ACCEPTANCE", "REQ-1", "AC-1")
    lid2 = compute_link_id(LinkType.REQUIREMENT_TO_ACCEPTANCE, "REQ-1", "AC-1")
    assert lid1 == lid2
    assert lid1 == "d586673da3a0109305eabb58e9cc17b01cc20f74e6822badb27986d16ef28aa0"
    assert len(lid1) == 64
    assert isinstance(lid1, str)


def test_pd_f6_003_revision_and_description_independence():
    """PD-F6-003: Changing revisions or descriptions leaves link identity unchanged."""
    l1 = TraceLink(
        link_type=LinkType.TEST_TO_EVIDENCE,
        source="TEST-1",
        destination="EV-1",
        revision=1,
        description="Version 1",
    )
    l2 = TraceLink(
        link_type=LinkType.TEST_TO_EVIDENCE,
        source="TEST-1",
        destination="EV-1",
        revision=42,
        description="Version 42 with extensive commentary",
    )
    assert l1.link_id == l2.link_id


def test_pd_f6_003_endpoint_change_creates_new_link_id():
    """PD-F6-003: Changing either endpoint creates a distinct link identity."""
    l1 = compute_link_id("TEST_TO_EVIDENCE", "TEST-1", "EV-1")
    l2 = compute_link_id("TEST_TO_EVIDENCE", "TEST-1", "EV-2")
    l3 = compute_link_id("TEST_TO_EVIDENCE", "TEST-2", "EV-1")
    assert l1 != l2
    assert l1 != l3


def test_pd_f6_003_tampered_link_id_raises_error():
    """PD-F6-003: Providing an explicit tampered link_id raises ValueError."""
    with pytest.raises(ValueError, match="Tampered or mismatched link_id"):
        TraceLink(
            link_type=LinkType.REQUIREMENT_TO_ACCEPTANCE,
            source="REQ-1",
            destination="AC-1",
            link_id="bad_forged_hash_value_here",
        )


def test_pd_f6_004_agent_asserted_100_percent_broken_chain_fails_closed():
    """PD-F6-004: Agent asserting 100% coverage cannot bypass missing links."""
    resolver = InMemorySourceRefResolver({"REQ-1": {}, "AC-1": {}, "VS-1": {}})
    spec = {
        "nodes": ["REQ-1", "AC-1", "VS-1"],
        "agent_claimed_coverage_percent": 100,
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
            # Broken: missing ACCEPTANCE_TO_VERIFICATION
        ],
    }
    out = evaluate_f6_traceability(spec, resolver=resolver)
    assert out.state == GateState.MISSING
    assert out.must_id in ("PD-F6-002", "PD-F6-004")


def test_pd_f6_005_source_endpoint_stale_fails_closed():
    """PD-F6-005: Stale source endpoint yields MISSING[PD-F6-005]."""
    resolver = InMemorySourceRefResolver({"REQ-1": {}, "AC-1": {}})
    spec = {
        "nodes": ["REQ-1", "AC-1"],
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"}
        ],
    }
    # Freshness predicate marks REQ-1 (source) as stale
    stale_source_pred = lambda nid: nid != "REQ-1"
    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=stale_source_pred)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-005"
    assert "stale" in out.detail.lower()
    assert "REQ-1" in out.detail


def test_pd_f6_005_freshness_predicate_callable_integration():
    """PD-F6-005: Custom caller-injected freshness predicate correctly rejects stale node."""
    resolver = InMemorySourceRefResolver({"REQ-1": {}, "AC-1": {}})
    spec = {
        "nodes": ["REQ-1", "AC-1"],
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"}
        ],
    }
    # Freshness predicate marks AC-1 as stale
    pred = lambda nid: nid != "AC-1"
    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=pred)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-005"
    assert "AC-1" in out.detail


# =============================================================================
# 3. Adversarial & Edge-Case Robustness Tests
# =============================================================================

def test_adversarial_cyclic_links_do_not_infinite_loop():
    """Adversarial: Cyclic graph links terminate safely without infinite recursion."""
    resolver = InMemorySourceRefResolver({"REQ-1": {}, "AC-1": {}})
    spec = {
        "nodes": ["REQ-1", "AC-1"],
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
            {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "REQ-1"},
        ],
    }
    out = evaluate_f6_traceability(spec, resolver=resolver)
    # Graph is invalid / has orphans or broken sequence, must terminate with MISSING
    assert out.state == GateState.MISSING


def test_adversarial_empty_spec_fails_closed():
    """Adversarial: Empty spec or non-mapping fails closed."""
    out = evaluate_f6_traceability({}, resolver=InMemorySourceRefResolver())
    assert out.state == GateState.MISSING

    out2 = evaluate_f6_traceability("invalid_string_spec", resolver=InMemorySourceRefResolver())  # type: ignore
    assert out2.state == GateState.MISSING
    assert out2.must_id == "PD-F6-001"


def test_trace_link_from_dict_and_to_dict():
    """TraceLink serialization and roundtripping."""
    d = {
        "type": "REQUIREMENT_TO_ACCEPTANCE",
        "source": "REQ-1",
        "destination": "AC-1",
        "source_provenance": "prov_hash_1",
        "description": "test link",
        "revision": 3,
    }
    link = TraceLink.from_dict(d)
    assert link.link_type == LinkType.REQUIREMENT_TO_ACCEPTANCE
    assert link.source == "REQ-1"
    assert link.destination == "AC-1"
    assert link.revision == 3

    out_d = link.to_dict()
    assert out_d["link_type"] == "REQUIREMENT_TO_ACCEPTANCE"
    assert out_d["link_id"] == link.link_id


# =============================================================================
# 4. Section F6 Freshness Remediation Anti-Gaming & Fail-Closed Suite (PD-F6-005)
# =============================================================================

def _build_valid_5link_fixture() -> Tuple[Dict[str, Any], InMemorySourceRefResolver]:
    """Helper constructing an authoritative 5-link realized chain with resolver."""
    nodes = ["REQ-1", "AC-1", "VS-1", "TEST-1", "EV-1", "OBL-1"]
    resolver = InMemorySourceRefResolver({
        nid: {"id": nid, "kind": nid.split("-")[0]} for nid in nodes
    })
    spec: Dict[str, Any] = {
        "nodes": list(nodes),
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
            {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "VS-1"},
            {"type": "VERIFICATION_TO_TEST", "source": "VS-1", "destination": "TEST-1"},
            {"type": "TEST_TO_EVIDENCE", "source": "TEST-1", "destination": "EV-1"},
            {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-1", "destination": "OBL-1"},
        ],
        "source_refs": list(nodes),
        "source_refs_resolve": True,
        "mode": "realized",
    }
    return spec, resolver


def test_f6_freshness_positive_control_with_confirming_predicate():
    """Positive Control: fully resolved 5-link chain with injected predicate yields SATISFIED."""
    spec, resolver = _build_valid_5link_fixture()
    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-F6-001"
    assert "verified" in out.detail.lower()


def test_f6_freshness_negative_no_freshness_info_and_no_predicate():
    """Negative Case 1: No freshness info and no injected predicate -> MISSING[PD-F6-005]."""
    spec, resolver = _build_valid_5link_fixture()
    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=None)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-005"
    assert "caller-injected" in out.detail.lower()

    # Positive control: confirming predicate -> SATISFIED
    pos = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert pos.state == GateState.SATISFIED


def test_f6_freshness_negative_all_true_payload_map_no_predicate():
    """Negative Case 2: All-True payload freshness_map, no predicate -> MISSING[PD-F6-005]."""
    spec, resolver = _build_valid_5link_fixture()
    spec["freshness_map"] = {nid: True for nid in spec["nodes"]}
    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=None)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-005"
    assert "caller-injected" in out.detail.lower()

    # Positive control
    pos = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert pos.state == GateState.SATISFIED


def test_f6_freshness_negative_source_and_destination_fresh_true_no_predicate():
    """Negative Case 3: source_fresh=True and destination_fresh=True, no predicate -> MISSING[PD-F6-005]."""
    spec, resolver = _build_valid_5link_fixture()
    spec["source_fresh"] = True
    spec["destination_fresh"] = True
    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=None)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-005"
    assert "caller-injected" in out.detail.lower()

    # Positive control
    pos = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert pos.state == GateState.SATISFIED


def test_f6_freshness_negative_predicate_returns_false_per_endpoint():
    """Negative Case 4: Injected predicate returns False for any one endpoint -> MISSING[PD-F6-005]."""
    spec, resolver = _build_valid_5link_fixture()
    for endpoint in spec["nodes"]:
        pred = lambda nid, target=endpoint: nid != target
        out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=pred)
        assert out.state == GateState.MISSING
        assert out.must_id == "PD-F6-005"
        assert endpoint in out.detail

    # Positive control: all endpoints fresh
    pos = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert pos.state == GateState.SATISFIED


def test_f6_freshness_negative_predicate_raises_exception():
    """Negative Case 5: Injected predicate raises -> MISSING[PD-F6-005] without uncaught exception or SATISFIED."""
    spec, resolver = _build_valid_5link_fixture()

    def raising_predicate(nid: str) -> bool:
        raise RuntimeError(f"Simulated authority exception on node {nid}")

    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=raising_predicate)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-005"
    assert "raised exception" in out.detail.lower() or "runtimeerror" in out.detail.lower()

    # Positive control: non-raising predicate
    pos = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert pos.state == GateState.SATISFIED


def test_f6_freshness_negative_payload_claims_freshness_no_predicate():
    """Negative Case 6: Payload claims all freshness mechanisms, no injected predicate -> MISSING[PD-F6-005]."""
    spec, resolver = _build_valid_5link_fixture()
    spec["freshness_map"] = {nid: True for nid in spec["nodes"]}
    spec["source_fresh"] = True
    spec["destination_fresh"] = True
    # Even embedding a spoofed predicate in candidate payload confers zero authority
    spec["freshness_predicate"] = lambda nid: True

    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=None)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-005"
    assert "caller-injected" in out.detail.lower()

    # Positive control: caller injects predicate
    pos = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert pos.state == GateState.SATISFIED


def test_f6_freshness_negative_payload_fresh_while_predicate_reports_stale():
    """Negative Case 7: Payload claims freshness while injected predicate reports stale -> MISSING[PD-F6-005]."""
    spec, resolver = _build_valid_5link_fixture()
    spec["freshness_map"] = {nid: True for nid in spec["nodes"]}
    spec["source_fresh"] = True
    spec["destination_fresh"] = True

    # Injected predicate reports EV-1 is stale
    stale_ev_pred = lambda nid: nid != "EV-1"
    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=stale_ev_pred)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-005"
    assert "EV-1" in out.detail

    # Positive control: predicate reports all fresh
    pos = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert pos.state == GateState.SATISFIED


def test_f6_freshness_negative_payload_stale_overrides_predicate():
    """Candidate explicit stale fields make result stricter (can never grant freshness)."""
    spec, resolver = _build_valid_5link_fixture()
    # Injected predicate says fresh, but candidate explicitly says TEST-1 is stale
    spec["freshness_map"] = {"TEST-1": False}

    out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F6-005"
    assert "TEST-1" in out.detail or "stale" in out.detail.lower()


def test_f6_freshness_negative_predicate_non_boolean_return():
    """Predicate result must be exactly True (bool); False, None, or non-bool fails closed."""
    spec, resolver = _build_valid_5link_fixture()

    for non_bool in [False, None, 0, 1, "true", "True", [], {}]:
        pred = lambda nid, val=non_bool: val
        out = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=pred)
        assert out.state == GateState.MISSING, f"Expected MISSING for return value {non_bool!r}"
        assert out.must_id == "PD-F6-005"

    # Positive control: exact boolean True succeeds
    pos = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=lambda nid: True)
    assert pos.state == GateState.SATISFIED


def test_f6_freshness_empty_call_negative_control():
    """Empty-call negative control: absence of valid injected authority never produces SATISFIED."""
    spec, resolver = _build_valid_5link_fixture()

    # Empty spec, no args
    assert evaluate_f6_traceability({}).state == GateState.MISSING
    # Spec only
    assert evaluate_f6_traceability(spec).state == GateState.MISSING
    # Resolver only, no freshness predicate
    out_no_pred = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate=None)
    assert out_no_pred.state == GateState.MISSING
    assert out_no_pred.must_id == "PD-F6-005"
    # Freshness predicate only, no resolver
    out_no_res = evaluate_f6_traceability(spec, resolver=None, freshness_predicate=lambda nid: True)
    assert out_no_res.state == GateState.MISSING
    assert out_no_res.must_id == "PD-F6-001"
    # Non-callable freshness predicate
    out_bad_pred = evaluate_f6_traceability(spec, resolver=resolver, freshness_predicate="not_callable")  # type: ignore
    assert out_bad_pred.state == GateState.MISSING
    assert out_bad_pred.must_id == "PD-F6-005"

