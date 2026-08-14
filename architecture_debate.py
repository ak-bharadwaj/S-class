"""
S-Class EOS V9.0 - Debate & Decision Intelligence Engine

Transforms DEBATE into a claim-level architectural decision engine:
EngineeringClaim -> Evidence Collection -> Multi-Perspective Challenge -> Architectural Alternatives -> Trade-Off & Blast-Radius Analysis -> DecisionRecord -> HMAC ApprovalRecord (DEBATE_ENGINE)
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple

from behavior_graph import BehaviorGraph, BehaviorNodeType, BehaviorRelationType, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind, NFRCategory
from hld_compiler import HLDDesign, HLDModule, ADRRecord, ValidationStatus, ApprovalStatus
from artifact_governor import ArtifactGovernor, ApprovalRecord, ApprovalAuthority, DecisionRiskClass


class ChallengeCategory(str, Enum):
    """Category of architectural debate challenges."""
    SCALE_THROUGHPUT_INVARIANT = "scale_throughput_invariant"
    TOPOLOGY_SCALE = "scale_throughput_invariant"
    AUTH_SECURITY = "auth_security"
    DATA_CONSISTENCY = "data_consistency"
    FAULT_TOLERANCE = "fault_tolerance"
    MODULAR_BOUNDARIES = "modular_boundaries"


class DebatePerspective(str, Enum):
    """Perspective of debate challenger."""
    ARCHITECT_FEASIBILITY = "ARCHITECT_FEASIBILITY"
    SKEPTIC_GROUNDING = "SKEPTIC_GROUNDING"
    SECURITY_AUDIT = "SECURITY_AUDIT"
    NFR_PERFORMANCE = "NFR_PERFORMANCE"


class DecisionOutcome(str, Enum):
    """Outcome of a debate decision."""
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REVISE = "REVISE"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


@dataclass
class EngineeringClaim:
    """A specific architectural claim extracted from an ADR decision for debate evaluation."""
    claim_id: str
    target_adr_id: str
    statement: str
    category: ChallengeCategory
    supporting_evidence: List[str]
    assumptions: List[str]
    initial_confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "target_adr_id": self.target_adr_id,
            "statement": self.statement,
            "category": self.category.value,
            "supporting_evidence": self.supporting_evidence,
            "assumptions": self.assumptions,
            "initial_confidence": self.initial_confidence
        }


@dataclass
class ArchitecturalAlternative:
    """An alternative architectural design choice evaluated during debate trade-off analysis."""
    option_id: str
    name: str
    description: str
    pros: List[str]
    cons: List[str]
    complexity_score: float  # 0.0 (low) to 1.0 (high)
    blast_radius_score: float  # 0.0 (localized) to 1.0 (systemic)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "name": self.name,
            "description": self.description,
            "pros": self.pros,
            "cons": self.cons,
            "complexity_score": self.complexity_score,
            "blast_radius_score": self.blast_radius_score
        }


@dataclass
class ClaimChallenge:
    """A challenge raised against an architectural claim by an independent perspective."""
    challenge_id: str
    category: ChallengeCategory
    perspective: DebatePerspective
    severity: str  # HIGH, MEDIUM, LOW
    argument: str
    missing_evidence: List[str]
    risk_assessment: Dict[str, Any]
    counter_proposal: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "perspective": self.perspective.value if hasattr(self.perspective, "value") else str(self.perspective),
            "severity": self.severity,
            "argument": self.argument,
            "missing_evidence": self.missing_evidence,
            "risk_assessment": self.risk_assessment,
            "counter_proposal": self.counter_proposal
        }


@dataclass
class DecisionRecord:
    """Authoritative decision record capturing the debate trade-offs, blast radius, chosen option, and signed ApprovalRecord."""
    decision_id: str
    claim_id: str
    adr_id: str
    chosen_option: str
    decision_outcome: DecisionOutcome
    confidence_score: float
    trade_off_analysis: List[Dict[str, Any]]
    blast_radius_analysis: Dict[str, Any]
    affected_artifacts: List[str]
    approval_record: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "claim_id": self.claim_id,
            "adr_id": self.adr_id,
            "chosen_option": self.chosen_option,
            "decision_outcome": self.decision_outcome.value,
            "confidence_score": self.confidence_score,
            "trade_off_analysis": self.trade_off_analysis,
            "blast_radius_analysis": self.blast_radius_analysis,
            "affected_artifacts": self.affected_artifacts,
            "approval_record": self.approval_record
        }


@dataclass
class DebateResult:
    """The formal outcome of an architectural debate audit."""
    accepted_adrs: List[ADRRecord]
    rejected_adrs: List[ADRRecord]
    required_revisions: List[str]
    epistemic_ledger: List[Dict[str, Any]]
    decision_records: List[DecisionRecord]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted_adrs": [a.to_dict() for a in self.accepted_adrs],
            "rejected_adrs": [a.to_dict() for a in self.rejected_adrs],
            "required_revisions": self.required_revisions,
            "epistemic_ledger": self.epistemic_ledger,
            "decision_records": [d.to_dict() for d in self.decision_records]
        }


class ArchitectureDebateEngine:
    """Claims-based Architecture Debate & Decision Intelligence Engine."""

    @classmethod
    def extract_claims(
        cls,
        hld: HLDDesign,
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph
    ) -> List[EngineeringClaim]:
        claims: List[EngineeringClaim] = []

        for idx, adr in enumerate(hld.adrs):
            cat = ChallengeCategory.TOPOLOGY_SCALE if "Topology" in adr.title else (
                ChallengeCategory.AUTH_SECURITY if "Auth" in adr.title or "Security" in adr.title else ChallengeCategory.MODULAR_BOUNDARIES
            )
            claims.append(EngineeringClaim(
                claim_id=f"CLAIM-{adr.id}",
                target_adr_id=adr.id,
                statement=adr.decision,
                category=cat,
                supporting_evidence=adr.evidence or [],
                assumptions=["Default architecture choice assumptions"],
                initial_confidence=adr.confidence
            ))

        return claims

    @classmethod
    def compute_blast_radius(
        cls,
        adr: ADRRecord,
        hld: HLDDesign,
        r_graph: RequirementGraph
    ) -> Dict[str, Any]:
        affected_modules = len(adr.affected_modules) or 1
        total_modules = len(hld.modules) or 1
        module_ratio = affected_modules / max(1, total_modules)

        is_high_risk_topic = any(kw in (adr.title + " " + adr.id).lower() for kw in ["topology", "security", "auth", "database", "migration"])

        security_impact = 0.9 if "security" in adr.title.lower() or "auth" in adr.title.lower() else 0.4
        data_irreversibility = 0.85 if "database" in adr.title.lower() or "topology" in adr.title.lower() else 0.3

        blast_radius_score = min(1.0, round(module_ratio * 0.4 + security_impact * 0.3 + data_irreversibility * 0.3, 2))

        return {
            "adr_id": adr.id,
            "affected_modules": adr.affected_modules,
            "module_ratio": round(module_ratio, 2),
            "security_impact": security_impact,
            "data_irreversibility": data_irreversibility,
            "blast_radius_score": blast_radius_score,
            "risk_class": "HIGH_RISK" if (is_high_risk_topic or blast_radius_score >= 0.6) else "LOW_RISK"
        }

    @classmethod
    def run_debate_cycle(
        cls,
        hld: HLDDesign,
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph,
        raw_request: str = "",
        workspace_dir: Optional[str] = None
    ) -> DebateResult:
        """
        Executes full V9 Debate & Decision Intelligence Cycle:
        1. Extract EngineeringClaims
        2. Evidence Collection & Requirement Grounding
        3. Multi-Perspective Architect & Skeptic Challenges
        4. Alternatives & Blast-Radius Trade-Off Analysis
        5. Resolution -> DecisionRecord -> HMAC signed ApprovalRecord (authority = DEBATE_ENGINE)
        """
        cwd = workspace_dir if workspace_dir else os.getcwd()
        ts_now = datetime.now(timezone.utc).isoformat() + "Z"
        sec_key = ArtifactGovernor._get_governance_secret(workspace_dir)

        accepted_adrs: List[ADRRecord] = []
        rejected_adrs: List[ADRRecord] = []
        required_revisions: List[str] = []
        epistemic_ledger: List[Dict[str, Any]] = []
        decision_records: List[DecisionRecord] = []

        reqs = list(r_graph.nodes.values())
        raw_clean = raw_request.lower()

        has_high_throughput_nfr = any(
            r.nfr_category == NFRCategory.PERFORMANCE and
            any(k in r.statement.lower() for k in ["50k", "10k", "50,000", "10,000", "high-throughput", "events/sec", "scale"])
            for r in reqs
        ) or any(k in raw_clean for k in ["50k", "10k", "50,000", "10,000", "high-throughput", "events/sec", "per second"])

        has_microservices_kw = any(k in raw_clean for k in ["microservice", "kafka", "distributed", "event-driven"])

        claims = cls.extract_claims(hld, r_graph, b_graph)

        # Existing verified approval records
        existing_approvals = ArtifactGovernor._load_verified_approval_records(workspace_dir)
        new_approval_records: List[ApprovalRecord] = list(existing_approvals.values())

        for adr in hld.adrs:
            claim = next((c for c in claims if c.target_adr_id == adr.id), None)
            challenges: List[ClaimChallenge] = []
            alternatives: List[ArchitecturalAlternative] = []

            blast_analysis = cls.compute_blast_radius(adr, hld, r_graph)

            # 1. Topology Debate (ADR-001)
            if adr.id == "ADR-001":
                is_monolith_decision = "Monolith" in adr.decision
                is_microservice_decision = "Microservices" in adr.decision or "Distributed" in adr.decision

                # Architect Feasibility & Skeptic Grounding Challenges
                if is_monolith_decision and has_high_throughput_nfr:
                    challenges.append(ClaimChallenge(
                        challenge_id="CHALLENGE-TOPOLOGY-01",
                        category=ChallengeCategory.TOPOLOGY_SCALE,
                        perspective=DebatePerspective.NFR_PERFORMANCE,
                        severity="HIGH",
                        argument=f"ADR-001 proposes '{adr.decision}', but Performance NFR demands high-throughput ingestion (>10k events/sec).",
                        missing_evidence=["No scale benchmarking or horizontal partitioning evidence for Monolith."],
                        risk_assessment={"scale_bottleneck": True},
                        counter_proposal="Distributed Microservices & Event-Driven Architecture with Kafka/Queue ingestion"
                    ))
                    alternatives.append(ArchitecturalAlternative(
                        option_id="ALT-TOPOLOGY-01",
                        name="Distributed Microservices with Kafka",
                        description="Event-driven streaming microservices for horizontal scaling.",
                        pros=["Independent scaling", "High throughput ingestion"],
                        cons=["High operational complexity", "Distributed transactions"],
                        complexity_score=0.85,
                        blast_radius_score=0.40
                    ))

                if is_microservice_decision and not has_high_throughput_nfr and not has_microservices_kw:
                    challenges.append(ClaimChallenge(
                        challenge_id="CHALLENGE-TOPOLOGY-02",
                        category=ChallengeCategory.TOPOLOGY_SCALE,
                        perspective=DebatePerspective.SKEPTIC_GROUNDING,
                        severity="HIGH",
                        argument=f"ADR-001 proposes '{adr.decision}', but source prompt and requirements lack scale or distributed evidence.",
                        missing_evidence=["No scale NFR or container deployment evidence."],
                        risk_assessment={"unnecessary_complexity": True},
                        counter_proposal="Modular Monolith with Bounded Contexts"
                    ))
                    alternatives.append(ArchitecturalAlternative(
                        option_id="ALT-TOPOLOGY-02",
                        name="Modular Monolith with Bounded Contexts",
                        description="Single deployable artifact with internal module boundaries.",
                        pros=["Simple operation", "Strong transactional consistency"],
                        cons=["Shared process space"],
                        complexity_score=0.25,
                        blast_radius_score=0.60
                    ))

            # 2. Security Debate (ADR-002)
            if adr.id == "ADR-002":
                has_auth_edges = any(e.relation == BehaviorRelationType.AUTHORIZED_FOR for e in b_graph.edges)
                has_actors = any(getattr(n, "behavior_type", None) == BehaviorNodeType.COMMAND for n in b_graph.nodes.values()) or len(b_graph.nodes) > 0 or len(r_graph.nodes) > 0
                if not has_auth_edges and not has_actors and "authorized" not in raw_clean and "permitted" not in raw_clean:
                    challenges.append(ClaimChallenge(
                        challenge_id="CHALLENGE-AUTH-01",
                        category=ChallengeCategory.AUTH_SECURITY,
                        perspective=DebatePerspective.SECURITY_AUDIT,
                        severity="MEDIUM",
                        argument="ADR-002 claims explicit RBAC authorization, but behavior graph contains no AUTHORIZED_FOR edges or domain actors.",
                        missing_evidence=["Explicit role authorization policy rules"],
                        risk_assessment={"unconfirmed_role_boundaries": True},
                        counter_proposal="Mark authorization guard status as PROPOSED pending clarification"
                    ))

            # 3. Initial Candidate ADR Grounding Check
            if (adr.status == "PROPOSED" or adr.epistemic_status == EpistemicStatus.PROPOSED) and adr.id not in existing_approvals:
                challenges.append(ClaimChallenge(
                    challenge_id=f"CHALLENGE-PROPOSED-{adr.id}",
                    category=ChallengeCategory.MODULAR_BOUNDARIES,
                    perspective=DebatePerspective.SKEPTIC_GROUNDING,
                    severity="MEDIUM",
                    argument=f"ADR {adr.id} ('{adr.title}') is PROPOSED with initial confidence {adr.confidence} and requires FSM DEBATE resolution.",
                    missing_evidence=["Formal debate resolution in DEBATE state"],
                    risk_assessment={"unconfirmed_candidate_adr": True},
                    counter_proposal=f"Execute FSM DEBATE state to resolve {adr.id}"
                ))

            # Resolution & Decision Synthesis
            high_sev_challenges = [c for c in challenges if c.severity == "HIGH"]
            med_sev_challenges = [c for c in challenges if c.severity == "MEDIUM"]

            if high_sev_challenges:
                adr.status = "REJECTED"
                adr.confidence = 0.20
                adr.epistemic_status = EpistemicStatus.REJECTED
                adr.approval_status = ApprovalStatus.REJECTED
                rejected_adrs.append(adr)

                for c in high_sev_challenges:
                    counter_prop = alternatives[0].name if alternatives else "Modular Monolith with Bounded Contexts"
                    required_revisions.append(f"REVISE {adr.id} [{c.category.value} / {c.perspective.value}]: {c.argument} Counter-proposal: {counter_prop}")
                    epistemic_ledger.append({
                        "adr_id": adr.id,
                        "claim": adr.decision,
                        "outcome": "REJECTED",
                        "challenge": c.to_dict()
                    })

                d_rec = DecisionRecord(
                    decision_id=f"DECISION-{adr.id}",
                    claim_id=claim.claim_id if claim else f"CLAIM-{adr.id}",
                    adr_id=adr.id,
                    chosen_option=adr.decision,
                    decision_outcome=DecisionOutcome.REJECT,
                    confidence_score=0.20,
                    trade_off_analysis=[a.to_dict() for a in alternatives],
                    blast_radius_analysis=blast_analysis,
                    affected_artifacts=[hld.system_name or "HLD-001"]
                )
                decision_records.append(d_rec)

            elif med_sev_challenges:
                adr.status = "PROPOSED"
                adr.confidence = 0.50
                adr.epistemic_status = EpistemicStatus.PROPOSED
                adr.approval_status = ApprovalStatus.PENDING
                accepted_adrs.append(adr)

                for c in med_sev_challenges:
                    required_revisions.append(f"REVISE {adr.id} [{c.category.value} / {c.perspective.value}]: {c.argument}")
                    epistemic_ledger.append({
                        "adr_id": adr.id,
                        "claim": adr.decision,
                        "outcome": "PROPOSED",
                        "challenge": c.to_dict()
                    })

                d_rec = DecisionRecord(
                    decision_id=f"DECISION-{adr.id}",
                    claim_id=claim.claim_id if claim else f"CLAIM-{adr.id}",
                    adr_id=adr.id,
                    chosen_option=adr.decision,
                    decision_outcome=DecisionOutcome.REVISE,
                    confidence_score=0.50,
                    trade_off_analysis=[a.to_dict() for a in alternatives],
                    blast_radius_analysis=blast_analysis,
                    affected_artifacts=[hld.system_name or "HLD-001"]
                )
                decision_records.append(d_rec)

            else:
                # Decision ACCEPTED with DEBATE_ENGINE HMAC Signing!
                adr.status = "ACCEPTED"
                adr.confidence = 0.95
                adr.epistemic_status = EpistemicStatus.CONFIRMED
                adr.validation_status = ValidationStatus.VALID
                adr.approval_status = ApprovalStatus.APPROVED
                accepted_adrs.append(adr)

                # Compute canonical full-ADR content hash
                canonical_hash = ArtifactGovernor.compute_canonical_adr_hash(adr)
                art_id = hld.system_name or "HLD-001"
                art_ver = getattr(hld, "version", 1)

                # Generate HMAC content-bound ApprovalRecord with DEBATE_ENGINE authority!
                app_rec = ApprovalRecord(
                    decision_id=adr.id,
                    artifact_id=art_id,
                    artifact_version=art_ver,
                    content_hash=canonical_hash,
                    decision="ACCEPTED",
                    authority=ApprovalAuthority.DEBATE_ENGINE,
                    reason=f"Debate resolved with confidence {adr.confidence} after multi-perspective audit.",
                    timestamp=ts_now,
                    evidence=[f"Debate Engine verification: 0 challenges remaining."]
                )
                app_rec.signature = app_rec.compute_signature(sec_key)
                new_approval_records.append(app_rec)

                epistemic_ledger.append({
                    "adr_id": adr.id,
                    "claim": adr.decision,
                    "outcome": "ACCEPTED",
                    "challenges_count": 0,
                    "approval_signature": app_rec.signature
                })

                d_rec = DecisionRecord(
                    decision_id=f"DECISION-{adr.id}",
                    claim_id=claim.claim_id if claim else f"CLAIM-{adr.id}",
                    adr_id=adr.id,
                    chosen_option=adr.decision,
                    decision_outcome=DecisionOutcome.ACCEPT,
                    confidence_score=adr.confidence,
                    trade_off_analysis=[a.to_dict() for a in alternatives],
                    blast_radius_analysis=blast_analysis,
                    affected_artifacts=[hld.system_name or "HLD-001"],
                    approval_record=app_rec.to_dict()
                )
                decision_records.append(d_rec)

                # Save individual DecisionRecord artifact to disk
                agents_dir = os.path.join(cwd, ".agents")
                os.makedirs(agents_dir, exist_ok=True)
                dec_file = os.path.join(agents_dir, f"decision_record_{adr.id}.json")
                try:
                    with open(dec_file, "w", encoding="utf-8") as f:
                        json.dump(d_rec.to_dict(), f, indent=2)
                except Exception:
                    pass

        # Write updated verified approval records to .agents/approvals.json!
        agents_dir = os.path.join(cwd, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        app_file = os.path.join(agents_dir, "approvals.json")
        try:
            dict_records = [r.to_dict() for r in new_approval_records]
            with open(app_file, "w", encoding="utf-8") as f:
                json.dump({"approval_records": dict_records, "timestamp": ts_now}, f, indent=2)
        except Exception:
            pass

        return DebateResult(
            accepted_adrs=accepted_adrs,
            rejected_adrs=rejected_adrs,
            required_revisions=required_revisions,
            epistemic_ledger=epistemic_ledger,
            decision_records=decision_records
        )

    @classmethod
    def debate_hld_adrs(
        cls,
        hld: HLDDesign,
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph,
        raw_request: str = ""
    ) -> DebateResult:
        """Backwards-compatible wrapper delegating to run_debate_cycle."""
        return cls.run_debate_cycle(hld, r_graph, b_graph, raw_request=raw_request)
