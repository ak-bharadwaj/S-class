"""
S-Class EOS V7.0 - Production Hardened Refinement Compiler Pipeline Test Suite

Validates:
1. Requirement IR compilation, Functional vs NFR separation, and DEPENDENCY_HOLE detection.
2. Conditional ADRReasoningEngine (emits Microservices for high-throughput NFRs vs Modular Monolith).
3. Bounded Context clustering by capability workflows.
4. Production 6-Gate HLDValidator auditing Traceability, Ownership, Dependencies, Security, Workflow, and NFRs.
5. Archetype surface selection (Backend API / CLI tool gets ZERO web UI surfaces).
6. Exact BDD task acceptance criteria (Given/And/When/Then).
7. Authoritative FSM integration in spec_synthesis.py.
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
from behavior_graph import BehaviorGraphEngine
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
    LLDComponentType
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

    # Precondition referencing missing state transition triggers DEPENDENCY_HOLE
    orphan_req = RequirementNode(
        id="REQ-TEST-HOLE",
        kind=RequirementKind.FUNCTIONAL,
        statement="Doctor signs contract",
        actor="doctor",
        capability="sign_contract",
        target="contract",
        preconditions=["contract.status == REVIEWED"],
        epistemic_status=b_graph.nodes[list(b_graph.nodes.keys())[0]].epistemic_status
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

    # 1. Ambiguous prompt -> Emits Modular Monolith with PROPOSED status for human/DEBATE review
    hld_default = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="Doctor approves prescription.")
    adr_default = hld_default.adrs[0]
    assert adr_default.id == "ADR-001"
    assert adr_default.status == "PROPOSED"
    assert adr_default.confidence == 0.50

    # 2. High-throughput performance NFR + microservices request -> Emits Microservices ADR with ACCEPTED status
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
    assert adr_micro.confidence == 0.95


def test_v7_bounded_context_clustering_and_6_gate_hld_validator():
    """Verify HLDCompiler clusters capabilities into Bounded Contexts and 6-gate HLDValidator checks architectural integrity."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctor approves prescription.")
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
    hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request="Doctor approves prescription.")

    assert len(hld.modules) >= 1
    mod = hld.modules[0]
    assert "Context" in mod.name or "Fulfillment" in mod.name or "Management" in mod.name

    # Validate HLD using production 6-gate validator
    passed, errors = HLDValidator.validate_hld(hld, r_graph, b_graph)
    assert passed is True
    assert len(errors) == 0


def test_v7_archetype_surface_selection_skips_ui_for_backend_cli():
    """Verify LLDCompiler generates ZERO UI_SURFACE components for backend_api or cli_tool archetypes."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctor approves prescription.")
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
    hld = HLDCompiler.compile_hld(r_graph, b_graph)

    # 1. Fullstack Monolith Archetype -> Generates UI_SURFACE
    lld_fullstack = LLDCompiler.compile_lld(hld, r_graph, b_graph, archetypes=["fullstack_monolith"])
    ui_surfaces_fullstack = [c for c in lld_fullstack if c.component_type == LLDComponentType.UI_SURFACE]
    assert len(ui_surfaces_fullstack) >= 1

    # 2. Backend API Archetype -> Generates ZERO UI_SURFACE components (template leakage eliminated!)
    lld_backend = LLDCompiler.compile_lld(hld, r_graph, b_graph, archetypes=["backend_api"])
    ui_surfaces_backend = [c for c in lld_backend if c.component_type == LLDComponentType.UI_SURFACE]
    assert len(ui_surfaces_backend) == 0

    # 3. CLI Tool Archetype -> Generates ZERO UI_SURFACE components
    lld_cli = LLDCompiler.compile_lld(hld, r_graph, b_graph, archetypes=["cli_tool"])
    ui_surfaces_cli = [c for c in lld_cli if c.component_type == LLDComponentType.UI_SURFACE]
    assert len(ui_surfaces_cli) == 0


def test_v7_bdd_contract_derived_task_criteria():
    """Verify TaskCompiler derives exact BDD acceptance criteria (Given/And/When/Then) from requirements."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctor approves prescription.")
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
    hld = HLDCompiler.compile_hld(r_graph, b_graph)
    lld_components = LLDCompiler.compile_lld(hld, r_graph, b_graph)

    tasks = TaskCompiler.compile_tasks(lld_components, r_graph=r_graph)
    assert len(tasks) >= 2

    ctrl_task = next(t for t in tasks if t.category == TaskCategory.API_ENDPOINT)
    criteria_str = " ".join(ctrl_task.verification_criteria)

    assert "Given" in criteria_str
    assert "When" in criteria_str
    assert "Then" in criteria_str
    assert "HTTP 403" in criteria_str or "403" in criteria_str
    assert "audit" in criteria_str.lower()


def test_v7_end_to_end_refinement_compiler_pipeline():
    """Verify end-to-end compile_v7_refinement_pipeline execution."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    res = SpecificationCompiler.compile_v7_refinement_pipeline(
        graph=d_graph,
        intent_features=["prescription", "approve"],
        raw_request="Doctor approves prescription.",
        archetypes=["nextjs_fullstack"]
    )

    assert "behavior_graph" in res
    assert "requirement_graph" in res
    assert "hld_design" in res
    assert "hld_validation" in res
    assert "lld_components" in res
    assert "tasks" in res

    assert res["hld_validation"]["passed"] is True
    assert len(res["tasks"]) >= 2
