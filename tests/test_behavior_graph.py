"""
S-Class EOS V6.0 - Behavior Graph & Edge Provenance Test Suite

Validates:
1. DomainEdge and BehaviorEdge first-class provenance tracking.
2. BehaviorGraph construction via BehaviorGraphEngine (Commands, Queries, Guards, Side Effects).
3. PracticalSkeptic SKEPTIC-STRUCTURAL-GROUNDING IR invariant evaluation.
"""

import os
import sys
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from domain_primitives import (
    DomainPrimitiveType,
    ProvenanceType,
    EdgeProvenanceType,
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
    BehaviorGraphEngine
)
from spec_compiler import SpecificationCompiler
from practical_skeptic import PracticalSkeptic


def test_domain_edge_first_class_provenance():
    """Verify DomainEdge stores typed provenance, confidence, evidence_ref, and assumptions."""
    edge = DomainEdge(
        source_id="actor_doctor",
        relation=RelationType.AUTHORIZED_FOR,
        target_id="entity_prescription",
        provenance=EdgeProvenanceType.EXPLICIT,
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
    assert reloaded.provenance == EdgeProvenanceType.EXPLICIT
    assert reloaded.confidence == 0.98
    assert reloaded.inference_rule == "explicit_user_prompt"


def test_behavior_graph_engine_derivation():
    """Verify BehaviorGraphEngine derives Commands, Queries, Guards, and Side Effects from domain graph."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_pilot", "Pilot", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_flight_plan", "Flight Plan", DomainPrimitiveType.ENTITY))
    d_graph.add_node(DomainNode("policy_airworthiness", "Airworthiness Policy", DomainPrimitiveType.POLICY))

    raw_request = "Pilots submit flight plans with airworthiness policy validation."
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, raw_request)

    nodes = b_graph.nodes
    assert len(nodes) > 0

    commands = [n for n in nodes.values() if n.behavior_type == BehaviorNodeType.COMMAND]
    queries = [n for n in nodes.values() if n.behavior_type == BehaviorNodeType.QUERY]
    guards = [n for n in nodes.values() if n.behavior_type == BehaviorNodeType.GUARD_CONDITION]
    side_effects = [n for n in nodes.values() if n.behavior_type == BehaviorNodeType.SIDE_EFFECT]

    assert len(commands) >= 1
    assert len(queries) >= 1
    assert len(guards) >= 1
    assert len(side_effects) >= 1

    # Verify edge authorization
    auth_edges = [e for e in b_graph.edges if e.relation == BehaviorRelationType.AUTHORIZED_FOR]
    assert len(auth_edges) >= 2


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
    # Verify SKEPTIC-STRUCTURAL-GROUNDING executed cleanly
    assert not any("[SKEPTIC-STRUCTURAL-GROUNDING]" in w for w in warnings)
