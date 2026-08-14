"""
S-Class EOS V5.0 - Graph Inference Engine & Specification Compiler

Operates over the SemanticDomainGraph to:
1. Infer required UI components, data structures, and REST APIs from graph topology.
2. Compile the domain graph into actor-scoped page spreads, LLD requirements, and API specs.
3. Compute structured reasoning graphs (why_graph) for every inferred item.
"""

import os
import re
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
from behavior_graph import (
    BehaviorGraphEngine,
    BehaviorGraph,
    BehaviorNodeType,
    BehaviorRelationType,
    EpistemicStatus
)

UNCOUNTABLE_OR_PLURAL = {
    "alumni": "alumni",
    "alumnus": "alumni",
    "data": "data",
    "equipment": "equipment",
    "staff": "staff",
    "telemetry": "telemetry",
    "metadata": "metadata",
    "media": "media",
    "criteria": "criteria",
    "info": "info",
    "information": "information",
    "content": "content",
    "feedback": "feedback",
    "research": "research",
    "person": "people"
}

def _plural(name: str) -> str:
    cleaned = name.strip().lower()
    if cleaned in UNCOUNTABLE_OR_PLURAL:
        return UNCOUNTABLE_OR_PLURAL[cleaned]
    if cleaned.endswith('y') and len(cleaned) > 2 and cleaned[-2] not in 'aeiou':
        return f"{cleaned[:-1]}ies"
    if cleaned.endswith('s') or cleaned.endswith('x') or cleaned.endswith('z') or cleaned.endswith('ch') or cleaned.endswith('sh'):
        if cleaned.endswith('s'):
            return cleaned
        return f"{cleaned}es"
    return f"{cleaned}s"


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
                    f"GET /api/{_plural(doc.id.replace('doc_', ''))}",
                    f"POST /api/{_plural(doc.id.replace('doc_', ''))}",
                    f"GET /api/{_plural(doc.id.replace('doc_', ''))}/{{id}}",
                    f"POST /api/{_plural(doc.id.replace('doc_', ''))}/{{id}}/sign"
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
                    f"GET /api/{_plural(res.id.replace('resource_', ''))}",
                    f"POST /api/{_plural(res.id.replace('resource_', ''))}",
                    f"GET /api/{_plural(res.id.replace('resource_', ''))}/{{id}}/health"
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
                    f"GET /api/{_plural(ent.id.replace('entity_', ''))}",
                    f"POST /api/{_plural(ent.id.replace('entity_', ''))}",
                    f"GET /api/{_plural(ent.id.replace('entity_', ''))}/{{id}}",
                    f"PUT /api/{_plural(ent.id.replace('entity_', ''))}/{{id}}"
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
    def compile_specification(
        cls,
        graph: SemanticDomainGraph,
        intent_features: List[str],
        archetypes: Optional[List[str]] = None,
        evidence: Optional[Any] = None,
        intent: Optional[Any] = None
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
        capabilities, assumptions = GraphInferenceEngine.infer_domain_capabilities(graph)

        # Merge target roles from intent extraction into domain graph actors
        if intent and getattr(intent, "target_roles", None):
            for role_name in intent.target_roles:
                if role_name and role_name not in ["operator"]:
                    node_id = f"actor_{role_name.lower().replace(' ', '_')}"
                    if not graph.get_node(node_id):
                        graph.add_node(DomainNode(
                            id=node_id,
                            name=role_name.replace('_', ' ').title(),
                            primitive_type=DomainPrimitiveType.ACTOR,
                            provenance=ProvenanceType.EXPLICIT,
                            description=f"Extracted target role: {role_name}"
                        ))

        # Merge any explicit roles from workspace evidence
        if evidence and getattr(evidence, "auth_permissions", None):
            for perm in evidence.auth_permissions:
                if perm and perm not in ["operator"]:
                    node_id = f"actor_{perm.lower()}"
                    if not graph.get_node(node_id):
                        graph.add_node(DomainNode(
                            id=node_id,
                            name=perm.replace('_', ' ').title(),
                            primitive_type=DomainPrimitiveType.ACTOR,
                            provenance=ProvenanceType.EXPLICIT,
                            description=f"Explicit workspace actor: {perm}"
                        ))

        # Construct BehaviorGraph and enforce Grounding Engine Epistemic Filter
        raw_text = intent.raw_request if (intent and getattr(intent, "raw_request", None)) else " ".join(intent_features)
        b_graph = BehaviorGraphEngine.build_behavior_graph(graph, raw_text)

        actors = graph.get_nodes_by_type(DomainPrimitiveType.ACTOR)

        page_spreads: Dict[str, List[Dict[str, Any]]] = {}
        low_level_designs: Dict[str, Dict[str, Any]] = {}

        is_pure_cli = bool(archetypes and "cli_tool" in archetypes and not any(a in ["fullstack", "web_frontend", "mobile_hybrid"] for a in archetypes))

        # Build lookup of explicit routes from workspace evidence
        explicit_routes = getattr(evidence, "api_routes", []) if evidence else []

        for actor in actors:
            actor_key = actor.name.lower().replace(' ', '_')
            pages: List[Dict[str, Any]] = []

            # Retrieve only ACCEPTED behavior nodes for actor (suppressing PROPOSED behaviors)
            accepted_cmds = b_graph.get_accepted_commands_for_actor(actor.id)
            accepted_queries = b_graph.get_accepted_queries_for_actor(actor.id)

            if is_pure_cli:
                # Compile CLI Subcommand & Flag Catalog instead of Web UI
                cli_actions = [f"cmd_{f.lower().replace(' ', '_')}" for f in intent_features if len(f.split()) <= 3]
                if not cli_actions:
                    cli_actions = ["init", "diff", "push", "status", "config"]

                pages.append({
                    "route": "cli://subcommands",
                    "page_name": f"{actor.name} CLI Command Dispatcher",
                    "module_key": "cli_dispatcher",
                    "description": f"CLI command suite and subcommands for {actor.name}"
                })
                low_level_designs[f"{actor_key}:cli://subcommands"] = {
                    "role": actor_key,
                    "page_name": f"{actor.name} CLI Command Suite",
                    "route": "cli://subcommands",
                    "layout": "cli_subcommand_dispatch",
                    "sub_components": ["ArgParser", "SubcommandRouter", "ConfigLoader", "ExitCodeHandler"],
                    "tabs": [
                        {
                            "name": "Subcommand Catalog",
                            "fields": ["subcommandName (string)", "arguments (list)", "flags (list)", "exitCode (integer)"],
                            "actions": cli_actions
                        }
                    ],
                    "api_endpoints": [],
                    "validation_rules": [
                        "CLI arguments must adhere to POSIX flag standards",
                        "Exit codes: 0 for success, 1 for runtime error, 2 for invalid usage"
                    ],
                    "reasoning_graph": [{"from": actor.id, "relation": "executes", "to": "CLI Subcommand Suite"}]
                }
                page_spreads[actor_key] = pages
                continue

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

                # Match explicit routes matching capability module_key
                explicit_matching = []
                mod_stem = cap['module_key'].replace('entity_', '').replace('wf_', '').replace('doc_', '').replace('resource_', '').lower()
                for er in explicit_routes:
                    path = er.get("path", "")
                    method = er.get("method", "")
                    path_tokens = [t.lower() for t in re.split(r'[/_\-]', path) if t and not t.startswith('{') and not t.startswith(':')]
                    if mod_stem in path_tokens or any(t.startswith(mod_stem) or mod_stem.startswith(t) for t in path_tokens if len(t) >= 4):
                        ep_str = f"{method} {path}"
                        if ep_str not in explicit_matching:
                            explicit_matching.append(ep_str)

                if explicit_matching:
                    endpoints = explicit_matching
                else:
                    endpoints = list(cap["api_endpoints"])

                # Register in LLD Catalog
                lld_key = f"{actor_key}:{route_path}"
                low_level_designs[lld_key] = {
                    "role": actor_key,
                    "page_name": cap["title"],
                    "route": route_path,
                    "layout": cap["layout"],
                    "sub_components": cap["sub_components"],
                    "tabs": cap["tabs"],
                    "api_endpoints": endpoints,
                    "validation_rules": cap["validation_rules"],
                    "reasoning_graph": cap.get("reasoning_graph", [])
                }

            # 3. Identity Profile & Security
            actor_singular = _plural(actor_key).rstrip('s')
            explicit_profile_matching = []
            for er in explicit_routes:
                path = er.get("path", "")
                method = er.get("method", "")
                path_lower = path.lower()
                if "profile" in path_lower or "password" in path_lower:
                    if actor_key in path_lower or actor_singular in path_lower or "/profile" in path_lower or "/password" in path_lower:
                        ep_str = f"{method} {path}"
                        if ep_str not in explicit_profile_matching:
                            explicit_profile_matching.append(ep_str)

            profile_endpoints = explicit_profile_matching if explicit_profile_matching else [
                "GET /api/account/profile",
                "PUT /api/account/profile",
                "PUT /api/auth/password"
            ]

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
                        "actions": ["Update Profile", "Change Password", "Terminate Active Sessions"]
                    }
                ],
                "api_endpoints": profile_endpoints,
                "validation_rules": [
                    "Email must be verified before self-update",
                    "Password update requires current password verification"
                ],
                "reasoning_graph": [{"from": actor.id, "relation": "owns", "to": "Personal Profile & Security"}]
            }

            page_spreads[actor_key] = pages

        # 4. Guarantee preservation of all explicit documented route groups from workspace
        if not is_pure_cli and explicit_routes and actors:
            for er in explicit_routes:
                path = er.get("path", "")
                method = er.get("method", "")
                tokens = [t.lower() for t in re.split(r'[/_\-]', path) if t and not t.startswith('{') and not t.startswith(':')]
                if tokens:
                    primary_entity = tokens[0]
                    if primary_entity not in ["api", "v1", "v2", "public", "account", "auth"]:
                        route_path = f"/{primary_entity}"
                        for actor in actors:
                            actor_key = actor.name.lower().replace(' ', '_')
                            lld_key = f"{actor_key}:{route_path}"
                            if lld_key not in low_level_designs:
                                title = f"{primary_entity.replace('_', ' ').title()} Domain Workspace"
                                low_level_designs[lld_key] = {
                                    "role": actor_key,
                                    "page_name": title,
                                    "route": route_path,
                                    "layout": "master_detail_grid",
                                    "sub_components": [f"{primary_entity.title()}DataGrid", f"{primary_entity.title()}Inspector"],
                                    "tabs": [{"name": "Overview", "fields": ["id (string)"], "actions": ["Manage"]}],
                                    "api_endpoints": [f"{method} {path}"],
                                    "validation_rules": [f"Validate {primary_entity} authorization contracts"],
                                    "reasoning_graph": [{"from": actor.id, "relation": "manages", "to": primary_entity}]
                                }
                                pages = page_spreads.get(actor_key, [])
                                if not any(p.get("route") == route_path for p in pages):
                                    pages.append({
                                        "route": route_path,
                                        "page_name": title,
                                        "module_key": primary_entity,
                                        "description": f"Domain interface for {primary_entity}"
                                    })
                            else:
                                ep_str = f"{method} {path}"
                                if ep_str not in low_level_designs[lld_key]["api_endpoints"]:
                                    low_level_designs[lld_key]["api_endpoints"].append(ep_str)

        return page_spreads, low_level_designs, [a.to_dict() for a in assumptions]

    @classmethod
    def compile_v7_refinement_pipeline(
        cls,
        graph: SemanticDomainGraph,
        intent_features: List[str],
        raw_request: str = "",
        archetypes: Optional[List[str]] = None,
        workspace_dir: Optional[str] = None,
        is_debate_phase: bool = False
    ) -> Dict[str, Any]:
        """
        V7/V9 Authoritative Architecture Refinement Pipeline:
        Semantic Domain -> Behavior Graph -> Requirement IR -> HLD + ADRs -> V9 Debate -> Artifact Governance -> LLD -> Tasks
        """
        from behavior_graph import BehaviorGraphEngine
        from requirement_ir import RequirementGraph
        from hld_compiler import HLDCompiler, HLDValidator
        from lld_compiler import LLDCompiler
        from task_compiler import TaskCompiler

        # 1. Behavior Graph Construction
        b_graph = BehaviorGraphEngine.build_behavior_graph(graph, raw_request or " ".join(intent_features))

        # 2. Requirement IR Graph Construction
        r_graph = RequirementGraph.compile_from_behavior_graph(b_graph)
        dep_holes = r_graph.detect_dependency_holes()

        # 3. High-Level Design (HLD) & ADR Compilation
        hld = HLDCompiler.compile_hld(r_graph, b_graph, raw_request=raw_request)

        # 4a. HLD Validation Gate
        passed_hld, hld_errors = HLDValidator.validate_hld(hld, r_graph, b_graph)

        # 4b. V9 Architecture Debate & Decision Intelligence Engine Audit
        from architecture_debate import ArchitectureDebateEngine
        debate_result = ArchitectureDebateEngine.run_debate_cycle(hld, r_graph, b_graph, raw_request=raw_request, workspace_dir=workspace_dir, is_debate_phase=is_debate_phase)

        # 4c. Artifact Governor HLD Control Plane Audit (Hard Execution Gate)
        from artifact_governor import ArtifactGovernor
        hld_gov = ArtifactGovernor.audit_hld_governance(hld, passed_hld, hld_errors, workspace_dir=workspace_dir)

        # 5. Low-Level Design (LLD) Refinement Compilation
        lld_components = LLDCompiler.compile_lld(hld, r_graph, b_graph, archetypes=archetypes)
        if workspace_dir and os.path.exists(workspace_dir):
            from spec_synthesis import WorkspaceDocumentScanner
            ev_disc = WorkspaceDocumentScanner.full_document_discovery(workspace_dir)
            if ev_disc and ev_disc.api_routes:
                for r_item in ev_disc.api_routes:
                    r_ep = f"{r_item.get('method', 'GET')} {r_item.get('path', '')}"
                    if lld_components and r_ep not in lld_components[0].api_endpoints:
                        lld_components[0].api_endpoints.append(r_ep)

        if hld_gov.is_blocked:
            return {
                "behavior_graph": b_graph,
                "requirement_graph": r_graph,
                "dependency_holes": dep_holes,
                "hld_design": hld,
                "hld_validation": {"passed": passed_hld, "errors": hld_errors},
                "debate_result": debate_result.to_dict(),
                "hld_governance": hld_gov.to_dict(),
                "lld_components": [],
                "lld_governance": {"is_blocked": True, "blocking_reasons": ["HLD compilation blocked by Artifact Governor"]},
                "tasks": [],
                "task_governance": {"is_blocked": True, "blocking_reasons": ["HLD compilation blocked by Artifact Governor"]},
                "blocked": True,
                "target_fsm_state": hld_gov.recommended_fsm_state.value
            }
        lld_components = LLDCompiler.compile_lld(hld, r_graph, b_graph, archetypes=archetypes)
        lld_gov = ArtifactGovernor.audit_lld_governance(lld_components, hld)

        if lld_gov.is_blocked:
            return {
                "behavior_graph": b_graph,
                "requirement_graph": r_graph,
                "dependency_holes": dep_holes,
                "hld_design": hld,
                "hld_validation": {"passed": passed_hld, "errors": hld_errors},
                "debate_result": debate_result.to_dict(),
                "hld_governance": hld_gov.to_dict(),
                "lld_components": lld_components,
                "lld_governance": lld_gov.to_dict(),
                "tasks": [],
                "task_governance": {"is_blocked": True, "blocking_reasons": ["LLD compilation blocked by Artifact Governor"]},
                "blocked": True,
                "target_fsm_state": lld_gov.recommended_fsm_state.value
            }

        # 6. Task Compilation with Full Lineage and BDD Contracts
        tasks = TaskCompiler.compile_tasks(lld_components, r_graph=r_graph, b_graph=b_graph)
        task_gov = ArtifactGovernor.audit_task_governance(tasks, r_graph)

        return {
            "behavior_graph": b_graph,
            "requirement_graph": r_graph,
            "dependency_holes": dep_holes,
            "hld_design": hld,
            "hld_validation": {"passed": passed_hld, "errors": hld_errors},
            "debate_result": debate_result.to_dict(),
            "hld_governance": hld_gov.to_dict(),
            "lld_components": lld_components,
            "lld_governance": lld_gov.to_dict(),
            "tasks": tasks,
            "task_governance": task_gov.to_dict(),
            "blocked": task_gov.is_blocked,
            "target_fsm_state": task_gov.recommended_fsm_state.value
        }

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

