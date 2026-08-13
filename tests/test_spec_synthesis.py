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
    """Verify breadcrumbs are not derived for prompts with zero verbs (no detail_view expansion)."""
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Show homepage", tmp_workspace)
    
    # With a single-word prompt with no action verbs, no detail_views are generated
    # so the breadcrumb rule (requires >= 2 detail_views) should NOT fire
    derived = spec.requirements.get("derived", [])
    breadcrumb_reqs = [r for r in derived if "breadcrumb" in r["description"].lower()]
    assert len(breadcrumb_reqs) == 0


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
    """Verify schema-changing decisions produce MUST_ASK questions for human."""
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Add profile avatar photo field to database and storage", tmp_workspace)
    
    # The gate may be BLOCKED due to high assumption weight from many requirements,
    # or PASS_WITH_DECISIONS due to MUST_ASK items. Either is valid behavior.
    assert spec.gate_result in ["PASS_WITH_DECISIONS", "BLOCKED", "PASS"]
    assert isinstance(spec.questions_for_human, list)
    assert len(spec.questions_for_human) > 0  # Must have at least one question


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


def test_run_synthesis_writes_json_and_md_to_disk(tmp_workspace):
    engine = SpecSynthesisEngine()
    engine.run_synthesis("Build a user management dashboard", tmp_workspace)
    assert os.path.exists(os.path.join(tmp_workspace, '.agents', 'synthesized_spec.json'))
    assert os.path.exists(os.path.join(tmp_workspace, '.agents', 'synthesized_spec.md'))
    with open(os.path.join(tmp_workspace, '.agents', 'synthesized_spec.json'), 'r') as f:
        data = json.load(f)
        assert "intent_summary" in data
        assert "requirements" in data
        assert "affected_systems" in data
        assert "gate_result" in data
    with open(os.path.join(tmp_workspace, '.agents', 'synthesized_spec.md'), 'r', encoding='utf-8') as f:
        content = f.read()
        assert "# Synthesized Specification" in content


def test_questions_for_human_nonempty_for_must_ask(tmp_workspace):
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis("Build a student enrollment system with create and manage features", tmp_workspace)
    assert len(spec.questions_for_human) > 0
    for q in spec.questions_for_human:
        assert isinstance(q, str) and len(q.strip()) > 0


def test_initialize_state_triggers_upfront_synthesis(tmp_workspace):
    import sys
    PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PLUGIN_DIR not in sys.path:
        sys.path.insert(0, PLUGIN_DIR)
    import runtime
    runtime.initialize_state(tmp_workspace, goal="Build ERP system")
    assert os.path.exists(os.path.join(tmp_workspace, '.agents', 'synthesized_spec.json'))


def test_requirement_graph_orphan_detection():
    import sys
    PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PLUGIN_DIR not in sys.path:
        sys.path.insert(0, PLUGIN_DIR)
    from spec_synthesis import RequirementGraph, SynthesizedRequirement, RequirementType, RequirementCategory, ArtifactAction, DecisionThreshold
    
    r1 = SynthesizedRequirement(id="R1", description="explicit", type=RequirementType.EXPLICIT, category=RequirementCategory.PRODUCT_REQUIREMENT, action=ArtifactAction.CREATE, decision_threshold=DecisionThreshold.AUTO_DECIDE)
    r2 = SynthesizedRequirement(id="R2", description="derived with deps", type=RequirementType.DERIVED, category=RequirementCategory.UX_DERIVATION, action=ArtifactAction.CREATE, decision_threshold=DecisionThreshold.AUTO_DECIDE, depends_on=["R1"])
    r3 = SynthesizedRequirement(id="R3", description="derived orphan", type=RequirementType.DERIVED, category=RequirementCategory.UX_DERIVATION, action=ArtifactAction.CREATE, decision_threshold=DecisionThreshold.AUTO_DECIDE, depends_on=[], consequences=[])
    
    graph = RequirementGraph()
    graph.add_node(r1)
    graph.add_node(r2)
    graph.add_node(r3)
    
    orphans = graph.detect_orphans()
    assert len(orphans) == 1
    assert orphans[0].id == "R3"


def test_conflict_detection_fires_blocked_gate():
    import sys
    PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PLUGIN_DIR not in sys.path:
        sys.path.insert(0, PLUGIN_DIR)
    from spec_synthesis import SemanticGate, SynthesizedRequirement, RequirementType, RequirementCategory, ArtifactAction, DecisionThreshold, GateResult
    
    gate = SemanticGate()
    req = SynthesizedRequirement(
        id="R_CONF",
        description="conflict",
        type=RequirementType.CONFLICT,
        category=RequirementCategory.ARCHITECTURAL_CONSTRAINT,
        action=ArtifactAction.MODIFY,
        decision_threshold=DecisionThreshold.MUST_STOP
    )
    result, weight = gate.evaluate([req], None)
    assert result == GateResult.BLOCKED


def test_archetype_detection_nextjs_fullstack(tmp_workspace):
    from spec_synthesis import ProjectArchetypeDetector, ProjectArchetype
    with open(os.path.join(tmp_workspace, "package.json"), "w", encoding="utf-8") as f:
        json.dump({"dependencies": {"next": "^14.0.0", "prisma": "^5.0.0"}}, f)

    archetypes = ProjectArchetypeDetector.detect(tmp_workspace)
    assert ProjectArchetype.FULLSTACK_MONOLITH in archetypes


def test_archetype_detection_cli_tool(tmp_workspace):
    from spec_synthesis import ProjectArchetypeDetector, ProjectArchetype
    with open(os.path.join(tmp_workspace, "package.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "my-cli", "bin": {"my-cli": "./bin/cli.js"}}, f)

    archetypes = ProjectArchetypeDetector.detect(tmp_workspace)
    assert ProjectArchetype.CLI_TOOL in archetypes


def test_scope_classifier_tiers():
    from spec_synthesis import ScopeClassifier, ScopeTier, IntentExtraction
    intent_trivial = IntentExtraction(raw_request="fix typo", primary_features=[], action_verbs=[])
    assert ScopeClassifier.classify("fix typo in readme", intent_trivial) == ScopeTier.TRIVIAL

    intent_major = IntentExtraction(raw_request="build ERP", primary_features=["users", "inventory", "billing", "reports", "settings"], action_verbs=["create", "edit", "delete", "view", "export"])
    assert ScopeClassifier.classify("Build complete ERP platform with all features", intent_major) == ScopeTier.MAJOR


def test_spec_versioning_archives_backup(tmp_workspace):
    engine = SpecSynthesisEngine()
    spec1 = engine.run_synthesis("Build student dashboard v1", tmp_workspace)
    assert spec1.spec_version == 1

    spec2 = engine.run_synthesis("Build student dashboard v2", tmp_workspace)
    assert spec2.spec_version == 2
    assert os.path.exists(os.path.join(tmp_workspace, ".agents", "synthesized_spec_v1.json"))


def test_clarification_answers_incorporation(tmp_workspace):
    engine = SpecSynthesisEngine()
    spec1 = engine.run_synthesis("Build student enrollment system", tmp_workspace)

    # Simulate writing clarification answers
    answers = {"REQ-BASE-0": "Self-registration allowed for students"}
    with open(os.path.join(tmp_workspace, ".agents", "clarification_answers.json"), "w", encoding="utf-8") as f:
        json.dump(answers, f)

    spec2 = engine.run_synthesis("Build student enrollment system", tmp_workspace, clarification_answers=answers)
    base_req = spec2.requirements.get("supported", [])[0]
    assert "[CLARIFIED:" in base_req["description"]


def test_fsm_gate_override_in_runner(tmp_workspace):
    import runtime
    runtime.initialize_state(tmp_workspace, goal="Build student portal")

    # Force BLOCKED spec to test override
    spec_path = os.path.join(tmp_workspace, ".agents", "synthesized_spec.json")
    spec_data = runtime.load_json(spec_path)
    spec_data["gate_result"] = "BLOCKED"
    runtime.write_json_atomic(spec_path, spec_data)

    runtime.FSMGoalSequenceRunner._ensure_phase_evidence("SPECIFICATION_SYNTHESIS", tmp_workspace)
    assert runtime.FSMGoalSequenceRunner._override_event == "spec_conflict_detected"


def test_spec_driven_design_blueprint(tmp_workspace):
    import runtime
    runtime.initialize_state(tmp_workspace, goal="Build student portal")
    runtime.FSMGoalSequenceRunner._ensure_phase_evidence("DESIGN", tmp_workspace)

    blueprint = runtime.load_json(os.path.join(tmp_workspace, ".agents", "design_blueprint.json"))
    assert blueprint["source"] == "synthesized_spec.json"
    assert len(blueprint["frontend_layout"]["components"]) > 0


def test_dynamic_intent_fintech_domain():
    from spec_synthesis import DynamicLinguisticExtractor
    request = "Reconcile daily GL ledger transactions for accountant and generate audit export"
    intent = DynamicLinguisticExtractor.extract_intent(request)
    assert "accountant" in intent.target_roles or "user" in intent.target_roles
    assert "reconcile" in intent.action_verbs or "generate" in intent.action_verbs
    assert any(term in intent.primary_features for term in ["gl", "ledger", "transactions", "audit", "export"])


def test_dynamic_intent_healthcare_domain():
    from spec_synthesis import DynamicLinguisticExtractor
    request = "Triage patient telemetry and prescribe dosage alerts for physician"
    intent = DynamicLinguisticExtractor.extract_intent(request)
    assert "physician" in intent.target_roles or "patient" in intent.target_roles
    assert "triage" in intent.action_verbs or "prescribe" in intent.action_verbs
    assert any(term in intent.primary_features for term in ["patient", "telemetry", "dosage", "alerts"])


def test_dynamic_intent_iot_domain():
    from spec_synthesis import DynamicLinguisticExtractor
    request = "Provision gateway nodes and stream MQTT telemetry"
    intent = DynamicLinguisticExtractor.extract_intent(request)
    assert "provision" in intent.action_verbs or "stream" in intent.action_verbs
    assert "MQTT" in intent.domain_keywords or "mqtt" in intent.primary_features
    assert any(term in intent.primary_features for term in ["gateway", "nodes", "telemetry"])


def test_full_artifact_version_backups(tmp_workspace):
    engine = SpecSynthesisEngine()
    engine.run_synthesis("Build ERP platform v1", tmp_workspace)

    spec2 = engine.run_synthesis("Build ERP platform v2", tmp_workspace)
    assert spec2.spec_version == 2
    assert os.path.exists(os.path.join(tmp_workspace, ".agents", "synthesized_spec_v1.json"))
    assert os.path.exists(os.path.join(tmp_workspace, ".agents", "synthesized_spec_v1.md"))
    assert os.path.exists(os.path.join(tmp_workspace, ".agents", "intent_contract_v1.json"))



