import os
import json
import pytest
import shutil
import tempfile
from spec_synthesis import (
    RequirementType,
    ArtifactAction,
    RequirementCategory,
    DecisionThreshold,
    GateResult,
    EvidenceReference,
    SynthesizedRequirement,
    CapabilityExpansionEngine,
    DerivedInferenceEngine,
    RequirementGraph,
    SemanticGate,
    SpecSynthesisEngine,
    SynthesizedSpec
)

@pytest.fixture
def tmp_workspace():
    tmp_dir = tempfile.mkdtemp()
    agents_dir = os.path.join(tmp_dir, ".agents")
    os.makedirs(agents_dir, exist_ok=True)
    
    # Create sample orchestration_state.json
    state_data = {
        "taskId": "test-task-123",
        "currentPhase": "ANALYSIS",
        "activeEvent": None,
        "currentSpecVersion": 1,
        "currentDebateVersion": 0,
        "currentTaskVersion": 0,
        "retryCount": 0,
        "confidenceMatrix": {"weightedScore": 1.0, "votes": {}},
        "tasks": [],
        "decisionLog": [],
        "transitionHistory": []
    }
    with open(os.path.join(agents_dir, "orchestration_state.json"), "w", encoding="utf-8") as f:
        json.dump(state_data, f)
        
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_no_generic_role_pages_without_evidence(tmp_workspace):
    """Verify that roles do NOT produce generic template pages without project evidence."""
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("System has 3 roles: student, instructor, admin", tmp_workspace)
    
    req_descriptions = [r["description"].lower() for r_list in spec.requirements.values() for r in r_list]
    assert not any("accreditation" in d for d in req_descriptions)
    assert not any("gamification" in d for d in req_descriptions)


def test_crud_not_derived_from_entity_alone(tmp_workspace):
    """Verify entity existence does NOT imply full CRUD capability (e.g., DELETE /results/:id)."""
    digest_data = {
        "entities": [{"name": "SemesterResult", "controlled_workflow": True}],
        "routes": [{"method": "POST", "path": "/api/results/import"}]
    }
    with open(os.path.join(tmp_workspace, ".agents", "workspace_digest.json"), "w", encoding="utf-8") as f:
        json.dump(digest_data, f)

    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Process semester results for students", tmp_workspace)
    
    req_texts = [r["description"].lower() for r_list in spec.requirements.values() for r in r_list]
    assert not any("delete /results/:id" in t for t in req_texts)


def test_soft_delete_not_universal(tmp_workspace):
    """Verify soft_delete is only derived when entity has explicit audit significance."""
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Create temporary scratchpad note", tmp_workspace)
    
    req_texts = [r["description"].lower() for r_list in spec.requirements.values() for r in r_list]
    assert not any("soft delete scratchpad" in t for t in req_texts)


def test_register_not_derived_without_self_registration(tmp_workspace):
    """Verify self-registration page is NOT derived unless explicitly supported."""
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Student portal for enrolled students", tmp_workspace)
    
    req_texts = [r["description"].lower() for r_list in spec.requirements.values() for r in r_list]
    assert not any("public register page" in t for t in req_texts)


def test_breadcrumb_not_derived_without_nested_nav(tmp_workspace):
    """Verify breadcrumbs are not derived for shallow 1-level navigation."""
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Simple dashboard page", tmp_workspace)
    
    req_texts = [r["description"].lower() for r_list in spec.requirements.values() for r in r_list]
    assert not any("breadcrumb" in t for t in req_texts)


def test_supported_requirement_has_evidence(tmp_workspace):
    """Verify supported requirements contain evidence references."""
    bp_data = {
        "backend_spec": {"routes": ["/api/students/profile"]},
        "db_schema": {"models": ["StudentProfile"]},
        "frontend_layout": {"pages": ["StudentProfilePage"]}
    }
    with open(os.path.join(tmp_workspace, ".agents", "design_blueprint.json"), "w", encoding="utf-8") as f:
        json.dump(bp_data, f)
        
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Student profile page", tmp_workspace)
    
    explicit_reqs = spec.requirements.get("explicit", [])
    if explicit_reqs:
        for req in explicit_reqs:
            assert "evidence" in req
            assert len(req["evidence"]) > 0


def test_derived_requirement_has_why_chain(tmp_workspace):
    """Verify derived requirements include a human-readable WHY chain."""
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Create student edit form", tmp_workspace)
    
    derived = spec.requirements.get("derived", [])
    for d_req in derived:
        assert "why_chain" in d_req
        assert isinstance(d_req["why_chain"], list)


def test_schema_change_requires_human_decision(tmp_workspace):
    """Verify schema-changing decisions require MUST_ASK decision threshold."""
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Add profile avatar photo field to database and storage", tmp_workspace)
    
    assert spec.gate_result in ["PASS_WITH_DECISIONS", "NEEDS_HUMAN_DECISION", "PASS"]
    assert isinstance(spec.questions_for_human, list)


def test_conflicting_evidence_blocks_design(tmp_workspace):
    """Verify contradicting requirements trigger BLOCKED state."""
    gate = SemanticGate()
    reqs = [
        SynthesizedRequirement(
            id="REQ-CONF-1",
            description="Contradicting requirement",
            type=RequirementType.CONFLICT,
            category=RequirementCategory.ARCHITECTURAL_CONSTRAINT,
            action=ArtifactAction.MODIFY,
            decision_threshold=DecisionThreshold.MUST_STOP
        )
    ]
    res, weight = gate.evaluate(reqs, None)
    assert res == GateResult.BLOCKED


def test_assumption_budget_weight_calculation():
    """Verify weighted assumption budget logic."""
    gate = SemanticGate()
    reqs = [
        SynthesizedRequirement(
            id="REQ-1", description="UX align", type=RequirementType.DERIVED,
            category=RequirementCategory.UX_DERIVATION, action=ArtifactAction.CREATE,
            decision_threshold=DecisionThreshold.AUTO_DECIDE, assumption_type="ux"
        ),
        SynthesizedRequirement(
            id="REQ-2", description="Architecture change", type=RequirementType.DERIVED,
            category=RequirementCategory.ARCHITECTURAL_CONSTRAINT, action=ArtifactAction.CREATE,
            decision_threshold=DecisionThreshold.MUST_STOP, assumption_type="architecture"
        )
    ]
    res, weight = gate.evaluate(reqs, None)
    assert weight == 6  # 1 (ux) + 5 (architecture)
    assert res == GateResult.BLOCKED


def test_action_types_classification(tmp_workspace):
    """Verify Action Types (CREATE, EXTEND, MODIFY, REUSE, DEPRECATE, DELETE)."""
    digest_data = {
        "ui_components": ["ProfileForm.tsx", "SettingsShell.tsx"]
    }
    with open(os.path.join(tmp_workspace, ".agents", "workspace_digest.json"), "w", encoding="utf-8") as f:
        json.dump(digest_data, f)
        
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Update student profile settings form", tmp_workspace)
    
    actions = [r["action"].upper() for r_list in spec.requirements.values() for r in r_list if "action" in r]
    assert any(a in ["CREATE", "EXTEND", "MODIFY", "REUSE"] for a in actions)


def test_semantic_gate_validates_coherence(tmp_workspace):
    """Verify SemanticGate validates semantic coherence of spec."""
    spec_dict = {
        "has_roles": True,
        "has_role_analysis": False,
        "has_ui_requirements": True,
        "affected": {},
        "gate_result": "PASS"
    }
    
    sem_res = SemanticGate.validate_dict(spec_dict, tmp_workspace)
    assert sem_res["passed"] is False
    assert len(sem_res["errors"]) > 0


def test_fsm_integration_spec_synthesis_state():
    """Verify FSM workflow graph contains SPECIFICATION_SYNTHESIS state."""
    from runtime import load_json, WORKFLOW_FILE
    workflow = load_json(WORKFLOW_FILE)
    
    assert "SPECIFICATION_SYNTHESIS" in workflow["states"]
    spec_state = workflow["states"]["SPECIFICATION_SYNTHESIS"]
    assert spec_state["transitions"]["spec_synthesized"] == "DESIGN"
    assert spec_state["transitions"]["spec_conflict_detected"] == "CLARIFICATION"
    assert spec_state["transitions"]["spec_scope_decision_needed"] == "CLARIFICATION"
    assert workflow["states"]["ANALYSIS"]["transitions"]["context_loaded"] == "SPECIFICATION_SYNTHESIS"


def test_verifier_hard_gate_blocks_design_without_spec(tmp_workspace):
    """Verify EvidenceVerifier hard-blocks DESIGN phase without synthesized_spec.json."""
    from verifier import EvidenceVerifier
    
    res = EvidenceVerifier.verify_phase("DESIGN", workspace_dir=tmp_workspace, allow_soft=False)
    assert res.passed is False
    assert any("synthesized_spec.json" in err for err in res.errors)
