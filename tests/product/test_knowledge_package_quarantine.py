"""Unit and regression tests for Chapter 6 Knowledge Package Quarantine Gate (Block 6, Lane B6-A).

Covers:
- PD-CH6-007: Package metadata closed schema, digests, license, capabilities, signature
- PD-CH6-008: Deterministic precedence and mandatory check preservation
- PD-CH6-009: Pack lifecycle labels as projections of qualification/revocation evidence
- PD-CH6-010: Quarantine conditions (unknown checks, weakened floors, invalid sig, compat)
- PD-CH6-011: License/provenance verification and rejection of public URL only
- PD-CH6-012: In-flight StepPack content and compiler digest pinning
"""
import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.knowledge_package_quarantine import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_PACKAGE_METADATA_FIELDS,
    evaluate_pd_ch6_007_package_metadata,
    evaluate_pd_ch6_008_precedence_and_conflicts,
    evaluate_pd_ch6_009_lifecycle_projection,
    evaluate_pd_ch6_010_quarantine_conditions,
    evaluate_pd_ch6_011_license_provenance_verification,
    evaluate_pd_ch6_012_steppack_digest_pinning,
    evaluate_b6_a_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


class ExplodingDependency:
    def __bool__(self):
        raise RuntimeError("Hostile dependency exploded")
    def __eq__(self, other):
        raise RuntimeError("Hostile dependency exploded")


class TestPDCH6007PackageMetadata:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_007_package_metadata({"closed_schema": True}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-007"

    def test_missing_metadata(self):
        res = evaluate_pd_ch6_007_package_metadata(None, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-007"

    @pytest.mark.parametrize("missing_field", list(REQUIRED_PACKAGE_METADATA_FIELDS))
    def test_missing_individual_fields(self, missing_field):
        meta = {f: "valid" for f in REQUIRED_PACKAGE_METADATA_FIELDS}
        del meta[missing_field]
        res = evaluate_pd_ch6_007_package_metadata(meta, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-007"

    def test_metadata_satisfied(self):
        meta = {f: "valid_val" for f in REQUIRED_PACKAGE_METADATA_FIELDS}
        res = evaluate_pd_ch6_007_package_metadata(meta, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH6008PrecedenceAndConflicts:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_008_precedence_and_conflicts(True, False, authority=None)
        assert res.state == GateState.MISSING

    def test_non_deterministic_precedence(self):
        res = evaluate_pd_ch6_008_precedence_and_conflicts(False, False, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-008"

    def test_lower_tier_removes_mandatory(self):
        res = evaluate_pd_ch6_008_precedence_and_conflicts(True, True, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-008"

    def test_precedence_satisfied(self):
        res = evaluate_pd_ch6_008_precedence_and_conflicts(True, False, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH6009LifecycleProjection:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_009_lifecycle_projection(True, authority=None)
        assert res.state == GateState.MISSING

    def test_independent_state_machine_rejected(self):
        res = evaluate_pd_ch6_009_lifecycle_projection(
            is_evidence_projection=True,
            independent_state_machine=True,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-009"

    def test_not_evidence_projection_rejected(self):
        res = evaluate_pd_ch6_009_lifecycle_projection(
            is_evidence_projection=False,
            independent_state_machine=False,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING

    def test_lifecycle_projection_satisfied(self):
        res = evaluate_pd_ch6_009_lifecycle_projection(
            is_evidence_projection=True,
            independent_state_machine=False,
            authority=AUTH,
        )
        assert res.state == GateState.SATISFIED


class TestPDCH6010QuarantineConditions:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_010_quarantine_conditions(authority=None)
        assert res.state == GateState.MISSING

    def test_omitted_evidence_fails_closed(self):
        # Valid authority, but no evidence supplied
        res = evaluate_pd_ch6_010_quarantine_conditions(authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-010"

    @pytest.mark.parametrize("invalid_val", [None, "False", 0, 1, [], ExplodingDependency()])
    def test_invalid_types_fail_closed(self, invalid_val):
        res = evaluate_pd_ch6_010_quarantine_conditions(
            unknown_checks=invalid_val,
            weakened_floors=False,
            invalid_signature=False,
            unsupported_compatibility=False,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-010"

    @pytest.mark.parametrize("kw", [
        {"unknown_checks": True},
        {"weakened_floors": True},
        {"invalid_signature": True},
        {"unsupported_compatibility": True},
    ])
    def test_flawed_packages_quarantined_or_missing(self, kw):
        # Without quarantine flag
        res1 = evaluate_pd_ch6_010_quarantine_conditions(**kw, quarantined=False, authority=AUTH)
        assert res1.state == GateState.MISSING
        assert res1.must_id == "PD-CH6-010"

        # With quarantine flag (still returns MISSING to prevent promotion/execution)
        res2 = evaluate_pd_ch6_010_quarantine_conditions(**kw, quarantined=True, authority=AUTH)
        assert res2.state == GateState.MISSING
        assert res2.must_id == "PD-CH6-010"

    def test_clean_package_satisfied(self):
        res = evaluate_pd_ch6_010_quarantine_conditions(
            unknown_checks=False,
            weakened_floors=False,
            invalid_signature=False,
            unsupported_compatibility=False,
            authority=AUTH,
        )
        assert res.state == GateState.SATISFIED

    def test_mutation_restore_default_false_is_killed(self):
        # Mutation: if an evaluator parameter defaulted to False when omitted,
        # calling it with only authority would return SATISFIED.
        # This test asserts that calling with NO evidence fails closed.
        res = evaluate_pd_ch6_010_quarantine_conditions(authority=AUTH)
        assert res.state == GateState.MISSING


class TestPDCH6011LicenseProvenanceVerification:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_011_license_provenance_verification(True, True, authority=None)
        assert res.state == GateState.MISSING

    def test_public_url_only_rejected(self):
        res = evaluate_pd_ch6_011_license_provenance_verification(
            license_verified=True, provenance_verified=True, public_url_only=True, authority=AUTH
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-011"

    @pytest.mark.parametrize("lic,prov", [
        (False, True),
        (True, False),
        (False, False),
    ])
    def test_unverified_license_or_provenance(self, lic, prov):
        res = evaluate_pd_ch6_011_license_provenance_verification(
            lic, prov, public_url_only=False, authority=AUTH
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-011"

    def test_license_provenance_satisfied(self):
        res = evaluate_pd_ch6_011_license_provenance_verification(
            True, True, public_url_only=False, authority=AUTH
        )
        assert res.state == GateState.SATISFIED


class TestPDCH6012StepPackDigestPinning:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_012_steppack_digest_pinning(True, True, True, authority=None)
        assert res.state == GateState.MISSING

    def test_not_in_flight(self):
        res = evaluate_pd_ch6_012_steppack_digest_pinning(False, False, False, authority=AUTH)
        assert res.state == GateState.SATISFIED

    @pytest.mark.parametrize("c_dig,comp_dig", [
        (False, True),
        (True, False),
        (False, False),
    ])
    def test_in_flight_missing_digests(self, c_dig, comp_dig):
        res = evaluate_pd_ch6_012_steppack_digest_pinning(
            in_flight=True, content_digest_pinned=c_dig, compiler_digest_pinned=comp_dig, authority=AUTH
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-012"

    def test_in_flight_satisfied(self):
        res = evaluate_pd_ch6_012_steppack_digest_pinning(
            in_flight=True, content_digest_pinned=True, compiler_digest_pinned=True, authority=AUTH
        )
        assert res.state == GateState.SATISFIED


class TestAggregateB6AGate:
    def test_aggregate_satisfied(self):
        payload = {
            "package_metadata": {f: "val" for f in REQUIRED_PACKAGE_METADATA_FIELDS},
            "precedence_deterministic": True,
            "lower_tier_removes_mandatory": False,
            "is_evidence_projection": True,
            "independent_state_machine": False,
            "unknown_checks": False,
            "weakened_floors": False,
            "invalid_signature": False,
            "unsupported_compatibility": False,
            "quarantined": False,
            "license_verified": True,
            "provenance_verified": True,
            "public_url_only": False,
            "in_flight": True,
            "content_digest_pinned": True,
            "compiler_digest_pinned": True,
        }
        res = evaluate_b6_a_gate(payload, authority=AUTH)
        assert len(res) == 6
        assert all(out.state == GateState.SATISFIED for out in res.values())

    def test_aggregate_no_authority(self):
        res = evaluate_b6_a_gate({}, authority=None)
        assert len(res) == 6
        assert all(out.state == GateState.MISSING for out in res.values())

    def test_aggregate_empty_payload_fails_closed(self):
        res = evaluate_b6_a_gate({}, authority=AUTH)
        assert len(res) == 6
        assert all(out.state == GateState.MISSING for out in res.values())
