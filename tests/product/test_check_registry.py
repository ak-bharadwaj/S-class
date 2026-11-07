"""Unit tests for check_registry.py.

Tests MUST PD-CH5-006, phase sub-check registry, and CH4 registry representation.
"""
import pytest

from sclass.product.check_registry import (
    CHECK_REGISTRY,
    CH4_REGISTRY,
    QUALIFIED_EVALUATOR_BOUNDARY,
    UNSPECIFIED_IN_MASTER,
    compute_check_id,
    get_check_record,
    lint_ch4_registry,
    validate_check_id,
)
from sclass.product.gate import GateOutput, GateState


def test_compute_check_id_deterministic():
    """Verify check ID calculation is deterministic C1 digest."""
    cid1 = compute_check_id("§2.6", "Profile completeness", "1.0")
    cid2 = compute_check_id("§2.6", "Profile completeness", "1.0")
    assert cid1 == cid2
    assert cid1 == "25e7fa0da2206e1fcb362e2d37bab0f135afb7947b0afad00c2475b583c69ce6"
    assert len(cid1) == 64
    assert isinstance(cid1, str)

    # Different section or name yields different ID
    cid3 = compute_check_id("§2.7", "Profile completeness", "1.0")
    assert cid1 != cid3


def test_pd_ch5_006_gaming_fixture_ch5_t6():
    """CH5-T6: hand-created check registry ID returns MISSING[PD-CH5-006]."""
    out = validate_check_id(
        "PRODUCT-UNREGISTERED-CHECK",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH5-006"
    assert "MISSING[PD-CH5-006]" in out.failures
    assert str(out) == "MISSING[PD-CH5-006]"


def test_pd_ch5_006_happy_registered_id():
    """Conforming registered ID from phase sub-check table returns SATISFIED."""
    cid = compute_check_id("§2.6", "Profile completeness", "1.0")
    assert cid in CHECK_REGISTRY

    out = validate_check_id(cid, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert out.state == GateState.SATISFIED
    assert str(out) == "SATISFIED"


def test_pd_ch5_006_caller_authority_enforced():
    """Unauthorized caller authority fails closed with MISSING[PD-CH5-006]."""
    cid = compute_check_id("§2.6", "Profile completeness", "1.0")

    # None caller
    out = validate_check_id(cid, caller_authority=None)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH5-006"

    # Arbitrary caller
    out = validate_check_id(cid, caller_authority="unauthorized_caller")
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH5-006"


def test_phase_subcheck_registry_coverage():
    """Verify registry covers all phases P0 to P11 with valid line citations."""
    sections = {record.owner_section for record in CHECK_REGISTRY.values()}
    # Must contain sections §2.6 through §2.17
    for s in ["§2.6", "§2.7", "§2.8", "§2.9", "§2.10", "§2.11", "§2.12", "§2.13", "§2.14", "§2.15", "§2.16", "§2.17"]:
        assert s in sections, f"Section {s} missing from check registry"

    for record in CHECK_REGISTRY.values():
        assert record.master_line > 0
        assert record.check_name
        assert record.check_class in ("M", "E", "J", "M/E", "M/J", "E/J")


def test_ch4_registry_representation():
    """Verify Chapter 4 records are represented with UNSPECIFIED_IN_MASTER marker."""
    required_ch4_keys = ["PD-CH4-002", "PD-CH4-005", "PD-CH4-006", "PD-CH4-007", "PD-CH4-008"]
    for key in required_ch4_keys:
        assert key in CH4_REGISTRY
        rec = CH4_REGISTRY[key]
        assert rec["owner_block"] == "CH4"
        assert rec["failure_route"] == f"MISSING[{key}]"

    # PD-CH4-008 has depends_on_draft_sections: ["§4.1"]
    assert CH4_REGISTRY["PD-CH4-008"]["depends_on_draft_sections"] == ["§4.1"]

    # Linter finds UNSPECIFIED_IN_MASTER entries
    findings = lint_ch4_registry()
    assert len(findings) > 0
    for finding in findings:
        assert finding["finding"] == UNSPECIFIED_IN_MASTER
