"""Unit and regression tests for Chapter 7 Notification Projections & Skill Normalization Gate (Block 7, Lane B7-B).

Covers:
- PD-CH7-014: Notifications derived from gate projections, no model message approval
- PD-CH7-015: External skill/playbook content normalized into S-Class-owned checks
"""
import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.notification_skill_normalization import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch7_014_notification_projections,
    evaluate_pd_ch7_015_external_skill_normalization,
    evaluate_b7_b_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


class TestPDCH7014NotificationProjections:
    def test_authority_enforced(self):
        res = evaluate_pd_ch7_014_notification_projections(True, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-014"

    def test_not_derived_from_gate(self):
        res = evaluate_pd_ch7_014_notification_projections(False, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-014"

    def test_implies_approval_on_model_message_rejected(self):
        res = evaluate_pd_ch7_014_notification_projections(
            derived_from_gate_projection=True,
            implies_approval_on_model_message=True,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-014"

    def test_valid_notification_projection_satisfied(self):
        res = evaluate_pd_ch7_014_notification_projections(
            derived_from_gate_projection=True,
            implies_approval_on_model_message=False,
            authority=AUTH,
        )
        assert res.state == GateState.SATISFIED


class TestPDCH7015ExternalSkillNormalization:
    def test_authority_enforced(self):
        res = evaluate_pd_ch7_015_external_skill_normalization(True, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-015"

    def test_not_normalized_into_checks(self):
        res = evaluate_pd_ch7_015_external_skill_normalization(False, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-015"

    def test_creates_alternate_lifecycle_rejected(self):
        res = evaluate_pd_ch7_015_external_skill_normalization(
            normalized_into_sclass_owned_checks=True,
            creates_alternate_lifecycle_or_loop=True,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH7-015"

    def test_valid_skill_normalization_satisfied(self):
        res = evaluate_pd_ch7_015_external_skill_normalization(
            normalized_into_sclass_owned_checks=True,
            creates_alternate_lifecycle_or_loop=False,
            authority=AUTH,
        )
        assert res.state == GateState.SATISFIED


class TestAggregateB7BGate:
    def test_aggregate_satisfied(self):
        payload = {
            "derived_from_gate_projection": True,
            "implies_approval_on_model_message": False,
            "normalized_into_sclass_owned_checks": True,
            "creates_alternate_lifecycle_or_loop": False,
        }
        res = evaluate_b7_b_gate(payload, authority=AUTH)
        assert len(res) == 2
        assert all(out.state == GateState.SATISFIED for out in res.values())

    def test_aggregate_no_authority(self):
        res = evaluate_b7_b_gate({}, authority=None)
        assert len(res) == 2
        assert all(out.state == GateState.MISSING for out in res.values())
