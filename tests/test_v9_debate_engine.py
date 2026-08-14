"""
S-Class EOS V9.0 - Debate & Decision Intelligence Engine Test Suite

Validates:
1. EngineeringClaim Extraction & Evidence Gathering.
2. Multi-Perspective Challenges (Architect Feasibility & Skeptic Grounding).
3. Trade-Off Analysis & Blast-Radius Score Computation.
4. DecisionRecord Artifact Generation & HMAC Signed ApprovalRecord (DEBATE_ENGINE).
5. End-to-End Control Plane Integration & ArtifactGovernor Unblocking.
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
from architecture_debate import ArchitectureDebateEngine, EngineeringClaim, ArchitecturalAlternative, ClaimChallenge, DecisionRecord, DebateResult, DecisionOutcome
import runtime


def test_claim_extraction_and_evidence_gathering():
    """Verify extract_claims extracts claim statements, categories, and evidence from HLD ADRs."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])

    adr_1 = ADRRecord("ADR-001", "Architectural Topology Selection", "Modular Monolith with Bounded Contexts", [], ["Domain graph cohesion"], ["mod_1"], [], "Default topology", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    adr_2 = ADRRecord("ADR-002", "Authentication & Authorization Architecture", "Role-Based Access Control (RBAC)", [], ["Role definitions"], ["mod_1"], [], "Default auth", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr_1, adr_2])

    claims = ArchitectureDebateEngine.extract_claims(hld, r_graph, b_graph)

    assert len(claims) == 2
    assert claims[0].claim_id == "CLAIM-ADR-001"
    assert claims[0].statement == "Modular Monolith with Bounded Contexts"
    assert claims[1].claim_id == "CLAIM-ADR-002"
    assert claims[1].statement == "Role-Based Access Control (RBAC)"


def test_multi_perspective_architect_and_skeptic_challenges():
    """Verify debate cycle raises Architect & Skeptic challenges against ungrounded choices."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])

    # High-throughput prompt requiring microservices
    adr_1 = ADRRecord("ADR-001", "Architectural Topology Selection", "Modular Monolith with Bounded Contexts", [], [], ["mod_1"], [], "Default", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr_1])

    result = ArchitectureDebateEngine.run_debate_cycle(hld, r_graph, b_graph, raw_request="High-throughput 50k events/sec ingestion service")

    assert len(result.rejected_adrs) == 1
    assert result.rejected_adrs[0].id == "ADR-001"
    assert any("REVISE ADR-001" in rev for rev in result.required_revisions)


def test_alternative_architecture_tradeoff_and_blast_radius_scoring():
    """Verify trade-off analysis and quantitative blast-radius score computation."""
    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])

    adr_1 = ADRRecord("ADR-001", "Architectural Topology Selection", "Modular Monolith with Bounded Contexts", [], ["Evidence"], ["mod_1"], [], "Default", "PROPOSED", 0.85, EpistemicStatus.DERIVED)
    hld = HLDDesign(system_name="TestSys", architecture_style="Monolith", modules=[mod], adrs=[adr_1])

    blast = ArchitectureDebateEngine.compute_blast_radius(adr_1, hld, r_graph)

    assert "blast_radius_score" in blast
    assert "risk_class" in blast
    assert blast["risk_class"] == "HIGH_RISK"  # Topology is HIGH_RISK topic


def test_decision_record_and_hmac_debate_engine_approval_signing(tmp_path):
    """Verify DecisionRecord generation and valid HMAC signed ApprovalRecord with DEBATE_ENGINE authority."""
    tmp_workspace = str(tmp_path)
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
    sec_key = ArtifactGovernor._get_governance_secret(tmp_workspace)

    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])

    adr_1 = ADRRecord("ADR-001", "Architectural Topology Selection", "Modular Monolith with Bounded Contexts", [], ["Cohesion"], ["mod_1"], [], "Plausible default topology", "ACCEPTED", 0.95, EpistemicStatus.CONFIRMED)
    hld = HLDDesign(system_name="HLD-001", architecture_style="Monolith", modules=[mod], adrs=[adr_1])

    res = ArchitectureDebateEngine.run_debate_cycle(hld, r_graph, b_graph, raw_request="Sensor reads item", workspace_dir=tmp_workspace)

    assert len(res.accepted_adrs) == 1
    assert len(res.decision_records) == 1

    d_rec = res.decision_records[0]
    assert d_rec.decision_outcome == DecisionOutcome.ACCEPT
    assert d_rec.approval_record is not None
    assert d_rec.approval_record["authority"] == "DEBATE_ENGINE"

    # Verify ApprovalRecord in .agents/approvals.json passes HMAC signature audit
    verified_approvals = ArtifactGovernor._load_verified_approval_records(tmp_workspace)
    assert "ADR-001" in verified_approvals
    assert verified_approvals["ADR-001"].authority == ApprovalAuthority.DEBATE_ENGINE
    assert verified_approvals["ADR-001"].is_valid(sec_key) is True


def test_end_to_end_debate_fsm_unblocking(tmp_path):
    """Integration Test: Debate engine execution unblocks ArtifactGovernor for downstream FSM transitions."""
    tmp_workspace = str(tmp_path)
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
    runtime.initialize_state(tmp_workspace, goal="Build grounded microservice")

    r_graph = RequirementGraph()
    b_graph = BehaviorGraph()
    mod = HLDModule(id="mod_1", name="Core Context", system_boundary="internal", owned_entities=["Item"], owned_capabilities=["act"])
    adr_1 = ADRRecord("ADR-001", "Architectural Topology Selection", "Modular Monolith with Bounded Contexts", [], ["Evidence"], ["mod_1"], [], "Plausible choice", "PROPOSED", 0.50, EpistemicStatus.PROPOSED)
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
