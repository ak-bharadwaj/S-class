"""
S-Class EOS V8.0 - Architecture Debate Engine & Claim Validation

Transforms DEBATE from generic discussion into a rigorous Architectural Claim & Evidence Ledger Engine:
CLAIM → EVIDENCE → CHALLENGE → ALTERNATIVES → RISK → DECISION → INVARIANT → VALIDATION
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import json

from behavior_graph import BehaviorGraph, BehaviorNodeType, BehaviorRelationType, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind, NFRCategory
from hld_compiler import HLDDesign, HLDModule, ADRRecord


class ChallengeCategory(str, Enum):
    """Category of architectural debate challenges."""
    REQUIREMENT_GROUNDING = "requirement_grounding"
    SCALE_THROUGHPUT_INVARIANT = "scale_throughput_invariant"
    SECURITY_AUTHORIZATION_EVIDENCE = "security_authorization_evidence"
    TRANSACTIONAL_COMPLEXITY_COST = "transactional_complexity_cost"


@dataclass
class DebateChallenge:
    """A specific architectural challenge raised against an ADR decision."""
    id: str
    category: ChallengeCategory
    severity: str  # HIGH, MEDIUM, LOW
    description: str
    evidence_found: List[str]
    counter_proposal: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity,
            "description": self.description,
            "evidence_found": self.evidence_found,
            "counter_proposal": self.counter_proposal
        }


@dataclass
class DebateResult:
    """The formal outcome of an architectural debate audit."""
    accepted_adrs: List[ADRRecord]
    rejected_adrs: List[ADRRecord]
    required_revisions: List[str]
    epistemic_ledger: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accepted_adrs": [a.to_dict() for a in self.accepted_adrs],
            "rejected_adrs": [a.to_dict() for a in self.rejected_adrs],
            "required_revisions": self.required_revisions,
            "epistemic_ledger": self.epistemic_ledger
        }


class ArchitectureDebateEngine:
    """Audits HLD ADRs against requirements, NFRs, scale evidence, and workspace constraints."""

    @classmethod
    def debate_hld_adrs(
        cls,
        hld: HLDDesign,
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph,
        raw_request: str = ""
    ) -> DebateResult:
        accepted_adrs: List[ADRRecord] = []
        rejected_adrs: List[ADRRecord] = []
        required_revisions: List[str] = []
        epistemic_ledger: List[Dict[str, Any]] = []

        reqs = list(r_graph.nodes.values())
        raw_clean = raw_request.lower()

        has_high_throughput_nfr = any(
            r.nfr_category == NFRCategory.PERFORMANCE and
            any(k in r.statement.lower() for k in ["50k", "10k", "50,000", "10,000", "high-throughput", "events/sec", "scale"])
            for r in reqs
        ) or any(k in raw_clean for k in ["50k", "10k", "50,000", "10,000", "high-throughput", "events/sec", "per second"])

        has_microservices_kw = any(k in raw_clean for k in ["microservice", "kafka", "distributed", "event-driven"])

        for adr in hld.adrs:
            challenges: List[DebateChallenge] = []

            # 1. Topology ADR Debate (ADR-001)
            if adr.id == "ADR-001":
                is_monolith_decision = "Monolith" in adr.decision
                is_microservice_decision = "Microservices" in adr.decision or "Distributed" in adr.decision

                # Fault Challenge A: Monolith decision for 50k req/sec high-throughput NFR
                if is_monolith_decision and has_high_throughput_nfr:
                    challenges.append(DebateChallenge(
                        id="CHALLENGE-TOPOLOGY-01",
                        category=ChallengeCategory.SCALE_THROUGHPUT_INVARIANT,
                        severity="HIGH",
                        description=f"ADR-001 proposes '{adr.decision}', but Performance NFR demands high-throughput ingestion (>10k events/sec).",
                        evidence_found=["Performance NFR: high-throughput event processing"],
                        counter_proposal="Distributed Microservices & Event-Driven Architecture with Kafka/Queue ingestion"
                    ))

                # Fault Challenge B: Microservices decision without scale or container evidence
                if is_microservice_decision and not has_high_throughput_nfr and not has_microservices_kw:
                    challenges.append(DebateChallenge(
                        id="CHALLENGE-TOPOLOGY-02",
                        category=ChallengeCategory.REQUIREMENT_GROUNDING,
                        severity="HIGH",
                        description=f"ADR-001 proposes '{adr.decision}', but source prompt and requirements lack scale or distributed evidence.",
                        evidence_found=["No scale NFR or microservice container evidence found"],
                        counter_proposal="Modular Monolith with Bounded Contexts"
                    ))

            # 2. Security ADR Debate (ADR-002)
            if adr.id == "ADR-002":
                has_auth_edges = any(
                    e.relation == BehaviorRelationType.AUTHORIZED_FOR
                    for e in b_graph.edges
                )
                if not has_auth_edges and "authorized" not in raw_clean and "permitted" not in raw_clean:
                    challenges.append(DebateChallenge(
                        id="CHALLENGE-AUTH-01",
                        category=ChallengeCategory.SECURITY_AUTHORIZATION_EVIDENCE,
                        severity="MEDIUM",
                        description="ADR-002 claims explicit RBAC authorization evidence, but behavior graph contains no AUTHORIZED_FOR edges.",
                        evidence_found=["Only PERFORMS prose assertions present in behavior graph"],
                        counter_proposal="Mark authorization guard status as PROPOSED pending clarification"
                    ))

            # Ledger Entry & Decision Resolution
            if any(c.severity == "HIGH" for c in challenges):
                adr.status = "REJECTED"
                adr.confidence = 0.20
                rejected_adrs.append(adr)

                for c in challenges:
                    required_revisions.append(f"REVISE {adr.id} [{c.category.value}]: {c.description} Counter-proposal: {c.counter_proposal}")
                    epistemic_ledger.append({
                        "adr_id": adr.id,
                        "claim": adr.decision,
                        "outcome": "REJECTED",
                        "challenge": c.to_dict()
                    })

            elif any(c.severity == "MEDIUM" for c in challenges):
                adr.status = "PROPOSED"
                adr.confidence = 0.50
                accepted_adrs.append(adr)

                for c in challenges:
                    epistemic_ledger.append({
                        "adr_id": adr.id,
                        "claim": adr.decision,
                        "outcome": "PROPOSED",
                        "challenge": c.to_dict()
                    })

            else:
                adr.status = "ACCEPTED"
                adr.confidence = 0.95
                accepted_adrs.append(adr)
                epistemic_ledger.append({
                    "adr_id": adr.id,
                    "claim": adr.decision,
                    "outcome": "ACCEPTED",
                    "challenge": None
                })

        return DebateResult(
            accepted_adrs=accepted_adrs,
            rejected_adrs=rejected_adrs,
            required_revisions=required_revisions,
            epistemic_ledger=epistemic_ledger
        )
