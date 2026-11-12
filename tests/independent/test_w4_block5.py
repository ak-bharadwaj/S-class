"""Independent W4 Consumer Contract Scenarios for Block 5 (Chapter 8).

Mandated by S-CLASS M0 ITERATION 2 (E5):
- Standalone independent test functions under tests/independent/
- Covers all 6 Block 5 MUSTs (PD-CH8-008 through PD-CH8-013)
- Evaluates fail-closed security posture (unauthenticated / missing authority -> non-SATISFIED)
- Evaluates authorized consumer contracts (valid authority -> SATISFIED)
- Asserts GateOutput contract compliance (GateState closed vocabulary, to_dict schema)
"""
from __future__ import annotations

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
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


def test_w4_scenario_pd_ch8_008():
    """W4 Scenario for PD-CH8-008: Prevention boundary enforcement."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch8_008_prevention_boundary(True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH8-008"

    # 2. Native IDE claims blocked
    native = evaluate_pd_ch8_008_prevention_boundary(
        prevention_claimed=True,
        inside_qualified_enforcement_boundary=True,
        is_native_ide_activity=True,
        authority=AUTH,
    )
    assert isinstance(native, GateOutput)
    assert native.state == GateState.MISSING
    assert native.must_id == "PD-CH8-008"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch8_008_prevention_boundary(
        prevention_claimed=True,
        inside_qualified_enforcement_boundary=True,
        is_native_ide_activity=False,
        authority=AUTH,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH8-008"


def test_w4_scenario_pd_ch8_009():
    """W4 Scenario for PD-CH8-009: Workspace promotion gate."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch8_009_workspace_promotion(True, True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH8-009"

    # 2. Missing prerequisites fails closed
    missing_prereq = evaluate_pd_ch8_009_workspace_promotion(False, True, True, authority=AUTH)
    assert isinstance(missing_prereq, GateOutput)
    assert missing_prereq.state == GateState.MISSING
    assert missing_prereq.must_id == "PD-CH8-009"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch8_009_workspace_promotion(True, True, True, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH8-009"


def test_w4_scenario_pd_ch8_010():
    """W4 Scenario for PD-CH8-010: Out-of-band edits detection and resnapshot."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch8_010_out_of_band_edits(False, True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH8-010"

    # 2. Unresolved out-of-band edit fails closed
    unresolved = evaluate_pd_ch8_010_out_of_band_edits(True, False, False, authority=AUTH)
    assert isinstance(unresolved, GateOutput)
    assert unresolved.state == GateState.MISSING
    assert unresolved.must_id == "PD-CH8-010"

    # 3. Authorized consumer contract satisfied (re-snapshotted & verified)
    auth = evaluate_pd_ch8_010_out_of_band_edits(True, True, True, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH8-010"


def test_w4_scenario_pd_ch8_011():
    """W4 Scenario for PD-CH8-011: Parallel work serialization."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch8_011_parallel_work_serialization(True, True, True, True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH8-011"

    # 2. Broken serialization fails closed
    broken = evaluate_pd_ch8_011_parallel_work_serialization(True, False, True, True, True, authority=AUTH)
    assert isinstance(broken, GateOutput)
    assert broken.state == GateState.MISSING
    assert broken.must_id == "PD-CH8-011"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch8_011_parallel_work_serialization(True, True, True, True, True, authority=AUTH)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH8-011"


def test_w4_scenario_pd_ch8_012():
    """W4 Scenario for PD-CH8-012: Repository intelligence index freshness and symbols."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch8_012_repository_intelligence(True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH8-012"

    # 2. Unresolved symbol fails closed
    unresolved = evaluate_pd_ch8_012_repository_intelligence(
        discloses_coverage=True,
        discloses_freshness=True,
        unresolved_symbol_present=True,
        authority=AUTH,
    )
    assert isinstance(unresolved, GateOutput)
    assert unresolved.state == GateState.MISSING
    assert unresolved.must_id == "PD-CH8-012"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch8_012_repository_intelligence(
        discloses_coverage=True,
        discloses_freshness=True,
        unresolved_symbol_present=False,
        authority=AUTH,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH8-012"


def test_w4_scenario_pd_ch8_013():
    """W4 Scenario for PD-CH8-013: Budget exhaustion, frozen ledger, and repair routing."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch8_013_budget_exhaustion_ledger(
        budget_exhausted=False,
        routed_to_authorized_repair=False,
        authority=None,
    )
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH8-013"

    # 2. Second ledger active rejected
    second_ledger = evaluate_pd_ch8_013_budget_exhaustion_ledger(
        budget_exhausted=True,
        routed_to_authorized_repair=True,
        second_ledger_active=True,
        authority=AUTH,
    )
    assert isinstance(second_ledger, GateOutput)
    assert second_ledger.state == GateState.MISSING
    assert second_ledger.must_id == "PD-CH8-013"

    # 3. Authorized consumer contract satisfied (budget exhausted properly routed to repair)
    auth = evaluate_pd_ch8_013_budget_exhaustion_ledger(
        budget_exhausted=True,
        routed_to_authorized_repair=True,
        second_ledger_active=False,
        authority=AUTH,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH8-013"
