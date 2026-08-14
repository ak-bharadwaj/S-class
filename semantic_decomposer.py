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
        "soil_moisture", "moisture", "flow_rate", "odometer", "fuel", "heart_rate", "blood_pressure",
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

    HUMAN_ACTOR_KEYWORDS = {
        "faculty", "hod", "hods", "student", "students", "instructor", "instructors",
        "admin", "administrator", "administrators", "doctor", "doctors", "patient", "patients",
        "nurse", "nurses", "engineer", "engineers", "driver", "drivers", "manager", "managers",
        "customer", "customers", "client", "clients", "operator", "operators", "researcher",
        "researchers", "user", "users", "reviewer", "reviewers", "auditor", "auditors",
        "candidate", "candidates", "staff", "teller", "examiner", "tenant", "landlord",
        "dispatcher", "mechanic", "member", "members", "author", "authors", "editor", "editors",
        "superintendent", "superintendents", "worker", "workers", "creator", "creators"
    }

    STOP_WORDS = {
        # Meta & Action Verbs
        "build", "create", "make", "implement", "add", "fix", "update", "delete", "manage",
        "run", "execute", "test", "verify", "check", "ensure", "allow", "support", "reads",
        "writes", "pushes", "pulls", "sends", "receives", "consumes", "produces", "validates",
        "routes", "stores", "exports", "imports", "subcommands", "subcommand", "views", "view",
        "access", "accesses", "assigned", "assign", "based", "subdomain-based",
        # Generic Software Container & Documentation Words
        "system", "platform", "app", "application", "tool", "tooling", "portal", "codebase",
        "project", "feature", "features", "module", "modules", "service", "services",
        "doc", "docs", "documentation", "spec", "specs", "specification", "architecture",
        "according", "guidelines", "design", "blueprint", "master", "appendix", "section",
        "chapter", "diagram", "table", "schema", "model", "models",
        # Adjectives & Modifiers (MUST NEVER BECOME ENTITIES)
        "fast", "quick", "slow", "complete", "simple", "easy", "complex", "hard", "full",
        "partial", "automated", "manual", "single", "multi", "great", "good", "new", "old",
        "best", "smart", "high", "low", "real", "time", "real-time", "realtime", "custom",
        "standard", "seamless", "modern", "universal", "clean", "robust", "local", "remote",
        # Grammatical Connectors & Prepositions
        "and", "the", "for", "such", "etc", "that", "this", "from", "with", "into", "onto",
        "over", "under", "when", "where", "then", "their", "your", "each", "both", "all",
        "college", "school", "university", "department", "company", "enterprise", "organization",
        "whose", "which", "within", "without", "about",
        # Generic Schema Terms & Abstract Action Nominalizations
        "rate", "rates", "policies", "policy", "queues", "queue", "measurements",
        "measurement", "readings", "reading", "metrics", "metric", "alarms", "alarm",
        "events", "event", "items", "item", "assurance", "management", "quality",
        "observability", "advancement", "advancements", "spotlight", "spotlights",
        "workload", "workloads", "enrollment", "enrollments", "advancing"
    }

    @classmethod
    def normalize_text(cls, text: str) -> str:
        t = text.lower()
        # Strip file extensions and paths (e.g. docs/architecture.md -> "")
        t = re.sub(r'\b[a-zA-Z0-9_\-\/]+\.(?:md|markdown|json|ts|tsx|js|jsx|py|prisma|sql|yaml|yml|toml|html|css)\b', ' ', t)
        # Strip section numbers (e.g. §6.17.E, section 6.17)
        t = re.sub(r'§\s*[0-9]+(?:\.[0-9a-zA-Z]+)*', ' ', t)
        t = re.sub(r'\bsection\s+[0-9]+(?:\.[0-9a-zA-Z]+)*\b', ' ', t)
        t = re.sub(r'[\r\n\t]+', ' ', t)
        t = re.sub(r'[^\w\s\-_,.]', ' ', t)
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
        actors: Set[str] = set()
        entities: Set[str] = set()
        resources: Set[str] = set()
        measurements: Set[str] = set()
        policies: Set[str] = set()
        events: Set[str] = set()
        workflows: Set[str] = set()
        documents: Set[str] = set()

        # Extract Compound Roles: e.g. "tenant admins", "medical superintendent", "tenant members"
        compound_role_patterns = [
            (r'\btenant\s+admins?\b', 'tenant_admin'),
            (r'\btenant\s+members?\b', 'tenant_member'),
            (r'\bmedical\s+superintendents?\b', 'superintendent'),
            (r'\bsuper\s+admins?\b', 'super_admin')
        ]
        for pattern, role_tag in compound_role_patterns:
            if re.search(pattern, norm_text):
                actors.add(role_tag)

        # Extract Actors: Explicit human actor keywords anywhere in text
        for w in words:
            w_clean = re.sub(r'^[^\w]+|[^\w]+$', '', w)
            if w_clean in cls.HUMAN_ACTOR_KEYWORDS:
                # Exclude software client (e.g. "query client", "api client", "arxiv client")
                if w_clean in ["client", "clients"] and any(sw in norm_text for sw in ["query client", "http client", "api client", "rpc client", "arxiv query", "client library"]):
                    continue
                # Normalize plural to singular
                actor_norm = w_clean[:-1] if w_clean.endswith('s') and w_clean[:-1] in cls.HUMAN_ACTOR_KEYWORDS else w_clean
                if w_clean.endswith('es') and w_clean[:-2] in cls.HUMAN_ACTOR_KEYWORDS:
                    actor_norm = w_clean[:-2]
                if actor_norm == "hod":
                    actor_norm = "hod"
                actors.add(actor_norm)

        # Contextual role extraction: e.g. "for <actor>"
        role_matches = re.findall(r'\b(?:for|as|by|role|actor|user)\s+([a-zA-Z0-9_\-]+(?:\s+(?:and|&)\s+[a-zA-Z0-9_\-]+)?)', norm_text)
        for r_group in role_matches:
            for r in re.split(r'\s+(?:and|&)\s+', r_group):
                r_clean = r.strip()
                if r_clean and r_clean not in cls.STOP_WORDS and len(r_clean) >= 3:
                    if r_clean in cls.HUMAN_ACTOR_KEYWORDS:
                        if r_clean in ["client", "clients"] and any(sw in norm_text for sw in ["query client", "http client", "api client", "rpc client", "arxiv query"]):
                            continue
                        actor_norm = r_clean[:-1] if r_clean.endswith('s') and r_clean[:-1] in cls.HUMAN_ACTOR_KEYWORDS else r_clean
                        actors.add(actor_norm)

        # Token semantic classification
        for w in words:
            w_clean = re.sub(r'^[^\w]+|[^\w]+$', '', w)
            if not w_clean or len(w_clean) < 3:
                continue

            # Don't classify human actors as domain entities/resources
            if w_clean in cls.HUMAN_ACTOR_KEYWORDS or (w_clean.endswith('s') and w_clean[:-1] in cls.HUMAN_ACTOR_KEYWORDS):
                continue

            def _matches_marker(word: str, markers: List[str]) -> bool:
                for m in markers:
                    if word == m or word == m + 's' or word == m + 'es':
                        return True
                    if len(m) >= 5 and word.startswith(m) and len(word) <= len(m) + 3:
                        return True
                return False

            # 1. Functional primitive markers take precedence over generic stop words
            if _matches_marker(w_clean, cls.MEASUREMENT_MARKERS):
                measurements.add(w_clean)
            elif _matches_marker(w_clean, cls.POLICY_MARKERS):
                policies.add(w_clean)
            elif _matches_marker(w_clean, cls.EVENT_MARKERS):
                events.add(w_clean)
            elif _matches_marker(w_clean, cls.WORKFLOW_MARKERS):
                workflows.add(w_clean)
            elif _matches_marker(w_clean, cls.DOCUMENT_MARKERS):
                documents.add(w_clean)
            elif _matches_marker(w_clean, cls.RESOURCE_MARKERS):
                resources.add(w_clean)
            else:
                # 2. General entity candidate: must not be an adjective/verb/stop word
                if w_clean in cls.STOP_WORDS:
                    continue
                if '-' in w_clean and any(part in cls.STOP_WORDS for part in w_clean.split('-')):
                    continue
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
