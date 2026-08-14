"""
S-Class EOS V6.0 - Behavior Graph & State Machine Infrastructure

Defines the Behavior Graph primitive types, typed behavior relationships,
first-class behavior provenance, and the BehaviorGraphEngine.

The Behavior Graph sits directly between the Semantic Domain Graph and Requirements:
EVIDENCE → DOMAIN GRAPH → BEHAVIOR GRAPH → REQUIREMENTS → HLD → LLD → TASKS
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import re
import json
from domain_primitives import (
    DomainPrimitiveType,
    ProvenanceType,
    EdgeProvenanceType,
    DomainNode,
    DomainEdge,
    RelationType,
    SemanticDomainGraph
)


class BehaviorNodeType(str, Enum):
    """Behavior primitive classification."""
    COMMAND = "command"                 # State-changing intent (e.g. IssuePrescription, GroundAircraft, BookRoom)
    QUERY = "query"                     # Read/Inspection intent (e.g. FetchAirworthinessStatus, CheckAvailability)
    STATE_TRANSITION = "transition"     # State lifecycle transition (e.g. Draft -> Signed -> Fulfilled)
    GUARD_CONDITION = "guard"           # Authorization / Policy check (e.g. IsDoctorLicensed, HasSufficientQuota)
    SIDE_EFFECT = "side_effect"         # Event emissions, notifications, audit log records


class BehaviorRelationType(str, Enum):
    """Semantic relations connecting behavior nodes."""
    AUTHORIZED_FOR = "authorized_for"   # Actor authorized to execute Command/Query
    TARGETS = "targets"                 # Command/Query targets Entity/Resource
    TRANSITIONS = "transitions"         # Command triggers State A -> State B transition
    REQUIRES_GUARD = "requires_guard"   # Command requires Guard Condition check
    EMITS_SIDE_EFFECT = "emits"         # Command emits Audit Event / Notification
    DEPENDS_ON_BEHAVIOR = "depends_on"  # Prerequisite command (e.g. Sign requires Draft)


@dataclass
class BehaviorNode:
    """A single behavioral primitive node in the Behavior Graph."""
    id: str
    name: str
    behavior_type: BehaviorNodeType
    actor_id: str
    target_entity_id: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    policy_ids: List[str] = field(default_factory=list)
    provenance: EdgeProvenanceType = EdgeProvenanceType.BEHAVIORAL_DERIVATION
    confidence: float = 1.0
    evidence_ref: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "behavior_type": self.behavior_type.value,
            "actor_id": self.actor_id,
            "target_entity_id": self.target_entity_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "policy_ids": self.policy_ids,
            "provenance": self.provenance.value,
            "confidence": self.confidence,
            "evidence_ref": self.evidence_ref,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BehaviorNode':
        prov_val = data.get("provenance", "derived")
        try:
            prov = EdgeProvenanceType(prov_val)
        except ValueError:
            prov = EdgeProvenanceType.BEHAVIORAL_DERIVATION
        return cls(
            id=data["id"],
            name=data["name"],
            behavior_type=BehaviorNodeType(data["behavior_type"]),
            actor_id=data.get("actor_id", "operator"),
            target_entity_id=data.get("target_entity_id", "system"),
            from_state=data.get("from_state"),
            to_state=data.get("to_state"),
            policy_ids=data.get("policy_ids", []),
            provenance=prov,
            confidence=data.get("confidence", 1.0),
            evidence_ref=data.get("evidence_ref"),
            description=data.get("description", "")
        )


@dataclass
class BehaviorEdge:
    """A directed behavioral relationship with first-class provenance."""
    source_id: str
    relation: BehaviorRelationType
    target_id: str
    provenance: EdgeProvenanceType = EdgeProvenanceType.BEHAVIORAL_DERIVATION
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
    def from_dict(cls, data: Dict[str, Any]) -> 'BehaviorEdge':
        prov_val = data.get("provenance", "derived")
        try:
            prov = EdgeProvenanceType(prov_val)
        except ValueError:
            prov = EdgeProvenanceType.BEHAVIORAL_DERIVATION
        return cls(
            source_id=data["source_id"],
            relation=BehaviorRelationType(data["relation"]),
            target_id=data["target_id"],
            provenance=prov,
            confidence=data.get("confidence", 1.0),
            evidence_ref=data.get("evidence_ref"),
            inference_rule=data.get("inference_rule"),
            assumptions=data.get("assumptions", []),
            metadata=data.get("metadata", {})
        )


class BehaviorGraph:
    """Typed Multigraph for system behavior, authorization, state transitions, and audit trails."""

    def __init__(self):
        self.nodes: Dict[str, BehaviorNode] = {}
        self.edges: List[BehaviorEdge] = []
        self._adjacency: Dict[str, List[BehaviorEdge]] = {}
        self._reverse_adjacency: Dict[str, List[BehaviorEdge]] = {}

    def add_node(self, node: BehaviorNode) -> BehaviorNode:
        self.nodes[node.id] = node
        if node.id not in self._adjacency:
            self._adjacency[node.id] = []
        if node.id not in self._reverse_adjacency:
            self._reverse_adjacency[node.id] = []
        return node

    def add_edge(
        self,
        source_id: str,
        relation: BehaviorRelationType,
        target_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: EdgeProvenanceType = EdgeProvenanceType.BEHAVIORAL_DERIVATION,
        confidence: float = 1.0,
        evidence_ref: Optional[str] = None,
        inference_rule: Optional[str] = None,
        assumptions: Optional[List[str]] = None
    ) -> BehaviorEdge:
        edge = BehaviorEdge(
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
        if source_id not in self._adjacency:
            self._adjacency[source_id] = []
        if target_id not in self._reverse_adjacency:
            self._reverse_adjacency[target_id] = []
        self._adjacency[source_id].append(edge)
        self._reverse_adjacency[target_id].append(edge)
        return edge

    def get_node(self, node_id: str) -> Optional[BehaviorNode]:
        return self.nodes.get(node_id)

    def get_commands_for_actor(self, actor_id: str) -> List[BehaviorNode]:
        return [n for n in self.nodes.values() if n.actor_id == actor_id and n.behavior_type == BehaviorNodeType.COMMAND]

    def get_queries_for_actor(self, actor_id: str) -> List[BehaviorNode]:
        return [n for n in self.nodes.values() if n.actor_id == actor_id and n.behavior_type == BehaviorNodeType.QUERY]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BehaviorGraph':
        graph = cls()
        for node_data in data.get("nodes", []):
            graph.add_node(BehaviorNode.from_dict(node_data))
        for edge_data in data.get("edges", []):
            graph.add_edge(
                source_id=edge_data["source_id"],
                relation=BehaviorRelationType(edge_data["relation"]),
                target_id=edge_data["target_id"],
                metadata=edge_data.get("metadata", {}),
                provenance=EdgeProvenanceType(edge_data.get("provenance", "derived")),
                confidence=edge_data.get("confidence", 1.0),
                evidence_ref=edge_data.get("evidence_ref"),
                inference_rule=edge_data.get("inference_rule"),
                assumptions=edge_data.get("assumptions", [])
            )
        return graph


class BehaviorGraphEngine:
    """
    Constructs a BehaviorGraph from SemanticDomainGraph and intent features.
    Maps Actor Capabilities -> Commands, State Transitions, Guard Conditions, and Audit Events.
    """

    @classmethod
    def build_behavior_graph(cls, domain_graph: SemanticDomainGraph, raw_request: str) -> BehaviorGraph:
        b_graph = BehaviorGraph()
        actors = domain_graph.get_nodes_by_type(DomainPrimitiveType.ACTOR)
        entities = domain_graph.get_nodes_by_type(DomainPrimitiveType.ENTITY)
        resources = domain_graph.get_nodes_by_type(DomainPrimitiveType.RESOURCE)
        policies = domain_graph.get_nodes_by_type(DomainPrimitiveType.POLICY)

        actor_ids = [a.id for a in actors] if actors else ["actor_operator"]
        target_entities = entities + resources if (entities or resources) else [DomainNode("entity_system", "System", DomainPrimitiveType.ENTITY)]

        # 1. Synthesize Behavior Commands from Action Verbs in raw_request
        action_verbs = re.findall(r'\b(submit|approve|reject|assign|schedule|upload|issue|waive|cancel|ground|inspect|prescribe|verify|override)\b', raw_request, re.IGNORECASE)
        action_verbs = list(dict.fromkeys([v.lower() for v in action_verbs]))

        if not action_verbs:
            action_verbs = ["manage", "process"]

        for actor in actors:
            actor_name = actor.name.lower().replace(" ", "_")
            for ent in target_entities:
                ent_name = ent.name.lower().replace(" ", "_")
                for verb in action_verbs:
                    cmd_id = f"cmd_{actor_name}_{verb}_{ent_name}"
                    cmd_node = b_graph.add_node(BehaviorNode(
                        id=cmd_id,
                        name=f"{actor.name} {verb.capitalize()} {ent.name}",
                        behavior_type=BehaviorNodeType.COMMAND,
                        actor_id=actor.id,
                        target_entity_id=ent.id,
                        provenance=EdgeProvenanceType.EXPLICIT if verb in raw_request.lower() else EdgeProvenanceType.BEHAVIORAL_DERIVATION,
                        description=f"Behavioral command: {actor.name} executes {verb} on {ent.name}"
                    ))
                    # Edge: Actor AUTHORIZED_FOR Command
                    b_graph.add_edge(actor.id, BehaviorRelationType.AUTHORIZED_FOR, cmd_id, inference_rule="actor_verb_intent_binding")
                    # Edge: Command TARGETS Entity
                    b_graph.add_edge(cmd_id, BehaviorRelationType.TARGETS, ent.id, inference_rule="command_entity_target")

                    # If policies exist, add Guard Condition
                    if policies:
                        for pol in policies:
                            guard_id = f"guard_{pol.id}_for_{cmd_id}"
                            b_graph.add_node(BehaviorNode(
                                id=guard_id,
                                name=f"Verify {pol.name} Compliance",
                                behavior_type=BehaviorNodeType.GUARD_CONDITION,
                                actor_id=actor.id,
                                target_entity_id=ent.id,
                                policy_ids=[pol.id],
                                description=f"Guard check verifying policy {pol.name}"
                            ))
                            b_graph.add_edge(cmd_id, BehaviorRelationType.REQUIRES_GUARD, guard_id, inference_rule="policy_guard_requirement")

                    # Emit Audit Side Effect for State-Changing Commands
                    side_id = f"side_effect_{cmd_id}_audit_log"
                    b_graph.add_node(BehaviorNode(
                        id=side_id,
                        name=f"Emit {verb.capitalize()}{ent.name}AuditEvent",
                        behavior_type=BehaviorNodeType.SIDE_EFFECT,
                        actor_id=actor.id,
                        target_entity_id=ent.id,
                        description=f"Audit trail log emitted when {cmd_node.name} occurs"
                    ))
                    b_graph.add_edge(cmd_id, BehaviorRelationType.EMITS_SIDE_EFFECT, side_id, inference_rule="audit_side_effect_emission")

                # Add Query Node for Actor
                query_id = f"query_{actor_name}_view_{ent_name}"
                b_graph.add_node(BehaviorNode(
                    id=query_id,
                    name=f"{actor.name} View {ent.name} Status",
                    behavior_type=BehaviorNodeType.QUERY,
                    actor_id=actor.id,
                    target_entity_id=ent.id,
                    description=f"Read query for {actor.name} to inspect {ent.name}"
                ))
                b_graph.add_edge(actor.id, BehaviorRelationType.AUTHORIZED_FOR, query_id, inference_rule="actor_query_authorization")
                b_graph.add_edge(query_id, BehaviorRelationType.TARGETS, ent.id, inference_rule="query_entity_target")

        return b_graph
