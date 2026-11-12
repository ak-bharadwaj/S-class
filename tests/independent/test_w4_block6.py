"""Independent W4 Consumer Contract Scenarios for Block 6 (Chapter 6).

Mandated by S-CLASS M0 ITERATION 2 (E5):
- Standalone independent test functions under tests/independent/
- Covers all 10 Block 6 MUSTs (PD-CH6-003, 006, 007, 008, 009, 010, 011, 012, 013, 014)
- Evaluates fail-closed security posture (unauthenticated / missing authority -> non-SATISFIED)
- Evaluates authorized consumer contracts (valid authority -> SATISFIED)
- Asserts GateOutput contract compliance (GateState closed vocabulary, to_dict schema)
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.knowledge_package_quarantine import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B6_A,
    REQUIRED_PACKAGE_METADATA_FIELDS,
    evaluate_pd_ch6_007_package_metadata,
    evaluate_pd_ch6_008_precedence_and_conflicts,
    evaluate_pd_ch6_009_lifecycle_projection,
    evaluate_pd_ch6_010_quarantine_conditions,
    evaluate_pd_ch6_011_license_provenance_verification,
    evaluate_pd_ch6_012_steppack_digest_pinning,
)
from sclass.product.oss_qualification_playbook import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B6_B,
    OSS_QUALIFICATION_FIELDS,
    REQUIRED_PLAYBOOK_PHASES,
    evaluate_pd_ch6_003_pack_activation,
    evaluate_pd_ch6_006_playbook_content,
    evaluate_pd_ch6_013_stack_pack_adapters,
    evaluate_pd_ch6_014_oss_qualification_record,
)


def test_w4_scenario_pd_ch6_003():
    """W4 Scenario for PD-CH6-003: OSS pack activation."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch6_003_pack_activation(True, False, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-003"

    # 2. Revoked pack rejected
    revoked = evaluate_pd_ch6_003_pack_activation(True, True, authority=AUTH_B6_B)
    assert isinstance(revoked, GateOutput)
    assert revoked.state == GateState.MISSING
    assert revoked.must_id == "PD-CH6-003"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch6_003_pack_activation(True, False, authority=AUTH_B6_B)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-003"


def test_w4_scenario_pd_ch6_006():
    """W4 Scenario for PD-CH6-006: Playbook phase content."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch6_006_playbook_content({"phases": list(REQUIRED_PLAYBOOK_PHASES)}, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-006"

    # 2. Incomplete phases fails closed
    incomplete = evaluate_pd_ch6_006_playbook_content({"phases": ["P0", "P1"]}, authority=AUTH_B6_B)
    assert isinstance(incomplete, GateOutput)
    assert incomplete.state == GateState.MISSING
    assert incomplete.must_id == "PD-CH6-006"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch6_006_playbook_content({"phases": list(REQUIRED_PLAYBOOK_PHASES)}, authority=AUTH_B6_B)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-006"


def test_w4_scenario_pd_ch6_007():
    """W4 Scenario for PD-CH6-007: Package metadata closed schema."""
    # 1. Unauthenticated caller fails closed
    meta = {f: "valid_val" for f in REQUIRED_PACKAGE_METADATA_FIELDS}
    unauth = evaluate_pd_ch6_007_package_metadata(meta, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-007"

    # 2. Missing field fails closed
    bad_meta = meta.copy()
    del bad_meta[list(REQUIRED_PACKAGE_METADATA_FIELDS)[0]]
    bad = evaluate_pd_ch6_007_package_metadata(bad_meta, authority=AUTH_B6_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH6-007"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch6_007_package_metadata(meta, authority=AUTH_B6_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-007"


def test_w4_scenario_pd_ch6_008():
    """W4 Scenario for PD-CH6-008: Deterministic precedence and mandatory check preservation."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch6_008_precedence_and_conflicts(True, False, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-008"

    # 2. Lower tier removes mandatory fails closed
    bad = evaluate_pd_ch6_008_precedence_and_conflicts(True, True, authority=AUTH_B6_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH6-008"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch6_008_precedence_and_conflicts(True, False, authority=AUTH_B6_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-008"


def test_w4_scenario_pd_ch6_009():
    """W4 Scenario for PD-CH6-009: Pack lifecycle projection."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch6_009_lifecycle_projection(True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-009"

    # 2. Independent state machine rejected
    bad = evaluate_pd_ch6_009_lifecycle_projection(
        is_evidence_projection=True,
        independent_state_machine=True,
        authority=AUTH_B6_A,
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH6-009"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch6_009_lifecycle_projection(
        is_evidence_projection=True,
        independent_state_machine=False,
        authority=AUTH_B6_A,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-009"


def test_w4_scenario_pd_ch6_010():
    """W4 Scenario for PD-CH6-010: Quarantine conditions."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch6_010_quarantine_conditions(authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-010"

    # 2. Unknown checks fails closed
    bad = evaluate_pd_ch6_010_quarantine_conditions(
        unknown_checks=True,
        weakened_floors=False,
        invalid_signature=False,
        unsupported_compatibility=False,
        quarantined=False,
        authority=AUTH_B6_A,
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH6-010"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch6_010_quarantine_conditions(
        unknown_checks=False,
        weakened_floors=False,
        invalid_signature=False,
        unsupported_compatibility=False,
        authority=AUTH_B6_A,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-010"


def test_w4_scenario_pd_ch6_011():
    """W4 Scenario for PD-CH6-011: License and provenance verification."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch6_011_license_provenance_verification(True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-011"

    # 2. Public URL only rejected
    bad = evaluate_pd_ch6_011_license_provenance_verification(
        license_verified=True, provenance_verified=True, public_url_only=True, authority=AUTH_B6_A
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH6-011"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch6_011_license_provenance_verification(
        True, True, public_url_only=False, authority=AUTH_B6_A
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-011"


def test_w4_scenario_pd_ch6_012():
    """W4 Scenario for PD-CH6-012: In-flight StepPack digest pinning."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch6_012_steppack_digest_pinning(True, True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-012"

    # 2. In-flight missing digests fails closed
    bad = evaluate_pd_ch6_012_steppack_digest_pinning(
        in_flight=True, content_digest_pinned=False, compiler_digest_pinned=True, authority=AUTH_B6_A
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH6-012"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch6_012_steppack_digest_pinning(
        in_flight=True, content_digest_pinned=True, compiler_digest_pinned=True, authority=AUTH_B6_A
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-012"


def test_w4_scenario_pd_ch6_013():
    """W4 Scenario for PD-CH6-013: Stack pack adapter capability families."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch6_013_stack_pack_adapters({"adapter_capability_families": {}}, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-013"

    # 2. Unqualified adapter unblocked fails closed
    unqual = {
        "adapter_capability_families": {
            "prop_test": {"qualified": False, "applicable_checks": ["CHECK_1"]}
        },
        "explicitly_blocked_checks": [],
    }
    bad = evaluate_pd_ch6_013_stack_pack_adapters(unqual, authority=AUTH_B6_B)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH6-013"

    # 3. Authorized consumer contract satisfied
    qual = {
        "adapter_capability_families": {
            "type_check": {"qualified": True, "applicable_checks": ["CHECK_TYPE"]}
        },
        "explicitly_blocked_checks": [],
    }
    auth = evaluate_pd_ch6_013_stack_pack_adapters(qual, authority=AUTH_B6_B)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-013"


def test_w4_scenario_pd_ch6_014():
    """W4 Scenario for PD-CH6-014: OSS qualification record envelope."""
    rec = {f: f"evidence_ref_{f}" for f in OSS_QUALIFICATION_FIELDS}

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch6_014_oss_qualification_record(rec, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH6-014"

    # 2. Unsupported verified claims rejected
    unsupp = rec.copy()
    unsupp["unsupported_verified_claims"] = True
    bad = evaluate_pd_ch6_014_oss_qualification_record(unsupp, authority=AUTH_B6_B)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH6-014"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch6_014_oss_qualification_record(rec, authority=AUTH_B6_B)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH6-014"
