"""
S-Class EOS V6.1 - Behavior Graph & Epistemic Grounding Infrastructure

Defines EpistemicStatus, Behavior Graph primitives, typed behavior relationships,
unified provenance tracking, and the BehaviorGraphEngine with SVO Triple Extraction.

The Behavior Graph sits directly between the Semantic Domain Graph and Requirements:
EVIDENCE → DOMAIN GRAPH → BEHAVIOR CANDIDATES → GROUNDING ENGINE → ACCEPTED BEHAVIOR GRAPH → HLD → LLD → TASKS
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import re
import json
from domain_primitives import (
    DomainPrimitiveType,
    ProvenanceKind,
    DomainNode,
    DomainEdge,
    RelationType,
    SemanticDomainGraph
)


class EpistemicStatus(str, Enum):
    """Epistemic certainty status of a behavioral node or requirement."""
    EXPLICIT = "explicit"               # Directly declared in user prompt/text
    OBSERVED = "observed"               # Discovered from workspace code/schema/routes
    DERIVED = "derived"                 # Deducible from graph topology with high certainty
    PROPOSED = "proposed"               # Unbacked candidate hypothesis, gated from HLD/LLD compilation
    CONFIRMED = "confirmed"             # Human-approved or policy-validated proposed behavior
    REJECTED = "rejected"               # Explicitly rejected or invalid behavior


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
    epistemic_status: EpistemicStatus = EpistemicStatus.DERIVED
    provenance: ProvenanceKind = ProvenanceKind.STRONGLY_DERIVED
    confidence: float = 1.0
    evidence_ref: Optional[str] = None
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    policy_ids: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "behavior_type": self.behavior_type.value,
            "actor_id": self.actor_id,
            "target_entity_id": self.target_entity_id,
            "epistemic_status": self.epistemic_status.value,
            "provenance": self.provenance.value,
            "confidence": self.confidence,
            "evidence_ref": self.evidence_ref,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "policy_ids": self.policy_ids,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BehaviorNode':
        ep_val = data.get("epistemic_status", "derived")
        try:
            ep = EpistemicStatus(ep_val)
        except ValueError:
            ep = EpistemicStatus.DERIVED

        prov_val = data.get("provenance", "strongly_derived")
        try:
            prov = ProvenanceKind(prov_val)
        except ValueError:
            prov = ProvenanceKind.STRONGLY_DERIVED

        return cls(
            id=data["id"],
            name=data["name"],
            behavior_type=BehaviorNodeType(data["behavior_type"]),
            actor_id=data.get("actor_id", "operator"),
            target_entity_id=data.get("target_entity_id", "system"),
            epistemic_status=ep,
            provenance=prov,
            confidence=data.get("confidence", 1.0),
            evidence_ref=data.get("evidence_ref"),
            from_state=data.get("from_state"),
            to_state=data.get("to_state"),
            policy_ids=data.get("policy_ids", []),
            description=data.get("description", "")
        )


@dataclass
class BehaviorEdge:
    """A directed behavioral relationship with unified provenance."""
    source_id: str
    relation: BehaviorRelationType
    target_id: str
    epistemic_status: EpistemicStatus = EpistemicStatus.DERIVED
    provenance: ProvenanceKind = ProvenanceKind.STRONGLY_DERIVED
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
            "epistemic_status": self.epistemic_status.value,
            "provenance": self.provenance.value,
            "confidence": self.confidence,
            "evidence_ref": self.evidence_ref,
            "inference_rule": self.inference_rule,
            "assumptions": self.assumptions,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BehaviorEdge':
        ep_val = data.get("epistemic_status", "derived")
        try:
            ep = EpistemicStatus(ep_val)
        except ValueError:
            ep = EpistemicStatus.DERIVED

        prov_val = data.get("provenance", "strongly_derived")
        try:
            prov = ProvenanceKind(prov_val)
        except ValueError:
            prov = ProvenanceKind.STRONGLY_DERIVED

        return cls(
            source_id=data["source_id"],
            relation=BehaviorRelationType(data["relation"]),
            target_id=data["target_id"],
            epistemic_status=ep,
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
        epistemic_status: EpistemicStatus = EpistemicStatus.DERIVED,
        provenance: ProvenanceKind = ProvenanceKind.STRONGLY_DERIVED,
        confidence: float = 1.0,
        evidence_ref: Optional[str] = None,
        inference_rule: Optional[str] = None,
        assumptions: Optional[List[str]] = None
    ) -> BehaviorEdge:
        edge = BehaviorEdge(
            source_id=source_id,
            relation=relation,
            target_id=target_id,
            epistemic_status=epistemic_status,
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

    def get_accepted_commands_for_actor(self, actor_id: str) -> List[BehaviorNode]:
        accepted = {EpistemicStatus.EXPLICIT, EpistemicStatus.OBSERVED, EpistemicStatus.DERIVED, EpistemicStatus.CONFIRMED}
        return [n for n in self.nodes.values() if n.actor_id == actor_id and n.behavior_type == BehaviorNodeType.COMMAND and n.epistemic_status in accepted]

    def get_accepted_queries_for_actor(self, actor_id: str) -> List[BehaviorNode]:
        accepted = {EpistemicStatus.EXPLICIT, EpistemicStatus.OBSERVED, EpistemicStatus.DERIVED, EpistemicStatus.CONFIRMED}
        return [n for n in self.nodes.values() if n.actor_id == actor_id and n.behavior_type == BehaviorNodeType.QUERY and n.epistemic_status in accepted]

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
                epistemic_status=EpistemicStatus(edge_data.get("epistemic_status", "derived")),
                provenance=ProvenanceKind(edge_data.get("provenance", "strongly_derived")),
                confidence=edge_data.get("confidence", 1.0),
                evidence_ref=edge_data.get("evidence_ref"),
                inference_rule=edge_data.get("inference_rule"),
                assumptions=edge_data.get("assumptions", [])
            )
        return graph


class BehaviorGraphEngine:
    """
    Constructs a grounded BehaviorGraph from SemanticDomainGraph and intent features.
    Uses Subject-Verb-Object (SVO) Triple Extraction to avoid Cartesian over-generation.
    Applies targeted policy binding and explicit state machine derivation.
    """

    @classmethod
    def extract_svo_triples(cls, raw_request: str, actors: List[DomainNode], entities: List[DomainNode]) -> List[Tuple[DomainNode, str, DomainNode]]:
        """
        Parses explicit Subject-Verb-Object (SVO) propositions from source text.
        Returns matching (Actor, Verb, Entity) triples directly grounded in prose.
        """
        triples = []
        sentences = re.split(r'[\.\n;]', raw_request)

        actor_map = {a.name.lower(): a for a in actors}
        # Add single word keys for actors (e.g. 'pilot' for 'Pilot')
        for a in actors:
            for w in a.name.lower().split():
                if len(w) >= 3:
                    actor_map[w] = a

        entity_map = {e.name.lower(): e for e in entities}
        for e in entities:
            for w in e.name.lower().split():
                if len(w) >= 3:
                    entity_map[w] = e

        action_verbs = [
            "submit", "approve", "reject", "assign", "schedule", "upload",
            "issue", "waive", "cancel", "ground", "inspect", "prescribe",
            "verify", "override", "create", "delete", "sign", "dispense", "renew"
        ]

        for s in sentences:
            s_clean = s.lower()
            matched_actor = None
            matched_entity = None
            matched_verb = None

            for a_key, a_node in actor_map.items():
                if re.search(r'\b' + re.escape(a_key) + r's?\b', s_clean):
                    matched_actor = a_node
                    break

            for e_key, e_node in entity_map.items():
                if re.search(r'\b' + re.escape(e_key) + r's?\b', s_clean):
                    matched_entity = e_node
                    break

            for v in action_verbs:
                if re.search(r'\b' + re.escape(v) + r'(?:s|d|ing)?\b', s_clean):
                    matched_verb = v
                    break

            if matched_actor and matched_entity and matched_verb:
                triple = (matched_actor, matched_verb, matched_entity)
                if triple not in triples:
                    triples.append(triple)

        return triples

    @classmethod
    def build_behavior_graph(cls, domain_graph: SemanticDomainGraph, raw_request: str) -> BehaviorGraph:
        b_graph = BehaviorGraph()
        actors = domain_graph.get_nodes_by_type(DomainPrimitiveType.ACTOR)
        entities = domain_graph.get_nodes_by_type(DomainPrimitiveType.ENTITY)
        resources = domain_graph.get_nodes_by_type(DomainPrimitiveType.RESOURCE)
        policies = domain_graph.get_nodes_by_type(DomainPrimitiveType.POLICY)
        states = domain_graph.get_nodes_by_type(DomainPrimitiveType.STATE)
        workflows = domain_graph.get_nodes_by_type(DomainPrimitiveType.WORKFLOW)

        target_entities = entities + resources if (entities or resources) else [DomainNode("entity_system", "System", DomainPrimitiveType.ENTITY)]
        if not actors:
            actors = [DomainNode("actor_operator", "Operator", DomainPrimitiveType.ACTOR)]

        # 1. Grounded SVO Triple Extraction (EXPLICIT Behavior)
        svo_triples = cls.extract_svo_triples(raw_request, actors, target_entities)

        # 2. State Machine Derivation (Draft -> Signed -> Fulfilled)
        state_names = [s.name.lower() for s in states]
        has_draft_signed = any("draft" in s for s in state_names) and any("sign" in s for s in state_names)

        # Process Explicit SVO Triples
        for actor, verb, ent in svo_triples:
            actor_name = actor.name.lower().replace(" ", "_")
            ent_name = ent.name.lower().replace(" ", "_")
            cmd_id = f"cmd_{actor_name}_{verb}_{ent_name}"

            from_st = "draft" if (has_draft_signed and verb in ["sign", "approve"]) else None
            to_st = "signed" if (has_draft_signed and verb in ["sign", "approve"]) else None

            cmd_node = b_graph.add_node(BehaviorNode(
                id=cmd_id,
                name=f"{actor.name} {verb.capitalize()} {ent.name}",
                behavior_type=BehaviorNodeType.COMMAND,
                actor_id=actor.id,
                target_entity_id=ent.id,
                epistemic_status=EpistemicStatus.EXPLICIT,
                provenance=ProvenanceKind.EXPLICIT,
                confidence=0.99,
                evidence_ref="source_text_svo_match",
                from_state=from_st,
                to_state=to_st,
                description=f"Explicitly grounded command: {actor.name} {verb} {ent.name}"
            ))

            b_graph.add_edge(
                actor.id, BehaviorRelationType.AUTHORIZED_FOR, cmd_id,
                epistemic_status=EpistemicStatus.EXPLICIT, provenance=ProvenanceKind.EXPLICIT,
                inference_rule="svo_actor_authorization"
            )
            b_graph.add_edge(
                cmd_id, BehaviorRelationType.TARGETS, ent.id,
                epistemic_status=EpistemicStatus.EXPLICIT, provenance=ProvenanceKind.EXPLICIT,
                inference_rule="svo_command_target"
            )

            # Targeted Policy Binding: Only attach policy if policy APPLIES_TO or EVALUATED_BY target entity
            for pol in policies:
                pol_edges = domain_graph.get_outgoing_edges(pol.id) + domain_graph.get_incoming_edges(pol.id)
                targets_ent = any(e.target_id == ent.id or e.source_id == ent.id for e in pol_edges)
                if targets_ent or pol.name.lower() in raw_request.lower():
                    guard_id = f"guard_{pol.id}_for_{cmd_id}"
                    b_graph.add_node(BehaviorNode(
                        id=guard_id,
                        name=f"Verify {pol.name} Compliance",
                        behavior_type=BehaviorNodeType.GUARD_CONDITION,
                        actor_id=actor.id,
                        target_entity_id=ent.id,
                        epistemic_status=EpistemicStatus.DERIVED,
                        provenance=ProvenanceKind.STRONGLY_DERIVED,
                        policy_ids=[pol.id],
                        description=f"Targeted policy guard verifying {pol.name} on {ent.name}"
                    ))
                    b_graph.add_edge(cmd_id, BehaviorRelationType.REQUIRES_GUARD, guard_id, inference_rule="targeted_policy_binding")

            # Audit Side Effect for State-Changing Commands
            if verb in ["approve", "reject", "override", "sign", "ground", "cancel", "issue"]:
                side_id = f"side_effect_{cmd_id}_audit_log"
                b_graph.add_node(BehaviorNode(
                    id=side_id,
                    name=f"Emit {verb.capitalize()}{ent.name}AuditEvent",
                    behavior_type=BehaviorNodeType.SIDE_EFFECT,
                    actor_id=actor.id,
                    target_entity_id=ent.id,
                    epistemic_status=EpistemicStatus.DERIVED,
                    provenance=ProvenanceKind.STRONGLY_DERIVED,
                    description=f"Audit trail log emitted when {cmd_node.name} occurs"
                ))
                b_graph.add_edge(cmd_id, BehaviorRelationType.EMITS_SIDE_EFFECT, side_id, inference_rule="audit_side_effect_emission")

            # Add Grounded Read Query for Actor
            query_id = f"query_{actor_name}_view_{ent_name}"
            if not b_graph.get_node(query_id):
                b_graph.add_node(BehaviorNode(
                    id=query_id,
                    name=f"{actor.name} View {ent.name}",
                    behavior_type=BehaviorNodeType.QUERY,
                    actor_id=actor.id,
                    target_entity_id=ent.id,
                    epistemic_status=EpistemicStatus.EXPLICIT,
                    provenance=ProvenanceKind.EXPLICIT,
                    description=f"Explicit read query for {actor.name} to view {ent.name}"
                ))
                b_graph.add_edge(actor.id, BehaviorRelationType.AUTHORIZED_FOR, query_id, inference_rule="actor_query_authorization")
                b_graph.add_edge(query_id, BehaviorRelationType.TARGETS, ent.id, inference_rule="query_entity_target")

        # 3. Fallback for un-grounded entities (DERIVED capabilities via domain graph topology)
        if not svo_triples:
            for actor in actors:
                actor_name = actor.name.lower().replace(" ", "_")
                for ent in target_entities:
                    ent_name = ent.name.lower().replace(" ", "_")
                    query_id = f"query_{actor_name}_inspect_{ent_name}"
                    b_graph.add_node(BehaviorNode(
                        id=query_id,
                        name=f"{actor.name} Inspect {ent.name}",
                        behavior_type=BehaviorNodeType.QUERY,
                        actor_id=actor.id,
                        target_entity_id=ent.id,
                        epistemic_status=EpistemicStatus.DERIVED,
                        provenance=ProvenanceKind.STRONGLY_DERIVED,
                        confidence=0.85,
                        description=f"Topological read query for {actor.name} to inspect {ent.name}"
                    ))
                    b_graph.add_edge(actor.id, BehaviorRelationType.AUTHORIZED_FOR, query_id, inference_rule="topological_query_derivation")
                    b_graph.add_edge(query_id, BehaviorRelationType.TARGETS, ent.id, inference_rule="query_target_binding")

        return b_graph
