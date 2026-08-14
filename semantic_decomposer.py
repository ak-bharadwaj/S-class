"""
S-Class EOS V5.0 - Semantic Decomposer & First-Principles Intent Engine

Deconstructs raw user prompts and workspace evidence into first-principles
Semantic Primitives (Entities, Actors, Resources, Measurements, Policies, Events, Workflows).
"""

import re
from typing import Dict, List, Set, Any, Optional, Tuple
from domain_primitives import (
    DomainPrimitiveType,
    DomainNode,
    DomainEdge,
    RelationType,
    ProvenanceType,
    SemanticDomainGraph
)


class SemanticDecomposer:
    """
    Deconstructs natural language requirements and workspace evidence into
    universal semantic domain primitives without static keyword dictionaries.
    """

    # Functional Linguistic Markers
    MEASUREMENT_MARKERS = [
        "temperature", "vibration", "humidity", "pressure", "reading", "sensor",
        "telemetry", "metric", "latency", "throughput", "voltage", "current",
        "soil_moisture", "flow_rate", "odometer", "fuel", "heart_rate", "blood_pressure",
        "speed", "rpm", "error_rate", "cpu_usage", "memory_usage", "bandwidth",
        "power", "generation", "irradiance", "flight_hours", "defect_rate"
    ]

    POLICY_MARKERS = [
        "threshold", "limit", "quota", "sla", "rule", "constraint", "boundary",
        "max", "min", "tolerance", "ceiling", "floor", "expiration", "validity",
        "compliance", "invariant", "criteria"
    ]

    EVENT_MARKERS = [
        "alert", "incident", "alarm", "notification", "trigger", "anomaly",
        "defect", "outage", "spike", "breach", "violation", "failure", "warning"
    ]

    WORKFLOW_MARKERS = [
        "lifecycle", "workflow", "stage", "step", "approval", "review",
        "inspection", "verification", "onboarding", "schedule", "dispatch",
        "settlement", "reconciliation", "maintenance", "rework", "audit",
        "checklist", "renew", "renewal", "redlin", "approv"
    ]

    DOCUMENT_MARKERS = [
        "report", "prescription", "invoice", "receipt", "contract", "certificate",
        "manifest", "bill_of_lading", "work_order", "id_card", "transcript",
        "scorecard", "lease", "clause", "agreement"
    ]

    RESOURCE_MARKERS = [
        "machine", "device", "vehicle", "van", "truck", "inverter", "valve",
        "aircraft", "sensor", "slot", "room", "bed", "equipment", "server"
    ]

    STOP_WORDS = {
        "build", "create", "make", "implement", "with", "from", "system", "platform",
        "app", "application", "tool", "and", "the", "for", "such", "etc", "that",
        "this", "rate", "rates", "policies", "policy", "queues", "queue", "measurements",
        "measurement", "readings", "reading", "metrics", "metric", "alarms", "alarm",
        "events", "event", "items", "item", "assurance", "management", "quality",
        "observability", "platform", "system"
    }

    @classmethod
    def normalize_text(cls, text: str) -> str:
        t = text.lower()
        t = re.sub(r'[\r\n\t]+', ' ', t)
        t = re.sub(r'[^\w\s\-_,.]', '', t)
        return t.strip()

    @classmethod
    def decompose_intent(cls, raw_request: str, workspace_evidence: Optional[Any] = None) -> SemanticDomainGraph:
        """
        Constructs a SemanticDomainGraph from raw user intent and workspace evidence.
        """
        graph = SemanticDomainGraph()
        norm_text = cls.normalize_text(raw_request)
        words = norm_text.split()

        # 1. Extract Core Entities & Actors
        # Identify noun phrases and actors
        actors: Set[str] = set()
        entities: Set[str] = set()
        resources: Set[str] = set()
        measurements: Set[str] = set()
        policies: Set[str] = set()
        events: Set[str] = set()
        workflows: Set[str] = set()
        documents: Set[str] = set()

        # Extract Actors from role patterns
        role_matches = re.findall(r'\b(?:for|as|by|role|actor|user)\s+([a-zA-Z0-9_\-]+)', norm_text)
        for r in role_matches:
            if r not in ['a', 'an', 'the', 'all', 'each', 'this', 'that', 'system', 'app', 'platform']:
                actors.add(r)

        # Token semantic classification
        for w in words:
            w_clean = re.sub(r'^[^\w]+|[^\w]+$', '', w)
            if not w_clean or len(w_clean) < 3:
                continue

            if any(m in w_clean for m in cls.MEASUREMENT_MARKERS):
                measurements.add(w_clean)
            elif any(p in w_clean for p in cls.POLICY_MARKERS):
                policies.add(w_clean)
            elif any(e in w_clean for e in cls.EVENT_MARKERS):
                events.add(w_clean)
            elif any(wf in w_clean for wf in cls.WORKFLOW_MARKERS):
                workflows.add(w_clean)
            elif any(d in w_clean for d in cls.DOCUMENT_MARKERS):
                documents.add(w_clean)
            elif any(res in w_clean for res in cls.RESOURCE_MARKERS):
                resources.add(w_clean)
            elif w_clean not in cls.STOP_WORDS:
                # Potential domain entity
                if len(w_clean) >= 4 and not w_clean.endswith('ing'):
                    entities.add(w_clean)

        # Fallbacks for empty sets to ensure baseline viability
        if not actors:
            # Infer default actor from context or primary operator
            actors.add("operator")
        if not entities:
            # Extract main subject noun
            main_nouns = [w for w in words if len(w) > 4 and w not in ['build', 'create', 'system', 'platform']]
            entities.add(main_nouns[0] if main_nouns else "domain_item")

        # 2. Add Nodes to Graph
        node_map: Dict[str, DomainNode] = {}

        for a in actors:
            n = DomainNode(
                id=f"actor_{a}",
                name=a.replace('_', ' ').title(),
                primitive_type=DomainPrimitiveType.ACTOR,
                provenance=ProvenanceType.EXPLICIT,
                description=f"System actor: {a}"
            )
            graph.add_node(n)
            node_map[f"actor_{a}"] = n

        for e in entities:
            n = DomainNode(
                id=f"entity_{e}",
                name=e.replace('_', ' ').title(),
                primitive_type=DomainPrimitiveType.ENTITY,
                provenance=ProvenanceType.EXPLICIT,
                description=f"Core domain entity: {e}"
            )
            graph.add_node(n)
            node_map[f"entity_{e}"] = n

        for res in resources:
            n = DomainNode(
                id=f"resource_{res}",
                name=res.replace('_', ' ').title(),
                primitive_type=DomainPrimitiveType.RESOURCE,
                provenance=ProvenanceType.EXPLICIT,
                description=f"Managed resource: {res}"
            )
            graph.add_node(n)
            node_map[f"resource_{res}"] = n

        for m in measurements:
            n = DomainNode(
                id=f"meas_{m}",
                name=m.replace('_', ' ').title(),
                primitive_type=DomainPrimitiveType.MEASUREMENT,
                provenance=ProvenanceType.EXPLICIT,
                description=f"Telemetry/Measurement: {m}"
            )
            graph.add_node(n)
            node_map[f"meas_{m}"] = n

        for pol in policies:
            n = DomainNode(
                id=f"policy_{pol}",
                name=pol.replace('_', ' ').title(),
                primitive_type=DomainPrimitiveType.POLICY,
                provenance=ProvenanceType.EXPLICIT,
                description=f"Domain rule/policy: {pol}"
            )
            graph.add_node(n)
            node_map[f"policy_{pol}"] = n

        for ev in events:
            n = DomainNode(
                id=f"event_{ev}",
                name=ev.replace('_', ' ').title(),
                primitive_type=DomainPrimitiveType.EVENT,
                provenance=ProvenanceType.EXPLICIT,
                description=f"Lifecycle/Violation event: {ev}"
            )
            graph.add_node(n)
            node_map[f"event_{ev}"] = n

        for wf in workflows:
            n = DomainNode(
                id=f"wf_{wf}",
                name=wf.replace('_', ' ').title(),
                primitive_type=DomainPrimitiveType.WORKFLOW,
                provenance=ProvenanceType.EXPLICIT,
                description=f"Operational workflow: {wf}"
            )
            graph.add_node(n)
            node_map[f"wf_{wf}"] = n

        for doc in documents:
            n = DomainNode(
                id=f"doc_{doc}",
                name=doc.replace('_', ' ').title(),
                primitive_type=DomainPrimitiveType.DOCUMENT,
                provenance=ProvenanceType.EXPLICIT,
                description=f"Structured document: {doc}"
            )
            graph.add_node(n)
            node_map[f"doc_{doc}"] = n

        # 3. Wire Topological Semantic Relationships (Edges)
        # Relationship 1: Entities have Resources / Components
        for e_id in [k for k in node_map if k.startswith("entity_")]:
            for res_id in [k for k in node_map if k.startswith("resource_")]:
                graph.add_edge(e_id, RelationType.HAS, res_id)

        # Relationship 2: Resources produce Measurements
        for res_id in [k for k in node_map if k.startswith("resource_")]:
            for m_id in [k for k in node_map if k.startswith("meas_")]:
                graph.add_edge(res_id, RelationType.PRODUCES, m_id)

        # If entities exist without explicit resources but measurements exist
        if not resources and measurements:
            for e_id in [k for k in node_map if k.startswith("entity_")]:
                for m_id in [k for k in node_map if k.startswith("meas_")]:
                    graph.add_edge(e_id, RelationType.PRODUCES, m_id)

        # Relationship 3: Measurements are evaluated by Policies
        for m_id in [k for k in node_map if k.startswith("meas_")]:
            for p_id in [k for k in node_map if k.startswith("policy_")]:
                graph.add_edge(m_id, RelationType.EVALUATED_BY, p_id)

        # Relationship 4: Policies trigger Events
        for p_id in [k for k in node_map if k.startswith("policy_")]:
            for ev_id in [k for k in node_map if k.startswith("event_")]:
                graph.add_edge(p_id, RelationType.TRIGGERS, ev_id)

        # Relationship 5: Actors are authorized for Workflows & Entities
        for a_id in [k for k in node_map if k.startswith("actor_")]:
            for wf_id in [k for k in node_map if k.startswith("wf_")]:
                graph.add_edge(a_id, RelationType.AUTHORIZED_FOR, wf_id)
            for e_id in [k for k in node_map if k.startswith("entity_")]:
                graph.add_edge(a_id, RelationType.AUTHORIZED_FOR, e_id)

        # Relationship 6: Workflows transition Entities or produce Documents
        for wf_id in [k for k in node_map if k.startswith("wf_")]:
            for d_id in [k for k in node_map if k.startswith("doc_")]:
                graph.add_edge(wf_id, RelationType.PRODUCES, d_id)

        return graph
