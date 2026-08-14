"""
S-Class EOS V9.5 - Single Source of Truth & Control-Plane Unification Test Suite

Validates:
1. FSM sequence runner respects blocked V9 pipeline without rerunning debate or overwriting blocked=False.
2. V7/V9 Refinement Pipeline is the single authoritative source of truth in SpecSynthesisEngine.
3. EvidenceVerifier strictly rejects synthetic/simulation receipts when executed in PRODUCTION mode.
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


def test_fsm_runner_respects_blocked_v9_pipeline_without_overwriting(tmp_path):
    """Adversarial Test 1: FSM runner MUST NOT rerun debate with empty graphs or overwrite blocked=False when pipeline is blocked."""
    tmp_workspace = str(tmp_path)
    state_dir = os.path.join(tmp_workspace, ".agents")
    os.makedirs(state_dir, exist_ok=True)

    # Write a blocked v7_refinement_pipeline.json artifact
    pipe_file = os.path.join(state_dir, "v7_refinement_pipeline.json")
    blocked_data = {
        "blocked": True,
        "hld_governance": {"is_blocked": True},
        "debate_result": {"rejected_adrs": [{"id": "ADR-001", "status": "REJECTED"}]}
    }
    write_json_atomic(pipe_file, blocked_data)

    # Run FSM helper
    FSMGoalSequenceRunner._ensure_phase_evidence("DESIGN", tmp_workspace)

    # 1. Blocked status MUST remain True (NEVER overwritten to False!)
    updated_pipe = load_json(pipe_file)
    assert updated_pipe.get("blocked") is True
    assert updated_pipe.get("hld_governance", {}).get("is_blocked") is True

    # 2. FSM transition event MUST be overridden to spec_conflict_detected
    assert FSMGoalSequenceRunner._override_event == "spec_conflict_detected"


def test_evidence_verifier_rejects_synthetic_simulation_receipts_in_production_mode(tmp_path):
    """Adversarial Test 2: EvidenceVerifier MUST reject synthetic simulation receipts when SCLASS_EXECUTION_MODE == 'PRODUCTION'."""
    tmp_workspace = str(tmp_path)
    state_dir = os.path.join(tmp_workspace, ".agents")
    os.makedirs(state_dir, exist_ok=True)

    # Write a valid synthesized_spec.json artifact
    spec_file = os.path.join(state_dir, "synthesized_spec.json")
    write_json_atomic(spec_file, {
        "intent_summary": "Test intent",
        "requirements": {"reqs": [{"id": "REQ-1"}]},
        "affected_systems": ["backend"],
        "acceptance_criteria": ["criteria 1"],
        "gate_result": "PASS"
    })

    # Write a synthetic design blueprint receipt
    design_file = os.path.join(state_dir, "design_blueprint.json")
    synthetic_design = {
        "phase": "DESIGN",
        "blueprint_status": "APPROVED",
        "provenance_metadata": {
            "mode": "SIMULATION",
            "synthetic": True,
            "authority": "FSM_TEST_RUNNER"
        },
        "backend_spec": {"services": ["AuthService"]},
        "db_schema": {"tables": ["users"]},
        "frontend_layout": {"components": ["Header"]}
    }
    write_json_atomic(design_file, synthetic_design)

    # In TEST execution mode -> Verifier allows soft/test verification
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
    res_test = EvidenceVerifier.verify_phase("DESIGN", workspace_dir=tmp_workspace, allow_soft=True)
    assert res_test.passed is True

    # In PRODUCTION execution mode -> Verifier MUST fail and reject synthetic receipt!
    os.environ["SCLASS_EXECUTION_MODE"] = "PRODUCTION"
    try:
        res_prod = EvidenceVerifier.verify_phase("DESIGN", workspace_dir=tmp_workspace, allow_soft=False)
        assert res_prod.passed is False
        assert any("PRODUCTION EXECUTION GATE FAILURE" in err for err in res_prod.errors)
    finally:
        os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
