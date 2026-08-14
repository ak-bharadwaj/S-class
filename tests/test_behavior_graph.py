"""
S-Class EOS V6.2 - Behavior Graph & Epistemic Grounding Test Suite

Validates:
1. DomainEdge and BehaviorEdge unified provenance tracking.
2. Atomic Clause SVO Parsing preventing cross-clause subject-verb-object mixing.
3. Open-Vocabulary Action Predicate Extraction for un-whitelisted domain verbs.
4. PERFORMS vs AUTHORIZED_FOR relation separation.
5. Demoted Fallback Query gating (PROPOSED status).
6. PracticalSkeptic SKEPTIC-STRUCTURAL-GROUNDING and SKEPTIC-EPISTEMIC-BEHAVIOR-GROUNDING auditing.
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

    reloaded = DomainEdge.from_dict(edge_dict)
    assert reloaded.provenance == ProvenanceKind.EXPLICIT


def test_atomic_clause_svo_parsing_prevents_cross_clause_mixing():
    """Verify compound sentences split on conjunctions to prevent cross-clause SVO mixing."""
    d_graph = SemanticDomainGraph()
    doctor = d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    nurse = d_graph.add_node(DomainNode("actor_nurse", "Nurse", DomainPrimitiveType.ACTOR))
    prescription = d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))
    appointment = d_graph.add_node(DomainNode("entity_appointment", "Appointment", DomainPrimitiveType.ENTITY))

    prompt = "The doctor reviews the patient's prescription before the nurse approves the appointment."
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, prompt)

    commands = [n for n in b_graph.nodes.values() if n.behavior_type == BehaviorNodeType.COMMAND]
    cmd_names = [c.name for c in commands]

    # Grounded clause 1: Doctor Review Prescription
    assert any("Doctor" in c.name and "Prescription" in c.name for c in commands)
    # Grounded clause 2: Nurse Approve Appointment
    assert any("Nurse" in c.name and "Appointment" in c.name for c in commands)

    # ZERO cross-clause leakage
    assert not any("Doctor" in c.name and "Appointment" in c.name for c in commands)
    assert not any("Nurse" in c.name and "Prescription" in c.name for c in commands)


def test_open_vocabulary_predicate_extraction():
    """Verify open-vocabulary domain verbs (calibrates, reconciles, escalates) are recognized dynamically."""
    d_graph = SemanticDomainGraph()
    tech = d_graph.add_node(DomainNode("actor_technician", "Technician", DomainPrimitiveType.ACTOR))
    spectrometer = d_graph.add_node(DomainNode("entity_spectrometer", "Spectrometer", DomainPrimitiveType.ENTITY))

    prompt = "Technician calibrates the spectrometer."
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, prompt)

    commands = [n for n in b_graph.nodes.values() if n.behavior_type == BehaviorNodeType.COMMAND]
    assert len(commands) == 1
    cmd = commands[0]
    assert "Technician" in cmd.name
    assert "Spectrometer" in cmd.name
    assert "Calibrate" in cmd.name or "Calibrates" in cmd.name


def test_performs_vs_authorized_for_separation():
    """Verify prose assertions generate PERFORMS edges, reserving AUTHORIZED_FOR for explicit security evidence."""
    d_graph = SemanticDomainGraph()
    doctor = d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    prescription = d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    prompt = "Doctor approves prescription."
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, prompt)

    performs_edges = [e for e in b_graph.edges if e.relation == BehaviorRelationType.PERFORMS]
    auth_edges = [e for e in b_graph.edges if e.relation == BehaviorRelationType.AUTHORIZED_FOR]

    assert len(performs_edges) >= 1
    # Prose assertion without RBAC wording does NOT invent AUTHORIZED_FOR
    assert len(auth_edges) == 0


def test_demoted_fallback_query_epistemic_gating():
    """Verify un-grounded fallback queries are marked as PROPOSED and gated from compilation."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    # Empty text prompt -> forces fallback
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "")

    # Fallback query nodes marked as PROPOSED
    proposed_queries = [n for n in b_graph.nodes.values() if n.epistemic_status == EpistemicStatus.PROPOSED]
    assert len(proposed_queries) >= 1
    assert proposed_queries[0].confidence == 0.35

    # Compiler helper excludes PROPOSED query nodes
    accepted = b_graph.get_accepted_queries_for_actor("actor_doctor")
    assert len(accepted) == 0


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
