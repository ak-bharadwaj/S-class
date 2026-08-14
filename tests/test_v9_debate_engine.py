"""
S-Class EOS V9.3 - Epistemic Grounding & Decision Risk Hardened Test Suite

Validates:
1. Monolith topology without explicit consistency evidence MUST return UNKNOWN Data Consistency gate (NOT PASS).
2. Single module without explicit modularity evidence MUST return UNKNOWN Modularity gate (NOT PASS).
3. Approved decision WITHOUT grounded alternatives MUST FAIL sufficiency gate (returns INSUFFICIENT_DEBATE).
4. Explicit consistency/ACID evidence returns PASS for Data Consistency gate.
5. Dynamic Decision Risk Profiling assigns required high-risk dimensions based on decision topic/domain.
6. Required UNKNOWN dimensions block decision acceptance.
"""

import os
import sys
import json
import pytest

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from domain_primitives import DomainPrimitiveType, DomainNode, SemanticDomainGraph
from behavior_graph import BehaviorGraphEngine, EpistemicStatus, BehaviorGraph
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


def test_monolith_without_consistency_evidence_returns_unknown_consistency_gate():
    """Adversarial Test 1: Monolith topology without explicit consistency evidence MUST return UNKNOWN Data Consistency gate (NOT PASS!)."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr = ADRRecord("ADR-001", "Database Persistence Selection", "Modular Monolith", [], ["General context"], ["mod_1"], [], "Monolith choice", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request="Item inventory list")
    challenges, alternatives, dim_gates = GenericDebateEvaluator.evaluate_5d_challenges(claim, adr, hld, r_graph, b_graph, raw_request="Item inventory list")

    dc_gate = next(d for d in dim_gates if d.dimension_name == "Data Consistency & Persistence")
    assert dc_gate.status == "UNKNOWN"
    assert "No explicit data consistency or ACID transaction evidence provided" in dc_gate.missing_evidence


def test_single_module_without_boundary_evidence_returns_unknown_modularity_gate():
    """Adversarial Test 2: Single HLD module without explicit boundary evidence MUST return UNKNOWN Modularity gate (NOT PASS!)."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr = ADRRecord("ADR-001", "Topology Selection", "Modular Monolith", [], ["General context"], ["mod_1"], [], "Single module", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request="")
    challenges, alternatives, dim_gates = GenericDebateEvaluator.evaluate_5d_challenges(claim, adr, hld, r_graph, b_graph, raw_request="")

    mod_gate = next(d for d in dim_gates if d.dimension_name == "Modularity & Coupling")
    assert mod_gate.status == "UNKNOWN"


def test_approved_decision_without_grounded_alternatives_fails_sufficiency_gate():
    """Adversarial Test 3: Approval receipt NO LONGER substitutes for grounded alternative exploration (returns INSUFFICIENT_DEBATE)."""
    synth_alt = ArchitecturalAlternative("ALT-GEN-01", "Modular Monolith", "Generic fallback", [], [], 0.3, 0.5, is_synthetic=True)
    ev_record = EvidenceQualityRecord("EV-1", EvidenceState.DIRECT_EVIDENCE, "REQUIREMENT_GRAPH", "Grounded requirement", 0.90, 1.0, 0.90, 0.90)
    claim = EngineeringClaim("CLAIM-1", "ADR-1", "Use Monolith", "Reason", [], [], [], [], [], [], [ev_record], "scale_throughput_invariant", 0.90)
    blast = {"blast_radius_score": 0.40}
    risk_prof = DecisionRiskProfile("ADR-1", "DATA_PERSISTENCE", ["Data Consistency & Persistence"])

    dim_gates_pass = [
        DimensionGateResult("Data Consistency & Persistence", "PASS", ["Matched"], [], [])
    ]

    # has_existing_approval = True BUT synthetic alternatives only -> MUST RETURN INSUFFICIENT_DEBATE!
    outcome, confidence, metrics = DecisionSufficiencyGate.evaluate_sufficiency(
        claim=claim,
        challenges=[],
        alternatives=[synth_alt],
        blast_analysis=blast,
        dimension_gates=dim_gates_pass,
        risk_profile=risk_prof,
        has_existing_approval=True
    )

    assert metrics["alternatives_explored"] is False
    assert outcome == DecisionOutcome.INSUFFICIENT_DEBATE


def test_explicit_consistency_evidence_returns_pass_consistency_gate():
    """Verify explicit ACID/relational database prompt evidence produces PASS for Data Consistency gate."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr = ADRRecord("ADR-001", "Database Persistence Selection", "PostgreSQL Relational DB", [], ["Relational schema with ACID transactions"], ["mod_1"], [], "ACID requirements", "ACCEPTED", 0.95, EpistemicStatus.CONFIRMED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request="PostgreSQL database with ACID transactions for financial ledger")
    challenges, alternatives, dim_gates = GenericDebateEvaluator.evaluate_5d_challenges(claim, adr, hld, r_graph, b_graph, raw_request="PostgreSQL database with ACID transactions for financial ledger")

    dc_gate = next(d for d in dim_gates if d.dimension_name == "Data Consistency & Persistence")
    assert dc_gate.status == "PASS"
    assert "Explicit transactional consistency requirements" in dc_gate.evidence_found[0]


def test_dynamic_decision_risk_profiling_assigns_domain_specific_required_dimensions():
    """Verify evaluate_risk_profile assigns domain-specific required high-risk dimensions."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()

    adr_db = ADRRecord("ADR-001", "Database Migration Strategy", "PostgreSQL", [], [], ["mod_1"], [], "DB", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    prof_db = GenericDebateEvaluator.evaluate_risk_profile(adr_db, r_graph, b_graph, raw_request="")
    assert "Data Consistency & Persistence" in prof_db.required_high_risk_dimensions

    adr_sec = ADRRecord("ADR-002", "Role Authorization Guard", "RBAC", [], [], ["mod_1"], [], "Auth", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    prof_sec = GenericDebateEvaluator.evaluate_risk_profile(adr_sec, r_graph, b_graph, raw_request="")
    assert "Security & Authorization" in prof_sec.required_high_risk_dimensions
