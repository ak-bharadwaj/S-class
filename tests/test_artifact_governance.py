"""
S-Class EOS V8.1.3 - Authoritative Artifact Governance & Control Plane Test Suite

Validates:
1. Triad Status Model (EpistemicStatus, ValidationStatus, ApprovalStatus).
2. Hard Execution Gate: Invalid HLD blocks downstream LLD and Task compilation (returns zero LLD/Tasks).
3. Hard Execution Gate: PROPOSED/PENDING or REJECTED ADR blocks downstream LLD compilation (emits FSM transition target DEBATE).
4. Authoritative Control Plane: FSM transition to CODING is HARD DENIED when artifact governance is blocked.
5. External Protected Key Custody: Secret key loaded outside workspace (~/.sclass/governance.key or ENV).
6. Canonical Full-ADR Content Hashing: Mutating any ADR field (alternatives, evidence, confidence) invalidates approval.
7. Exact Version & ID Anti-Replay: Version mismatch causes immediate approval rejection.
8. Fail-Closed Production Default: Execution mode defaults to PRODUCTION, hard-rejecting TEST_SYNTHETIC receipts.
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


def test_external_key_custody_outside_workspace(tmp_path):
    """Security Test: Governance secret key is stored OUTSIDE workspace (~/.sclass/governance.key)."""
    tmp_workspace = str(tmp_path)
    sec_key = ArtifactGovernor._get_governance_secret(tmp_workspace)

    assert len(sec_key) >= 32
    workspace_key_file = os.path.join(tmp_workspace, ".agents", "governance.key")
    assert not os.path.exists(workspace_key_file)


def test_canonical_full_adr_content_hash_invalidation(tmp_path):
    """Security Test: Mutating alternatives/evidence in ADR invalidates content hash and blocks approval."""
    tmp_workspace = str(tmp_path)
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
    sec_key = ArtifactGovernor._get_governance_secret(tmp_workspace)
    mod = HLDModule(id="mod_1", name="Core", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])

    adr = ADRRecord(
        id="ADR-001",
        title="Topology Selection",
        decision="Modular Monolith",
        alternatives=["Microservices"],
        evidence=["Benchmark 1"],
        affected_modules=["mod_1"],
        rejected_options=["Microservices"],
        reason="Plausible",
        status="PROPOSED",
        confidence=0.50,
        epistemic_status=EpistemicStatus.PROPOSED
    )
    orig_hash = ArtifactGovernor.compute_canonical_adr_hash(adr)

    rec = ApprovalRecord("ADR-001", "HLD-001", 1, orig_hash, "ACCEPTED", ApprovalAuthority.TEST_SYNTHETIC, "Approved", "2026-08-14T22:00:00Z")
    rec.signature = rec.compute_signature(sec_key)

    app_file = os.path.join(tmp_workspace, ".agents", "approvals.json")
    runtime.write_json_atomic(app_file, {"approval_records": [rec.to_dict()]})

    # Mutate alternatives in ADR!
    adr.alternatives.append("Serverless")
    hld = HLDDesign(system_name="HLD-001", architecture_style="Monolith", modules=[mod], adrs=[adr])

    # Governor MUST REJECT due to canonical content hash mismatch!
    gov = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov.is_blocked is True
    assert "canonical content hash mismatch" in gov.blocking_reasons[0]


def test_artifact_version_mismatch_anti_replay(tmp_path):
    """Security Test: Approval record artifact_version mismatch causes immediate rejection."""
    tmp_workspace = str(tmp_path)
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
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
        reason="Plausible",
        status="PROPOSED",
        confidence=0.50,
        epistemic_status=EpistemicStatus.PROPOSED
    )
    curr_hash = ArtifactGovernor.compute_canonical_adr_hash(adr)

    # Approval record for version 1
    rec = ApprovalRecord("ADR-001", "HLD-001", 1, curr_hash, "ACCEPTED", ApprovalAuthority.TEST_SYNTHETIC, "Approved", "2026-08-14T22:00:00Z")
    rec.signature = rec.compute_signature(sec_key)

    app_file = os.path.join(tmp_workspace, ".agents", "approvals.json")
    runtime.write_json_atomic(app_file, {"approval_records": [rec.to_dict()]})

    # HLD is now version 2!
    hld = HLDDesign(system_name="HLD-001", architecture_style="Monolith", modules=[mod], adrs=[adr], version=2)

    # Governor MUST REJECT due to artifact version mismatch!
    gov = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov.is_blocked is True
    assert "artifact version mismatch" in gov.blocking_reasons[0]


def test_fail_closed_production_mode_default(tmp_path):
    """Security Test: Unconfigured environment defaults to PRODUCTION mode (fail-closed), rejecting TEST_SYNTHETIC."""
    tmp_workspace = str(tmp_path)
    if "SCLASS_EXECUTION_MODE" in os.environ:
        del os.environ["SCLASS_EXECUTION_MODE"]

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

    curr_hash = ArtifactGovernor.compute_canonical_adr_hash(adr)
    synth_rec = ApprovalRecord("ADR-001", "HLD-001", 1, curr_hash, "ACCEPTED", ApprovalAuthority.TEST_SYNTHETIC, "Test choice", "2026-08-14T22:00:00Z")
    synth_rec.signature = synth_rec.compute_signature(sec_key)

    app_file = os.path.join(tmp_workspace, ".agents", "approvals.json")
    runtime.write_json_atomic(app_file, {"approval_records": [synth_rec.to_dict()]})

    # Unconfigured environment defaults to PRODUCTION mode (fail-closed!)
    assert ArtifactGovernor._get_execution_mode(tmp_workspace) == "PRODUCTION"

    # Governor MUST REJECT TEST_SYNTHETIC receipt in PRODUCTION mode!
    gov = ArtifactGovernor.audit_hld_governance(hld, True, [], workspace_dir=tmp_workspace)
    assert gov.is_blocked is True
    assert "TEST_SYNTHETIC approval record is FORBIDDEN in PRODUCTION mode" in gov.blocking_reasons[0]
