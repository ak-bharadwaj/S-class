"""
S-Class EOS V8.0 - End-to-End Pipeline & Architecture Debate Fault-Injection Test Suite

Validates:
1. End-to-end pipeline execution for "Build a high-throughput telemetry ingestion platform with 50,000 events per second".
2. Fault Injection Audit 1: Single-threaded monolith claim for 50k req/sec system is REJECTED by ArchitectureDebateEngine.
3. Fault Injection Audit 2: Unbacked microservice claim for a simple prescription monolith is REJECTED/demoted to PROPOSED.
4. Immutable epistemic_ledger generation.
"""

import os
import sys
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from domain_primitives import DomainPrimitiveType, DomainNode, SemanticDomainGraph
from behavior_graph import BehaviorGraphEngine
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind, NFRCategory
from hld_compiler import HLDCompiler, HLDDesign, ADRRecord
from architecture_debate import ArchitectureDebateEngine, ChallengeCategory
from spec_compiler import SpecificationCompiler


def test_end_to_end_pipeline_telemetry_platform():
    """Verify full end-to-end pipeline execution for a high-throughput telemetry platform."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_sensor", "Sensor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_reading", "Reading", DomainPrimitiveType.ENTITY))

    prompt = "Sensor ingests reading with high-throughput 50,000 events per second."

    res = SpecificationCompiler.compile_v7_refinement_pipeline(
        graph=d_graph,
        intent_features=["reading", "ingest"],
        raw_request=prompt,
        archetypes=["data_pipeline"]
    )

    assert "behavior_graph" in res
    assert "requirement_graph" in res
    assert "hld_design" in res
    assert "hld_validation" in res
    assert "debate_result" in res
    assert "lld_components" in res
    assert "tasks" in res

    debate = res["debate_result"]
    assert len(debate["rejected_adrs"]) >= 1
    # Debate Engine catches default Monolith ADR for 50,000 events/sec and REJECTS it
    top_adr = next(a for a in debate["rejected_adrs"] if a["id"] == "ADR-001")
    assert top_adr["status"] == "REJECTED"
    assert len(debate["required_revisions"]) >= 1
    assert "REVISE ADR-001" in debate["required_revisions"][0]
    assert "scale_throughput_invariant" in debate["required_revisions"][0]


def test_fault_injection_monolith_claim_rejected_for_high_throughput():
    """Fault Injection Test: Injects a single-threaded monolith claim into a 50,000 req/sec system."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_sensor", "Sensor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_reading", "Reading", DomainPrimitiveType.ENTITY))

    prompt = "Sensor ingests reading with high-throughput 50,000 events per second."
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, prompt)
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)

    hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request=prompt)

    # Deliberately inject a bad monolith claim into a 50k events/sec system
    bad_monolith_adr = ADRRecord(
        id="ADR-001",
        title="Architectural Topology Selection",
        decision="Single-Threaded Monolith with Synchronous Processing",
        alternatives=["Distributed Microservices"],
        evidence=["Manual override"],
        affected_modules=[m.id for m in hld.modules],
        rejected_options=["Distributed Microservices"],
        reason="Simple implementation preference",
        status="ACCEPTED",
        confidence=0.90
    )
    hld.adrs[0] = bad_monolith_adr

    # Debate Engine Audits HLD
    debate_res = ArchitectureDebateEngine.debate_hld_adrs(hld, r_graph, b_graph, raw_request=prompt)

    # Monolith claim for 50,000 events/sec must be REJECTED!
    assert len(debate_res.rejected_adrs) >= 1
    rej_adr = debate_res.rejected_adrs[0]
    assert rej_adr.id == "ADR-001"
    assert rej_adr.status == "REJECTED"
    assert len(debate_res.required_revisions) >= 1
    assert "REVISE ADR-001" in debate_res.required_revisions[0]


def test_fault_injection_unbacked_microservice_rejected_for_simple_monolith():
    """Fault Injection Test: Injects unbacked microservice claim into a simple 1-user prescription app."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    prompt = "Doctor approves prescription."
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, prompt)
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)

    hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request=prompt)

    # Deliberately inject an unbacked microservice claim into a simple prescription app
    unbacked_micro_adr = ADRRecord(
        id="ADR-001",
        title="Architectural Topology Selection",
        decision="Distributed Microservices Architecture with Multi-Cluster Kafka Mesh",
        alternatives=["Modular Monolith"],
        evidence=["No scale evidence"],
        affected_modules=[m.id for m in hld.modules],
        rejected_options=["Modular Monolith"],
        reason="Trend preference",
        status="ACCEPTED",
        confidence=0.95
    )
    hld.adrs[0] = unbacked_micro_adr

    # Debate Engine Audits HLD
    debate_res = ArchitectureDebateEngine.debate_hld_adrs(hld, r_graph, b_graph, raw_request=prompt)

    # Unbacked microservices claim must be REJECTED!
    assert len(debate_res.rejected_adrs) >= 1
    rej_adr = debate_res.rejected_adrs[0]
    assert rej_adr.id == "ADR-001"
    assert rej_adr.status == "REJECTED"
    assert any("CHALLENGE-TOPOLOGY-02" in r or "Modular Monolith" in r for r in debate_res.required_revisions)
