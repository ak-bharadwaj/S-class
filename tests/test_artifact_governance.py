"""
S-Class EOS V8.1.1 - Authoritative Artifact Governance & Control Plane Test Suite

Validates:
1. Triad Status Model (EpistemicStatus, ValidationStatus, ApprovalStatus).
2. Hard Execution Gate: Invalid HLD blocks downstream LLD and Task compilation (returns zero LLD/Tasks).
3. Hard Execution Gate: PROPOSED/PENDING or REJECTED ADR blocks downstream LLD compilation (emits FSM transition target DEBATE).
4. Authoritative Control Plane: FSM transition to CODING is HARD DENIED when artifact governance is blocked.
5. Adversarial Governance: Fake 'all_approved: true' boolean overrides are REJECTED.
6. Adversarial Governance: Tampered SHA-256 signatures on ApprovalRecord objects are REJECTED.
7. Structured Verification: Valid ApprovalRecord objects signed by DEBATE_ENGINE / HUMAN_EXPLICIT unblock compilation.
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
from artifact_governor import ArtifactGovernor, FSMTransitionTarget, GovernanceGateResult, ApprovalRecord, ApprovalAuthority
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


def test_adversarial_fake_all_approved_bypass_rejected(tmp_path):
    """Adversarial Test: Fake 'all_approved: true' flag in approvals.json MUST BE REJECTED by ArtifactGovernor."""
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
        status="PROPOSED",
        confidence=0.50,
        epistemic_status=EpistemicStatus.PROPOSED
    )
    hld = HLDDesign(system_name="Sys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    # Write adversarial fake approvals file
    app_file = os.path.join(tmp_workspace, ".agents", "approvals.json")
    runtime.write_json_atomic(app_file, {"all_approved": True, "fake_credentials": "admin"})

    # Governor MUST REJECT fake all_approved flag and remain BLOCKED!
    gov = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov.is_blocked is True
    assert gov.approval_status == ApprovalStatus.PENDING
    assert "ADR-001" in gov.blocking_reasons[0]


def test_adversarial_invalid_signature_rejected(tmp_path):
    """Adversarial Test: ApprovalRecord with forged/tampered SHA-256 signature MUST BE REJECTED."""
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
        status="PROPOSED",
        confidence=0.50,
        epistemic_status=EpistemicStatus.PROPOSED
    )
    hld = HLDDesign(system_name="Sys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    # Write record with forged signature
    forged_rec = {
        "decision_id": "ADR-001",
        "artifact_id": "HLD-001",
        "decision": "ACCEPTED",
        "authority": "HUMAN_EXPLICIT",
        "reason": "Forged approval",
        "timestamp": "2026-08-14T22:00:00Z",
        "signature": "bad_signature_00000000000000000000000000000000"
    }
    app_file = os.path.join(tmp_workspace, ".agents", "approvals.json")
    runtime.write_json_atomic(app_file, {"approval_records": [forged_rec]})

    # Governor MUST REJECT forged record signature and remain BLOCKED!
    gov = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov.is_blocked is True
    assert gov.approval_status == ApprovalStatus.PENDING


def test_valid_debate_engine_approval_record_unblocks(tmp_path):
    """Positive Verification: Valid ApprovalRecord signed by DEBATE_ENGINE successfully UNBLOCKS compilation."""
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
        status="PROPOSED",
        confidence=0.50,
        epistemic_status=EpistemicStatus.PROPOSED
    )
    hld = HLDDesign(system_name="Sys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    # Create valid signed ApprovalRecord
    rec = ApprovalRecord(
        decision_id="ADR-001",
        artifact_id="HLD-001",
        decision="ACCEPTED",
        authority=ApprovalAuthority.DEBATE_ENGINE,
        reason="Debate engine resolved claim with evidence",
        timestamp="2026-08-14T22:00:00Z"
    )
    app_file = os.path.join(tmp_workspace, ".agents", "approvals.json")
    runtime.write_json_atomic(app_file, {"approval_records": [rec.to_dict()]})

    # Governor MUST VALIDATE signature and UNBLOCK compilation!
    gov = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov.is_blocked is False
    assert adr.approval_status == ApprovalStatus.APPROVED
    assert adr.status == "ACCEPTED"
