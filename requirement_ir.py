"""
S-Class EOS V7.0 - Machine-Verifiable Requirement IR & Dependency Graph

Defines:
1. RequirementKind (FUNCTIONAL vs NON_FUNCTIONAL)
2. NFRCategory (SECURITY, AUDITABILITY, PERFORMANCE, AVAILABILITY, RELIABILITY, DATA_INTEGRITY)
3. RequirementNode dataclass (machine-verifiable schema with preconditions, postconditions, evidence, dependencies)
4. RequirementGraph with automated DEPENDENCY_HOLE detection
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import json
import uuid

from behavior_graph import (
    BehaviorGraph,
    BehaviorNode,
    BehaviorNodeType,
    BehaviorRelationType,
    EpistemicStatus
)
from domain_primitives import ProvenanceKind


class RequirementKind(str, Enum):
    """Classification of requirements."""
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"


class NFRCategory(str, Enum):
    """Category of non-functional requirements."""
    SECURITY = "security"
    AUDITABILITY = "auditability"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    RELIABILITY = "reliability"
    DATA_INTEGRITY = "data_integrity"


@dataclass
class RequirementNode:
    """A machine-verifiable software requirement with full evidence lineage."""
    id: str
    kind: RequirementKind
    statement: str
    actor: str
    capability: str
    target: str
    nfr_category: Optional[NFRCategory] = None
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    priority: str = "HIGH"
    risk: str = "LOW"
    epistemic_status: EpistemicStatus = EpistemicStatus.DERIVED
    provenance: ProvenanceKind = ProvenanceKind.STRONGLY_DERIVED
    confidence: float = 1.0
    evidence: Optional[str] = None
    source_behaviors: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "statement": self.statement,
            "actor": self.actor,
            "capability": self.capability,
            "target": self.target,
            "nfr_category": self.nfr_category.value if self.nfr_category else None,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "constraints": self.constraints,
            "priority": self.priority,
            "risk": self.risk,
            "epistemic_status": self.epistemic_status.value,
            "provenance": self.provenance.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_behaviors": self.source_behaviors,
            "assumptions": self.assumptions,
            "dependencies": self.dependencies
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RequirementNode':
        return cls(
            id=data["id"],
            kind=RequirementKind(data["kind"]),
            statement=data["statement"],
            actor=data.get("actor", "operator"),
            capability=data.get("capability", "manage"),
            target=data.get("target", "system"),
            nfr_category=NFRCategory(data["nfr_category"]) if data.get("nfr_category") else None,
            preconditions=data.get("preconditions", []),
            postconditions=data.get("postconditions", []),
            constraints=data.get("constraints", []),
            priority=data.get("priority", "HIGH"),
            risk=data.get("risk", "LOW"),
            epistemic_status=EpistemicStatus(data.get("epistemic_status", "derived")),
            provenance=ProvenanceKind(data.get("provenance", "strongly_derived")),
            confidence=data.get("confidence", 1.0),
            evidence=data.get("evidence"),
            source_behaviors=data.get("source_behaviors", []),
            assumptions=data.get("assumptions", []),
            dependencies=data.get("dependencies", [])
        )


class DuplicateIDConflictError(ValueError):
    """Raised when adding a requirement with an existing ID but conflicting semantic content."""
    pass


class CircularDependencyError(ValueError):
    """Raised when adding a requirement dependency that creates a cycle."""
    pass


class RequirementGraph:
    """Graph of machine-verifiable requirements, tracking dependencies and detecting holes."""

    def __init__(self):
        self.nodes: Dict[str, RequirementNode] = {}
        self.edges: List[Tuple[str, str, str]] = []  # (source_id, relation, target_id)

    def add_requirement(self, req: RequirementNode) -> RequirementNode:
        if req.id in self.nodes:
            existing = self.nodes[req.id]
            # Check for semantic conflict under same ID
            if (existing.statement != req.statement or
                existing.capability != req.capability or
                existing.target != req.target or
                existing.kind != req.kind):
                raise DuplicateIDConflictError(
                    f"Requirement ID '{req.id}' semantic conflict: "
                    f"Existing '{existing.statement}' ({existing.capability}) vs "
                    f"New '{req.statement}' ({req.capability}). CASUAL MERGING REJECTED."
                )
            return existing

        self.nodes[req.id] = req
        return req

    def _has_path(self, start_id: str, target_id: str, visited: Optional[Set[str]] = None) -> bool:
        if visited is None:
            visited = set()
        if start_id == target_id:
            return True
        visited.add(start_id)
        for src, rel, tgt in self.edges:
            if src == start_id and rel == "depends_on" and tgt not in visited:
                if self._has_path(tgt, target_id, visited):
                    return True
        return False

    def add_dependency(self, req_id: str, depends_on_req_id: str):
        if req_id in self.nodes and depends_on_req_id in self.nodes:
            if req_id == depends_on_req_id or self._has_path(depends_on_req_id, req_id):
                raise CircularDependencyError(
                    f"Circular requirement dependency detected: '{req_id}' -> '{depends_on_req_id}' -> '{req_id}'"
                )
            if (req_id, "depends_on", depends_on_req_id) not in self.edges:
                self.edges.append((req_id, "depends_on", depends_on_req_id))
            if depends_on_req_id not in self.nodes[req_id].dependencies:
                self.nodes[req_id].dependencies.append(depends_on_req_id)

    def detect_dependency_holes(self) -> List[Dict[str, Any]]:
        """
        Detects missing prerequisite state machine lifecycles or un-satisfied capability dependencies.
        Returns a list of dependency hole issue dictionaries.
        """
        holes = []
        for req in self.nodes.values():
            # Check if requirement references state preconditions without an explicit state transition requirement
            for pre in req.preconditions:
                if "==" in pre:
                    var_name, val = [x.strip() for x in pre.split("==", 1)]
                    # Verify if a corresponding state requirement or behavior exists
                    has_state_req = any(
                        r.target == req.target and any(val in post for post in r.postconditions)
                        for r in self.nodes.values()
                    )
                    if not has_state_req and req.epistemic_status == EpistemicStatus.EXPLICIT:
                        holes.append({
                            "req_id": req.id,
                            "type": "MISSING_PRECONDITION_STATE_MODEL",
                            "severity": "HIGH",
                            "message": f"Requirement {req.id} ({req.capability}) requires state {pre}, but no state transition requirement produces state {val} for entity {req.target}."
                        })

        return holes

    @classmethod
    def compile_from_behavior_graph(cls, b_graph: BehaviorGraph) -> 'RequirementGraph':
        """Compiles a grounded BehaviorGraph into a machine-verifiable RequirementGraph."""
        r_graph = cls()
        req_counter = 1

        for b_node in b_graph.nodes.values():
            # Only compile ACCEPTED behaviors (suppress PROPOSED)
            if b_node.epistemic_status not in [EpistemicStatus.EXPLICIT, EpistemicStatus.OBSERVED, EpistemicStatus.DERIVED, EpistemicStatus.CONFIRMED]:
                continue

            if b_node.behavior_type == BehaviorNodeType.COMMAND:
                req_id = f"REQ-{req_counter:03d}"
                req_counter += 1

                preconds = [f"{b_node.target_entity_id}.status == {b_node.from_state.upper()}"] if b_node.from_state else []
                postconds = [f"{b_node.target_entity_id}.status == {b_node.to_state.upper()}"] if b_node.to_state else []

                r_graph.add_requirement(RequirementNode(
                    id=req_id,
                    kind=RequirementKind.FUNCTIONAL,
                    statement=f"The system shall allow {b_node.actor_id} to execute {b_node.name}.",
                    actor=b_node.actor_id,
                    capability=b_node.id,
                    target=b_node.target_entity_id,
                    preconditions=preconds,
                    postconditions=postconds,
                    epistemic_status=b_node.epistemic_status,
                    provenance=b_node.provenance,
                    confidence=b_node.confidence,
                    evidence=b_node.evidence_ref,
                    source_behaviors=[b_node.id]
                ))

                # Synthesize NFR Audit Log Requirement for state-changing commands
                if b_node.from_state or b_node.to_state or any(v in b_node.name.lower() for v in ["approve", "sign", "override", "reject", "ground"]):
                    nfr_id = f"REQ-{req_counter:03d}"
                    req_counter += 1
                    r_graph.add_requirement(RequirementNode(
                        id=nfr_id,
                        kind=RequirementKind.NON_FUNCTIONAL,
                        nfr_category=NFRCategory.AUDITABILITY,
                        statement=f"Execution of {b_node.name} by {b_node.actor_id} must emit an immutable audit log record.",
                        actor=b_node.actor_id,
                        capability=f"{b_node.id}_audit_log",
                        target=b_node.target_entity_id,
                        epistemic_status=EpistemicStatus.DERIVED,
                        provenance=ProvenanceKind.STRONGLY_DERIVED,
                        confidence=0.95,
                        evidence=f"Audit side effect for {b_node.id}",
                        source_behaviors=[b_node.id]
                    ))
                    r_graph.add_dependency(nfr_id, req_id)

        return r_graph

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": self.edges
        }
