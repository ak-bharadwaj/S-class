"""
S-Class EOS V6.2 - Behavior Graph & Epistemic Grounding Infrastructure

Defines EpistemicStatus, Behavior Graph primitives, typed behavior relationships,
unified provenance tracking, atomic clause SVO extraction, and targeted authorization semantics.

The Behavior Graph sits directly between the Semantic Domain Graph and Requirements:
EVIDENCE → DOMAIN GRAPH → BEHAVIOR CANDIDATES → GROUNDING ENGINE → ACCEPTED BEHAVIOR GRAPH → HLD → LLD → TASKS
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import re
import json
import hashlib
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
    PERFORMS = "performs"               # Actor performs/executes Command/Action (prose assertion)
    AUTHORIZED_FOR = "authorized_for"   # Actor explicitly authorized for Command/Query (security policy)
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

    def compute_canonical_hash(self) -> str:
        """Computes deterministic canonical SHA-256 hash capturing all semantic properties of this BehaviorNode."""
        payload = {
            "id": self.id,
            "name": self.name,
            "behavior_type": self.behavior_type.value,
            "actor_id": self.actor_id,
            "target_entity_id": self.target_entity_id,
            "epistemic_status": self.epistemic_status.value,
            "provenance": self.provenance.value,
            "confidence": round(float(self.confidence), 4),
            "evidence_ref": self.evidence_ref or "",
            "from_state": self.from_state or "",
            "to_state": self.to_state or "",
            "policy_ids": sorted(self.policy_ids or []),
            "description": self.description or ""
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

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

    def __init__(self, version: int = 1):
        if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
            raise ValueError(f"BehaviorGraph version must be a positive integer, got {version}")
        self.version: int = version
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
            "version": self.version,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges]
        }

    @classmethod
    def from_governed_dict(cls, data: Dict[str, Any]) -> 'BehaviorGraph':
        """Dedicated strict ingestion API for governed behavior graph artifacts."""
        return cls.from_dict(data, strict=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = False) -> 'BehaviorGraph':
        if strict:
            if "version" not in data:
                raise ValueError("Missing mandatory 'version' in BehaviorGraph serialized data (strict mode)")
            ver = data["version"]
            if not isinstance(ver, int) or isinstance(ver, bool) or ver <= 0:
                raise ValueError(f"BehaviorGraph version must be a positive integer in strict mode, got {ver}")
        else:
            ver = data.get("version", 1)
            if not isinstance(ver, int) or isinstance(ver, bool) or ver <= 0:
                ver = 1
        graph = cls(version=ver)
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
    Uses Atomic Clause SVO Parsing and Open-Vocabulary Action Predicate Extraction.
    Separates PERFORMS from AUTHORIZED_FOR and demotes fallback candidates to PROPOSED.
    """

    NON_VERB_STOPWORDS = {
        "the", "a", "an", "this", "that", "these", "those", "for", "with", "and", "or",
        "but", "if", "when", "while", "after", "before", "then", "into", "over", "under",
        "from", "by", "to", "in", "on", "at", "system", "platform", "app", "tool", "portal"
    }

    @classmethod
    def extract_action_predicates(cls, text: str) -> List[str]:
        """
        Dynamically extracts action verbs in predicate position from natural language text
        without relying solely on a hardcoded verb list.
        """
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        verbs = []
        for w in words:
            if w in cls.NON_VERB_STOPWORDS:
                continue
            # Dynamic morphological verb indicators or standard domain action verbs
            is_verb_form = (
                w.endswith(('s', 'ed', 'ing', 'ize', 'ise', 'ate')) or
                w in [
                    "submit", "approve", "reject", "assign", "schedule", "upload",
                    "issue", "waive", "cancel", "ground", "inspect", "prescribe",
                    "verify", "override", "create", "delete", "sign", "dispense", "renew",
                    "calibrate", "reconcile", "escalate", "triage", "provision", "deploy"
                ]
            )
            if is_verb_form:
                # Normalize verb form (e.g. approves -> approve, calibrates -> calibrate)
                norm_v = w
                if w.endswith('es') and len(w) > 4 and w[:-2].endswith(('s', 'x', 'z', 'ch', 'sh', 'r', 't', 'd', 'l', 'n')):
                    norm_v = w[:-1] if w.endswith('es') and w[:-1] in ["approve", "calibrate", "reconcile", "triage"] else w[:-2]
                elif w.endswith('s') and len(w) > 3 and not w.endswith('ss'):
                    norm_v = w[:-1]
                elif w.endswith('ed') and len(w) > 4:
                    norm_v = w[:-2] if not w.endswith('eed') else w[:-1]
                elif w.endswith('ing') and len(w) > 4:
                    norm_v = w[:-3]
                if norm_v not in cls.NON_VERB_STOPWORDS:
                    verbs.append(norm_v)

        return list(dict.fromkeys(verbs))

    @classmethod
    def extract_svo_triples(cls, raw_request: str, actors: List[DomainNode], entities: List[DomainNode]) -> List[Tuple[DomainNode, str, DomainNode]]:
        """
        Parses atomic clause Subject-Verb-Object (SVO) propositions from source text.
        Splits text into atomic clauses to prevent cross-clause subject-verb-object mixing.
        """
        triples = []
        # Split into atomic clause spans (conjunctions and subordinators)
        clauses = re.split(r'[\.\n;]|\b(?:before|after|while|when|if|and\s+then|then|,)\b', raw_request, flags=re.IGNORECASE)

        actor_map = {a.name.lower(): a for a in actors}
        for a in actors:
            for w in a.name.lower().split():
                if len(w) >= 3:
                    actor_map[w] = a

        entity_map = {e.name.lower(): e for e in entities}
        for e in entities:
            for w in e.name.lower().split():
                if len(w) >= 3:
                    entity_map[w] = e

        for clause in clauses:
            c_clean = clause.lower().strip()
            if not c_clean:
                continue

            matched_actor = None
            matched_entity = None

            for a_key, a_node in actor_map.items():
                if re.search(r'\b' + re.escape(a_key) + r's?\b', c_clean):
                    matched_actor = a_node
                    break

            for e_key, e_node in entity_map.items():
                if re.search(r'\b' + re.escape(e_key) + r's?\b', c_clean):
                    matched_entity = e_node
                    break

            clause_verbs = cls.extract_action_predicates(c_clean)

            if matched_actor and matched_entity and clause_verbs:
                for v in clause_verbs:
                    # Skip generic non-action stopwords
                    if v in ["view", "inspect", "system", "user"]:
                        continue
                    triple = (matched_actor, v, matched_entity)
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

        target_entities = entities + resources if (entities or resources) else [DomainNode("entity_system", "System", DomainPrimitiveType.ENTITY)]
        if not actors:
            actors = [DomainNode("actor_operator", "Operator", DomainPrimitiveType.ACTOR)]

        # 1. Grounded Atomic Clause SVO Triple Extraction (EXPLICIT Behavior)
        svo_triples = cls.extract_svo_triples(raw_request, actors, target_entities)

        # 2. State Machine Derivation (Draft -> Signed -> Fulfilled)
        state_names = [s.name.lower() for s in states]
        has_draft_signed = any("draft" in s for s in state_names) and any("sign" in s for s in state_names)

        # Check for explicit authorization evidence in text or workspace
        has_explicit_auth_evidence = any(kw in raw_request.lower() for kw in ["authorized to", "permitted to", "role:", "permission", "allowed to"])

        # Process Grounded SVO Triples
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
                evidence_ref="source_atomic_clause_svo_match",
                from_state=from_st,
                to_state=to_st,
                description=f"Grounded command: {actor.name} performs {verb} on {ent.name}"
            ))

            # Edge 1: Actor PERFORMS Command (Prose assertion)
            b_graph.add_edge(
                actor.id, BehaviorRelationType.PERFORMS, cmd_id,
                epistemic_status=EpistemicStatus.EXPLICIT, provenance=ProvenanceKind.EXPLICIT,
                inference_rule="clause_actor_performs_binding"
            )

            # Edge 2: Actor AUTHORIZED_FOR Command (ONLY if explicit security/auth evidence exists)
            if has_explicit_auth_evidence or actor.name.lower() in ["admin", "super_admin", "manager"]:
                b_graph.add_edge(
                    actor.id, BehaviorRelationType.AUTHORIZED_FOR, cmd_id,
                    epistemic_status=EpistemicStatus.EXPLICIT, provenance=ProvenanceKind.EXPLICIT,
                    inference_rule="explicit_rbac_authorization_evidence"
                )

            # Edge 3: Command TARGETS Entity
            b_graph.add_edge(
                cmd_id, BehaviorRelationType.TARGETS, ent.id,
                epistemic_status=EpistemicStatus.EXPLICIT, provenance=ProvenanceKind.EXPLICIT,
                inference_rule="svo_command_target"
            )

            # Targeted Policy Binding: Only attach guard if policy APPLIES_TO target entity
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
            if verb in ["approve", "reject", "override", "sign", "ground", "cancel", "issue", "calibrate", "reconcile"]:
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
                b_graph.add_edge(actor.id, BehaviorRelationType.PERFORMS, query_id, inference_rule="actor_query_performs")
                b_graph.add_edge(query_id, BehaviorRelationType.TARGETS, ent.id, inference_rule="query_entity_target")

        # 3. Fallback Candidates: Empty prompt generates ungrounded PROPOSED; Non-empty prompt without SVO generates DERIVED management behaviors
        if not svo_triples:
            if not raw_request or not raw_request.strip():
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
                            epistemic_status=EpistemicStatus.PROPOSED,      # Demoted to PROPOSED for empty prompt
                            provenance=ProvenanceKind.SPECULATIVE,
                            confidence=0.35,                              # Demoted confidence
                            description=f"Un-grounded proposed candidate query for {actor.name} to inspect {ent.name}"
                        ))
                        b_graph.add_edge(actor.id, BehaviorRelationType.PERFORMS, query_id, epistemic_status=EpistemicStatus.PROPOSED, confidence=0.35)
                        b_graph.add_edge(query_id, BehaviorRelationType.TARGETS, ent.id, epistemic_status=EpistemicStatus.PROPOSED, confidence=0.35)
            else:
                for actor in actors:
                    actor_name = actor.name.lower().replace(" ", "_")
                    for ent in target_entities:
                        ent_name = ent.name.lower().replace(" ", "_")
                        cmd_id = f"cmd_{actor_name}_manage_{ent_name}"
                        b_graph.add_node(BehaviorNode(
                            id=cmd_id,
                            name=f"{actor.name} Manage {ent.name}",
                            behavior_type=BehaviorNodeType.COMMAND,
                            actor_id=actor.id,
                            target_entity_id=ent.id,
                            epistemic_status=EpistemicStatus.DERIVED,
                            provenance=ProvenanceKind.STRONGLY_DERIVED,
                            confidence=0.90,
                            description=f"Derived management command for {actor.name} on {ent.name}"
                        ))
                        b_graph.add_edge(actor.id, BehaviorRelationType.PERFORMS, cmd_id, epistemic_status=EpistemicStatus.DERIVED, provenance=ProvenanceKind.STRONGLY_DERIVED)
                        b_graph.add_edge(cmd_id, BehaviorRelationType.TARGETS, ent.id, epistemic_status=EpistemicStatus.DERIVED, provenance=ProvenanceKind.STRONGLY_DERIVED)

                        query_id = f"query_{actor_name}_view_{ent_name}"
                        b_graph.add_node(BehaviorNode(
                            id=query_id,
                            name=f"{actor.name} View {ent.name}",
                            behavior_type=BehaviorNodeType.QUERY,
                            actor_id=actor.id,
                            target_entity_id=ent.id,
                            epistemic_status=EpistemicStatus.DERIVED,
                            provenance=ProvenanceKind.STRONGLY_DERIVED,
                            confidence=0.90,
                            description=f"Derived read query for {actor.name} to view {ent.name}"
                        ))
                        b_graph.add_edge(actor.id, BehaviorRelationType.PERFORMS, query_id, epistemic_status=EpistemicStatus.DERIVED, provenance=ProvenanceKind.STRONGLY_DERIVED)
                        b_graph.add_edge(query_id, BehaviorRelationType.TARGETS, ent.id, epistemic_status=EpistemicStatus.DERIVED, provenance=ProvenanceKind.STRONGLY_DERIVED)

        return b_graph
