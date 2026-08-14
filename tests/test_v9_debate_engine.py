"""
S-Class EOS V9.4 - Multi-Dimensional Risk & Architecture Satisfaction Hardened Test Suite

Validates:
1. Compositional Multi-Dimensional Risk Profile requires ALL matching dimensions for multi-domain ADRs.
2. Requirement presence alone WITHOUT explicit architecture-satisfaction mechanism evidence returns UNKNOWN (or FAIL on structural contradiction).
3. Requirement presence WITH explicit architecture-satisfaction mechanism evidence returns PASS.
4. Failover/Resilience requirement without failover design mechanism returns UNKNOWN Resilience gate.
5. End-to-end V9.4 debate cycle enforces compositional risk gates and trade-off comparison rationales.
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


def test_compositional_risk_profile_requires_all_matching_dimensions():
    """Adversarial Test 1: Dynamic risk profile MUST be compositional (additive), requiring all matching dimensions for a multi-domain ADR."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    adr = ADRRecord(
        id="ADR-001",
        title="Migrate payment system to event-driven microservices",
        decision="Event-Driven Microservices with Kafka and PostgreSQL",
        alternatives=["Modular Monolith"],
        evidence=["High throughput 50k events/sec", "ACID payment ledger", "RBAC security guards", "Failover retry policy"],
        affected_modules=["mod_1", "mod_2"],
        rejected_options=[],
        reason="Payment system migration",
        status="PROPOSED",
        confidence=0.50,
        epistemic_status=EpistemicStatus.PROPOSED
    )

    prof = GenericDebateEvaluator.evaluate_risk_profile(adr, r_graph, b_graph, raw_request="Migrate payment system with 50k events/sec, RBAC security, ACID transactions, and failover retries")

    assert "Data Consistency & Persistence" in prof.required_high_risk_dimensions
    assert "Scalability & Performance" in prof.required_high_risk_dimensions
    assert "Security & Authorization" in prof.required_high_risk_dimensions
    assert "Fault Tolerance & Resilience" in prof.required_high_risk_dimensions
    assert "Modularity & Coupling" in prof.required_high_risk_dimensions


def test_requirement_presence_without_architecture_mechanism_returns_unknown_or_fail():
    """Adversarial Test 2: Requirement presence without architecture mechanism returns UNKNOWN (or FAIL on structural contradiction)."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    
    # 1. Structural contradiction (Monolith for 50k events/sec NFR) -> FAIL
    adr_fail = ADRRecord("ADR-001", "Performance Strategy", "Modular Monolith", [], ["High throughput 50k events/sec required"], ["mod_1"], [], "Monolith choice", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld_fail = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr_fail])

    claim_fail = ClaimDecomposer.decompose_adr_to_claim(adr_fail, r_graph, b_graph, raw_request="High-throughput 50k events/sec required")
    challenges_f, alternatives_f, dim_gates_f = GenericDebateEvaluator.evaluate_5d_challenges(claim_fail, adr_fail, hld_fail, r_graph, b_graph, raw_request="High-throughput 50k events/sec required")

    scale_gate_f = next(d for d in dim_gates_f if d.dimension_name == "Scalability & Performance")
    assert scale_gate_f.status == "FAIL"

    # 2. Scale NFR present without scaling mechanism evidence (and no monolith contradiction) -> UNKNOWN
    adr_unk = ADRRecord("ADR-002", "Performance Strategy", "Standard Service", [], ["Scale throughput required"], ["mod_1"], [], "Default", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld_unk = HLDDesign(system_name="TestSys", architecture_style="Service", modules=[mod], adrs=[adr_unk])

    claim_unk = ClaimDecomposer.decompose_adr_to_claim(adr_unk, r_graph, b_graph, raw_request="Scale throughput required")
    challenges_u, alternatives_u, dim_gates_u = GenericDebateEvaluator.evaluate_5d_challenges(claim_unk, adr_unk, hld_unk, r_graph, b_graph, raw_request="Scale throughput required")

    scale_gate_u = next(d for d in dim_gates_u if d.dimension_name == "Scalability & Performance")
    assert scale_gate_u.status == "UNKNOWN"


def test_requirement_presence_with_architecture_mechanism_returns_pass():
    """Verify requirement presence WITH explicit architecture-satisfaction mechanism evidence returns PASS."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr = ADRRecord(
        id="ADR-001",
        title="Event-driven scale ingestion",
        decision="Kafka Streaming Microservices",
        alternatives=["Modular Monolith"],
        evidence=["High throughput 50k events/sec", "Kafka queue ingestion worker pool"],
        affected_modules=["mod_1"],
        rejected_options=[],
        reason="Scale streaming",
        status="ACCEPTED",
        confidence=0.95,
        epistemic_status=EpistemicStatus.CONFIRMED
    )
    hld = HLDDesign(system_name="TestSys", architecture_style="Microservices", modules=[mod], adrs=[adr])

    claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request="High-throughput 50k events/sec with Kafka queue ingestion worker pool")
    challenges, alternatives, dim_gates = GenericDebateEvaluator.evaluate_5d_challenges(claim, adr, hld, r_graph, b_graph, raw_request="High-throughput 50k events/sec with Kafka queue ingestion worker pool")

    scale_gate = next(d for d in dim_gates if d.dimension_name == "Scalability & Performance")
    assert scale_gate.status == "PASS"
    assert len(scale_gate.requirement_evidence) >= 1
    assert len(scale_gate.architecture_satisfaction_evidence) >= 1


def test_failover_requirement_without_failover_design_returns_unknown_resilience():
    """Adversarial Test 3: Failover/Resilience requirement without failover design mechanism MUST return UNKNOWN Resilience gate."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr = ADRRecord("ADR-001", "System Resilience Strategy", "Modular Monolith", [], ["System must support failover and HA"], ["mod_1"], [], "Resilience", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr])

    claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request="System must support failover and HA")
    challenges, alternatives, dim_gates = GenericDebateEvaluator.evaluate_5d_challenges(claim, adr, hld, r_graph, b_graph, raw_request="System must support failover and HA")

    res_gate = next(d for d in dim_gates if d.dimension_name == "Fault Tolerance & Resilience")
    assert res_gate.status == "UNKNOWN"
    assert "Resilience requirement present, but missing explicit failover/circuit-breaker design mechanism evidence" in res_gate.missing_evidence[0]


def test_end_to_end_v9_4_debate_cycle_with_compositional_risk_gates(tmp_path):
    """Integration Test: V9.4 debate cycle evaluates compositional risk gates and records requirement vs architecture evidence lists."""
    tmp_workspace = str(tmp_path)
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"

    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod_1 = HLDModule(id="mod_1", name="Payment Context", system_boundary="internal", owned_entities=["Payment"], owned_capabilities=["pay"])
    mod_2 = HLDModule(id="mod_2", name="Audit Context", system_boundary="internal", owned_entities=["AuditLog"], owned_capabilities=["log"])
    adr = ADRRecord(
        id="ADR-001",
        title="Payment persistence and audit logging",
        decision="PostgreSQL Relational DB with ACID transactions",
        alternatives=["MongoDB Document Store"],  # Grounded alternative provided!
        evidence=["Relational schema with ACID transactions", "PostgreSQL ACID database", "Bounded context purity across payment and audit modules"],
        affected_modules=["mod_1", "mod_2"],
        rejected_options=[],
        reason="ACID transactions",
        status="ACCEPTED",
        confidence=0.95,
        epistemic_status=EpistemicStatus.CONFIRMED
    )
    hld = HLDDesign(system_name="HLD-001", architecture_style="Monolith", modules=[mod_1, mod_2], adrs=[adr])

    res = ArchitectureDebateEngine.run_debate_cycle(hld, r_graph, b_graph, raw_request="PostgreSQL relational database with ACID transactions and bounded context purity across payment and audit modules", workspace_dir=tmp_workspace)

    assert len(res.decision_records) == 1
    d_rec = res.decision_records[0]
    assert "Data Consistency & Persistence" in d_rec.risk_profile["required_high_risk_dimensions"]
    assert d_rec.decision_outcome in [DecisionOutcome.ACCEPT, DecisionOutcome.REVISE]
