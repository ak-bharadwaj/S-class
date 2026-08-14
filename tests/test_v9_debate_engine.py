"""
S-Class EOS V9.4.1 - Trade-off Complete & Security Gate Integrity Test Suite

Validates:
1. Grounded alternative WITHOUT comparison rationale DOES NOT count as explored (fails sufficiency gate).
2. Security architecture evidence WITHOUT security requirement returns UNKNOWN.
3. Security requirement WITHOUT security architecture evidence returns UNKNOWN.
4. Security requirement WITH security architecture evidence returns PASS.
5. All V9.4 multi-dimensional compositional risk gates remain enforced.
"""

import os
import sys
import json
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from domain_primitives import DomainPrimitiveType, DomainNode, SemanticDomainGraph
from behavior_graph import BehaviorGraphEngine, EpistemicStatus, BehaviorGraph, BehaviorNodeType, BehaviorRelationType, BehaviorNode
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind, NFRCategory
from hld_compiler import HLDCompiler, HLDDesign, HLDModule, ADRRecord, ValidationStatus, ApprovalStatus
from artifact_governor import ArtifactGovernor, ApprovalRecord, ApprovalAuthority, FSMTransitionTarget
from architecture_debate import (
    ArchitectureDebateEngine,
    EngineeringClaim,
    ArchitecturalAlternative,
    ClaimChallenge,
    DecisionRecord,
    DebateResult,
    DecisionOutcome,
    EvidenceQualityRecord,
    EvidenceState,
    DimensionGateResult,
    DecisionRiskProfile,
    ClaimDecomposer,
    GenericDebateEvaluator,
    DecisionSufficiencyGate
)
import runtime


def test_grounded_alternative_without_comparison_rationale_fails_sufficiency_gate():
    """Adversarial Test 1: Grounded alternative WITHOUT comparison rationale MUST NOT count as explored."""
    unrationale_alt = ArchitecturalAlternative("ALT-01", "Monolith", "Desc", ["Pro"], ["Con"], 0.3, 0.5, is_synthetic=False, comparison_rationale="")
    rationale_alt = ArchitecturalAlternative("ALT-02", "Microservices", "Desc", ["Pro"], ["Con"], 0.8, 0.4, is_synthetic=False, comparison_rationale="Evaluated trade-off")

    ev_record = EvidenceQualityRecord("EV-1", EvidenceState.DIRECT_EVIDENCE, "REQUIREMENT_GRAPH", "Requirement", 0.90, 1.0, 0.90, 0.90)
    claim = EngineeringClaim("CLAIM-1", "ADR-1", "Use Monolith", "Reason", [], [], [], [], [], [], [ev_record], "scale_throughput_invariant", 0.90)
    blast = {"blast_radius_score": 0.40}
    risk_prof = DecisionRiskProfile("ADR-1", "DATA_PERSISTENCE", ["Data Consistency & Persistence"])
    dim_gates_pass = [DimensionGateResult("Data Consistency & Persistence", "PASS", ["Matched"], ["Matched"], [], [])]

    # Without comparison rationale -> alternatives_explored MUST BE FALSE!
    outcome_un, conf_un, metrics_un = DecisionSufficiencyGate.evaluate_sufficiency(claim, [], [unrationale_alt], blast, dim_gates_pass, risk_prof)
    assert metrics_un["alternatives_explored"] is False
    assert outcome_un == DecisionOutcome.INSUFFICIENT_DEBATE

    # With comparison rationale -> alternatives_explored IS TRUE!
    outcome_rat, conf_rat, metrics_rat = DecisionSufficiencyGate.evaluate_sufficiency(claim, [], [rationale_alt], blast, dim_gates_pass, risk_prof)
    assert metrics_rat["alternatives_explored"] is True
    assert outcome_rat == DecisionOutcome.ACCEPT


def test_security_arch_evidence_without_security_requirement_returns_unknown():
    """Adversarial Test 2: Security architecture evidence WITHOUT explicit security requirement MUST return UNKNOWN."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()

    # Add actor and AUTHORIZED_FOR edge to BehaviorGraph (Architecture Evidence present)
    n1 = BehaviorNode(id="node_1", name="ApprovePrescription", behavior_type=BehaviorNodeType.COMMAND, actor_id="actor_doctor", target_entity_id="entity_prescription")
    n2 = BehaviorNode(id="node_2", name="PrescriptionApproved", behavior_type=BehaviorNodeType.SIDE_EFFECT, actor_id="actor_doctor", target_entity_id="entity_prescription")
    b_graph.add_node(n1)
    b_graph.add_node(n2)
    b_graph.add_edge(n1.id, BehaviorRelationType.AUTHORIZED_FOR, n2.id)

    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr = ADRRecord("ADR-002", "Role Authorization Guard", "RBAC Strategy", [], ["Evidence"], ["mod_1"], [], "RBAC", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request="Doctor approves prescription.")
    challenges, alternatives, dim_gates = GenericDebateEvaluator.evaluate_5d_challenges(claim, adr, hld, r_graph, b_graph, raw_request="Doctor approves prescription.")

    sec_gate = next(d for d in dim_gates if d.dimension_name == "Security & Authorization")
    assert sec_gate.status == "UNKNOWN"
    assert "Security architecture mechanism present, but explicit security requirement unstated" in sec_gate.missing_evidence[0]


def test_security_requirement_without_security_arch_evidence_returns_unknown():
    """Adversarial Test 3: Security requirement WITHOUT security architecture evidence MUST return UNKNOWN."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()  # Empty behavior graph: no actors, no AUTHORIZED_FOR edges!

    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr = ADRRecord("ADR-002", "Role Authorization Guard", "RBAC Strategy", [], ["Evidence"], ["mod_1"], [], "RBAC", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request="System requires RBAC security policy and role-based guards.")
    challenges, alternatives, dim_gates = GenericDebateEvaluator.evaluate_5d_challenges(claim, adr, hld, r_graph, b_graph, raw_request="System requires RBAC security policy and role-based guards.")

    sec_gate = next(d for d in dim_gates if d.dimension_name == "Security & Authorization")
    assert sec_gate.status == "UNKNOWN"
    assert "Security requirement present, but missing explicit role authorization policy rules and protected boundaries" in sec_gate.missing_evidence[0]


def test_security_requirement_with_security_arch_evidence_returns_pass():
    """Adversarial Test 4: Security requirement WITH security architecture evidence MUST return PASS."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()

    n1 = BehaviorNode(id="node_1", name="ApprovePrescription", behavior_type=BehaviorNodeType.COMMAND, actor_id="actor_doctor", target_entity_id="entity_prescription")
    n2 = BehaviorNode(id="node_2", name="PrescriptionApproved", behavior_type=BehaviorNodeType.SIDE_EFFECT, actor_id="actor_doctor", target_entity_id="entity_prescription")
    b_graph.add_node(n1)
    b_graph.add_node(n2)
    b_graph.add_edge(n1.id, BehaviorRelationType.AUTHORIZED_FOR, n2.id)

    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr = ADRRecord("ADR-002", "Role Authorization Guard", "RBAC Strategy", [], ["Role authorization security policy"], ["mod_1"], [], "RBAC", "ACCEPTED", 0.95, EpistemicStatus.CONFIRMED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request="System requires RBAC security policy with role-based guards.")
    challenges, alternatives, dim_gates = GenericDebateEvaluator.evaluate_5d_challenges(claim, adr, hld, r_graph, b_graph, raw_request="System requires RBAC security policy with role-based guards.")

    sec_gate = next(d for d in dim_gates if d.dimension_name == "Security & Authorization")
    assert sec_gate.status == "PASS"
    assert len(sec_gate.requirement_evidence) >= 1
    assert len(sec_gate.architecture_satisfaction_evidence) >= 1
