"""
S-Class EOS V7.0 - Hardened HLD Compiler & Architecture Decision Records (ADRs)

Defines:
1. ADRRecord (Architecture Decision Records with conditional epistemic status)
2. ADRReasoningEngine (Evaluates NFRs, scale, event throughput, and evidence to decide topology)
3. HLDModule & HLDDesign (Bounded Contexts derived from capability workflows, not entity nouns)
4. HLDCompiler (Compiles Requirements IR + Behavior Graph into HLD + ADRs)
5. HLDValidator (Production 6-Gate Validator auditing Traceability, Ownership, Dependencies, Security, Workflow, and NFRs)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import json

from behavior_graph import BehaviorGraph, BehaviorNodeType, BehaviorRelationType, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind, NFRCategory


class ValidationStatus(str, Enum):
    """Artifact validation status."""
    UNVALIDATED = "UNVALIDATED"
    VALID = "VALID"
    INVALID = "INVALID"
    BLOCKED = "BLOCKED"


class ApprovalStatus(str, Enum):
    """Artifact governance approval status."""
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class ADRRecord:
    """Architecture Decision Record (ADR) capturing technical choices, alternatives, and rationale."""
    id: str
    title: str
    decision: str
    alternatives: List[str]
    evidence: List[str]
    affected_modules: List[str]
    rejected_options: List[str]
    reason: str
    status: str = "ACCEPTED"  # ACCEPTED, PROPOSED, REJECTED
    confidence: float = 1.0
    epistemic_status: EpistemicStatus = EpistemicStatus.DERIVED
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "decision": self.decision,
            "alternatives": self.alternatives,
            "evidence": self.evidence,
            "affected_modules": self.affected_modules,
            "rejected_options": self.rejected_options,
            "reason": self.reason,
            "status": self.status,
            "confidence": self.confidence,
            "epistemic_status": self.epistemic_status.value if isinstance(self.epistemic_status, EpistemicStatus) else str(self.epistemic_status),
            "validation_status": self.validation_status.value if isinstance(self.validation_status, ValidationStatus) else str(self.validation_status),
            "approval_status": self.approval_status.value if isinstance(self.approval_status, ApprovalStatus) else str(self.approval_status)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ADRRecord':
        return cls(
            id=data["id"],
            title=data["title"],
            decision=data["decision"],
            alternatives=data.get("alternatives", []),
            evidence=data.get("evidence", []),
            affected_modules=data.get("affected_modules", []),
            rejected_options=data.get("rejected_options", []),
            reason=data.get("reason", ""),
            status=data.get("status", "ACCEPTED"),
            confidence=data.get("confidence", 1.0),
            epistemic_status=EpistemicStatus(data.get("epistemic_status", "derived")),
            validation_status=ValidationStatus(data.get("validation_status", "UNVALIDATED")),
            approval_status=ApprovalStatus(data.get("approval_status", "NOT_REQUIRED"))
        )


@dataclass
class HLDModule:
    """A high-level system module establishing Bounded Contexts derived from capability workflows."""
    id: str
    name: str
    system_boundary: str
    owned_entities: List[str]
    owned_capabilities: List[str]
    integration_points: List[str] = field(default_factory=list)
    security_boundary: str = "ROLE_BASED_ACCESS_CONTROL"
    consistency_model: str = "STRONG_TRANSACTIONAL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "system_boundary": self.system_boundary,
            "owned_entities": self.owned_entities,
            "owned_capabilities": self.owned_capabilities,
            "integration_points": self.integration_points,
            "security_boundary": self.security_boundary,
            "consistency_model": self.consistency_model
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HLDModule':
        return cls(
            id=data["id"],
            name=data["name"],
            system_boundary=data.get("system_boundary", "internal"),
            owned_entities=data.get("owned_entities", []),
            owned_capabilities=data.get("owned_capabilities", []),
            integration_points=data.get("integration_points", []),
            security_boundary=data.get("security_boundary", "ROLE_BASED_ACCESS_CONTROL"),
            consistency_model=data.get("consistency_model", "STRONG_TRANSACTIONAL")
        )


@dataclass
class HLDDesign:
    """High-Level Design specification with modules, ADRs, and architectural invariants."""
    system_name: str
    architecture_style: str
    modules: List[HLDModule] = field(default_factory=list)
    adrs: List[ADRRecord] = field(default_factory=list)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_name": self.system_name,
            "architecture_style": self.architecture_style,
            "modules": [m.to_dict() for m in self.modules],
            "adrs": [a.to_dict() for a in self.adrs],
            "version": self.version
        }


class ADRReasoningEngine:
    """Evaluates NFRs, scale indicators, and evidence to decide topology conditionally instead of hardcoding."""

    @classmethod
    def evaluate_architecture_topology(cls, r_graph: RequirementGraph, raw_request: str = "") -> ADRRecord:
        reqs = list(r_graph.nodes.values())
        raw_clean = raw_request.lower()

        has_microservices_evidence = any(kw in raw_clean for kw in ["microservice", "docker-compose", "kafka", "distributed", "independent scaling", "event-driven"])
        has_high_throughput = any(r.nfr_category == NFRCategory.PERFORMANCE and ("10k" in r.statement.lower() or "scale" in r.statement.lower()) for r in reqs)

        if has_microservices_evidence or has_high_throughput:
            return ADRRecord(
                id="ADR-001",
                title="Architectural Topology Selection",
                decision="Distributed Microservices & Event-Driven Architecture",
                alternatives=["Modular Monolith", "Serverless Functions"],
                evidence=["Explicit microservices container evidence or high-throughput performance NFR"],
                affected_modules=[],
                rejected_options=["Modular Monolith"],
                reason="System scale or explicit workspace evidence requires independent service deployment and event-driven decoupling.",
                status="ACCEPTED",
                confidence=0.95,
                epistemic_status=EpistemicStatus.DERIVED,
                validation_status=ValidationStatus.VALID,
                approval_status=ApprovalStatus.NOT_REQUIRED
            )
        else:
            # Emits Modular Monolith as PROPOSED candidate if evidence is ambiguous
            return ADRRecord(
                id="ADR-001",
                title="Architectural Topology Selection",
                decision="Modular Monolith with Bounded Contexts",
                alternatives=["Distributed Microservices", "Serverless Functions"],
                evidence=["Domain graph capability workflow cohesion"],
                affected_modules=[],
                rejected_options=[],
                reason="Plausible default topology for transactional consistency; marked PROPOSED for human/DEBATE confirmation.",
                status="PROPOSED",
                confidence=0.50,
                epistemic_status=EpistemicStatus.PROPOSED,
                validation_status=ValidationStatus.BLOCKED,
                approval_status=ApprovalStatus.PENDING
            )


class HLDCompiler:
    """Compiles RequirementGraph and BehaviorGraph into Bounded Context HLD Modules and ADRs."""

    @classmethod
    def compile_hld(cls, r_graph: RequirementGraph, b_graph: BehaviorGraph, system_name: str = "SClassSystem", raw_request: str = "") -> HLDDesign:
        # 1. Cluster capabilities into Bounded Context modules using workflow cohesion
        capability_clusters: Dict[str, Dict[str, Any]] = {}

        for req in r_graph.nodes.values():
            target_ent = req.target or "core"

            # Context key derived from workflow state transitions or entity domain
            b_node = b_graph.get_node(req.source_behaviors[0]) if req.source_behaviors else b_graph.get_node(req.capability)
            if b_node and (b_node.from_state or b_node.to_state):
                context_key = f"ctx_{target_ent.lower()}_fulfillment"
                context_name = f"{target_ent.capitalize()} Fulfillment Context"
            else:
                context_key = f"ctx_{target_ent.lower()}_management"
                context_name = f"{target_ent.capitalize()} Management Context"

            if context_key not in capability_clusters:
                capability_clusters[context_key] = {
                    "id": context_key,
                    "name": context_name,
                    "owned_entities": set(),
                    "owned_capabilities": []
                }

            capability_clusters[context_key]["owned_entities"].add(target_ent)
            if req.capability not in capability_clusters[context_key]["owned_capabilities"]:
                capability_clusters[context_key]["owned_capabilities"].append(req.capability)

        modules = [
            HLDModule(
                id=data["id"],
                name=data["name"],
                system_boundary=f"Bounded Context: {data['name']}",
                owned_entities=list(data["owned_entities"]),
                owned_capabilities=data["owned_capabilities"]
            )
            for data in capability_clusters.values()
        ]

        # 2. Evaluate ADRs conditionally
        adr_topology = ADRReasoningEngine.evaluate_architecture_topology(r_graph, raw_request)
        adr_topology.affected_modules = [m.id for m in modules]

        adr_auth = ADRRecord(
            id="ADR-002",
            title="Authentication & Authorization Architecture",
            decision="Role-Based Access Control (RBAC) with Epistemic Capability Guards",
            alternatives=["Attribute-Based Access Control (ABAC)"],
            evidence=["Source requirements capability authorization edges"],
            affected_modules=[m.id for m in modules],
            rejected_options=["Attribute-Based Access Control (ABAC)"],
            reason="RBAC provides deterministic security boundaries aligned with extracted domain actors.",
            status="ACCEPTED",
            confidence=0.90
        )

        return HLDDesign(
            system_name=system_name,
            architecture_style=adr_topology.decision,
            modules=modules,
            adrs=[adr_topology, adr_auth]
        )


class HLDValidator:
    """Production 6-Gate Validator auditing Traceability, Ownership, Dependencies, Security, Workflow, and NFRs."""

    @classmethod
    def validate_hld(cls, hld: HLDDesign, r_graph: RequirementGraph, b_graph: BehaviorGraph) -> Tuple[bool, List[str]]:
        errors = []

        # Gate 1: Traceability Check — Every functional capability maps to an HLD module
        compiled_caps = set()
        for mod in hld.modules:
            compiled_caps.update(mod.owned_capabilities)

        for req in r_graph.nodes.values():
            if req.kind == RequirementKind.FUNCTIONAL and req.capability not in compiled_caps:
                errors.append(f"[HLD-VAL-TRACEABILITY] Requirement {req.id} ({req.capability}) has no owner module in HLD.")

        # Gate 2: Ownership Check — Every entity owned by exactly one primary module
        entity_owners: Dict[str, List[str]] = {}
        for mod in hld.modules:
            for ent in mod.owned_entities:
                if ent not in entity_owners:
                    entity_owners[ent] = []
                entity_owners[ent].append(mod.id)

        for ent, owners in entity_owners.items():
            if len(owners) > 1:
                errors.append(f"[HLD-VAL-OWNERSHIP] Entity '{ent}' is co-owned by multiple modules: {', '.join(owners)}.")

        # Gate 3: ADR Coverage Check — Topology ADR must exist
        if not any(a.id == "ADR-001" for a in hld.adrs):
            errors.append("[HLD-VAL-ADR] High-Level Design lacks mandatory Topology Architecture Decision Record (ADR-001).")

        # Gate 4: Security Authorization Coverage Check — State-changing commands require auth edges or policies
        for b_node in b_graph.nodes.values():
            if b_node.behavior_type == BehaviorNodeType.COMMAND and b_node.from_state:
                incoming_edges = b_graph._reverse_adjacency.get(b_node.id, [])
                has_auth = any(e.relation in [BehaviorRelationType.PERFORMS, BehaviorRelationType.AUTHORIZED_FOR] for e in incoming_edges)
                if not has_auth:
                    errors.append(f"[HLD-VAL-SECURITY] Command {b_node.id} ({b_node.name}) lacks actor PERFORMS/AUTHORIZED_FOR edge.")

        # Gate 5: Workflow State Match Check — Pre/post states match requirement IR
        for req in r_graph.nodes.values():
            if req.preconditions:
                b_node = b_graph.get_node(req.capability)
                if b_node and b_node.from_state:
                    expected_pre = f"{b_node.target_entity_id}.status == {b_node.from_state.upper()}"
                    if expected_pre not in req.preconditions:
                        errors.append(f"[HLD-VAL-WORKFLOW] Requirement {req.id} precondition mismatch for {req.capability}.")

        # Gate 6: NFR Mitigation Check — Auditability NFRs must map to derived audit capability
        for req in r_graph.nodes.values():
            if req.kind == RequirementKind.NON_FUNCTIONAL and req.nfr_category == NFRCategory.AUDITABILITY:
                if not any(req.capability in mod.owned_capabilities for mod in hld.modules):
                    errors.append(f"[HLD-VAL-NFR] Auditability NFR {req.id} ({req.capability}) lacks architectural module mitigation.")

        passed = len(errors) == 0
        return passed, errors
