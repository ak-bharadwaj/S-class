"""Tests for Lifecycle P11 & Operations Governance Engine.

Verifies:
- PD-CH2-054: Signals must ground in canonical facts; propose P0 re-entry only (CH2-T54).
- PD-CH2-058: Work type phase applicability matrix (CH2-T61 gaming A1..A3, CH2-T62 happy).
- PD-CH2-060: User-facing default flows preserve P0..P11 order (CH2-T65 gaming A1..A3, CH2-T66 happy).
- PD-CH2-061: Operations/delivery flows bind entry, gate outputs, rollback (CH2-T67 gaming A1..A3, CH2-T68 happy).
- PD-CH2-062: Project-class qualification requires explicit fit evidence (CH2-T69 gaming A1..A3, CH2-T70 happy).
- PD-CH2-063: Question budget integer enforcement and blocker preservation (CH2-T71 gaming A1..A3, CH2-T72 happy).
"""
from __future__ import annotations

import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p11 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    ALL_PHASES,
    REGISTERED_WORK_TYPES,
    DEFAULT_QUESTION_BATCH_CAP,
    evaluate_pd_ch2_054_signal,
    evaluate_pd_ch2_058_applicability,
    evaluate_pd_ch2_060_flow_order,
    evaluate_pd_ch2_061_delivery_flow,
    evaluate_pd_ch2_062_project_class,
    evaluate_pd_ch2_063_question_budget,
    evaluate_p11_gate,
)


# =============================================================================
# 1. PD-CH2-054 Signals Tests
# =============================================================================

def test_pd_ch2_054_gaming_fixture_ch2_t54():
    """CH2-T54 Gaming: Missing source event ref and proposes workspace mutation -> MISSING[PD-CH2-054]."""
    payload = {
        "source_event_ref": "absent",
        "baseline_digest": "D1",
        "observed_digest": "D2",
        "proposed_action": "mutate_workspace",
    }
    res = evaluate_pd_ch2_054_signal(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-054"
    assert str(res) == "MISSING[PD-CH2-054]"


def test_pd_ch2_054_missing_source_event_ref_isolated():
    """Mutant kill test: source_event_ref absent with valid propose_p0_reentry action."""
    payload = {
        "source_event_ref": "absent",
        "baseline_digest": "D1",
        "observed_digest": "D2",
        "proposed_action": "propose_p0_reentry",
    }
    res = evaluate_pd_ch2_054_signal(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-054"
    assert "lacks canonical source_event_ref" in res.detail


def test_pd_ch2_054_mutate_workspace_isolated():
    """Mutant kill test: valid source_event_ref but proposing workspace mutation."""
    payload = {
        "source_event_ref": "EVT-CANONICAL-10",
        "baseline_digest": "D1",
        "observed_digest": "D2",
        "proposed_action": "mutate_workspace",
    }
    res = evaluate_pd_ch2_054_signal(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-054"
    assert "autonomous canonical mutation" in res.detail


def test_pd_ch2_054_happy_fixture_ch2_t54():
    """CH2-T54 Happy: Valid signal with source_event_ref proposing P0 re-entry -> SATISFIED."""
    payload = {
        "source_event_ref": "EVT-CANONICAL-10",
        "baseline_digest": "D1",
        "observed_digest": "D2",
        "proposed_action": "propose_p0_reentry",
    }
    res = evaluate_pd_ch2_054_signal(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
    assert str(res) == "SATISFIED"


# =============================================================================
# 2. PD-CH2-058 Applicability Tests
# =============================================================================

def test_pd_ch2_058_happy_fixture_ch2_t62():
    """CH2-T62 Happy: All 12 phases declared with explicit skip reasons and evaluator ref -> SATISFIED."""
    payload = {
        "must_id": "PD-CH2-058",
        "work_type": "FEATURE",
        "applicability_records[P0..P11]": list(ALL_PHASES),
        "skip_reason": "none",
        "evaluator_record_ref": "EVAL-APP-001",
    }
    res = evaluate_pd_ch2_058_applicability(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_pd_ch2_058_gaming_fixture_ch2_t61_variant_a1():
    """CH2-T61 A1: applicability_records has 11 phases (P7 missing) -> MISSING[PD-CH2-058]."""
    phases_missing_p7 = [p for p in ALL_PHASES if p != "P7"]
    payload = {
        "must_id": "PD-CH2-058",
        "work_type": "FEATURE",
        "applicability_records[P0..P11]": phases_missing_p7,
        "skip_reason": "none",
        "evaluator_record_ref": "EVAL-APP-001",
    }
    res = evaluate_pd_ch2_058_applicability(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-058"


def test_pd_ch2_058_gaming_fixture_ch2_t61_variant_a2():
    """CH2-T61 A2: skip_reason empty for P4 skipped -> MISSING[PD-CH2-058]."""
    payload = {
        "must_id": "PD-CH2-058",
        "work_type": "SPIKE_RESEARCH",
        "applicability_records[P0..P11]": list(ALL_PHASES),
        "skip_reason": "   ",
        "evaluator_record_ref": "EVAL-APP-001",
    }
    res = evaluate_pd_ch2_058_applicability(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-058"


def test_pd_ch2_058_gaming_fixture_ch2_t61_variant_a3():
    """CH2-T61 A3: agent marks phase without evaluator_record_ref -> MISSING[PD-CH2-058]."""
    payload = {
        "must_id": "PD-CH2-058",
        "work_type": "FEATURE",
        "applicability_records[P0..P11]": list(ALL_PHASES),
        "skip_reason": "none",
        "evaluator_record_ref": None,
    }
    res = evaluate_pd_ch2_058_applicability(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-058"


# =============================================================================
# 3. PD-CH2-060 Default Flow Order Tests
# =============================================================================

def test_pd_ch2_060_happy_fixture_ch2_t66():
    """CH2-T66 Happy: Default user flow preserves P0..P11 order -> SATISFIED."""
    payload = {
        "must_id": "PD-CH2-060",
        "flow_definition_digest": "FLOW-DEF-01",
        "phase_order": ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"],
        "defect_origin_phase": "P2",
        "replay_start_phase": "P2",
    }
    res = evaluate_pd_ch2_060_flow_order(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_pd_ch2_060_gaming_fixture_ch2_t65_variant_a1():
    """CH2-T65 A1: phase_order lists P5 before P4 -> MISSING[PD-CH2-060]."""
    payload = {
        "must_id": "PD-CH2-060",
        "phase_order": ["P0", "P1", "P2", "P3", "P5", "P4"],
    }
    res = evaluate_pd_ch2_060_flow_order(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-060"


def test_pd_ch2_060_gaming_fixture_ch2_t65_variant_a2():
    """CH2-T65 A2: defect_origin_phase=P2 but replay starts at P5 -> MISSING[PD-CH2-060]."""
    payload = {
        "must_id": "PD-CH2-060",
        "phase_order": ["P0", "P1", "P2"],
        "defect_origin_phase": "P2",
        "replay_start_phase": "P5",
    }
    res = evaluate_pd_ch2_060_flow_order(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-060"


# =============================================================================
# 4. PD-CH2-061 Delivery Flow Tests
# =============================================================================

def test_pd_ch2_061_happy_fixture_ch2_t68():
    """CH2-T68 Happy: Bound entry, gate outputs, and rollback conditions -> SATISFIED."""
    payload = {
        "must_id": "PD-CH2-061",
        "entry_predicate_digest": "DIGEST-ENTRY-01",
        "gate_output_digests": ["DIGEST-GATE-01", "DIGEST-GATE-02"],
        "rollback_condition_digest": "DIGEST-ROLLBACK-01",
    }
    res = evaluate_pd_ch2_061_delivery_flow(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_pd_ch2_061_gaming_fixture_ch2_t67_variant_a1():
    """CH2-T67 A1: rollback_condition_digest absent -> MISSING[PD-CH2-061]."""
    payload = {
        "must_id": "PD-CH2-061",
        "entry_predicate_digest": "DIGEST-ENTRY-01",
        "gate_output_digests": ["DIGEST-GATE-01"],
    }
    res = evaluate_pd_ch2_061_delivery_flow(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-061"


def test_pd_ch2_061_gaming_fixture_ch2_t67_variant_a2():
    """CH2-T67 A2: entry_predicate_digest stale -> MISSING[PD-CH2-061]."""
    payload = {
        "must_id": "PD-CH2-061",
        "entry_predicate_digest": "DIGEST-OLD",
        "entry_predicate_stale": True,
        "gate_output_digests": ["DIGEST-GATE-01"],
        "rollback_condition_digest": "DIGEST-RB",
    }
    res = evaluate_pd_ch2_061_delivery_flow(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-061"


# =============================================================================
# 5. PD-CH2-062 Project-Class Qualification Tests
# =============================================================================

def test_pd_ch2_062_happy_fixture_ch2_t70():
    """CH2-T70 Happy: Pinned qualified adapter record satisfies required capabilities -> SATISFIED."""
    payload = {
        "must_id": "PD-CH2-062",
        "project_class": "python_backend",
        "fit_evidence_digest": "DIGEST-FIT-001",
        "qualification_record_digest": "DIGEST-QUAL-001",
    }
    res = evaluate_pd_ch2_062_project_class(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_pd_ch2_062_gaming_fixture_ch2_t69_variant_a1():
    """CH2-T69 A1: fit_evidence_digest absent (inferred from language) -> MISSING[PD-CH2-062]."""
    payload = {
        "must_id": "PD-CH2-062",
        "project_class": "python_backend",
        "qualification_record_digest": "DIGEST-QUAL-001",
    }
    res = evaluate_pd_ch2_062_project_class(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-062"


def test_pd_ch2_062_gaming_fixture_ch2_t69_variant_a2():
    """CH2-T69 A2: repo size 12k files used as fit evidence -> MISSING[PD-CH2-062]."""
    payload = {
        "must_id": "PD-CH2-062",
        "project_class": "python_backend",
        "fit_evidence_digest": "repo_size_12k_files",
        "qualification_record_digest": "DIGEST-QUAL-001",
    }
    res = evaluate_pd_ch2_062_project_class(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-062"


def test_pd_ch2_062_gaming_fixture_ch2_t69_variant_a3():
    """CH2-T69 A3: agent writes qualified=true in project profile -> MISSING[PD-CH2-062]."""
    payload = {
        "must_id": "PD-CH2-062",
        "project_class": "python_backend",
        "fit_evidence_digest": "DIGEST-FIT-001",
        "qualification_record_digest": "agent_self_asserted_qualified_true",
    }
    res = evaluate_pd_ch2_062_project_class(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-062"


# =============================================================================
# 6. PD-CH2-063 Question Budget Tests
# =============================================================================

def test_pd_ch2_063_happy_fixture_ch2_t72():
    """CH2-T72 Happy: questions_asked within budget, unresolved blockers open -> SATISFIED."""
    payload = {
        "must_id": "PD-CH2-063",
        "question_budget": 5,
        "questions_asked": 3,
        "open_blockers_digest": "DIGEST-BLOCKERS-01",
        "treated_as_complete": False,
    }
    res = evaluate_pd_ch2_063_question_budget(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_pd_ch2_063_gaming_fixture_ch2_t71_variant_a1():
    """CH2-T71 A1: questions_asked is negative or non-integer -> MISSING[PD-CH2-063]."""
    payload = {
        "must_id": "PD-CH2-063",
        "questions_asked": -1,
    }
    res = evaluate_pd_ch2_063_question_budget(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-063"


def test_pd_ch2_063_gaming_fixture_ch2_t71_variant_a2():
    """CH2-T71 A2: questions_asked exceeds budget while open blockers remain -> MISSING[PD-CH2-063]."""
    payload = {
        "must_id": "PD-CH2-063",
        "question_budget": 5,
        "questions_asked": 6,
        "open_blockers_digest": "DIGEST-BLOCKERS-01",
        "treated_as_complete": True,
    }
    res = evaluate_pd_ch2_063_question_budget(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-063"


def test_pd_ch2_063_gaming_fixture_ch2_t71_variant_a3():
    """CH2-T71 A3: open_blockers_digest cleared by an agent write -> MISSING[PD-CH2-063]."""
    payload = {
        "must_id": "PD-CH2-063",
        "question_budget": 5,
        "questions_asked": 5,
        "open_blockers_digest": "cleared_by_agent",
    }
    res = evaluate_pd_ch2_063_question_budget(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-063"


# =============================================================================
# 7. Security & Dispatcher Tests
# =============================================================================

def test_unauthorized_p11_caller_rejected():
    """Fails closed when caller_authority is omitted or incorrect."""
    payload = {"source_event_ref": "EVT-1"}
    res_none = evaluate_pd_ch2_054_signal(payload, caller_authority=None)
    assert res_none.state == GateState.MISSING
    assert res_none.must_id == "PD-CH2-054"

    res_agent = evaluate_pd_ch2_054_signal(payload, caller_authority="AGENT")
    assert res_agent.state == GateState.MISSING
    assert res_agent.must_id == "PD-CH2-054"


def test_unified_evaluate_p11_gate_dispatch():
    """Verifies evaluate_p11_gate dispatches across MUST IDs."""
    payload = {
        "must_id": "PD-CH2-054",
        "source_event_ref": "EVT-1",
        "proposed_action": "p0",
    }
    res = evaluate_p11_gate(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED
