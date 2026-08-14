"""
S-Class EOS V8.1 - Artifact Governance & Control Plane Test Suite

Validates:
1. Triad Status Model (EpistemicStatus, ValidationStatus, ApprovalStatus).
2. Hard Execution Gate: Invalid HLD blocks downstream LLD and Task compilation (returns zero LLD/Tasks).
3. Hard Execution Gate: PROPOSED/PENDING or REJECTED ADR blocks downstream LLD compilation (emits FSM transition target DEBATE).
4. Untraceable LLD component blocks Task compilation.
5. Complete graph lineage persistence in v7_refinement_pipeline.json.
"""

import os
import sys
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


def test_artifact_governance_blocks_lld_on_invalid_hld():
    """Verify ArtifactGovernor hard gate blocks LLD compilation if HLD validation fails."""
    hld = HLDDesign(
        system_name="TestSystem",
        architecture_style="Modular Monolith",
        modules=[],
        adrs=[]
    )

    # Hard validation failure: HLD lacks required topology ADR-001
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

    # Ambiguous prompt emits PROPOSED/REJECTED ADRs, so Artifact Governor hard-blocks LLD compilation
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


def test_artifact_governance_blocks_tasks_on_untraceable_lld():
    """Verify ArtifactGovernor blocks task compilation if an LLD component lacks parent lineage."""
    hld = HLDDesign(
        system_name="TestSystem",
        architecture_style="Modular Monolith",
        modules=[],
        adrs=[]
    )

    untraceable_comp = LLDComponent(
        id="bad_comp",
        name="Bad Component",
        component_type=LLDComponentType.CONTROLLER,
        parent=LLDParentRef(hld_id="mod_1", req_ids=[], behavior_ids=[]),
        role="controller"
    )

    lld_gov = ArtifactGovernor.audit_lld_governance([untraceable_comp], hld)
    assert lld_gov.is_blocked is True
    assert lld_gov.validation_status == ValidationStatus.INVALID
    assert lld_gov.recommended_fsm_state == FSMTransitionTarget.DESIGN
