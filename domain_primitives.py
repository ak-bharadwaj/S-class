"""
S-Class EOS V5.0 - Semantic Primitives & Domain Graph Architecture

Defines first-principles ontology primitives, provenance categories,
typed relationship edges, and the SemanticDomainGraph data structure.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import json


class DomainPrimitiveType(str, Enum):
    """Core domain primitives that can describe any software system across any industry."""
    ENTITY = "entity"                 # Core business noun / domain concept (e.g. Machine, Patient, Contract, Batch)
    ACTOR = "actor"                   # Human role or system service taking actions (e.g. Dispatcher, Pilot, Technician)
    RESOURCE = "resource"             # Physical/virtual asset with capacity or state (e.g. Inverter, Vehicle, Room, Valve)
    MEASUREMENT = "measurement"       # Numerical or categorical time-series/reading (e.g. Temperature, Latency, Odometer)
    EVENT = "event"                   # Discrete occurrence or threshold violation (e.g. Alert, Incident, Breakdown)
    TRANSACTION = "transaction"       # Value exchange or state commitment (e.g. LeaseAgreement, FactoringSettlement)
    STATE = "state"                   # Lifecycle phase or operational condition (e.g. Acknowledged, Quarantined, Overdue)
    WORKFLOW = "workflow"             # Multi-step ordered procedure (e.g. QualityInspection, NOCVerification)
    POLICY = "policy"                 # Rule, threshold, limit, or invariant (e.g. TemperatureThreshold, WaterQuota)
    DOCUMENT = "document"             # Formally structured artifact or digital proof (e.g. PrescriptionPDF, BillOfLading)


class ProvenanceKind(str, Enum):
    """Unified provenance trail across nodes, edges, and behavioral primitives."""
    EXPLICIT = "explicit"                     # Directly stated in source prompt/doc
    OBSERVED = "observed"                     # Extracted from AST code/DB schema/routes
    STRONGLY_DERIVED = "strongly_derived"     # Deducible from graph topology with near certainty
    WEAKLY_DERIVED = "weakly_derived"         # Plausible operational standard, flagged for review
    SPECULATIVE = "speculative"               # Unbacked assumption, must be suppressed or confirmed
    INVALID = "invalid"                       # Malformed or corrupted provenance metadata

# Backwards compatibility aliases
ProvenanceType = ProvenanceKind
EdgeProvenanceType = ProvenanceKind


class RelationType(str, Enum):
    """Semantic edges connecting domain primitives."""
    HAS = "has"                               # Entity has child entity/attribute
    PRODUCES = "produces"                     # Resource/Entity produces Measurement or Event
    MEASURES = "measures"                     # Sensor/Telemetry measures metric
    EVALUATED_BY = "evaluated_by"             # Measurement checked against Policy/Threshold
    TRIGGERS = "triggers"                     # Threshold violation triggers Event/Alert
    TRANSITIONS_TO = "transitions_to"         # State A transitions to State B
    AUTHORIZED_FOR = "authorized_for"         # Actor has permission for Workflow/Action
    APPLIES_TO = "applies_to"                 # Policy applies to Entity/Resource
    BELONGS_TO = "belongs_to"                 # Resource/Component belongs to Parent Entity
    DEPENDS_ON = "depends_on"                 # Workflow requires prerequisite state/event
    CONTAINS = "contains"                     # Document/Entity contains sub-items (e.g. Contract has Clauses)


@dataclass
class DomainNode:
    """A single semantic primitive node in the Domain Graph."""
    id: str
    name: str
    primitive_type: DomainPrimitiveType
    attributes: Dict[str, str] = field(default_factory=dict)
    provenance: ProvenanceType = ProvenanceType.STRONGLY_DERIVED
    confidence: float = 1.0
    evidence_ref: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "primitive_type": self.primitive_type.value,
            "attributes": self.attributes,
            "provenance": self.provenance.value,
            "confidence": self.confidence,
            "evidence_ref": self.evidence_ref,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DomainNode':
        prim_type_str = data.get("primitive_type", "entity")
        try:
            prim_type = DomainPrimitiveType(prim_type_str)
        except ValueError:
            prim_type = DomainPrimitiveType.ENTITY
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            primitive_type=prim_type,
            attributes=data.get("attributes", {}),
            provenance=ProvenanceType(data.get("provenance", "strongly_derived")),
            confidence=data.get("confidence", 1.0),
            evidence_ref=data.get("evidence_ref"),
            description=data.get("description", "")
        )


@dataclass
class DomainEdge:
    """A directed semantic relationship between two domain nodes with first-class provenance."""
    source_id: str
    relation: RelationType
    target_id: str
    provenance: EdgeProvenanceType = EdgeProvenanceType.STRONGLY_DERIVED
    confidence: float = 1.0
    evidence_ref: Optional[str] = None
    inference_rule: Optional[str] = None
    assumptions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "relation": self.relation.value,
            "target_id": self.target_id,
            "provenance": self.provenance.value,
            "confidence": self.confidence,
            "evidence_ref": self.evidence_ref,
            "inference_rule": self.inference_rule,
            "assumptions": self.assumptions,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DomainEdge':
        prov_val = data.get("provenance", "strongly_derived")
        try:
            prov = ProvenanceKind(prov_val)
        except ValueError:
            prov = ProvenanceKind.STRONGLY_DERIVED
        return cls(
            source_id=data.get("source_id", ""),
            relation=RelationType(data.get("relation", "relates_to")),
            target_id=data.get("target_id", ""),
            provenance=prov,
            confidence=data.get("confidence", 1.0),
            evidence_ref=data.get("evidence_ref"),
            inference_rule=data.get("inference_rule"),
            assumptions=data.get("assumptions", []),
            metadata=data.get("metadata", {})
        )


@dataclass
class AssumptionRecord:
    """Auditable assumption record with reversibility tracking."""
    id: str
    statement: str
    basis: str
    confidence: float
    risk_level: str                          # low | medium | high
    reversible: bool = True
    affected_nodes: List[str] = field(default_factory=list)
    affected_requirements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "basis": self.basis,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "reversible": self.reversible,
            "affected_nodes": self.affected_nodes,
            "affected_requirements": self.affected_requirements
        }


class SemanticDomainGraph:
    """
    Typed Directed Multigraph representing the domain model of an application.
    Supports composition, traversal, topological inference, and consistency checks.
    """

    def __init__(self):
        self.nodes: Dict[str, DomainNode] = {}
        self.edges: List[DomainEdge] = []
        self._adjacency: Dict[str, List[DomainEdge]] = {}
        self._reverse_adjacency: Dict[str, List[DomainEdge]] = {}

    def add_node(self, node: DomainNode) -> DomainNode:
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []
        if node.id not in self._reverse_adjacency:
            self._reverse_adjacency[node.id] = []
        return node

    def add_edge(
        self,
        source_id: str,
        relation: RelationType,
        target_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: EdgeProvenanceType = EdgeProvenanceType.STRONGLY_DERIVED,
        confidence: float = 1.0,
        evidence_ref: Optional[str] = None,
        inference_rule: Optional[str] = None,
        assumptions: Optional[List[str]] = None
    ) -> DomainEdge:
        if source_id not in self.nodes:
            raise KeyError(f"Source node '{source_id}' does not exist in domain graph")
        if target_id not in self.nodes:
            raise KeyError(f"Target node '{target_id}' does not exist in domain graph")

        edge = DomainEdge(
            source_id=source_id,
            relation=relation,
            target_id=target_id,
            provenance=provenance,
            confidence=confidence,
            evidence_ref=evidence_ref,
            inference_rule=inference_rule,
            assumptions=assumptions or [],
            metadata=metadata or {}
        )
        self.edges.append(edge)
        self._adjacency[source_id].append(edge)
        self._reverse_adjacency[target_id].append(edge)
        return edge

    def get_node(self, node_id: str) -> Optional[DomainNode]:
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, primitive_type: DomainPrimitiveType) -> List[DomainNode]:
        return [n for n in self.nodes.values() if n.primitive_type == primitive_type]

    def get_outgoing_edges(self, node_id: str, relation: Optional[RelationType] = None) -> List[DomainEdge]:
        edges = self._adjacency.get(node_id, [])
        if relation:
            return [e for e in edges if e.relation == relation]
        return edges

    def get_incoming_edges(self, node_id: str, relation: Optional[RelationType] = None) -> List[DomainEdge]:
        edges = self._reverse_adjacency.get(node_id, [])
        if relation:
            return [e for e in edges if e.relation == relation]
        return edges

    def get_connected_targets(self, node_id: str, relation: Optional[RelationType] = None) -> List[DomainNode]:
        edges = self.get_outgoing_edges(node_id, relation)
        return [self.nodes[e.target_id] for e in edges if e.target_id in self.nodes]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SemanticDomainGraph':
        graph = cls()
        for node_data in data.get("nodes", []):
            graph.add_node(DomainNode.from_dict(node_data))
        for edge_data in data.get("edges", []):
            graph.add_edge(
                source_id=edge_data["source_id"],
                relation=RelationType(edge_data["relation"]),
                target_id=edge_data["target_id"],
                metadata=edge_data.get("metadata", {})
            )
        return graph


# --- Requirement Synthesis Primitive Taxonomies ---

class RequirementType(str, Enum):
    EXPLICIT = "explicit"
    SUPPORTED = "supported"
    DERIVED = "derived"
    OPTIONAL = "optional"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"
    REUSE = "reuse"


class ArtifactAction(str, Enum):
    CREATE = "create"
    EXTEND = "extend"
    MODIFY = "modify"
    REUSE = "reuse"
    DEPRECATE = "deprecate"
    DELETE = "delete"


class RequirementCategory(str, Enum):
    PRODUCT_REQUIREMENT = "product_requirement"
    SYSTEM_INVARIANT = "system_invariant"
    UX_DERIVATION = "ux_derivation"
    ARCHITECTURAL_CONSTRAINT = "architectural_constraint"


class DecisionThreshold(str, Enum):
    AUTO_DECIDE = "auto"
    PROBABLY_DECIDE = "probably"
    MUST_ASK = "must_ask"
    MUST_STOP = "must_stop"


@dataclass
class EvidenceReference:
    source_file: str
    section: Optional[str] = None
    reference_text: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class SynthesizedRequirement:
    id: str
    description: str
    type: RequirementType
    category: RequirementCategory
    action: ArtifactAction
    decision_threshold: DecisionThreshold
    evidence: List[EvidenceReference] = field(default_factory=list)
    why_chain: List[str] = field(default_factory=list)
    affects: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    consequences: List[str] = field(default_factory=list)
    assumption_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "type": self.type.value if hasattr(self.type, "value") else str(self.type),
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "action": self.action.value if hasattr(self.action, "value") else str(self.action),
            "decision_threshold": self.decision_threshold.value if hasattr(self.decision_threshold, "value") else str(self.decision_threshold),
            "evidence": [e.__dict__ if hasattr(e, "__dict__") else e for e in self.evidence],
            "why_chain": self.why_chain,
            "affects": self.affects,
            "depends_on": self.depends_on,
            "consequences": self.consequences,
            "assumption_type": self.assumption_type
        }

