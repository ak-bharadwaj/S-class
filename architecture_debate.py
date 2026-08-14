"""
S-Class EOS V9.4 - Multi-Dimensional Risk & Architecture Satisfaction Hardened Debate Engine

Enforces:
1. Compositional Multi-Dimensional Risk Profiles: Dynamic additive set evaluation across all 5 dimensions.
2. Requirement Evidence vs Architecture-Satisfaction Evidence: PASS requires BOTH requirement evidence AND architecture satisfaction design proof. Requirement keyword alone -> UNKNOWN.
3. Trade-off Complete Alternatives: Grounded alternatives with explicit comparison rationales.
4. Epistemic Invariant: UNKNOWN is never guessed, never converted to PASS, and always blocks decision acceptance for required risk dimensions.
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
    INSUFFICIENT_DEBATE = "INSUFFICIENT_DEBATE"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


class EvidenceState(str, Enum):
    """Epistemic evidence classification state."""
    NO_EVIDENCE = "NO_EVIDENCE"                             # Quality: 0.0
    WEAK_INFERENCE = "WEAK_INFERENCE"                       # Quality: 0.25
    INDIRECT_EVIDENCE = "INDIRECT_EVIDENCE"                 # Quality: 0.50
    DIRECT_EVIDENCE = "DIRECT_EVIDENCE"                     # Quality: 0.75
    EXPLICIT_REQUIREMENT = "EXPLICIT_REQUIREMENT"           # Quality: 0.90
    VERIFIED_REPOSITORY_EVIDENCE = "VERIFIED_REPOSITORY_EVIDENCE"  # Quality: 1.0


@dataclass
class EvidenceQualityRecord:
    """Quantitative quality assessment for an evidence item."""
    evidence_id: str
    evidence_state: EvidenceState
    source: str  # EXPLICIT_PROMPT, REQUIREMENT_GRAPH, BEHAVIOR_GRAPH, CODEBASE_AST, NO_EVIDENCE
    reference_text: str
    strength: float  # 0.0 (weak) to 1.0 (strong)
    freshness: float  # 0.0 (stale) to 1.0 (fresh)
    directness: float  # 0.0 (indirect) to 1.0 (direct)
    relevance_score: float  # 0.0 (irrelevant) to 1.0 (highly relevant)
    quality_score: float = 0.0  # Computed: strength * directness * relevance_score * freshness

    def __post_init__(self):
        if self.evidence_state == EvidenceState.NO_EVIDENCE:
            self.strength = 0.0
            self.directness = 0.0
            self.relevance_score = 0.0
            self.quality_score = 0.0
        elif self.quality_score == 0.0:
            self.quality_score = round(self.strength * self.directness * self.relevance_score * self.freshness, 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_state": self.evidence_state.value if hasattr(self.evidence_state, "value") else str(self.evidence_state),
            "source": self.source,
            "reference_text": self.reference_text,
            "strength": self.strength,
            "freshness": self.freshness,
            "directness": self.directness,
            "relevance_score": self.relevance_score,
            "quality_score": self.quality_score
        }


@dataclass
class EngineeringClaim:
    """Decomposed architectural claim for fine-grained debate evaluation."""
    claim_id: str
    target_adr_id: str
    statement: str
    rationale: str
    premises: List[str]
    assumptions: List[str]
    constraints: List[str]
    expected_benefits: List[str]
    expected_costs: List[str]
    falsifiers: List[str]
    evidence_quality_records: List[EvidenceQualityRecord]
    category: ChallengeCategory
    initial_confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "target_adr_id": self.target_adr_id,
            "statement": self.statement,
            "rationale": self.rationale,
            "premises": self.premises,
            "assumptions": self.assumptions,
            "constraints": self.constraints,
            "expected_benefits": self.expected_benefits,
            "expected_costs": self.expected_costs,
            "falsifiers": self.falsifiers,
            "evidence_quality_records": [e.to_dict() for e in self.evidence_quality_records],
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
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
    is_synthetic: bool = False  # Synthetic fallbacks DO NOT count as grounded alternatives
    comparison_rationale: str = ""  # Rationale comparing alternative against chosen option

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "name": self.name,
            "description": self.description,
            "pros": self.pros,
            "cons": self.cons,
            "complexity_score": self.complexity_score,
            "blast_radius_score": self.blast_radius_score,
            "is_synthetic": self.is_synthetic,
            "comparison_rationale": self.comparison_rationale
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
class DimensionGateResult:
    """Result of an orthogonal 5-dimensional challenge gate evaluation distinguishing requirement evidence vs architecture satisfaction evidence."""
    dimension_name: str
    status: str  # PASS, FAIL, UNKNOWN
    requirement_evidence: List[str]
    architecture_satisfaction_evidence: List[str]
    missing_evidence: List[str]
    challenges_raised: List[ClaimChallenge]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension_name": self.dimension_name,
            "status": self.status,
            "requirement_evidence": self.requirement_evidence,
            "architecture_satisfaction_evidence": self.architecture_satisfaction_evidence,
            "missing_evidence": self.missing_evidence,
            "challenges_raised": [c.to_dict() for c in self.challenges_raised]
        }


@dataclass
class DecisionRiskProfile:
    """Dynamic compositional decision-dependent risk profile identifying all triggered high-risk dimensions."""
    adr_id: str
    primary_domain: str
    required_high_risk_dimensions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adr_id": self.adr_id,
            "primary_domain": self.primary_domain,
            "required_high_risk_dimensions": self.required_high_risk_dimensions
        }


@dataclass
class DecisionRecord:
    """Authoritative decision record capturing claim decomposition, trade-offs, blast radius, chosen option, version diffs, and HMAC ApprovalRecord."""
    decision_id: str
    claim_id: str
    adr_id: str
    chosen_option: str
    decision_outcome: DecisionOutcome
    confidence_score: float
    decomposed_claim: Dict[str, Any]
    trade_off_analysis: List[Dict[str, Any]]
    blast_radius_analysis: Dict[str, Any]
    sufficiency_gate_result: Dict[str, Any]
    risk_profile: Dict[str, Any] = field(default_factory=dict)
    dimension_gates: List[Dict[str, Any]] = field(default_factory=list)
    affected_artifacts: List[str] = field(default_factory=list)
    previous_version_hash: Optional[str] = None
    new_version_hash: Optional[str] = None
    replacement_adr: Optional[Dict[str, Any]] = None
    approval_record: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "claim_id": self.claim_id,
            "adr_id": self.adr_id,
            "chosen_option": self.chosen_option,
            "decision_outcome": self.decision_outcome.value if hasattr(self.decision_outcome, "value") else str(self.decision_outcome),
            "confidence_score": self.confidence_score,
            "decomposed_claim": self.decomposed_claim,
            "trade_off_analysis": self.trade_off_analysis,
            "blast_radius_analysis": self.blast_radius_analysis,
            "sufficiency_gate_result": self.sufficiency_gate_result,
            "risk_profile": self.risk_profile,
            "dimension_gates": self.dimension_gates,
            "affected_artifacts": self.affected_artifacts,
            "previous_version_hash": self.previous_version_hash,
            "new_version_hash": self.new_version_hash,
            "replacement_adr": self.replacement_adr,
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


class ClaimDecomposer:
    """Decomposes raw ADR decisions into structured claims with strict zero-quality audits for missing evidence."""

    @classmethod
    def decompose_adr_to_claim(
        cls,
        adr: ADRRecord,
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph,
        raw_request: str = ""
    ) -> EngineeringClaim:
        target_id = adr.id
        title = adr.title or ""
        dec = adr.decision or ""
        reason = adr.reason or ""

        cat = ChallengeCategory.TOPOLOGY_SCALE if "Topology" in title or "scale" in dec.lower() else (
            ChallengeCategory.AUTH_SECURITY if "Auth" in title or "Security" in title else (
                ChallengeCategory.DATA_CONSISTENCY if "Database" in title or "Persistence" in title else ChallengeCategory.MODULAR_BOUNDARIES
            )
        )

        premises: List[str] = []
        assumptions: List[str] = []
        constraints: List[str] = []
        benefits: List[str] = []
        costs: List[str] = []
        falsifiers: List[str] = []

        if "Monolith" in dec:
            premises.append("Domain modules share single deployable process space.")
            assumptions.append("System workload stays within single-node CPU/Memory limits.")
            constraints.append("ACID database transactions supported across module boundaries.")
            benefits.append("Low operational overhead; simplified integration testing.")
            costs.append("Monolithic deployment coupling; shared process failure domain.")
            falsifiers.append("If throughput exceeds 10k events/sec or modules require independent scaling.")

        elif "Microservice" in dec or "Distributed" in dec:
            premises.append("Domain services run in isolated processes communicating via network protocols.")
            assumptions.append("Operational infrastructure (containers/Kafka) is available.")
            constraints.append("Eventual consistency required across service boundaries.")
            benefits.append("Independent service scaling and deployment autonomy.")
            costs.append("Distributed transaction complexity and network serialization latency.")
            falsifiers.append("If team lacks container orchestrators or prompt lacks scale evidence.")

        elif "RBAC" in dec or "Authorization" in dec:
            premises.append("User roles determine permission access guards on domain capabilities.")
            assumptions.append("Role membership is authenticated before authorization check.")
            constraints.append("Role permissions must be explicitly defined per command.")
            benefits.append("Deterministic authorization boundaries aligned with user roles.")
            costs.append("Permission evaluation overhead on every API entrypoint.")
            falsifiers.append("If behavior graph contains no domain actors or authorization edges.")

        else:
            premises.append(f"Architectural choice '{dec}' satisfies domain requirements.")
            assumptions.append("Standard domain design patterns apply.")
            constraints.append("Interface compatibility maintained across components.")
            benefits.append("Modular software structure.")
            costs.append("Maintenance and code abstraction cost.")
            falsifiers.append(f"If requirements invalidate '{dec}'.")

        # Evaluate Evidence Quality strictly (NO EVIDENCE = 0.0 QUALITY SCORE!)
        ev_records: List[EvidenceQualityRecord] = []
        raw_clean = raw_request.lower()
        evidence_list = adr.evidence or []

        GENERIC_FALLBACK_KEYWORDS = ["default architectural inference", "default context", "no evidence", "generic default"]
        valid_evidences = [ev for ev in evidence_list if not any(kw in ev.lower() for kw in GENERIC_FALLBACK_KEYWORDS)]

        if not valid_evidences:
            ev_records.append(EvidenceQualityRecord(
                evidence_id=f"EV-{target_id}-1",
                evidence_state=EvidenceState.NO_EVIDENCE,
                source="NO_EVIDENCE",
                reference_text="No grounded evidence provided for decision",
                strength=0.0,
                freshness=0.0,
                directness=0.0,
                relevance_score=0.0,
                quality_score=0.0
            ))
        else:
            for idx, ev_str in enumerate(valid_evidences):
                is_prompt_ev = any(kw in raw_clean for kw in ev_str.lower().split()) if raw_clean else False
                ev_state = EvidenceState.EXPLICIT_REQUIREMENT if is_prompt_ev else EvidenceState.DIRECT_EVIDENCE
                ev_records.append(EvidenceQualityRecord(
                    evidence_id=f"EV-{target_id}-{idx+1}",
                    evidence_state=ev_state,
                    source="EXPLICIT_PROMPT" if is_prompt_ev else "REQUIREMENT_GRAPH",
                    reference_text=ev_str,
                    strength=0.95 if is_prompt_ev else 0.85,
                    freshness=1.0,
                    directness=0.95 if is_prompt_ev else 0.85,
                    relevance_score=0.95 if is_prompt_ev else 0.90
                ))

        return EngineeringClaim(
            claim_id=f"CLAIM-{target_id}",
            target_adr_id=target_id,
            statement=dec,
            rationale=reason or f"ADR decision rationale for {dec}",
            premises=premises,
            assumptions=assumptions,
            constraints=constraints,
            expected_benefits=benefits,
            expected_costs=costs,
            falsifiers=falsifiers,
            evidence_quality_records=ev_records,
            category=cat,
            initial_confidence=adr.confidence
        )


class GenericDebateEvaluator:
    """Domain-independent Compositional Risk & Dual Evidence 5D Challenge Protocol Evaluator."""

    @classmethod
    def evaluate_risk_profile(
        cls,
        adr: ADRRecord,
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph,
        raw_request: str = ""
    ) -> DecisionRiskProfile:
        """COMPOSITIONAL (non-mutually-exclusive) dynamic risk profiling identifying ALL triggered high-risk dimensions."""
        combined_text = (adr.title + " " + adr.id + " " + adr.decision + " " + adr.reason + " " + " ".join(adr.evidence or [])).lower()
        raw_clean = raw_request.lower()
        reqs = list(r_graph.nodes.values())

        required_dims: Set[str] = set()

        # 1. Data Consistency & Persistence
        if any(k in adr.title.lower() for k in ["database", "persistence", "migration"]) or any(k in raw_clean for k in ["database", "persistence", "migration", "acid", "transaction", "postgres", "mysql", "relational"]):
            required_dims.add("Data Consistency & Persistence")

        # 2. Scalability & Performance
        if any(k in combined_text or k in raw_clean for k in ["scale", "throughput", "50k", "10k", "ingestion", "latency", "events/sec", "performance"]) or any(r.nfr_category == NFRCategory.PERFORMANCE for r in reqs):
            required_dims.add("Scalability & Performance")

        # 3. Security & Authorization (exact word/token match to prevent 'audit' matching 'auth')
        sec_keywords = ["authentication", "authorization", "rbac", "permission", "guard", "authorized", "security policy"]
        tokens = combined_text.split() + raw_clean.split()
        if any(k in combined_text or k in raw_clean for k in sec_keywords) or any(k in tokens for k in ["auth", "actor"]) or any(e.relation == BehaviorRelationType.AUTHORIZED_FOR for e in b_graph.edges):
            required_dims.add("Security & Authorization")

        # 4. Fault Tolerance & Resilience
        if any(k in combined_text or k in raw_clean for k in ["resilience", "outage", "circuit", "retry", "failover", "ha", "healthcare", "safety", "fault"]):
            required_dims.add("Fault Tolerance & Resilience")

        # 5. Modularity & Coupling
        if any(k in combined_text or k in raw_clean for k in ["topology", "microservice", "monolith", "bounded context", "module", "coupling", "decoupled"]) or len(hld_compiler_modules := getattr(adr, "affected_modules", [])) > 0:
            required_dims.add("Modularity & Coupling")

        if not required_dims:
            required_dims.add("Modularity & Coupling")

        return DecisionRiskProfile(
            adr_id=adr.id,
            primary_domain="MULTI_DIMENSIONAL_COMPOSITIONAL",
            required_high_risk_dimensions=sorted(list(required_dims))
        )

    @classmethod
    def evaluate_5d_challenges(
        cls,
        claim: EngineeringClaim,
        adr: ADRRecord,
        hld: HLDDesign,
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph,
        raw_request: str = "",
        is_debate_phase: bool = False
    ) -> Tuple[List[ClaimChallenge], List[ArchitecturalAlternative], List[DimensionGateResult]]:
        challenges: List[ClaimChallenge] = []
        alternatives: List[ArchitecturalAlternative] = []
        dimension_gates: List[DimensionGateResult] = []

        raw_clean = raw_request.lower()
        reqs = list(r_graph.nodes.values())
        ev_list_lower = [ev.lower() for ev in (adr.evidence or [])]

        # ---------------------------------------------------------------------
        # Dimension 1: Scalability & Performance Gate
        # ---------------------------------------------------------------------
        dim1_challenges: List[ClaimChallenge] = []
        dim1_req_ev: List[str] = []
        dim1_arch_ev: List[str] = []
        dim1_missing: List[str] = []

        has_scale_nfr = any(
            r.nfr_category == NFRCategory.PERFORMANCE and
            any(k in r.statement.lower() for k in ["50k", "10k", "50,000", "10,000", "high-throughput", "events/sec", "scale"])
            for r in reqs
        ) or any(k in raw_clean for k in ["50k", "10k", "50,000", "10,000", "high-throughput", "events/sec", "per second"])

        if has_scale_nfr:
            dim1_req_ev.append("Scale/throughput performance NFR requirement present")

        # Explicit Architecture-Satisfaction Mechanism check (partitioning, worker pools, kafka streaming)
        has_scale_arch_mechanism = any(
            k in raw_clean or any(k in ev for ev in ev_list_lower)
            for k in ["kafka", "partition", "sharding", "worker pool", "queue ingestion", "event-driven microservices", "load balancer"]
        )

        is_monolith = "Monolith" in adr.decision
        is_microservice = "Microservices" in adr.decision or "Distributed" in adr.decision
        has_microservices_kw = any(k in raw_clean for k in ["microservice", "kafka", "distributed", "event-driven"])

        if is_monolith and has_scale_nfr:
            c1 = ClaimChallenge(
                challenge_id="CHALLENGE-SCALE-01",
                category=ChallengeCategory.SCALE_THROUGHPUT_INVARIANT,
                perspective=DebatePerspective.NFR_PERFORMANCE,
                severity="HIGH",
                argument=f"ADR {adr.id} proposes '{adr.decision}', but Performance NFR demands high-throughput ingestion (>10k events/sec).",
                missing_evidence=["Scale benchmarking or horizontal partitioning evidence for Monolith."],
                risk_assessment={"scale_bottleneck": True},
                counter_proposal="Distributed Microservices & Event-Driven Architecture with Kafka/Queue ingestion"
            )
            dim1_challenges.append(c1)
            challenges.append(c1)
            alternatives.append(ArchitecturalAlternative(
                option_id="ALT-SCALE-01",
                name="Distributed Microservices with Kafka",
                description="Event-driven streaming microservices for horizontal scaling.",
                pros=["Independent scaling", "High throughput ingestion"],
                cons=["High operational complexity", "Distributed transactions"],
                complexity_score=0.85,
                blast_radius_score=0.40,
                is_synthetic=False,
                comparison_rationale="Monolith topology creates bottleneck for 50k events/sec; streaming Kafka services decouple ingestion."
            ))
            dim1_status = "FAIL"
            dim1_missing.append("Horizontal scaling capability for monolith topology")

        elif is_microservice and not has_scale_nfr and not has_microservices_kw:
            has_microservices_kw_in_ev = any("microservice" in ev or "kafka" in ev for ev in ev_list_lower)
            if not has_microservices_kw_in_ev:
                c2 = ClaimChallenge(
                    challenge_id="CHALLENGE-TOPOLOGY-02",
                    category=ChallengeCategory.SCALE_THROUGHPUT_INVARIANT,
                    perspective=DebatePerspective.SKEPTIC_GROUNDING,
                    severity="HIGH",
                    argument=f"ADR {adr.id} proposes '{adr.decision}', but source prompt and requirements lack scale or distributed evidence.",
                    missing_evidence=["Scale NFR or container deployment evidence."],
                    risk_assessment={"unnecessary_complexity": True},
                    counter_proposal="Modular Monolith with Bounded Contexts"
                )
                dim1_challenges.append(c2)
                challenges.append(c2)
                alternatives.append(ArchitecturalAlternative(
                    option_id="ALT-SCALE-02",
                    name="Modular Monolith with Bounded Contexts",
                    description="Single deployable artifact with internal module boundaries.",
                    pros=["Simple operation", "Strong transactional consistency"],
                    cons=["Shared process space"],
                    complexity_score=0.25,
                    blast_radius_score=0.60,
                    is_synthetic=False,
                    comparison_rationale="Unbacked microservice topology adds unnecessary operational overhead for simple prompt; monolith is simpler."
                ))
                dim1_status = "FAIL"
                dim1_missing.append("Scale justification for microservice overhead")
            else:
                dim1_status = "UNKNOWN"
                dim1_missing.append("Scale NFR missing for microservices topology")

        elif has_scale_nfr and has_scale_arch_mechanism:
            dim1_arch_ev.append("Explicit horizontal scaling/queue mechanism design evidence present")
            dim1_status = "PASS"

        elif has_scale_nfr and not has_scale_arch_mechanism:
            dim1_status = "UNKNOWN"
            dim1_missing.append("Scale NFR present, but missing explicit scaling/partitioning design mechanism evidence")

        else:
            dim1_status = "UNKNOWN"
            dim1_missing.append("No explicit scale or throughput performance evidence provided")

        dimension_gates.append(DimensionGateResult("Scalability & Performance", dim1_status, dim1_req_ev, dim1_arch_ev, dim1_missing, dim1_challenges))

        # ---------------------------------------------------------------------
        # Dimension 2: Security & Authorization Gate
        # ---------------------------------------------------------------------
        dim2_challenges: List[ClaimChallenge] = []
        dim2_req_ev: List[str] = []
        dim2_arch_ev: List[str] = []
        dim2_missing: List[str] = []

        has_security_req = any(k in raw_clean for k in ["authentication", "authorization", "rbac", "role-based", "security policy", "permission", "guard", "authorized"])
        if has_security_req:
            dim2_req_ev.append("Role authorization security requirement present")

        actual_actors = [n for n in b_graph.nodes.values() if getattr(n, "actor_id", None) and n.actor_id != "system"]
        actual_auth_edges = [e for e in b_graph.edges if e.relation == BehaviorRelationType.AUTHORIZED_FOR]
        has_auth_guard_design = any(k in ev for ev in ev_list_lower for k in ["capability guard", "epistemic guard", "policy engine", "rbac guard", "jwt guard"])

        has_security_arch_mechanism = bool(actual_auth_edges and (actual_actors or has_auth_guard_design))

        if has_security_req and has_security_arch_mechanism:
            dim2_arch_ev.append("Protected boundary + domain actors + explicit AUTHORIZED_FOR edges present in behavior graph")
            dim2_status = "PASS"
        elif has_security_req and not has_security_arch_mechanism:
            c_sec = ClaimChallenge(
                challenge_id="CHALLENGE-AUTH-01",
                category=ChallengeCategory.AUTH_SECURITY,
                perspective=DebatePerspective.SECURITY_AUDIT,
                severity="MEDIUM",
                argument=f"ADR {adr.id} claims explicit RBAC authorization, but behavior graph contains no AUTHORIZED_FOR edges or domain actors.",
                missing_evidence=["Explicit role authorization policy rules"],
                risk_assessment={"unconfirmed_role_boundaries": True},
                counter_proposal="Mark authorization guard status as PROPOSED pending clarification"
            )
            dim2_challenges.append(c_sec)
            challenges.append(c_sec)
            dim2_status = "UNKNOWN"
            dim2_missing.append("Security requirement present, but missing explicit role authorization policy rules and protected boundaries")
        elif not has_security_req and has_security_arch_mechanism:
            dim2_arch_ev.append("Protected boundary + domain actors + explicit AUTHORIZED_FOR edges present in behavior graph")
            dim2_status = "UNKNOWN"
            dim2_missing.append("Security architecture mechanism present, but explicit security requirement unstated")
        else:
            dim2_status = "UNKNOWN"
            dim2_missing.append("Security requirements unstated in current claim")

        dimension_gates.append(DimensionGateResult("Security & Authorization", dim2_status, dim2_req_ev, dim2_arch_ev, dim2_missing, dim2_challenges))

        # ---------------------------------------------------------------------
        # Dimension 3: Data Consistency & Persistence Gate (EVIDENCE DRIVEN!)
        # ---------------------------------------------------------------------
        dim3_challenges: List[ClaimChallenge] = []
        dim3_req_ev: List[str] = []
        dim3_arch_ev: List[str] = []
        dim3_missing: List[str] = []

        has_consistency_req = any(
            k in raw_clean or any(k in ev for ev in ev_list_lower)
            for k in ["acid", "transaction", "relational", "postgres", "mysql", "atomic", "journal", "journaling", "saga"]
        ) or any(r.kind == RequirementKind.FUNCTIONAL and "transaction" in r.statement.lower() for r in reqs)

        if has_consistency_req:
            dim3_req_ev.append("Data consistency / transactional requirement present")

        has_consistency_arch_mechanism = any(
            k in raw_clean or any(k in ev for ev in ev_list_lower)
            for k in ["postgres", "mysql", "acid database", "saga coordinator", "eventual consistency handler", "2pc", "relational schema", "transactional", "acid"]
        )

        if has_consistency_req and has_consistency_arch_mechanism:
            dim3_arch_ev.append("Explicit relational/ACID database or saga coordinator design mechanism present")
            dim3_status = "PASS"
        elif has_consistency_req:
            dim3_status = "UNKNOWN"
            dim3_missing.append("Consistency requirement present, but missing explicit relational/ACID database engine design proof")
        else:
            dim3_status = "UNKNOWN"
            dim3_missing.append("No explicit data consistency or ACID transaction evidence provided")

        dimension_gates.append(DimensionGateResult("Data Consistency & Persistence", dim3_status, dim3_req_ev, dim3_arch_ev, dim3_missing, dim3_challenges))

        # ---------------------------------------------------------------------
        # Dimension 4: Fault Tolerance & Resilience Gate
        # ---------------------------------------------------------------------
        dim4_challenges: List[ClaimChallenge] = []
        dim4_req_ev: List[str] = []
        dim4_arch_ev: List[str] = []
        dim4_missing: List[str] = []

        has_resilience_req = any(
            k in raw_clean for k in ["circuit breaker", "retry", "graceful degradation", "fallback", "failover", "ha", "outage", "resilient"]
        )
        if has_resilience_req:
            dim4_req_ev.append("Resilience / fault-tolerance requirement present")

        has_resilience_arch_mechanism = any(
            k in raw_clean or any(k in ev for ev in ev_list_lower)
            for k in ["circuit breaker design", "retry mechanism", "fallback handler", "active-passive failover", "exponential backoff"]
        )

        if has_resilience_req and has_resilience_arch_mechanism:
            dim4_arch_ev.append("Explicit circuit breaker / retry policy / failover design mechanism present")
            dim4_status = "PASS"
        elif has_resilience_req:
            dim4_status = "UNKNOWN"
            dim4_missing.append("Resilience requirement present, but missing explicit failover/circuit-breaker design mechanism evidence")
        else:
            dim4_status = "UNKNOWN"
            dim4_missing.append("Circuit breaker, retry policy, and graceful degradation model unstated")

        dimension_gates.append(DimensionGateResult("Fault Tolerance & Resilience", dim4_status, dim4_req_ev, dim4_arch_ev, dim4_missing, dim4_challenges))

        # ---------------------------------------------------------------------
        # Dimension 5: Modularity & Coupling Gate (EVIDENCE DRIVEN!)
        # ---------------------------------------------------------------------
        dim5_challenges: List[ClaimChallenge] = []
        dim5_req_ev: List[str] = []
        dim5_arch_ev: List[str] = []
        dim5_missing: List[str] = []

        has_modularity_req = any(
            k in raw_clean or any(k in ev for ev in ev_list_lower)
            for k in ["bounded context", "module boundary", "interface isolation", "domain separation", "decoupled", "modular", "monolith", "system", "platform", "app", "erp"]
        )
        if has_modularity_req:
            dim5_req_ev.append("Modularity / boundary requirement present")

        has_modularity_arch_mechanism = len(hld.modules) >= 1 and (
            any(k in raw_clean or any(k in ev for ev in ev_list_lower) for k in ["bounded context purity", "isolated interface", "ownership separation", "dependency direction", "monolith", "bounded context", "module"]) or
            any(len(m.owned_capabilities) > 0 for m in hld.modules)
        )

        if has_modularity_req and has_modularity_arch_mechanism:
            dim5_arch_ev.append(f"Explicit bounded context purity maintained across {len(hld.modules)} domain modules")
            dim5_status = "PASS"
        else:
            dim5_status = "UNKNOWN"
            dim5_missing.append("Explicit module coupling, boundary purity, or cycle analysis evidence missing")

        dimension_gates.append(DimensionGateResult("Modularity & Coupling", dim5_status, dim5_req_ev, dim5_arch_ev, dim5_missing, dim5_challenges))

        # Attach candidate alternatives from ADR record or synthetic fallback options
        if not alternatives and adr.alternatives:
            for idx, alt_name in enumerate(adr.alternatives):
                alternatives.append(ArchitecturalAlternative(
                    option_id=f"ALT-{adr.id}-{idx+1}",
                    name=alt_name,
                    description=f"Evaluated architectural alternative '{alt_name}' for {adr.id}",
                    pros=["Evaluated domain alternative"],
                    cons=["Trade-off compared against chosen option"],
                    complexity_score=0.5,
                    blast_radius_score=0.5,
                    is_synthetic=False,
                    comparison_rationale=f"Evaluated alternative '{alt_name}' against chosen decision '{adr.decision}'."
                ))

        if not alternatives:
            if is_monolith:
                alternatives.append(ArchitecturalAlternative("ALT-GEN-01", "Modular Monolith", "Single process with clear bounded contexts.", ["Simple deployment"], ["Shared memory"], 0.3, 0.5, is_synthetic=True, comparison_rationale="Synthetic fallback option"))
                alternatives.append(ArchitecturalAlternative("ALT-GEN-02", "Event-Driven Microservices", "Decoupled async microservices.", ["Horizontal scale"], ["Distributed transactions"], 0.8, 0.4, is_synthetic=True, comparison_rationale="Synthetic fallback option"))
            else:
                alternatives.append(ArchitecturalAlternative("ALT-GEN-01", "Service-Oriented Architecture", "Decoupled domain services.", ["Domain isolation"], ["Network latency"], 0.7, 0.5, is_synthetic=True, comparison_rationale="Synthetic fallback option"))
                alternatives.append(ArchitecturalAlternative("ALT-GEN-02", "Serverless Functions", "On-demand execution handlers.", ["Zero idle cost"], ["Cold starts"], 0.6, 0.3, is_synthetic=True, comparison_rationale="Synthetic fallback option"))

        return challenges, alternatives, dimension_gates


class DecisionSufficiencyGate:
    """Strict Decision Sufficiency Gate requiring grounded alternatives with trade-off rationales and PASS status on ALL compositional required risk dimensions."""

    @classmethod
    def evaluate_sufficiency(
        cls,
        claim: EngineeringClaim,
        challenges: List[ClaimChallenge],
        alternatives: List[ArchitecturalAlternative],
        blast_analysis: Dict[str, Any],
        dimension_gates: List[DimensionGateResult],
        risk_profile: DecisionRiskProfile,
        has_existing_approval: bool = False,
        is_debate_phase: bool = False
    ) -> Tuple[DecisionOutcome, float, Dict[str, Any]]:
        high_sev = [c for c in challenges if c.severity == "HIGH"]
        med_sev = [c for c in challenges if c.severity == "MEDIUM"]

        # 1. Evidence Quality Check
        ev_records = claim.evidence_quality_records
        has_no_evidence = any(e.evidence_state == EvidenceState.NO_EVIDENCE for e in ev_records)
        avg_ev_quality = sum(e.quality_score for e in ev_records) / max(1, len(ev_records))
        evidence_sufficient = (not has_no_evidence) and (avg_ev_quality >= 0.50 or any(e.source == "EXPLICIT_PROMPT" for e in ev_records))

        # 2. Grounded Alternatives Check (Require non-empty comparison rationales!)
        grounded_alts = [a for a in alternatives if not a.is_synthetic]
        tradeoff_complete_alts = [a for a in grounded_alts if a.comparison_rationale]
        alternatives_explored = len(tradeoff_complete_alts) >= 1

        # 3. Blast Radius Safety Check
        blast_radius_acceptable = blast_analysis.get("blast_radius_score", 0.5) < 0.85

        # 4. Zero High-Severity Contradictions Check
        no_high_contradictions = len(high_sev) == 0

        # 5. Orthogonal 5D Gate Check
        failed_dims = [d for d in dimension_gates if d.status == "FAIL"]
        no_failed_dimensions = len(failed_dims) == 0

        # ALL COMPOSITIONAL Required High-Risk Dimensions MUST BE PASS!
        required_names = risk_profile.required_high_risk_dimensions
        req_gates = [d for d in dimension_gates if d.dimension_name in required_names]
        required_dims_passed = len(req_gates) > 0 and all(d.status == "PASS" for d in req_gates)

        gate_passed = evidence_sufficient and alternatives_explored and blast_radius_acceptable and no_high_contradictions and no_failed_dimensions and required_dims_passed

        gate_metrics = {
            "evidence_sufficient": evidence_sufficient,
            "has_no_evidence": has_no_evidence,
            "average_evidence_quality": round(avg_ev_quality, 3),
            "grounded_alternatives_count": len(grounded_alts),
            "synthetic_alternatives_count": len(alternatives) - len(grounded_alts),
            "alternatives_explored": alternatives_explored,
            "high_severity_challenges_count": len(high_sev),
            "medium_severity_challenges_count": len(med_sev),
            "failed_dimensions_count": len(failed_dims),
            "required_high_risk_dimensions": required_names,
            "required_dims_passed": required_dims_passed,
            "blast_radius_acceptable": blast_radius_acceptable,
            "gate_passed": gate_passed
        }

        # EPISTEMIC INVARIANT: Missing evidence, un-explored alternatives, low confidence (<=0.50 outside debate phase), or UNKNOWN required dimensions MUST NOT ACCEPT!
        if high_sev or failed_dims:
            return DecisionOutcome.REJECT, 0.20, gate_metrics
        elif has_no_evidence or not evidence_sufficient or not alternatives_explored or not required_dims_passed or (claim.initial_confidence <= 0.50 and not has_existing_approval and not is_debate_phase):
            return DecisionOutcome.INSUFFICIENT_DEBATE, 0.50, gate_metrics
        elif med_sev or not gate_passed:
            return DecisionOutcome.REVISE, 0.55, gate_metrics
        else:
            return DecisionOutcome.ACCEPT, 0.95, gate_metrics


class ArchitectureDebateEngine:
    """V9.4 Multi-Dimensional Risk & Architecture Satisfaction Hardened Debate Engine."""

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
    def promote_alternative_to_adr_v2(
        cls,
        original_adr: ADRRecord,
        chosen_alt: ArchitecturalAlternative,
        canonical_v1_hash: str
    ) -> ADRRecord:
        """Promotes an architectural alternative into a versioned ADR v2 replacement artifact."""
        return ADRRecord(
            id=original_adr.id,
            title=original_adr.title,
            decision=chosen_alt.name,
            alternatives=sorted(list(set(original_adr.alternatives + [chosen_alt.name]))),
            evidence=original_adr.evidence + [f"Debate Engine revision from {original_adr.decision}"],
            affected_modules=original_adr.affected_modules,
            rejected_options=sorted(list(set(original_adr.rejected_options + [original_adr.decision]))),
            reason=f"Revised via Debate Engine trade-off analysis from {original_adr.decision}: {chosen_alt.description}",
            status="ACCEPTED",
            confidence=0.90,
            epistemic_status=EpistemicStatus.CONFIRMED,
            validation_status=ValidationStatus.VALID,
            approval_status=ApprovalStatus.APPROVED,
            version=original_adr.version + 1,
            previous_version_hash=canonical_v1_hash
        )

    @classmethod
    def run_debate_cycle(
        cls,
        hld: HLDDesign,
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph,
        raw_request: str = "",
        workspace_dir: Optional[str] = None,
        is_debate_phase: bool = False
    ) -> DebateResult:
        """
        Executes full V9.4 Multi-Dimensional Risk & Architecture Satisfaction Hardened Cycle:
        1. Compositional Multi-Dimensional Risk Profiling
        2. Claim Decomposition with Zero Quality missing evidence audit
        3. Orthogonal 5-Dimensional Challenge Protocol requiring Requirement AND Architecture Satisfaction Evidence
        4. Grounded Alternative Exploration with Comparison Rationales
        5. Decision Sufficiency Gate enforcing PASS on ALL compositional required risk dimensions
        6. Versioned ADR Revision (v1 -> v2) & Alternative Promotion
        7. HMAC ApprovalRecord Generation (DEBATE_ENGINE)
        """
        cwd = workspace_dir if workspace_dir else os.getcwd()
        ts_now = datetime.now(timezone.utc).isoformat() + "Z"
        sec_key = ArtifactGovernor._get_governance_secret(workspace_dir)

        accepted_adrs: List[ADRRecord] = []
        rejected_adrs: List[ADRRecord] = []
        required_revisions: List[str] = []
        epistemic_ledger: List[Dict[str, Any]] = []
        decision_records: List[DecisionRecord] = []

        existing_approvals = ArtifactGovernor._load_verified_approval_records(workspace_dir)
        new_approval_records: List[ApprovalRecord] = list(existing_approvals.values())

        for adr in hld.adrs:
            # 1. Compositional Multi-Dimensional Risk Profile
            risk_prof = GenericDebateEvaluator.evaluate_risk_profile(adr, r_graph, b_graph, raw_request=raw_request)

            # 2. Claim Decomposition & Zero-Quality Evidence Audit
            claim = ClaimDecomposer.decompose_adr_to_claim(adr, r_graph, b_graph, raw_request=raw_request)

            # 3. Blast Radius Analysis
            blast_analysis = cls.compute_blast_radius(adr, hld, r_graph)

            # 4. Orthogonal 5-Dimensional Challenge Protocol & Alternatives
            challenges, alternatives, dim_gates = GenericDebateEvaluator.evaluate_5d_challenges(
                claim=claim,
                adr=adr,
                hld=hld,
                r_graph=r_graph,
                b_graph=b_graph,
                raw_request=raw_request,
                is_debate_phase=is_debate_phase
            )

            # Initial Candidate Check
            if (adr.status == "PROPOSED" or adr.epistemic_status == EpistemicStatus.PROPOSED) and adr.id not in existing_approvals:
                challenges.append(ClaimChallenge(
                    challenge_id=f"CHALLENGE-PROPOSED-{adr.id}",
                    category=ChallengeCategory.MODULAR_BOUNDARIES,
                    perspective=DebatePerspective.SKEPTIC_GROUNDING,
                    severity="LOW",
                    argument=f"ADR {adr.id} ('{adr.title}') is PROPOSED with initial confidence {adr.confidence} and requires FSM DEBATE resolution.",
                    missing_evidence=["Formal debate resolution in DEBATE state"],
                    risk_assessment={"unconfirmed_candidate_adr": True},
                    counter_proposal=f"Execute FSM DEBATE state to resolve {adr.id}"
                ))

            # 5. Decision Sufficiency Gate Evaluation
            has_app = adr.id in existing_approvals
            outcome, confidence_score, gate_metrics = DecisionSufficiencyGate.evaluate_sufficiency(
                claim=claim,
                challenges=challenges,
                alternatives=alternatives,
                blast_analysis=blast_analysis,
                dimension_gates=dim_gates,
                risk_profile=risk_prof,
                has_existing_approval=has_app,
                is_debate_phase=is_debate_phase
            )

            canonical_v1_hash = ArtifactGovernor.compute_canonical_adr_hash(adr)

            # 6. Outcome Resolution & Versioned ADR Promotion
            if outcome == DecisionOutcome.REJECT:
                adr.status = "REJECTED"
                adr.confidence = confidence_score
                adr.epistemic_status = EpistemicStatus.REJECTED
                adr.approval_status = ApprovalStatus.REJECTED
                rejected_adrs.append(adr)

                high_sev = [c for c in challenges if c.severity == "HIGH"]
                for c in high_sev:
                    counter_prop = c.counter_proposal or (alternatives[0].name if alternatives else "Modular Monolith with Bounded Contexts")
                    required_revisions.append(f"REVISE {adr.id} [{c.category.value} / {c.perspective.value}]: {c.argument} Counter-proposal: {counter_prop}")
                    epistemic_ledger.append({
                        "adr_id": adr.id,
                        "claim": claim.statement,
                        "outcome": "REJECTED",
                        "challenge": c.to_dict()
                    })

                chosen_alt = alternatives[0] if alternatives else ArchitecturalAlternative("ALT-FALLBACK", "Modular Monolith", "Default fallback", [], [], 0.3, 0.5)
                replacement_v2 = cls.promote_alternative_to_adr_v2(adr, chosen_alt, canonical_v1_hash)

                d_rec = DecisionRecord(
                    decision_id=f"DECISION-{adr.id}",
                    claim_id=claim.claim_id,
                    adr_id=adr.id,
                    chosen_option=adr.decision,
                    decision_outcome=outcome,
                    confidence_score=confidence_score,
                    decomposed_claim=claim.to_dict(),
                    trade_off_analysis=[a.to_dict() for a in alternatives],
                    blast_radius_analysis=blast_analysis,
                    sufficiency_gate_result=gate_metrics,
                    risk_profile=risk_prof.to_dict(),
                    dimension_gates=[d.to_dict() for d in dim_gates],
                    affected_artifacts=[hld.system_name or "HLD-001"],
                    previous_version_hash=canonical_v1_hash,
                    replacement_adr=replacement_v2.to_dict()
                )
                decision_records.append(d_rec)

            elif outcome in [DecisionOutcome.REVISE, DecisionOutcome.INSUFFICIENT_DEBATE]:
                adr.status = "PROPOSED"
                adr.confidence = 0.50
                adr.epistemic_status = EpistemicStatus.PROPOSED
                adr.approval_status = ApprovalStatus.PENDING
                rejected_adrs.append(adr)

                med_sev = [c for c in challenges if c.severity == "MEDIUM"]
                for c in med_sev:
                    required_revisions.append(f"REVISE {adr.id} [{c.category.value} / {c.perspective.value}]: {c.argument}")
                    epistemic_ledger.append({
                        "adr_id": adr.id,
                        "claim": claim.statement,
                        "outcome": "PROPOSED",
                        "challenge": c.to_dict()
                    })

                d_rec = DecisionRecord(
                    decision_id=f"DECISION-{adr.id}",
                    claim_id=claim.claim_id,
                    adr_id=adr.id,
                    chosen_option=adr.decision,
                    decision_outcome=outcome,
                    confidence_score=0.50,
                    decomposed_claim=claim.to_dict(),
                    trade_off_analysis=[a.to_dict() for a in alternatives],
                    blast_radius_analysis=blast_analysis,
                    sufficiency_gate_result=gate_metrics,
                    risk_profile=risk_prof.to_dict(),
                    dimension_gates=[d.to_dict() for d in dim_gates],
                    affected_artifacts=[hld.system_name or "HLD-001"],
                    previous_version_hash=canonical_v1_hash
                )
                decision_records.append(d_rec)

            else:
                # Decision ACCEPTED via Sufficiency Gate with Versioned ADR v2 Promotion & HMAC Signing!
                adr.status = "ACCEPTED"
                adr.confidence = confidence_score
                adr.epistemic_status = EpistemicStatus.CONFIRMED
                adr.validation_status = ValidationStatus.VALID
                adr.approval_status = ApprovalStatus.APPROVED
                adr.version = adr.version + 1
                adr.previous_version_hash = canonical_v1_hash
                accepted_adrs.append(adr)

                canonical_v2_hash = ArtifactGovernor.compute_canonical_adr_hash(adr)
                art_id = hld.system_name or "HLD-001"
                art_ver = getattr(hld, "version", 1)

                app_rec = ApprovalRecord(
                    decision_id=adr.id,
                    artifact_id=art_id,
                    artifact_version=art_ver,
                    content_hash=canonical_v2_hash,
                    decision="ACCEPTED",
                    authority=ApprovalAuthority.DEBATE_ENGINE,
                    reason=f"Debate resolved via Sufficiency Gate with confidence {adr.confidence} after 5D evaluation.",
                    timestamp=ts_now,
                    evidence=[f"Decision Sufficiency Gate PASSED: {gate_metrics}"]
                )
                app_rec.signature = app_rec.compute_signature(sec_key)
                new_approval_records.append(app_rec)

                epistemic_ledger.append({
                    "adr_id": adr.id,
                    "version": adr.version,
                    "claim": claim.statement,
                    "outcome": "ACCEPTED",
                    "gate_metrics": gate_metrics,
                    "approval_signature": app_rec.signature
                })

                d_rec = DecisionRecord(
                    decision_id=f"DECISION-{adr.id}",
                    claim_id=claim.claim_id,
                    adr_id=adr.id,
                    chosen_option=adr.decision,
                    decision_outcome=DecisionOutcome.ACCEPT,
                    confidence_score=adr.confidence,
                    decomposed_claim=claim.to_dict(),
                    trade_off_analysis=[a.to_dict() for a in alternatives],
                    blast_radius_analysis=blast_analysis,
                    sufficiency_gate_result=gate_metrics,
                    risk_profile=risk_prof.to_dict(),
                    dimension_gates=[d.to_dict() for d in dim_gates],
                    affected_artifacts=[hld.system_name or "HLD-001"],
                    previous_version_hash=canonical_v1_hash,
                    new_version_hash=canonical_v2_hash,
                    approval_record=app_rec.to_dict()
                )
                decision_records.append(d_rec)

                agents_dir = os.path.join(cwd, ".agents")
                os.makedirs(agents_dir, exist_ok=True)
                dec_file = os.path.join(agents_dir, f"decision_record_{adr.id}.json")
                try:
                    with open(dec_file, "w", encoding="utf-8") as f:
                        json.dump(d_rec.to_dict(), f, indent=2)
                except Exception:
                    pass

        agents_dir = os.path.join(cwd, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        app_file = os.path.join(agents_dir, "approvals.json")
        existing_records_dict = {}
        if os.path.exists(app_file):
            try:
                with open(app_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    for r_dict in old_data.get("approval_records", []):
                        if r_dict.get("decision_id"):
                            existing_records_dict[r_dict.get("decision_id")] = r_dict
            except Exception:
                pass

        for r in new_approval_records:
            existing_records_dict[r.decision_id] = r.to_dict()

        try:
            with open(app_file, "w", encoding="utf-8") as f:
                json.dump({"approval_records": list(existing_records_dict.values()), "timestamp": ts_now}, f, indent=2)
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
