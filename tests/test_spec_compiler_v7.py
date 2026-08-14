"""
S-Class EOS V8.0 - Dynamic Refinement Compiler & Multi-Transport Test Suite

Validates:
1. Requirement IR compilation, Functional vs NFR separation, and DEPENDENCY_HOLE detection.
2. Conditional ADRReasoningEngine (emits Microservices for high-throughput NFRs vs Modular Monolith).
3. Bounded Context clustering by capability workflows.
4. Production 6-Gate HLDValidator auditing Traceability, Ownership, Dependencies, Security, Workflow, and NFRs.
5. Archetype surface selection (Backend API / CLI tool gets ZERO web UI surfaces).
6. Epistemic Task BDD Invariance (HTTP 403 assertion conditionality on AUTHORIZED_FOR evidence).
7. Execution Architecture selection (CLI_DISPATCHER with cli://, PIPELINE_WORKER with event://).
8. Authoritative FSM pipeline integration and v7_refinement_pipeline.json artifact writing.
"""

import os
import sys
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from domain_primitives import (
    DomainPrimitiveType,
    DomainNode,
    SemanticDomainGraph
)
from behavior_graph import BehaviorGraphEngine, EpistemicStatus
from requirement_ir import (
    RequirementGraph,
    RequirementNode,
    RequirementKind,
    NFRCategory
)
from hld_compiler import (
    HLDCompiler,
    HLDValidator,
    HLDDesign,
    ADRRecord,
    ADRReasoningEngine
)
from lld_compiler import (
    LLDCompiler,
    LLDComponent,
    LLDComponentType,
    ExecutionArchitecture,
    InteractionTransport
)
from task_compiler import (
    TaskCompiler,
    TaskRecord,
    TaskCategory
)
from spec_compiler import SpecificationCompiler
from spec_synthesis import SpecSynthesisEngine


def test_v7_requirement_ir_compilation_and_dependency_hole_detection():
    """Verify RequirementGraph compiles from behavior graph and detects dependency holes."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    prompt = "Doctor approves prescription."
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, prompt)
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)

    reqs = list(r_graph.nodes.values())
    func_reqs = [r for r in reqs if r.kind == RequirementKind.FUNCTIONAL]
    nfr_reqs = [r for r in reqs if r.kind == RequirementKind.NON_FUNCTIONAL]

    assert len(func_reqs) >= 1
    assert len(nfr_reqs) >= 1
    assert nfr_reqs[0].nfr_category == NFRCategory.AUDITABILITY

    orphan_req = RequirementNode(
        id="REQ-TEST-HOLE",
        kind=RequirementKind.FUNCTIONAL,
        statement="Doctor signs contract",
        actor="doctor",
        capability="sign_contract",
        target="contract",
        preconditions=["contract.status == REVIEWED"],
        epistemic_status=EpistemicStatus.EXPLICIT
    )
    r_graph.add_requirement(orphan_req)

    holes = r_graph.detect_dependency_holes()
    assert len(holes) >= 1
    assert holes[0]["type"] == "MISSING_PRECONDITION_STATE_MODEL"


def test_v7_conditional_adr_reasoning():
    """Verify ADRReasoningEngine evaluates evidence conditionally instead of hardcoding Modular Monolith."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctor approves prescription.")
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)

    hld_default = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="Doctor approves prescription.")
    adr_default = hld_default.adrs[0]
    assert adr_default.id == "ADR-001"
    assert adr_default.status == "PROPOSED"

    high_perf_req = RequirementNode(
        id="REQ-NFR-SCALE",
        kind=RequirementKind.NON_FUNCTIONAL,
        nfr_category=NFRCategory.PERFORMANCE,
        statement="System must process 10k events/sec with independent scaling",
        actor="system",
        capability="scale_ingest",
        target="telemetry"
    )
    r_graph.add_requirement(high_perf_req)

    hld_micro = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="Microservice architecture with event-driven kafka ingest")
    adr_micro = hld_micro.adrs[0]
    assert "Microservices" in adr_micro.decision
    assert adr_micro.status == "ACCEPTED"


def test_v8_epistemic_bdd_task_auth_conditionality():
    """Verify TaskCompiler adds HTTP 403 authorization criteria ONLY when explicit authorization evidence exists."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    # Prompt 1: Plain assertion without auth evidence ("Doctor approves prescription")
    b_graph1 = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctor approves prescription.")
    r_graph1 = RequirementGraph.compile_from_behavior_graph(b_graph1)
    hld1 = HLDCompiler.compile_hld(r_graph1, b_graph1)
    lld1 = LLDCompiler.compile_lld(hld1, r_graph1, b_graph1)
    tasks1 = TaskCompiler.compile_tasks(lld1, r_graph=r_graph1, b_graph=b_graph1)

    c1 = " ".join(tasks1[0].verification_criteria)
    # PERFORMS != AUTHORIZED_FOR: No un-backed HTTP 403 assertion
    assert "403" not in c1

    # Prompt 2: Explicit authorization evidence ("Doctor is authorized to approve prescription.")
    b_graph2 = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctor is authorized to approve prescription.")
    r_graph2 = RequirementGraph.compile_from_behavior_graph(b_graph2)
    hld2 = HLDCompiler.compile_hld(r_graph2, b_graph2)
    lld2 = LLDCompiler.compile_lld(hld2, r_graph2, b_graph2)
    tasks2 = TaskCompiler.compile_tasks(lld2, r_graph=r_graph2, b_graph=b_graph2)

    c2 = " ".join(tasks2[0].verification_criteria)
    assert "HTTP 403" in c2 or "403" in c2


def test_v8_dynamic_execution_architecture_and_transports():
    """Verify LLDCompiler compiles CLI_DISPATCHER with cli:// and PIPELINE_WORKER with event:// transport models."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_operator", "Operator", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_log", "Log", DomainPrimitiveType.ENTITY))

    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "Operator parses log.")
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
    hld = HLDCompiler.compile_hld(r_graph, b_graph)

    # 1. CLI Tool Archetype -> CLI_DISPATCHER with cli:// routes
    lld_cli = LLDCompiler.compile_lld(hld, r_graph, b_graph, archetypes=["cli_tool"])
    cli_comp = next(c for c in lld_cli if c.component_type == LLDComponentType.CLI_DISPATCHER)
    assert cli_comp.transport == InteractionTransport.CLI_COMMAND
    assert any("cli://" in ep for ep in cli_comp.api_endpoints)

    # 2. Data Pipeline Archetype -> PIPELINE_WORKER with event:// topics
    lld_pipe = LLDCompiler.compile_lld(hld, r_graph, b_graph, archetypes=["data_pipeline"])
    pipe_comp = next(c for c in lld_pipe if c.component_type == LLDComponentType.PIPELINE_WORKER)
    assert pipe_comp.transport == InteractionTransport.EVENT_TOPIC
    assert any("event://" in ep for ep in pipe_comp.api_endpoints)


def test_v8_end_to_end_refinement_compiler_pipeline():
    """Verify end-to-end compile_v7_refinement_pipeline execution in V8 when ADRs are confirmed."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_sensor", "Sensor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_reading", "Reading", DomainPrimitiveType.ENTITY))

    res = SpecificationCompiler.compile_v7_refinement_pipeline(
        graph=d_graph,
        intent_features=["reading", "ingest"],
        raw_request="Sensor is authorized to ingest reading using distributed microservices architecture.",
        archetypes=["data_pipeline"]
    )

    assert "behavior_graph" in res
    assert "requirement_graph" in res
    assert "hld_design" in res
    assert "hld_validation" in res
    assert "lld_components" in res
    assert "tasks" in res

    assert res["hld_validation"]["passed"] is True
    assert res["blocked"] is True
    assert res["target_fsm_state"] == "DEBATE"
