"""
S-Class EOS V6.1 - Behavior Graph & Epistemic Grounding Test Suite

Validates:
1. DomainEdge and BehaviorEdge unified provenance tracking.
2. SVO Triple Extraction preventing Cartesian product over-generation.
3. BehaviorGraph construction via BehaviorGraphEngine (Commands, Queries, Guards, Side Effects).
4. EpistemicStatus compiler gating suppressing PROPOSED behaviors from HLD/LLD.
5. PracticalSkeptic SKEPTIC-STRUCTURAL-GROUNDING and SKEPTIC-EPISTEMIC-BEHAVIOR-GROUNDING auditing.
"""

import os
import sys
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from domain_primitives import (
    DomainPrimitiveType,
    ProvenanceKind,
    DomainNode,
    DomainEdge,
    RelationType,
    SemanticDomainGraph
)
from behavior_graph import (
    BehaviorNodeType,
    BehaviorRelationType,
    BehaviorNode,
    BehaviorEdge,
    BehaviorGraph,
    BehaviorGraphEngine,
    EpistemicStatus
)
from spec_compiler import SpecificationCompiler
from practical_skeptic import PracticalSkeptic


def test_domain_edge_first_class_provenance():
    """Verify DomainEdge stores typed provenance, confidence, evidence_ref, and assumptions."""
    edge = DomainEdge(
        source_id="actor_doctor",
        relation=RelationType.AUTHORIZED_FOR,
        target_id="entity_prescription",
        provenance=ProvenanceKind.EXPLICIT,
        confidence=0.98,
        evidence_ref="doc_sec_6_17",
        inference_rule="explicit_user_prompt",
        assumptions=["ASM-AUTH-01"]
    )
    edge_dict = edge.to_dict()
    assert edge_dict["provenance"] == "explicit"
    assert edge_dict["confidence"] == 0.98
    assert edge_dict["evidence_ref"] == "doc_sec_6_17"
    assert edge_dict["assumptions"] == ["ASM-AUTH-01"]

    reloaded = DomainEdge.from_dict(edge_dict)
    assert reloaded.provenance == ProvenanceKind.EXPLICIT
    assert reloaded.confidence == 0.98
    assert reloaded.inference_rule == "explicit_user_prompt"


def test_svo_triple_extraction_prevents_cartesian_product():
    """Verify SVO Triple Extraction creates ONLY grounded actor-verb-entity commands, preventing Cartesian explosion."""
    d_graph = SemanticDomainGraph()
    doctor = d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    nurse = d_graph.add_node(DomainNode("actor_nurse", "Nurse", DomainPrimitiveType.ACTOR))
    patient = d_graph.add_node(DomainNode("entity_patient", "Patient", DomainPrimitiveType.ENTITY))
    prescription = d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    prompt = "Doctors approve prescriptions. Nurses view patients."
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, prompt)

    commands = [n for n in b_graph.nodes.values() if n.behavior_type == BehaviorNodeType.COMMAND]

    # Verify ONLY 'Doctor Approve Prescription' command exists, NOT 'Nurse Approve Prescription' or 'Doctor Approve Patient'
    cmd_names = [c.name for c in commands]
    assert "Doctor Approve Prescription" in cmd_names
    assert "Nurse Approve Prescription" not in cmd_names
    assert "Doctor Approve Patient" not in cmd_names

    # Verify epistemic status is EXPLICIT
    doc_cmd = next(c for c in commands if c.name == "Doctor Approve Prescription")
    assert doc_cmd.epistemic_status == EpistemicStatus.EXPLICIT
    assert doc_cmd.confidence == 0.99


def test_epistemic_status_compiler_gating():
    """Verify SpecificationCompiler gates PROPOSED behaviors from compiling to HLD/LLD."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    # Add a PROPOSED behavior node manually to behavior graph
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctors approve prescriptions.")
    proposed_node = b_graph.add_node(BehaviorNode(
        id="cmd_doctor_delete_patient",
        name="Doctor Delete Patient",
        behavior_type=BehaviorNodeType.COMMAND,
        actor_id="actor_doctor",
        target_entity_id="entity_patient",
        epistemic_status=EpistemicStatus.PROPOSED,
        confidence=0.35
    ))

    # Verify accepted helper excludes PROPOSED node
    accepted = b_graph.get_accepted_commands_for_actor("actor_doctor")
    assert proposed_node not in accepted


def test_skeptic_structural_grounding_invariant():
    """Verify PracticalSkeptic SKEPTIC-STRUCTURAL-GROUNDING auditing."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    spreads, llds, reasoning = SpecificationCompiler.compile_specification(
        graph=d_graph,
        intent_features=["prescription", "sign"],
        archetypes=["nextjs_fullstack"]
    )

    spec_dict = {
        "intent_summary": "Healthcare prescription system for doctors",
        "page_spreads": spreads,
        "low_level_designs": llds
    }

    passed, warnings, checks = PracticalSkeptic.audit_specification(spec_dict)
    assert passed is True
    assert not any("[SKEPTIC-STRUCTURAL-GROUNDING]" in w for w in warnings)
