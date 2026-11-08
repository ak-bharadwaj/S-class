"""Unit and regression tests for Chapter 6 OSS Qualification & Playbook Gate (Block 6, Lane B6-B).

Covers:
- PD-CH6-013: Stack pack adapter capability families or blocked checks
- PD-CH6-014: OSS qualification record 16 fields and UNVERIFIED evidence envelope
- PD-CH6-003: Pack activation requiring qualification and absence of revocation
- PD-CH6-006: Playbook phase checklists (P0..P11) and qualified adapter families
"""
import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.oss_qualification_playbook import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    OSS_QUALIFICATION_FIELDS,
    REQUIRED_PLAYBOOK_PHASES,
    evaluate_pd_ch6_013_stack_pack_adapters,
    evaluate_pd_ch6_014_oss_qualification_record,
    evaluate_pd_ch6_003_pack_activation,
    evaluate_pd_ch6_006_playbook_content,
    evaluate_b6_b_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


class TestPDCH6013StackPackAdapters:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_013_stack_pack_adapters({"adapter_capability_families": {}}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-013"

    def test_missing_stack_pack(self):
        res = evaluate_pd_ch6_013_stack_pack_adapters(None, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-013"

    def test_unqualified_adapter_not_blocked(self):
        sp = {
            "adapter_capability_families": {
                "property_testing": {"qualified": False, "applicable_checks": ["CHECK_PROP"]}
            },
            "explicitly_blocked_checks": [],
        }
        res = evaluate_pd_ch6_013_stack_pack_adapters(sp, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-013"

    def test_unqualified_adapter_explicitly_blocked(self):
        sp = {
            "adapter_capability_families": {
                "property_testing": {"qualified": False, "applicable_checks": ["CHECK_PROP"]}
            },
            "explicitly_blocked_checks": ["CHECK_PROP"],
        }
        res = evaluate_pd_ch6_013_stack_pack_adapters(sp, authority=AUTH)
        assert res.state == GateState.SATISFIED

    def test_qualified_adapters_satisfied(self):
        sp = {
            "adapter_capability_families": {
                "schema_validation": {"qualified": True, "applicable_checks": ["CHECK_SCHEMA"]},
                "type_checking": {"qualified": True, "applicable_checks": ["CHECK_TYPE"]},
            },
            "explicitly_blocked_checks": [],
        }
        res = evaluate_pd_ch6_013_stack_pack_adapters(sp, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH6014OSSQualificationRecord:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_014_oss_qualification_record({}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-014"

    def test_missing_record(self):
        res = evaluate_pd_ch6_014_oss_qualification_record(None, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-014"

    @pytest.mark.parametrize("missing_field", list(OSS_QUALIFICATION_FIELDS))
    def test_missing_field(self, missing_field):
        rec = {f: f"val_{f}" for f in OSS_QUALIFICATION_FIELDS}
        del rec[missing_field]
        res = evaluate_pd_ch6_014_oss_qualification_record(rec, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-014"

    def test_unsupported_verified_claims_rejected(self):
        rec = {f: f"val_{f}" for f in OSS_QUALIFICATION_FIELDS}
        rec["unsupported_verified_claims"] = True
        res = evaluate_pd_ch6_014_oss_qualification_record(rec, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-014"

    def test_complete_envelope_satisfied(self):
        rec = {f: f"evidence_ref_{f}" for f in OSS_QUALIFICATION_FIELDS}
        res = evaluate_pd_ch6_014_oss_qualification_record(rec, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH6003PackActivation:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_003_pack_activation(True, False, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-003"

    def test_unqualified_pack_rejected(self):
        res = evaluate_pd_ch6_003_pack_activation(False, False, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-003"

    def test_revocation_present_rejected(self):
        res = evaluate_pd_ch6_003_pack_activation(True, True, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-003"

    def test_pack_activation_satisfied(self):
        res = evaluate_pd_ch6_003_pack_activation(True, False, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH6006PlaybookContent:
    def test_authority_enforced(self):
        res = evaluate_pd_ch6_006_playbook_content({"phases": list(REQUIRED_PLAYBOOK_PHASES)}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-006"

    def test_missing_playbook(self):
        res = evaluate_pd_ch6_006_playbook_content(None, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-006"

    def test_missing_phase_checklist(self):
        pb = {"phases": ["P0", "P1", "P2"]}
        res = evaluate_pd_ch6_006_playbook_content(pb, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-006"

    def test_unqualified_adapter_claimed_usable(self):
        pb = {
            "phases": list(REQUIRED_PLAYBOOK_PHASES),
            "unqualified_adapter_claimed_usable": True,
        }
        res = evaluate_pd_ch6_006_playbook_content(pb, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH6-006"

    def test_playbook_content_satisfied(self):
        pb = {
            "phases": list(REQUIRED_PLAYBOOK_PHASES),
            "unqualified_adapter_claimed_usable": False,
        }
        res = evaluate_pd_ch6_006_playbook_content(pb, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestAggregateB6BGate:
    def test_aggregate_satisfied(self):
        payload = {
            "stack_pack": {
                "adapter_capability_families": {"schema": {"qualified": True}},
                "explicitly_blocked_checks": [],
            },
            "oss_qualification_record": {f: f"ref_{f}" for f in OSS_QUALIFICATION_FIELDS},
            "scope_specific_qualification": True,
            "effective_revocation_present": False,
            "playbook_content": {
                "phases": list(REQUIRED_PLAYBOOK_PHASES),
                "unqualified_adapter_claimed_usable": False,
            },
        }
        res = evaluate_b6_b_gate(payload, authority=AUTH)
        assert len(res) == 4
        assert all(out.state == GateState.SATISFIED for out in res.values())

    def test_aggregate_no_authority(self):
        res = evaluate_b6_b_gate({}, authority=None)
        assert len(res) == 4
        assert all(out.state == GateState.MISSING for out in res.values())
