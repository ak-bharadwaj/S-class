"""
S-Class EOS V9.1 - Genuine Decision Resolution Engine Test Suite

Validates:
1. Claim Decomposition (premises, rationale, assumptions, constraints, benefits, costs, falsifiers).
2. Evidence Quality Assessment Framework (strength, directness, relevance, freshness, quality_score).
3. Generic 5-Dimensional Challenge Protocol (Scale, Auth, Consistency, Resilience, Modularity).
4. Strict Decision Sufficiency Gate (6-factor gate replacing default auto-acceptance).
5. Versioned ADR v1 -> v2 Revision Promotion & HMAC signed ApprovalRecord (DEBATE_ENGINE).
6. End-to-End Control Plane Integration & ArtifactGovernor Unblocking.
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
    ClaimDecomposer,
    GenericDebateEvaluator,
    DecisionSufficiencyGate
)
import runtime


def test_claim_decomposition_premises_assumptions_falsifiers():
    """Verify ClaimDecomposer decomposes ADR into explicit rationale, premises, assumptions, falsifiers, and evidence quality."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    adr = ADRRecord(
        id="ADR-001",
        title="Architectural Topology Selection",
        decision="Modular Monolith with Bounded Contexts",
        alternatives=["Distributed Microservices"],
        evidence=["Domain context cohesion"],
        affected_modules=["mod_1"],
        rejected_options=[],
        reason="Transactional consistency across scheduling and billing",
        status="PROPOSED",
        confidence=0.50,
        epistemic_status=EpistemicStatus.PROPOSED
    )

    claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request="Doctor approves prescription")

    assert claim.claim_id == "CLAIM-ADR-001"
    assert claim.statement == "Modular Monolith with Bounded Contexts"
    assert len(claim.premises) >= 1
    assert len(claim.assumptions) >= 1
    assert len(claim.falsifiers) >= 1
    assert len(claim.evidence_quality_records) >= 1
    assert claim.evidence_quality_records[0].quality_score > 0.0


def test_evidence_quality_scoring_framework():
    """Verify EvidenceQualityRecord computes quality_score = strength * directness * relevance_score * freshness."""
    ev = EvidenceQualityRecord(
        evidence_id="EV-001",
        source="EXPLICIT_PROMPT",
        reference_text="High-throughput 50k events/sec",
        strength=0.90,
        freshness=1.0,
        directness=0.95,
        relevance_score=0.90
    )

    expected_score = round(0.90 * 0.95 * 0.90 * 1.0, 3)
    assert ev.quality_score == expected_score


def test_generic_5_dimensional_challenge_protocol():
    """Verify GenericDebateEvaluator audits 5D challenges across scale, security, and evidence quality."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])

    adr_1 = ADRRecord("ADR-001", "Architectural Topology Selection", "Modular Monolith with Bounded Contexts", [], [], ["mod_1"], [], "Default", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr_1])

    claim = ClaimDecomposer.decompose_adr_to_claim(adr_1, r_graph, b_graph, raw_request="High-throughput 50k events/sec ingestion service")
    challenges, alternatives = GenericDebateEvaluator.evaluate_5d_challenges(claim, adr_1, hld, r_graph, b_graph, raw_request="High-throughput 50k events/sec ingestion service")

    assert len(challenges) >= 1
    assert challenges[0].category == "scale_throughput_invariant"
    assert challenges[0].severity == "HIGH"
    assert len(alternatives) >= 1


def test_decision_sufficiency_gate_rejects_unsupported_claim():
    """Verify DecisionSufficiencyGate blocks acceptance when high-severity challenges or insufficient evidence exist."""
    ev_record = EvidenceQualityRecord("EV-1", "REQUIREMENT_GRAPH", "Indirect text", 0.30, 0.50, 0.40, 0.40)
    claim = EngineeringClaim(
        claim_id="CLAIM-1",
        target_adr_id="ADR-1",
        statement="Use Monolith",
        rationale="Default",
        premises=[],
        assumptions=[],
        constraints=[],
        expected_benefits=[],
        expected_costs=[],
        falsifiers=[],
        evidence_quality_records=[ev_record],
        category="scale_throughput_invariant",
        initial_confidence=0.40
    )

    high_challenge = ClaimChallenge("CH-1", "scale_throughput_invariant", "NFR_PERFORMANCE", "HIGH", "Bottleneck", [], {}, "Microservices")
    blast = {"blast_radius_score": 0.90}

    outcome, confidence, metrics = DecisionSufficiencyGate.evaluate_sufficiency(claim, [high_challenge], [], blast)

    assert outcome == DecisionOutcome.REJECT
    assert confidence == 0.20
    assert metrics["gate_passed"] is False


def test_versioned_adr_v1_to_v2_promotion_and_hmac_signing(tmp_path):
    """Verify promote_alternative_to_adr_v2 creates versioned ADR v2 with previous_version_hash and HMAC DEBATE_ENGINE signature."""
    tmp_workspace = str(tmp_path)
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
    sec_key = ArtifactGovernor._get_governance_secret(tmp_workspace)

    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])

    adr_v1 = ADRRecord("ADR-001", "Architectural Topology Selection", "Modular Monolith with Bounded Contexts", [], ["Cohesion"], ["mod_1"], [], "Plausible default topology", "ACCEPTED", 0.95, EpistemicStatus.CONFIRMED, version=1)
    hld = HLDDesign(system_name="HLD-001", architecture_style="Monolith", modules=[mod], adrs=[adr_v1])

    res = ArchitectureDebateEngine.run_debate_cycle(hld, r_graph, b_graph, raw_request="Sensor reads item", workspace_dir=tmp_workspace)

    assert len(res.accepted_adrs) == 1
    assert len(res.decision_records) == 1

    d_rec = res.decision_records[0]
    assert d_rec.decision_outcome == DecisionOutcome.ACCEPT
    assert d_rec.approval_record is not None
    assert d_rec.approval_record["authority"] == "DEBATE_ENGINE"

    # Verify ADR v2 version increment and previous_version_hash binding
    accepted_v2 = res.accepted_adrs[0]
    assert accepted_v2.version == 2
    assert accepted_v2.previous_version_hash is not None

    # Verify ApprovalRecord passes HMAC signature audit
    verified_approvals = ArtifactGovernor._load_verified_approval_records(tmp_workspace)
    assert "ADR-001" in verified_approvals
    assert verified_approvals["ADR-001"].authority == ApprovalAuthority.DEBATE_ENGINE
    assert verified_approvals["ADR-001"].is_valid(sec_key) is True


def test_end_to_end_debate_fsm_unblocking(tmp_path):
    """Integration Test: V9.1 Debate engine execution unblocks ArtifactGovernor for downstream FSM transitions."""
    tmp_workspace = str(tmp_path)
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
    runtime.initialize_state(tmp_workspace, goal="Build grounded microservice")

    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr_1 = ADRRecord("ADR-001", "Architectural Topology Selection", "Modular Monolith with Bounded Contexts", [], ["Evidence"], ["mod_1"], [], "Plausible choice", "ACCEPTED", 0.95, EpistemicStatus.CONFIRMED, version=1)
    hld = HLDDesign(system_name="HLD-001", architecture_style="Monolith", modules=[mod], adrs=[adr_1])

    # Run debate cycle -> emits DEBATE_ENGINE HMAC signed ApprovalRecord into .agents/approvals.json
    deb_res = ArchitectureDebateEngine.run_debate_cycle(hld, r_graph, b_graph, workspace_dir=tmp_workspace)

    # Save pipeline result to .agents/v7_refinement_pipeline.json
    pipe_dict = {
        "blocked": False,
        "target_fsm_state": "CODING",
        "hld_design": hld.to_dict(),
        "hld_governance": {"is_blocked": False, "recommended_fsm_state": "CODING", "validation_status": "VALID", "approval_status": "APPROVED"}
    }
    pipe_file = os.path.join(tmp_workspace, ".agents", "v7_refinement_pipeline.json")
    runtime.write_json_atomic(pipe_file, pipe_dict)

    state = runtime.get_state(tmp_workspace)
    state.currentPhase = "DEBATE"
    runtime.save_state(state, tmp_workspace)

    # Transition from DEBATE to DESIGN_REVISION must be ALLOWED by ArtifactGovernor!
    gov = ArtifactGovernor.enforce_fsm_transition("DEBATE", "debate_resolved", "DESIGN_REVISION", workspace_dir=tmp_workspace)
    assert gov.is_blocked is False
    assert gov.recommended_fsm_state == FSMTransitionTarget.CODING
