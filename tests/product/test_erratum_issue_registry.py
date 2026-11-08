"""Unit and regression tests for Chapter 10 Erratum Governance, Open Issue Schema & Cross-Link Gate (Block 9, Lane B9-C).

Covers:
- PD-CH10-012: Formal erratum path, insufficiency/replay analysis, rejection of ad-hoc edits
- PD-CH10-013: Open issue schema, OI-008 closure requirements (2 raw fresh-chat reviews)
- PD-CH10-007: Version/qualification and issue/claim registry cross-links to master
"""
import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.erratum_issue_registry import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_OPEN_ISSUE_FIELDS,
    evaluate_pd_ch10_012_frozen_erratum_path,
    evaluate_pd_ch10_013_open_issue_schema,
    evaluate_pd_ch10_007_master_cross_links,
    evaluate_b9_c_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


class TestPDCH10012FrozenErratumPath:
    def test_authority_enforced(self):
        res = evaluate_pd_ch10_012_frozen_erratum_path(True, True, True, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-012"

    def test_ad_hoc_edit_rejected(self):
        res = evaluate_pd_ch10_012_frozen_erratum_path(
            True, True, True, ad_hoc_source_edit=True, authority=AUTH
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-012"

    @pytest.mark.parametrize("formal,insuff,replay", [
        (False, True, True),
        (True, False, True),
        (True, True, False),
    ])
    def test_missing_prerequisites(self, formal, insuff, replay):
        res = evaluate_pd_ch10_012_frozen_erratum_path(formal, insuff, replay, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-012"

    def test_erratum_path_satisfied(self):
        res = evaluate_pd_ch10_012_frozen_erratum_path(True, True, True, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH10013OpenIssueSchema:
    def test_authority_enforced(self):
        res = evaluate_pd_ch10_013_open_issue_schema({}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-013"

    def test_missing_issue_payload(self):
        res = evaluate_pd_ch10_013_open_issue_schema(None, authority=AUTH)
        assert res.state == GateState.MISSING

    @pytest.mark.parametrize("missing_field", list(REQUIRED_OPEN_ISSUE_FIELDS))
    def test_missing_issue_field(self, missing_field):
        issue = {f: f"val_{f}" for f in REQUIRED_OPEN_ISSUE_FIELDS}
        del issue[missing_field]
        res = evaluate_pd_ch10_013_open_issue_schema(issue, authority=AUTH)
        assert res.state == GateState.MISSING
        assert "BLOCKED" in res.detail

    def test_oi_008_closed_without_reviews_rejected(self):
        issue = {f: f"val_{f}" for f in REQUIRED_OPEN_ISSUE_FIELDS}
        issue["id"] = "OI-008"
        issue["status"] = "CLOSED"
        res = evaluate_pd_ch10_013_open_issue_schema(issue, oi_008_owner_reviews_count=1, authority=AUTH)
        assert res.state == GateState.MISSING
        assert "BLOCKED" in res.detail

    def test_oi_008_closed_with_2_reviews_satisfied(self):
        issue = {f: f"val_{f}" for f in REQUIRED_OPEN_ISSUE_FIELDS}
        issue["id"] = "OI-008"
        issue["status"] = "CLOSED"
        res = evaluate_pd_ch10_013_open_issue_schema(issue, oi_008_owner_reviews_count=2, authority=AUTH)
        assert res.state == GateState.SATISFIED

    def test_standard_issue_satisfied(self):
        issue = {f: f"val_{f}" for f in REQUIRED_OPEN_ISSUE_FIELDS}
        issue["id"] = "OI-001"
        issue["status"] = "OPEN"
        res = evaluate_pd_ch10_013_open_issue_schema(issue, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH10007MasterCrossLinks:
    def test_authority_enforced(self):
        res = evaluate_pd_ch10_007_master_cross_links(True, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH10-007"

    def test_unknown_references_rejected(self):
        res = evaluate_pd_ch10_007_master_cross_links(
            cross_linked_to_master=True, unknown_references_present=True, authority=AUTH
        )
        assert res.state == GateState.MISSING

    def test_missing_cross_links_rejected(self):
        res = evaluate_pd_ch10_007_master_cross_links(
            cross_linked_to_master=False, unknown_references_present=False, authority=AUTH
        )
        assert res.state == GateState.MISSING

    def test_cross_links_satisfied(self):
        res = evaluate_pd_ch10_007_master_cross_links(
            cross_linked_to_master=True, unknown_references_present=False, authority=AUTH
        )
        assert res.state == GateState.SATISFIED


class TestAggregateB9CGate:
    def test_aggregate_satisfied(self):
        payload = {
            "formal_erratum_path": True,
            "insufficiency_analysis_present": True,
            "replay_analysis_present": True,
            "ad_hoc_source_edit": False,
            "issue": {f: f"val_{f}" for f in REQUIRED_OPEN_ISSUE_FIELDS},
            "cross_linked_to_master": True,
            "unknown_references_present": False,
        }
        res = evaluate_b9_c_gate(payload, authority=AUTH)
        assert len(res) == 3
        assert all(out.state == GateState.SATISFIED for out in res.values())

    def test_aggregate_no_authority(self):
        res = evaluate_b9_c_gate({}, authority=None)
        assert len(res) == 3
        assert all(out.state == GateState.MISSING for out in res.values())
