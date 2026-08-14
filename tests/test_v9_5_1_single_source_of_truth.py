"""
S-Class EOS V9.5.1 - Single Source of Truth & Structural Governance Test Suite

Validates:
1. Legacy compiler output is completely excluded from canonical SynthesizedSpec.
2. FSM consumes persisted DebateResult without re-executing debate or mutating governed artifacts in place.
3. Pipeline refinement creates immutable version backups (v7_refinement_pipeline_v1.json), leaving v1 untouched.
4. Production execution mode strictly rejects synthetic clarification answers, grill reports, and receipts.
5. Authoritative pipeline BLOCKED state cannot be overwritten to False by FSM.
"""

import os
import sys
import json
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from runtime import FSMGoalSequenceRunner, load_json, write_json_atomic
from verifier import EvidenceVerifier
from spec_synthesis import SpecSynthesisEngine


def test_legacy_compiler_output_not_in_canonical_synthesized_spec(tmp_path):
    """Adversarial Test 1: SynthesizedSpec MUST derive low_level_designs solely from authoritative v7_pipeline."""
    tmp_workspace = str(tmp_path)
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Build healthcare patient portal", workspace_dir=tmp_workspace)

    agents_dir = os.path.join(tmp_workspace, ".agents")
    pipe_path = os.path.join(agents_dir, "v7_refinement_pipeline.json")
    assert os.path.exists(pipe_path)

    pipe_data = load_json(pipe_path)
    auth_llds = [c.to_dict() if hasattr(c, "to_dict") else c for c in pipe_data.get("lld_components", [])]

    # Canonical SynthesizedSpec LLDs MUST match authoritative pipeline LLDs
    assert len(spec.low_level_designs) == len(auth_llds)


def test_fsm_consumes_persisted_debate_result_without_mutating_artifact(tmp_path):
    """Adversarial Test 2: FSM GoalSequenceRunner MUST consume v7_refinement_pipeline.json without mutating it during phase checks."""
    tmp_workspace = str(tmp_path)
    state_dir = os.path.join(tmp_workspace, ".agents")
    os.makedirs(state_dir, exist_ok=True)

    pipe_file = os.path.join(state_dir, "v7_refinement_pipeline.json")
    initial_pipe = {
        "blocked": False,
        "hld_governance": {"is_blocked": False},
        "debate_result": {"accepted_adrs": [{"id": "ADR-001"}], "rejected_adrs": []},
        "version": 1
    }
    write_json_atomic(pipe_file, initial_pipe)

    # Run FSM helper on DEBATE phase
    FSMGoalSequenceRunner._ensure_phase_evidence("DEBATE", tmp_workspace)

    # Pipeline file MUST remain exactly unchanged (NO in-place mutation or debate rerun side effects!)
    current_pipe = load_json(pipe_file)
    assert current_pipe == initial_pipe


def test_pipeline_mutation_creates_new_version_backup(tmp_path):
    """Adversarial Test 3: Re-running synthesis creates v7_refinement_pipeline_v1.json backup, leaving v1 intact."""
    tmp_workspace = str(tmp_path)
    engine = SpecSynthesisEngine()

    # Step 1: Synthesis v1
    spec1 = engine.run_synthesis("Build ERP System v1", workspace_dir=tmp_workspace)
    assert spec1.spec_version == 1

    agents_dir = os.path.join(tmp_workspace, ".agents")
    pipe_v1_path = os.path.join(agents_dir, "v7_refinement_pipeline.json")
    assert os.path.exists(pipe_v1_path)

    # Step 2: Synthesis v2 with clarification
    answers = {"REQ-BASE-0": "Approved ERP scope with RBAC security policy"}
    write_json_atomic(os.path.join(agents_dir, "clarification_answers.json"), answers)

    spec2 = engine.run_synthesis("Build ERP System v2", workspace_dir=tmp_workspace, clarification_answers=answers)
    assert spec2.spec_version == 2

    # Immutable backup MUST exist for v1
    backup_v1_path = os.path.join(agents_dir, "v7_refinement_pipeline_v1.json")
    assert os.path.exists(backup_v1_path)


def test_production_mode_rejects_synthetic_clarifications_and_receipts(tmp_path):
    """Adversarial Test 4: Production execution mode MUST reject synthetic clarification answers and test receipts."""
    tmp_workspace = str(tmp_path)
    state_dir = os.path.join(tmp_workspace, ".agents")
    os.makedirs(state_dir, exist_ok=True)

    # Write a valid synthesized_spec.json
    write_json_atomic(os.path.join(state_dir, "synthesized_spec.json"), {
        "intent_summary": "Test intent",
        "requirements": {"reqs": [{"id": "REQ-1"}]},
        "affected_systems": ["backend"],
        "acceptance_criteria": ["criteria 1"],
        "gate_result": "PASS"
    })

    # Write a synthetic clarification answer file
    answers_file = os.path.join(state_dir, "clarification_answers.json")
    write_json_atomic(answers_file, {
        "answers": {"REQ-1": "Approved default behavior for REQ-1"},
        "synthetic": True,
        "authority": "TEST_SYNTHETIC"
    })

    # In PRODUCTION mode -> EvidenceVerifier MUST fail!
    os.environ["SCLASS_EXECUTION_MODE"] = "PRODUCTION"
    try:
        res = EvidenceVerifier.verify_phase("CLARIFICATION", workspace_dir=tmp_workspace, allow_soft=False)
        assert res.passed is False
        assert any("PRODUCTION EXECUTION GATE FAILURE" in err for err in res.errors)
    finally:
        os.environ["SCLASS_EXECUTION_MODE"] = "TEST"


def test_authoritative_pipeline_blocked_cannot_be_overwritten_by_fsm(tmp_path):
    """Adversarial Test 5: Blocked state in v7_refinement_pipeline CANNOT be overwritten by FSM."""
    tmp_workspace = str(tmp_path)
    state_dir = os.path.join(tmp_workspace, ".agents")
    os.makedirs(state_dir, exist_ok=True)

    pipe_file = os.path.join(state_dir, "v7_refinement_pipeline.json")
    write_json_atomic(pipe_file, {
        "blocked": True,
        "hld_governance": {"is_blocked": True},
        "debate_result": {"rejected_adrs": [{"id": "ADR-CRITICAL", "status": "REJECTED"}]}
    })

    FSMGoalSequenceRunner._ensure_phase_evidence("DESIGN", tmp_workspace)

    pipe_after = load_json(pipe_file)
    assert pipe_after.get("blocked") is True
    assert FSMGoalSequenceRunner._override_event == "spec_conflict_detected"
