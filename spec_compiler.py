"""
S-Class EOS V5.0 - Graph Inference Engine & Specification Compiler

Operates over the SemanticDomainGraph to:
1. Infer required UI components, data structures, and REST APIs from graph topology.
2. Compile the domain graph into actor-scoped page spreads, LLD requirements, and API specs.
3. Compute structured reasoning graphs (why_graph) for every inferred item.
"""

from typing import Dict, List, Set, Any, Optional, Tuple
from domain_primitives import (
    DomainPrimitiveType,
    DomainNode,
    DomainEdge,
    RelationType,
    ProvenanceType,
    SemanticDomainGraph,
    AssumptionRecord
)


class GraphInferenceEngine:
    """
    Performs compositional multi-hop graph deduction over the SemanticDomainGraph.
    Deduces system behavior from topological primitives (e.g. Measurement -> Policy -> Event).
    """

    @classmethod
    def infer_domain_capabilities(cls, graph: SemanticDomainGraph) -> Tuple[List[Dict[str, Any]], List[AssumptionRecord]]:
        inferred_capabilities = []
        assumptions = []

        # 1. Measurement Monitoring & Telemetry Loop
        # Pattern: (Resource/Entity) -> produces -> (Measurement) -> evaluated_by -> (Policy) -> triggers -> (Event)
        measurements = graph.get_nodes_by_type(DomainPrimitiveType.MEASUREMENT)
        policies = graph.get_nodes_by_type(DomainPrimitiveType.POLICY)
        events = graph.get_nodes_by_type(DomainPrimitiveType.EVENT)

        if measurements:
            meas_names = [m.name for m in measurements]
            pol_names = [p.name for p in policies]
            ev_names = [e.name for e in events]

            reasoning = [
                {"from": "Resource/Entity", "relation": "produces", "to": f"Measurements: {', '.join(meas_names)}"}
            ]
            if policies:
                reasoning.append({"from": "Measurements", "relation": "evaluated_by", "to": f"Policies: {', '.join(pol_names)}"})
            if events:
                reasoning.append({"from": "Policies", "relation": "triggers", "to": f"Events: {', '.join(ev_names)}"})

            inferred_capabilities.append({
                "module_key": "telemetry_monitoring",
                "title": "Real-Time Telemetry & Monitoring Hub",
                "layout": "telemetry_dashboard",
                "sub_components": [
                    "TelemetryTimeSeriesChart",
                    "MetricThresholdConfigDrawer",
                    "LiveReadingStatGrid",
                    "ActiveAlertBanner",
                    "TelemetryDataExporter"
                ],
                "tabs": [
                    {
                        "name": "Live Metrics & Signals",
                        "fields": [f"{m.id}_currentValue (number)" for m in measurements] + ["sampleTimestamp (datetime)", "signalStatus (badge)"],
                        "actions": ["Refresh Telemetry Stream", "Export Metric Time-Series CSV", "Configure Alert Threshold"]
                    },
                    {
                        "name": "Threshold Policies",
                        "fields": [f"{p.id}_limitValue (number)" for p in policies] or ["upperThresholdLimit (number)", "lowerThresholdLimit (number)", "evaluationWindowSeconds (number)"],
                        "actions": ["Save Policy Rules", "Simulate Trigger Test"]
                    }
                ],
                "api_endpoints": [
                    "GET /api/telemetry/readings",
                    "POST /api/telemetry/ingest",
                    "GET /api/telemetry/thresholds",
                    "PUT /api/telemetry/thresholds"
                ],
                "validation_rules": [
                    "Telemetry values must conform to valid physical measurement range",
                    "Threshold violation must dispatch event within 500ms"
                ],
                "reasoning_graph": reasoning
            })

            assumptions.append(AssumptionRecord(
                id="ASM-TELEMETRY-01",
                statement="System requires real-time telemetry charting and threshold alerting",
                basis="Domain graph contains Measurement nodes linked to Policies/Events",
                confidence=0.92,
                risk_level="low",
                reversible=True,
                affected_nodes=[m.id for m in measurements]
            ))

        # 2. Workflow & Multi-Stage Lifecycle Execution
        # Pattern: (Workflow) -> contains -> (States) -> authorized_for -> (Actor)
        workflows = graph.get_nodes_by_type(DomainPrimitiveType.WORKFLOW)
        for wf in workflows:
            wf_clean = wf.name.replace(' ', '')
            inferred_capabilities.append({
                "module_key": wf.id,
                "title": f"{wf.name} Workflow & Verification Queue",
                "layout": "multi_stage_queue",
                "sub_components": [
                    f"{wf_clean}StageStepper",
                    f"{wf_clean}InspectionTimeline",
                    f"{wf_clean}VerificationChecklist",
                    "ReviewDecisionDrawer",
                    "AuditHistoryTimeline",
                    "BatchSignOffBar"
                ],
                "tabs": [
                    {
                        "name": "Active Verification Queue",
                        "fields": ["queueItemId (string)", "currentStage (select)", "assignedReviewer (string)", "verificationNotes (text)", "lifecycleStatus (badge)"],
                        "actions": ["Advance Stage", "Reject with Reason", "Batch Sign-Off", "Export Audit Report"]
                    }
                ],
                "api_endpoints": [
                    f"GET /api/{wf.id.replace('wf_', '')}/queue",
                    f"POST /api/{wf.id.replace('wf_', '')}/{{id}}/advance",
                    f"POST /api/{wf.id.replace('wf_', '')}/{{id}}/reject"
                ],
                "validation_rules": [
                    "State transitions require authorized actor verification",
                    "Rejection notes are mandatory when transitioning to rejected state"
                ],
                "reasoning_graph": [
                    {"from": wf.id, "relation": "orchestrates", "to": "Multi-Stage Lifecycle"}
                ]
            })

        # 3. Documents, Records & Invariant Vaults
        documents = graph.get_nodes_by_type(DomainPrimitiveType.DOCUMENT)
        for doc in documents:
            doc_clean = doc.name.replace(' ', '')
            inferred_capabilities.append({
                "module_key": doc.id,
                "title": f"{doc.name} Vault & Lifecycle Board",
                "layout": "document_vault",
                "sub_components": [
                    f"{doc_clean}LifecycleBoard",
                    f"{doc_clean}VersionDiffViewer",
                    f"{doc_clean}RecordSignatoryModal",
                    "DocumentSecurityBadge",
                    "DigitalProofExporter"
                ],
                "tabs": [
                    {
                        "name": f"{doc.name} Registry",
                        "fields": [f"{doc.id}_reference (string)", "signatoryParty (string)", "effectiveDate (date)", "expirationDate (date)", "complianceStatus (badge)"],
                        "actions": [f"Create {doc.name}", f"Upload Signed {doc.name} PDF", f"Initiate Renewal", "Export Archive"]
                    }
                ],
                "api_endpoints": [
                    f"GET /api/{doc.id.replace('doc_', '')}s",
                    f"POST /api/{doc.id.replace('doc_', '')}s",
                    f"GET /api/{doc.id.replace('doc_', '')}s/{{id}}",
                    f"POST /api/{doc.id.replace('doc_', '')}s/{{id}}/sign"
                ],
                "validation_rules": [
                    f"{doc.name} requires certified cryptographic or physical signature verification"
                ],
                "reasoning_graph": [
                    {"from": doc.id, "relation": "requires", "to": "Formal Document Lifecycle & Signature"}
                ]
            })

        # 4. Resources, Physical Fleet & Equipment Matrix
        resources = graph.get_nodes_by_type(DomainPrimitiveType.RESOURCE)
        for res in resources:
            if any(res.id in c["module_key"] for c in inferred_capabilities):
                continue
            res_clean = res.name.replace(' ', '')
            inferred_capabilities.append({
                "module_key": res.id,
                "title": f"{res.name} Fleet & Status Matrix",
                "layout": "resource_matrix",
                "sub_components": [
                    f"{res_clean}StatusMatrix",
                    f"{res_clean}OperationalBadge",
                    f"{res_clean}TelemetryChart",
                    f"{res_clean}MaintenanceTimeline",
                    "AssetLocationDrawer"
                ],
                "tabs": [
                    {
                        "name": f"{res.name} Asset Registry",
                        "fields": [f"{res.id}_serialNumber (string)", "operationalCondition (badge)", "lastInspectionDate (date)", "assignedOperator (string)"],
                        "actions": [f"Register {res.name}", f"Schedule Maintenance", "Log Inspection Defect"]
                    }
                ],
                "api_endpoints": [
                    f"GET /api/{res.id.replace('resource_', '')}s",
                    f"POST /api/{res.id.replace('resource_', '')}s",
                    f"GET /api/{res.id.replace('resource_', '')}s/{{id}}/health"
                ],
                "validation_rules": [
                    f"{res.name} operational status must meet safety compliance thresholds"
                ],
                "reasoning_graph": [
                    {"from": res.id, "relation": "maintains", "to": "Asset Health & Operational Condition"}
                ]
            })

        # 5. Entity Domain Master-Detail Views (Only for core primary business entities)
        entities = graph.get_nodes_by_type(DomainPrimitiveType.ENTITY)
        for ent in entities:
            # Skip if entity is covered by telemetry, workflow, document, or resource
            if any(ent.id in c["module_key"] or ent.name.lower() in c["title"].lower() for c in inferred_capabilities):
                continue

            ent_clean = ent.name.replace(' ', '')
            inferred_capabilities.append({
                "module_key": ent.id,
                "title": f"{ent.name} Domain Workspace",
                "layout": "master_detail_grid",
                "sub_components": [
                    f"{ent_clean}DomainInspector",
                    f"{ent_clean}AttributeMatrix",
                    f"{ent_clean}ActivityTimeline",
                    f"{ent_clean}MetricsHeaderCard",
                    f"{ent_clean}ActionDrawer"
                ],
                "tabs": [
                    {
                        "name": f"{ent.name} Overview",
                        "fields": [f"{ent.id}_identifier (string)", "title / label (string)", "operationalStatus (badge)", "createdDate (datetime)", "assignedActor (string)"],
                        "actions": [f"Create {ent.name}", f"Edit {ent.name}", f"Archive {ent.name}", "Export CSV"]
                    }
                ],
                "api_endpoints": [
                    f"GET /api/{ent.id.replace('entity_', '')}s",
                    f"POST /api/{ent.id.replace('entity_', '')}s",
                    f"GET /api/{ent.id.replace('entity_', '')}s/{{id}}",
                    f"PUT /api/{ent.id.replace('entity_', '')}s/{{id}}"
                ],
                "validation_rules": [
                    f"{ent.name} identifier must be unique"
                ],
                "reasoning_graph": [
                    {"from": ent.id, "relation": "requires", "to": "Domain Workspace & Inspector"}
                ]
            })

        return inferred_capabilities, assumptions


class SpecificationCompiler:
    """
    Compiles the SemanticDomainGraph and inferred capabilities into:
    1. Actor-Scoped Route Sitemaps
    2. Low-Level Design (LLD) Component & Field Specifications
    3. REST API & RBAC Contracts
    """

    @classmethod
    def compile_specification(cls, graph: SemanticDomainGraph, intent_features: List[str]) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
        capabilities, assumptions = GraphInferenceEngine.infer_domain_capabilities(graph)
        actors = graph.get_nodes_by_type(DomainPrimitiveType.ACTOR)

        page_spreads: Dict[str, List[Dict[str, Any]]] = {}
        low_level_designs: Dict[str, Dict[str, Any]] = {}

        for actor in actors:
            actor_key = actor.name.lower().replace(' ', '_')
            pages: List[Dict[str, Any]] = []

            # 1. Actor Operational Dashboard
            pages.append({
                "route": "/dashboard",
                "page_name": f"{actor.name} Operational Dashboard",
                "module_key": "dashboard",
                "description": f"Real-time operational signals, tasks, and status for {actor.name}"
            })

            # 2. Inferred Domain Capabilities
            for cap in capabilities:
                route_path = f"/{cap['module_key'].replace('_', '-')}"
                pages.append({
                    "route": route_path,
                    "page_name": cap["title"],
                    "module_key": cap["module_key"],
                    "description": f"Domain interface for {cap['title']}"
                })

                # Register in LLD Catalog
                lld_key = f"{actor_key}:{route_path}"
                low_level_designs[lld_key] = {
                    "role": actor_key,
                    "page_name": cap["title"],
                    "route": route_path,
                    "layout": cap["layout"],
                    "sub_components": cap["sub_components"],
                    "tabs": cap["tabs"],
                    "api_endpoints": cap["api_endpoints"],
                    "validation_rules": cap["validation_rules"],
                    "reasoning_graph": cap.get("reasoning_graph", [])
                }

            # 3. Identity Profile & Security
            pages.append({
                "route": "/profile",
                "page_name": f"{actor.name} Profile & Security",
                "module_key": "profile",
                "description": f"User credentials, contact details, and session management for {actor.name}"
            })
            low_level_designs[f"{actor_key}:/profile"] = {
                "role": actor_key,
                "page_name": f"{actor.name} Profile & Security",
                "route": "/profile",
                "layout": "tabbed_card_layout",
                "sub_components": ["AvatarUploader", "BioHeaderCard", "PersonalDetailsTab", "SecurityPasswordModal"],
                "tabs": [
                    {
                        "name": "Personal Details",
                        "fields": ["fullName (string)", "emailAddress (email)", "contactPhone (tel)", "roleDesignation (string, read-only)"],
                        "actions": ["Update Profile Info", "Upload Avatar Image"]
                    },
                    {
                        "name": "Security Credentials",
                        "fields": ["currentPassword (password)", "newPassword (password)", "twoFactorAuth (boolean)"],
                        "actions": ["Change Password", "Revoke Active Sessions"]
                    }
                ],
                "api_endpoints": [
                    "GET /api/account/profile",
                    "PUT /api/account/profile",
                    "PUT /api/auth/password"
                ],
                "validation_rules": [
                    "Password must meet complexity requirements"
                ],
                "reasoning_graph": [{"from": actor.id, "relation": "requires", "to": "Identity & Security"}]
            }

            page_spreads[actor_key] = pages

        return page_spreads, low_level_designs, [a.to_dict() for a in assumptions]

    @classmethod
    def synthesize_compiled_lld_requirements(cls, lld_catalog: Dict[str, Dict[str, Any]]) -> List[Any]:
        """
        Converts compiled Low-Level Design (LLD) catalog into explicit/derived SynthesizedRequirements.
        Ensures requirements are grounded directly in the SemanticDomainGraph with evidence.
        """
        from spec_synthesis import (
            SynthesizedRequirement,
            RequirementType,
            RequirementCategory,
            ArtifactAction,
            DecisionThreshold,
            EvidenceReference
        )

        lld_reqs = []
        seen = set()

        for key, lld in lld_catalog.items():
            role = lld["role"]
            page_name = lld["page_name"]
            route = lld["route"]
            dedup_key = f"{role}_{page_name}_{route}".lower()

            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            components_str = ", ".join(lld.get("sub_components", [])[:4])
            why_chain = [
                f"Compiled Low-Level Design expansion for {page_name} ({route})",
                f"Layout architecture: {lld.get('layout')}",
                f"Composed components: {components_str}"
            ]
            if lld.get("reasoning_graph"):
                for step in lld["reasoning_graph"][:2]:
                    why_chain.append(f"Provenance: ({step.get('from')}) -> {step.get('relation')} -> ({step.get('to')})")

            lld_reqs.append(SynthesizedRequirement(
                id=f"REQ-LLD-COMP-{len(lld_reqs) + 1}",
                description=f"[{role.upper()}] {page_name} — UI Component Hierarchy: {components_str}",
                type=RequirementType.DERIVED,
                category=RequirementCategory.UX_DERIVATION,
                action=ArtifactAction.CREATE,
                decision_threshold=DecisionThreshold.AUTO_DECIDE,
                evidence=[EvidenceReference(source_file="domain_graph_compiler", reference_text=f"UI hierarchy for {page_name}")],
                why_chain=why_chain,
                affects=["frontend"],
                assumption_type="ux"
            ))

            for tab in lld.get("tabs", []):
                tab_name = tab.get("name", "Main")
                fields_str = ", ".join(tab.get("fields", [])[:5])
                actions_str = ", ".join(tab.get("actions", [])[:3])
                lld_reqs.append(SynthesizedRequirement(
                    id=f"REQ-LLD-FIELDS-{len(lld_reqs) + 1}",
                    description=f"[{role.upper()}] {page_name} ({tab_name}) — Form Fields: {fields_str} | Actions: {actions_str}",
                    type=RequirementType.DERIVED,
                    category=RequirementCategory.PRODUCT_REQUIREMENT,
                    action=ArtifactAction.CREATE,
                    decision_threshold=DecisionThreshold.AUTO_DECIDE,
                    evidence=[EvidenceReference(source_file="domain_graph_compiler", reference_text=f"Fields for {page_name} -> {tab_name}")],
                    why_chain=[
                        f"Field definitions for {page_name} -> {tab_name}",
                        f"Input fields: {fields_str}",
                        f"Actions: {actions_str}"
                    ],
                    affects=["frontend", "backend"],
                    assumption_type="data"
                ))

            endpoints_str = ", ".join(lld.get("api_endpoints", [])[:3])
            if endpoints_str:
                lld_reqs.append(SynthesizedRequirement(
                    id=f"REQ-LLD-API-{len(lld_reqs) + 1}",
                    description=f"[{role.upper()}] {page_name} — Backing REST APIs: {endpoints_str}",
                    type=RequirementType.DERIVED,
                    category=RequirementCategory.ARCHITECTURAL_CONSTRAINT,
                    action=ArtifactAction.CREATE,
                    decision_threshold=DecisionThreshold.AUTO_DECIDE,
                    evidence=[EvidenceReference(source_file="domain_graph_compiler", reference_text=f"API endpoints for {page_name}")],
                    why_chain=[
                        f"Backing API endpoints for {page_name}",
                        f"Endpoints: {endpoints_str}"
                    ],
                    affects=["backend"],
                    assumption_type="api"
                ))

        return lld_reqs

