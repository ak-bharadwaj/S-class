"""
S-Class EOS V8.1 - Authoritative Artifact Governance & Control Plane Test Suite

Validates:
1. Triad Status Model (EpistemicStatus, ValidationStatus, ApprovalStatus).
2. Hard Execution Gate: Invalid HLD blocks downstream LLD and Task compilation (returns zero LLD/Tasks).
3. Hard Execution Gate: PROPOSED/PENDING or REJECTED ADR blocks downstream LLD compilation (emits FSM transition target DEBATE).
4. Authoritative Control Plane: FSM transition to CODING is HARD DENIED when artifact governance is blocked.
5. Strict Approval Semantics: Confidence < 0.90 without explicit receipt stays PENDING; explicit receipt approves.
"""

import os
import sys
import json
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from domain_primitives import DomainPrimitiveType, DomainNode, SemanticDomainGraph
from behavior_graph import BehaviorGraphEngine, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode
from hld_compiler import HLDCompiler, HLDDesign, HLDModule, ADRRecord, ValidationStatus, ApprovalStatus
from lld_compiler import LLDCompiler, LLDComponent, LLDComponentType, LLDParentRef
from task_compiler import TaskCompiler, TaskCategory
from artifact_governor import ArtifactGovernor, FSMTransitionTarget, GovernanceGateResult
from spec_compiler import SpecificationCompiler
import runtime


def test_artifact_governance_blocks_lld_on_invalid_hld():
    """Verify ArtifactGovernor hard gate blocks LLD compilation if HLD validation fails."""
    hld = HLDDesign(
        system_name="TestSystem",
        architecture_style="Modular Monolith",
        modules=[],
        adrs=[]
    )

    hld_gov = ArtifactGovernor.audit_hld_governance(
        hld=hld,
        hld_validation_passed=False,
        hld_errors=["[HLD-VAL-ADR] High-Level Design lacks mandatory Topology ADR."]
    )

    assert hld_gov.is_blocked is True
    assert hld_gov.validation_status == ValidationStatus.INVALID
    assert hld_gov.approval_status == ApprovalStatus.REJECTED
    assert hld_gov.recommended_fsm_state == FSMTransitionTarget.DESIGN


def test_artifact_governance_blocks_lld_on_proposed_adr():
    """Verify ArtifactGovernor hard gate blocks LLD compilation if an ADR is PROPOSED or PENDING approval."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    prompt = "Doctor approves prescription."
    res = SpecificationCompiler.compile_v7_refinement_pipeline(
        graph=d_graph,
        intent_features=["prescription", "approve"],
        raw_request=prompt
    )

    assert res["blocked"] is True
    assert res["target_fsm_state"] == "DEBATE"
    assert len(res["lld_components"]) == 0
    assert len(res["tasks"]) == 0
    assert res["hld_governance"]["is_blocked"] is True


def test_artifact_governance_allows_compilation_on_confirmed_adr():
    """Verify ArtifactGovernor permits downstream LLD compilation when ADR is CONFIRMED and HLD is VALID."""
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["action_item"])
    adr_1 = ADRRecord(
        id="ADR-001",
        title="Topology Selection",
        decision="Modular Monolith",
        alternatives=[],
        evidence=["Confirmed"],
        affected_modules=["mod_1"],
        rejected_options=[],
        reason="Explicitly confirmed",
        status="ACCEPTED",
        epistemic_status=EpistemicStatus.CONFIRMED,
        validation_status=ValidationStatus.VALID,
        approval_status=ApprovalStatus.APPROVED
    )
    hld = HLDDesign(
        system_name="TestSystem",
        architecture_style="Modular Monolith",
        modules=[mod],
        adrs=[adr_1]
    )

    hld_gov = ArtifactGovernor.audit_hld_governance(hld, hld_validation_passed=True, hld_errors=[])
    assert hld_gov.is_blocked is False
    assert hld_gov.validation_status == ValidationStatus.VALID
    assert hld_gov.approval_status == ApprovalStatus.APPROVED
    assert hld_gov.recommended_fsm_state == FSMTransitionTarget.CODING


def test_fsm_transition_denied_when_artifact_governance_blocked(tmp_path):
    """Verify runtime dispatch_event HARD DENIES FSM transition when artifact governance is blocked."""
    tmp_workspace = str(tmp_path)
    runtime.initialize_state(tmp_workspace, goal="Test Governance Goal")

    agents_dir = os.path.join(tmp_workspace, ".agents")
    pipe_file = os.path.join(agents_dir, "v7_refinement_pipeline.json")
    runtime.write_json_atomic(pipe_file, {
        "blocked": True,
        "hld_governance": {
            "is_blocked": True,
            "blocking_reasons": ["ADR-001 is PROPOSED pending debate"],
            "recommended_fsm_state": "DEBATE",
            "validation_status": "BLOCKED",
            "approval_status": "PENDING"
        }
    })

    state = runtime.get_state(tmp_workspace)
    state.currentPhase = "SPECIFICATION_SYNTHESIS"
    runtime.save_state(state, tmp_workspace)

    # Attempting transition to DESIGN from SPECIFICATION_SYNTHESIS must be DENIED!
    with pytest.raises(ValueError) as excinfo:
        runtime.dispatch_event("spec_synthesized", workspace_dir=tmp_workspace, enforce_evidence=False)

    assert "ArtifactGovernor DENIED transition" in str(excinfo.value)
    assert "Recommended FSM target: 'DEBATE'" in str(excinfo.value)

    state = runtime.get_state(tmp_workspace)
    assert state.activeEvent == "BLOCKED:spec_synthesized"
    assert any("DENIED by ArtifactGovernor" in d.decision for d in state.decisionLog)


def test_strict_approval_status_requires_explicit_receipt(tmp_path):
    """Verify confidence < 0.90 stays PENDING without explicit receipt, and approves when receipt exists."""
    tmp_workspace = str(tmp_path)
    mod = HLDModule(id="mod_1", name="Core", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr = ADRRecord(
        id="ADR-001",
        title="Topology",
        decision="Monolith",
        alternatives=[],
        evidence=[],
        affected_modules=["mod_1"],
        rejected_options=[],
        reason="Plausible",
        status="ACCEPTED",
        confidence=0.85,
        epistemic_status=EpistemicStatus.DERIVED
    )
    hld = HLDDesign(system_name="Sys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    # 1. Without approvals file: confidence 0.85 stays PENDING!
    gov1 = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov1.is_blocked is True
    assert gov1.approval_status == ApprovalStatus.PENDING

    # 2. With explicit approval receipt in approvals.json: becomes APPROVED!
    app_file = os.path.join(tmp_workspace, ".agents", "approvals.json")
    runtime.write_json_atomic(app_file, {"approved_adrs": ["ADR-001"]})

    gov2 = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov2.is_blocked is False
    assert adr.approval_status == ApprovalStatus.APPROVED
