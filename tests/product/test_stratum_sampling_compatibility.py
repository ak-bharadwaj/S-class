"""Unit and regression tests for Chapter 9 & 10 Stratum Sampling, Compatibility & Roadmap Gate (Block 9, Lane B9-B).

Covers:
- PD-CH9-006: Stratum sampling paired tasks and false-completion rate
- PD-CH9-007: Secret egress claims on launched workers
- PD-CH10-008: Explicit compatibility matrix
- PD-CH10-009: Audit export bindings and sequence range
- PD-CH10-010: Roadmap integrity (H0-H7, dependencies, exit tests)
- PD-CH10-011: Implementation fact classification (keep/replace/retire/qualify)
"""
import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.stratum_sampling_compatibility import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    VALID_ROADMAP_HORIZONS,
    VALID_FACT_CLASSIFICATIONS,
    REQUIRED_AUDIT_EXPORT_FIELDS,
    REQUIRED_COMPATIBILITY_FIELDS,
    evaluate_pd_ch9_006_stratum_sampling_promotion,
    evaluate_pd_ch9_007_secret_egress_claims,
    evaluate_pd_ch10_008_explicit_compatibility,
    evaluate_pd_ch10_009_audit_export_bindings,
    evaluate_pd_ch10_010_roadmap_integrity,
    evaluate_pd_ch10_011_fact_classification,
    evaluate_b9_b_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


class TestPDCH9006StratumSamplingPromotion:
    def test_authority_enforced(self):
        res = evaluate_pd_ch9_006_stratum_sampling_promotion(False, {"S1": 150}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-006"

    def test_false_completion_worsened_blocks(self):
        res = evaluate_pd_ch9_006_stratum_sampling_promotion(True, {"S1": 150}, authority=AUTH)
        assert res.state == GateState.MISSING
        assert "BLOCKED" in res.detail

    def test_stratum_below_minimum_blocks(self):
        res = evaluate_pd_ch9_006_stratum_sampling_promotion(False, {"S1": 99}, minimum_per_stratum=100, authority=AUTH)
        assert res.state == GateState.MISSING
        assert "BLOCKED" in res.detail

    def test_stratum_sampling_satisfied(self):
        res = evaluate_pd_ch9_006_stratum_sampling_promotion(False, {"S1": 100, "S2": 150}, minimum_per_stratum=100, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH9007SecretEgressClaims:
    def test_authority_enforced(self):
        res = evaluate_pd_ch9_007_secret_egress_claims(True, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-007"

    def test_unqualified_scanner_rejected(self):
        res = evaluate_pd_ch9_007_secret_egress_claims(
            True, unqualified_scanner_or_native_host_write=True, authority=AUTH
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-007"

    def test_missing_receipt_rejected(self):
        res = evaluate_pd_ch9_007_secret_egress_claims(False, authority=AUTH)
        assert res.state == GateState.MISSING

    def test_qualified_receipt_satisfied(self):
        res = evaluate_pd_ch9_007_secret_egress_claims(True, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH10008ExplicitCompatibility:
    def test_authority_enforced(self):
        res = evaluate_pd_ch10_008_explicit_compatibility({}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-008"

    def test_unsupported_pair_blocks(self):
        matrix = {f: "1.0" for f in REQUIRED_COMPATIBILITY_FIELDS}
        res = evaluate_pd_ch10_008_explicit_compatibility(matrix, unsupported_pair_present=True, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-008"

    @pytest.mark.parametrize("missing_field", list(REQUIRED_COMPATIBILITY_FIELDS))
    def test_missing_field(self, missing_field):
        matrix = {f: "1.0" for f in REQUIRED_COMPATIBILITY_FIELDS}
        del matrix[missing_field]
        res = evaluate_pd_ch10_008_explicit_compatibility(matrix, authority=AUTH)
        assert res.state == GateState.MISSING

    def test_compatibility_satisfied(self):
        matrix = {f: "1.0" for f in REQUIRED_COMPATIBILITY_FIELDS}
        res = evaluate_pd_ch10_008_explicit_compatibility(matrix, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH10009AuditExportBindings:
    def test_authority_enforced(self):
        res = evaluate_pd_ch10_009_audit_export_bindings({}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-009"

    def test_missing_payload(self):
        res = evaluate_pd_ch10_009_audit_export_bindings(None, authority=AUTH)
        assert res.state == GateState.MISSING

    @pytest.mark.parametrize("missing_field", list(REQUIRED_AUDIT_EXPORT_FIELDS))
    def test_missing_field(self, missing_field):
        export = {f: f"val_{f}" for f in REQUIRED_AUDIT_EXPORT_FIELDS}
        del export[missing_field]
        res = evaluate_pd_ch10_009_audit_export_bindings(export, authority=AUTH)
        assert res.state == GateState.MISSING

    def test_audit_export_satisfied(self):
        export = {f: f"val_{f}" for f in REQUIRED_AUDIT_EXPORT_FIELDS}
        res = evaluate_pd_ch10_009_audit_export_bindings(export, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH10010RoadmapIntegrity:
    def test_authority_enforced(self):
        res = evaluate_pd_ch10_010_roadmap_integrity([], authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-010"

    def test_invalid_horizon(self):
        cap = [{"id": "C1", "horizon": "H8", "dependency": "DEP", "exit_test": "TEST"}]
        res = evaluate_pd_ch10_010_roadmap_integrity(cap, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-010"

    def test_missing_dependency_or_exit_test(self):
        cap1 = [{"id": "C1", "horizon": "H1", "dependency": "", "exit_test": "TEST"}]
        assert evaluate_pd_ch10_010_roadmap_integrity(cap1, authority=AUTH).state == GateState.MISSING
        cap2 = [{"id": "C1", "horizon": "H1", "dependency": "DEP", "exit_test": ""}]
        assert evaluate_pd_ch10_010_roadmap_integrity(cap2, authority=AUTH).state == GateState.MISSING

    def test_planning_claimed_as_implemented_rejected(self):
        cap = [{"id": "C1", "horizon": "H2", "dependency": "DEP", "exit_test": "TEST", "planning_claimed_as_implemented": True}]
        res = evaluate_pd_ch10_010_roadmap_integrity(cap, authority=AUTH)
        assert res.state == GateState.MISSING

    def test_roadmap_satisfied(self):
        cap = [{"id": "C1", "horizon": "H1", "dependency": "DEP", "exit_test": "TEST", "planning_claimed_as_implemented": False}]
        res = evaluate_pd_ch10_010_roadmap_integrity(cap, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH10011FactClassification:
    def test_authority_enforced(self):
        res = evaluate_pd_ch10_011_fact_classification([], authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-011"

    def test_invalid_classification(self):
        facts = [{"id": "F1", "classification": "ignore", "evidence_ref": "REF"}]
        res = evaluate_pd_ch10_011_fact_classification(facts, authority=AUTH)
        assert res.state == GateState.MISSING

    def test_neither_evidence_nor_unverified(self):
        facts = [{"id": "F1", "classification": "keep", "evidence_ref": "", "unverified": False}]
        res = evaluate_pd_ch10_011_fact_classification(facts, authority=AUTH)
        assert res.state == GateState.MISSING

    def test_fact_classification_satisfied(self):
        facts = [
            {"id": "F1", "classification": "keep", "evidence_ref": "REF1", "unverified": False},
            {"id": "F2", "classification": "qualify", "evidence_ref": "", "unverified": True},
        ]
        res = evaluate_pd_ch10_011_fact_classification(facts, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestAggregateB9BGate:
    def test_aggregate_satisfied(self):
        payload = {
            "false_completion_worsened": False,
            "stratum_counts": {"core": 120},
            "minimum_per_stratum": 100,
            "qualified_receipt_on_launched_worker": True,
            "unqualified_scanner_or_native_host_write": False,
            "compatibility_matrix": {f: "1.0" for f in REQUIRED_COMPATIBILITY_FIELDS},
            "unsupported_pair_present": False,
            "audit_export": {f: f"val_{f}" for f in REQUIRED_AUDIT_EXPORT_FIELDS},
            "capabilities": [{"id": "C1", "horizon": "H1", "dependency": "DEP", "exit_test": "TEST"}],
            "facts": [{"id": "F1", "classification": "keep", "evidence_ref": "REF"}],
        }
        res = evaluate_b9_b_gate(payload, authority=AUTH)
        assert len(res) == 6
        assert all(out.state == GateState.SATISFIED for out in res.values())

    def test_aggregate_no_authority(self):
        res = evaluate_b9_b_gate({}, authority=None)
        assert len(res) == 6
        assert all(out.state == GateState.MISSING for out in res.values())
