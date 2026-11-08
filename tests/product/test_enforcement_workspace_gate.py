"""Unit and regression tests for Chapter 8 Enforcement and Workspace Management Gate (Block 5, Lane B5).

Covers:
- PD-CH8-008: Prevention inside qualified enforcement boundary vs native IDE
- PD-CH8-009: Workspace promotion requiring target verification, release authority, rollback evidence
- PD-CH8-010: Out-of-band edits triggering re-snapshot and digest comparison
- PD-CH8-011: Parallel work serialization and canonical delta order
- PD-CH8-012: Repository intelligence index freshness and unresolved symbols
- PD-CH8-013: Budget exhaustion, frozen RetryBudget, and rejection of second ledger
"""
import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.enforcement_workspace_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch8_008_prevention_boundary,
    evaluate_pd_ch8_009_workspace_promotion,
    evaluate_pd_ch8_010_out_of_band_edits,
    evaluate_pd_ch8_011_parallel_work_serialization,
    evaluate_pd_ch8_012_repository_intelligence,
    evaluate_pd_ch8_013_budget_exhaustion_ledger,
    evaluate_b5_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


class TestPDCH8008PreventionBoundary:
    def test_authority_enforced(self):
        res = evaluate_pd_ch8_008_prevention_boundary(True, True, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH8-008"

    def test_prevention_claimed_native_ide(self):
        res = evaluate_pd_ch8_008_prevention_boundary(
            prevention_claimed=True,
            inside_qualified_enforcement_boundary=True,
            is_native_ide_activity=True,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING
        assert "BLOCKED" in res.detail

    def test_prevention_claimed_outside_boundary(self):
        res = evaluate_pd_ch8_008_prevention_boundary(
            prevention_claimed=True,
            inside_qualified_enforcement_boundary=False,
            is_native_ide_activity=False,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING
        assert "BLOCKED" in res.detail

    def test_prevention_claimed_inside_boundary(self):
        res = evaluate_pd_ch8_008_prevention_boundary(
            prevention_claimed=True,
            inside_qualified_enforcement_boundary=True,
            is_native_ide_activity=False,
            authority=AUTH,
        )
        assert res.state == GateState.SATISFIED

    def test_no_prevention_claimed(self):
        res = evaluate_pd_ch8_008_prevention_boundary(
            prevention_claimed=False,
            inside_qualified_enforcement_boundary=False,
            authority=AUTH,
        )
        assert res.state == GateState.SATISFIED


class TestPDCH8009WorkspacePromotion:
    def test_authority_enforced(self):
        res = evaluate_pd_ch8_009_workspace_promotion(True, True, True, authority=None)
        assert res.state == GateState.MISSING

    @pytest.mark.parametrize("t,k,r", [
        (False, True, True),
        (True, False, True),
        (True, True, False),
        (False, False, False),
    ])
    def test_missing_prerequisites(self, t, k, r):
        res = evaluate_pd_ch8_009_workspace_promotion(t, k, r, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH8-009"

    def test_promotion_satisfied(self):
        res = evaluate_pd_ch8_009_workspace_promotion(True, True, True, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH8010OutOfBandEdits:
    def test_authority_enforced(self):
        res = evaluate_pd_ch8_010_out_of_band_edits(False, True, True, authority=None)
        assert res.state == GateState.MISSING

    def test_no_oob_edits(self):
        res = evaluate_pd_ch8_010_out_of_band_edits(False, False, False, authority=AUTH)
        assert res.state == GateState.SATISFIED

    @pytest.mark.parametrize("re_snap,digest", [
        (False, True),
        (True, False),
        (False, False),
    ])
    def test_oob_edits_failure(self, re_snap, digest):
        res = evaluate_pd_ch8_010_out_of_band_edits(True, re_snap, digest, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH8-010"

    def test_oob_edits_satisfied(self):
        res = evaluate_pd_ch8_010_out_of_band_edits(True, True, True, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH8011ParallelWorkSerialization:
    def test_authority_enforced(self):
        res = evaluate_pd_ch8_011_parallel_work_serialization(True, True, True, True, True, authority=None)
        assert res.state == GateState.MISSING

    @pytest.mark.parametrize("d,c,o,t,v", [
        (False, True, True, True, True),
        (True, False, True, True, True),
        (True, True, False, True, True),
        (True, True, True, False, True),
        (True, True, True, True, False),
    ])
    def test_parallel_work_failures(self, d, c, o, t, v):
        res = evaluate_pd_ch8_011_parallel_work_serialization(d, c, o, t, v, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH8-011"

    def test_parallel_work_satisfied(self):
        res = evaluate_pd_ch8_011_parallel_work_serialization(True, True, True, True, True, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH8012RepositoryIntelligence:
    def test_authority_enforced(self):
        res = evaluate_pd_ch8_012_repository_intelligence(True, True, authority=None)
        assert res.state == GateState.MISSING

    @pytest.mark.parametrize("cov,fresh,unresolved", [
        (False, True, False),
        (True, False, False),
        (True, True, True),
        (False, False, True),
    ])
    def test_repo_intel_failures(self, cov, fresh, unresolved):
        res = evaluate_pd_ch8_012_repository_intelligence(
            cov, fresh, unresolved_symbol_present=unresolved, authority=AUTH
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH8-012"

    def test_repo_intel_satisfied(self):
        res = evaluate_pd_ch8_012_repository_intelligence(True, True, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH8013BudgetExhaustionLedger:
    def test_authority_enforced(self):
        res = evaluate_pd_ch8_013_budget_exhaustion_ledger(False, False, authority=None)
        assert res.state == GateState.MISSING

    def test_second_ledger_rejected(self):
        res = evaluate_pd_ch8_013_budget_exhaustion_ledger(
            False, False, second_ledger_active=True, authority=AUTH
        )
        assert res.state == GateState.MISSING

    def test_model_reported_only_rejected(self):
        res = evaluate_pd_ch8_013_budget_exhaustion_ledger(
            False, False, model_reported_only_cost=True, authority=AUTH
        )
        assert res.state == GateState.MISSING

    def test_no_authoritative_cost_rejected(self):
        res = evaluate_pd_ch8_013_budget_exhaustion_ledger(
            False, False, authoritative_host_cost=False, authority=AUTH
        )
        assert res.state == GateState.MISSING

    def test_exhausted_without_repair_route_rejected(self):
        res = evaluate_pd_ch8_013_budget_exhaustion_ledger(
            True, False, authority=AUTH
        )
        assert res.state == GateState.MISSING

    def test_exhausted_with_repair_route_satisfied(self):
        res = evaluate_pd_ch8_013_budget_exhaustion_ledger(
            True, True, authority=AUTH
        )
        assert res.state == GateState.SATISFIED

    def test_normal_budget_satisfied(self):
        res = evaluate_pd_ch8_013_budget_exhaustion_ledger(
            False, False, authority=AUTH
        )
        assert res.state == GateState.SATISFIED


class TestAggregateB5Gate:
    def test_aggregate_gate_all_satisfied(self):
        payload = {
            "prevention_claimed": True,
            "inside_qualified_enforcement_boundary": True,
            "target_verified": True,
            "kernel_release_authority": True,
            "rollback_evidence_preserved": True,
            "out_of_band_edits_detected": False,
            "dependencies_satisfied": True,
            "canonical_delta_order": True,
            "overlapping_writes_serialized": True,
            "target_identity_match": True,
            "all_task_verification_pass": True,
            "discloses_coverage": True,
            "discloses_freshness": True,
            "budget_exhausted": False,
        }
        res = evaluate_b5_gate(payload, authority=AUTH)
        assert len(res) == 6
        assert all(out.state == GateState.SATISFIED for out in res.values())

    def test_aggregate_gate_no_auth(self):
        res = evaluate_b5_gate({}, authority=None)
        assert len(res) == 6
        assert all(out.state == GateState.MISSING for out in res.values())
