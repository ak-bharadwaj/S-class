"""
S-Class EOS V7.0 - Refinement Compiler Pipeline Test Suite

Validates:
1. Requirement IR compilation, Functional vs NFR separation, and DEPENDENCY_HOLE detection.
2. HLD Compiler module boundaries, Architecture Decision Record (ADR) generation, and HLDValidator gates.
3. LLD Compiler refinement, 100% parent lineage traceability, and behavior-derived UI/APIs.
4. Task Compiler task generation with complete upstream lineage.
5. End-to-End compile_v7_refinement_pipeline execution.
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
    ADRRecord
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


def test_v7_requirement_ir_compilation_and_dependency_hole_detection():
    """Verify RequirementGraph compiles from behavior graph and detects dependency holes."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    prompt = "Doctor approves prescription."
    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, prompt)
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)

    # Verify Functional & NFR requirements synthesized
    reqs = list(r_graph.nodes.values())
    func_reqs = [r for r in reqs if r.kind == RequirementKind.FUNCTIONAL]
    nfr_reqs = [r for r in reqs if r.kind == RequirementKind.NON_FUNCTIONAL]

    assert len(func_reqs) >= 1
    assert len(nfr_reqs) >= 1
    assert nfr_reqs[0].nfr_category == NFRCategory.AUDITABILITY

    # Test DEPENDENCY_HOLE detection when precondition references missing state transition
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


def test_v7_hld_compiler_and_adr_generation():
    """Verify HLDCompiler establishes module boundaries and emits Architecture Decision Records (ADRs)."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctor approves prescription.")
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
    hld = HLDCompiler.compile_hld(r_graph, b_graph)

    assert len(hld.modules) >= 1
    assert len(hld.adrs) >= 2
    assert hld.adrs[0].id == "ADR-001"

    # Validate HLD with HLDValidator
    passed, errors = HLDValidator.validate_hld(hld, r_graph, b_graph)
    assert passed is True
    assert len(errors) == 0


def test_v7_lld_refinement_compiler_and_parent_traceability():
    """Verify LLDCompiler refines HLD with 100% parent lineage traceability and behavior-derived UI/APIs."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctor approves prescription.")
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
    hld = HLDCompiler.compile_hld(r_graph, b_graph)
    lld_components = LLDCompiler.compile_lld(hld, r_graph, b_graph)

    assert len(lld_components) >= 3

    # Check parent lineage traceability
    for comp in lld_components:
        assert comp.parent.hld_id is not None
        assert len(comp.parent.req_ids) >= 1
        assert len(comp.parent.behavior_ids) >= 1

    # Check behavior-derived REST route
    ctrl = next(c for c in lld_components if c.component_type == LLDComponentType.CONTROLLER)
    assert any("POST /api/prescriptions/{id}/approve" in ep for ep in ctrl.api_endpoints)


def test_v7_task_compiler_with_full_upstream_lineage():
    """Verify TaskCompiler generates tasks with complete upstream lineage (task -> lld -> hld -> req -> behavior)."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    b_graph = BehaviorGraphEngine.build_behavior_graph(d_graph, "Doctor approves prescription.")
    r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
    hld = HLDCompiler.compile_hld(r_graph, b_graph)
    lld_components = LLDCompiler.compile_lld(hld, r_graph, b_graph)
    tasks = TaskCompiler.compile_tasks(lld_components)

    assert len(tasks) >= 3
    for t in tasks:
        assert t.id.startswith("TASK-")
        assert t.parent_lld != ""
        assert t.parent_hld != ""
        assert len(t.parent_reqs) >= 1
        assert len(t.parent_behaviors) >= 1


def test_v7_end_to_end_refinement_compiler_pipeline():
    """Verify end-to-end compile_v7_refinement_pipeline execution."""
    d_graph = SemanticDomainGraph()
    d_graph.add_node(DomainNode("actor_doctor", "Doctor", DomainPrimitiveType.ACTOR))
    d_graph.add_node(DomainNode("entity_prescription", "Prescription", DomainPrimitiveType.ENTITY))

    res = SpecificationCompiler.compile_v7_refinement_pipeline(
        graph=d_graph,
        intent_features=["prescription", "approve"],
        raw_request="Doctor approves prescription."
    )

    assert "behavior_graph" in res
    assert "requirement_graph" in res
    assert "hld_design" in res
    assert "hld_validation" in res
    assert "lld_components" in res
    assert "tasks" in res

    assert res["hld_validation"]["passed"] is True
    assert len(res["tasks"]) >= 3
