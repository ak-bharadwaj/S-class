"""
S-Class EOS V8.1.2 - Authoritative Artifact Governance & Control Plane Test Suite

Validates:
1. Triad Status Model (EpistemicStatus, ValidationStatus, ApprovalStatus).
2. Hard Execution Gate: Invalid HLD blocks downstream LLD and Task compilation (returns zero LLD/Tasks).
3. Hard Execution Gate: PROPOSED/PENDING or REJECTED ADR blocks downstream LLD compilation (emits FSM transition target DEBATE).
4. Authoritative Control Plane: FSM transition to CODING is HARD DENIED when artifact governance is blocked.
5. HMAC Signature Verification: Secret key mismatches or tampered signatures are REJECTED.
6. Content Hash Drift Binding: Mutated ADR decision/reason content invalidates previous approval records.
7. Risk-Scoped Policy Constraints: HIGH_RISK decisions (topology, auth) FORBID DETERMINISTIC_POLICY auto-approval.
8. Mode Isolation: TEST_SYNTHETIC approval records are HARD REJECTED in PRODUCTION mode.
"""

import os
import sys
import json
import hashlib
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
        id="ADR-999",
        title="Logging Level Choice",
        decision="JSON Structured Logs",
        alternatives=[],
        evidence=["Confirmed"],
        affected_modules=["mod_1"],
        rejected_options=[],
        reason="Low risk logging standard choice",
        status="ACCEPTED",
        epistemic_status=EpistemicStatus.CONFIRMED,
        validation_status=ValidationStatus.VALID,
        approval_status=ApprovalStatus.APPROVED,
        confidence=1.0
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


def test_hmac_signature_verification_and_key_mismatch_rejection(tmp_path):
    """Adversarial Test: Tampered HMAC signature or wrong governance key MUST BE REJECTED."""
    tmp_workspace = str(tmp_path)
    sec_key = ArtifactGovernor._get_governance_secret(tmp_workspace)

    curr_hash = hashlib.sha256("ADR-001:Monolith:Plausible".encode("utf-8")).hexdigest()
    rec = ApprovalRecord("ADR-001", "HLD-001", 1, curr_hash, "ACCEPTED", ApprovalAuthority.HUMAN_EXPLICIT, "Plausible", "2026-08-14T22:00:00Z")
    rec.signature = rec.compute_signature(sec_key)

    assert rec.is_valid(sec_key) is True
    assert rec.is_valid("wrong_secret_key_0000000000000000000") is False


def test_content_hash_drift_rejection(tmp_path):
    """Adversarial Test: Mutating ADR decision content invalidates previous approval record."""
    tmp_workspace = str(tmp_path)
    sec_key = ArtifactGovernor._get_governance_secret(tmp_workspace)
    mod = HLDModule(id="mod_1", name="Core", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])

    # Original decision content
    orig_hash = hashlib.sha256("ADR-001:Modular Monolith:Original decision".encode("utf-8")).hexdigest()
    rec = ApprovalRecord("ADR-001", "HLD-001", 1, orig_hash, "ACCEPTED", ApprovalAuthority.HUMAN_EXPLICIT, "Original decision", "2026-08-14T22:00:00Z")
    rec.signature = rec.compute_signature(sec_key)

    app_file = os.path.join(tmp_workspace, ".agents", "approvals.json")
    runtime.write_json_atomic(app_file, {"approval_records": [rec.to_dict()]})

    # ADR content is mutated to Microservices!
    mutated_adr = ADRRecord(
        id="ADR-001",
        title="Topology Selection",
        decision="Distributed Microservices", # Mutated!
        alternatives=[],
        evidence=[],
        affected_modules=["mod_1"],
        rejected_options=[],
        reason="Original decision",
        status="PROPOSED",
        confidence=0.50,
        epistemic_status=EpistemicStatus.PROPOSED
    )
    hld = HLDDesign(system_name="HLD-001", architecture_style="Microservices", modules=[mod], adrs=[mutated_adr])

    # Governor MUST REJECT stale approval due to content_hash mismatch!
    gov = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov.is_blocked is True
    assert "content hash mismatch" in gov.blocking_reasons[0]


def test_high_risk_policy_auto_approval_rejection(tmp_path):
    """Governance Test: HIGH_RISK decisions (topology, auth) FORBID DETERMINISTIC_POLICY auto-approval."""
    tmp_workspace = str(tmp_path)
    mod = HLDModule(id="mod_1", name="Core", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    high_risk_adr = ADRRecord(
        id="ADR-001",
        title="Architectural Topology Selection",
        decision="Modular Monolith",
        alternatives=[],
        evidence=[],
        affected_modules=["mod_1"],
        rejected_options=[],
        reason="Default topology choice",
        status="ACCEPTED",
        confidence=0.95,
        epistemic_status=EpistemicStatus.DERIVED
    )
    hld = HLDDesign(system_name="Sys", architecture_style="Monolith", modules=[mod], adrs=[high_risk_adr])

    # High-risk ADR without explicit HUMAN_EXPLICIT or DEBATE_ENGINE receipt MUST BE BLOCKED!
    gov = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov.is_blocked is True
    assert "HIGH_RISK" in gov.blocking_reasons[0]


def test_production_mode_rejects_test_synthetic_approvals(tmp_path):
    """Security Test: TEST_SYNTHETIC approval receipts are HARD REJECTED in production mode."""
    tmp_workspace = str(tmp_path)
    sec_key = ArtifactGovernor._get_governance_secret(tmp_workspace)
    mod = HLDModule(id="mod_1", name="Core", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])

    adr = ADRRecord(
        id="ADR-001",
        title="Topology Selection",
        decision="Modular Monolith",
        alternatives=[],
        evidence=[],
        affected_modules=["mod_1"],
        rejected_options=[],
        reason="Test choice",
        status="PROPOSED",
        confidence=0.50,
        epistemic_status=EpistemicStatus.PROPOSED
    )
    hld = HLDDesign(system_name="HLD-001", architecture_style="Monolith", modules=[mod], adrs=[adr])

    curr_hash = hashlib.sha256("ADR-001:Modular Monolith:Test choice".encode("utf-8")).hexdigest()
    synth_rec = ApprovalRecord("ADR-001", "HLD-001", 1, curr_hash, "ACCEPTED", ApprovalAuthority.TEST_SYNTHETIC, "Test choice", "2026-08-14T22:00:00Z")
    synth_rec.signature = synth_rec.compute_signature(sec_key)

    app_file = os.path.join(tmp_workspace, ".agents", "approvals.json")
    runtime.write_json_atomic(app_file, {"approval_records": [synth_rec.to_dict()]})

    # Enable production mode in sclass.config.json
    cfg_file = os.path.join(tmp_workspace, "sclass.config.json")
    runtime.write_json_atomic(cfg_file, {"productionMode": True, "executionMode": "production"})

    # Governor MUST REJECT TEST_SYNTHETIC receipt in production mode!
    gov = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov.is_blocked is True
    assert "TEST_SYNTHETIC approval record is FORBIDDEN in production mode" in gov.blocking_reasons[0]
