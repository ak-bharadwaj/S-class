"""
S-Class EOS V5.0 - Graph Inference Engine & Specification Compiler

Operates over the SemanticDomainGraph to:
1. Infer required UI components, data structures, and REST APIs from graph topology.
2. Compile the domain graph into actor-scoped page spreads, LLD requirements, and API specs.
3. Compute structured reasoning graphs (why_graph) for every inferred item.
"""

import os
import re
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Set, Any, Optional, Tuple

def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json_atomic(path: str, data: Any) -> None:
    temp_path = f"{path}.tmp.{os.getpid()}"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_path, path)
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
        graph: Optional[SemanticDomainGraph] = None,
        intent_features: Optional[List[str]] = None,
        raw_request: str = "",
        archetypes: Optional[List[str]] = None,
        workspace_dir: Optional[str] = None,
        is_debate_phase: bool = False
    ) -> Dict[str, Any]:
        """
        V7/V9 Authoritative Architecture Refinement Pipeline:
        Semantic Domain -> Behavior Graph -> Requirement IR -> HLD + ADRs -> V9 Debate -> Artifact Governance -> LLD -> Tasks
        """
        if graph is None:
            from spec_synthesis import SemanticDecomposer, WorkspaceDocumentScanner
            evidence = WorkspaceDocumentScanner.full_document_discovery(workspace_dir) if workspace_dir else None
            req_text = raw_request or (" ".join(intent_features) if intent_features else "")
            graph = SemanticDecomposer.decompose_intent(req_text, evidence) if req_text else SemanticDomainGraph()
        if intent_features is None:
            intent_features = [raw_request] if raw_request else []
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
        if debate_result and debate_result.accepted_adrs:
            hld.adrs = debate_result.accepted_adrs

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
            res_dict = {
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
            if workspace_dir:
                cls.save_versioned_pipeline_artifact(res_dict, workspace_dir)
            return res_dict

        lld_components = LLDCompiler.compile_lld(hld, r_graph, b_graph, archetypes=archetypes)
        lld_gov = ArtifactGovernor.audit_lld_governance(lld_components, hld)

        if lld_gov.is_blocked:
            res_dict = {
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
            if workspace_dir:
                cls.save_versioned_pipeline_artifact(res_dict, workspace_dir)
            return res_dict

        # 6. Task Compilation with Full Lineage and BDD Contracts
        tasks = TaskCompiler.compile_tasks(lld_components, r_graph=r_graph, b_graph=b_graph)
        task_gov = ArtifactGovernor.audit_task_governance(tasks, r_graph, lld_components, b_graph, hld_modules=hld.modules)

        # 7. V10 Execution Plan Compilation & Governance Audit
        from execution_plan_compiler import ExecutionPlanCompiler
        execution_plan = None
        plan_gov = None
        if not task_gov.is_blocked and tasks:
            execution_plan = ExecutionPlanCompiler.compile_execution_plan(
                tasks,
                lld_components=lld_components,
                r_graph=r_graph,
                b_graph=b_graph,
                hld=hld
            )
            plan_gov = ArtifactGovernor.audit_execution_plan_governance(
                execution_plan,
                tasks,
                lld_components=lld_components,
                r_graph=r_graph,
                b_graph=b_graph
            )

        repo_snapshot = None
        snap_gov = None
        authorized_changeset = None
        if workspace_dir:
            from repository_snapshot import RepositorySnapshotEngine
            from changeset_ir import AuthorizedChangeSet, AuthorizedFileChange, FileMutationOp
            repo_snapshot = RepositorySnapshotEngine.capture_snapshot(workspace_dir)
            snap_gov = ArtifactGovernor.audit_repository_snapshot_governance(repo_snapshot, repo_root=workspace_dir)

            # 1. Save immutable planning snapshot anchor
            anchor_path = os.path.join(workspace_dir, ".agents", "planning_snapshot.json")
            RepositorySnapshotEngine.save_snapshot(repo_snapshot, anchor_path)

            # 2. Save active repo_snapshot.json baseline pointer
            snap_path = os.path.join(workspace_dir, ".agents", "repo_snapshot.json")
            RepositorySnapshotEngine.save_snapshot(repo_snapshot, snap_path)

        final_blocked = task_gov.is_blocked or (plan_gov.is_blocked if plan_gov else False) or (snap_gov.is_blocked if snap_gov else False)
        if snap_gov and snap_gov.is_blocked:
            recommended_target = snap_gov.recommended_fsm_state.value
        elif plan_gov and plan_gov.is_blocked:
            recommended_target = plan_gov.recommended_fsm_state.value
        else:
            recommended_target = task_gov.recommended_fsm_state.value

        res_dict = {
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
            "execution_plan": execution_plan.to_dict() if execution_plan else None,
            "execution_plan_governance": plan_gov.to_dict() if plan_gov else {},
            "planning_snapshot": repo_snapshot.to_dict() if repo_snapshot else None,
            "authorized_changeset": None,
            "repository_snapshot": repo_snapshot.to_dict() if repo_snapshot else None,
            "repository_snapshot_governance": snap_gov.to_dict() if snap_gov else {},
            "blocked": final_blocked,
            "target_fsm_state": recommended_target
        }

        # V11.2 Engineering World Model Construction & Governance
        world_model = None
        world_model_gov = None
        if workspace_dir and repo_snapshot:
            from world_model_engine import WorldModelEngine
            world_model = WorldModelEngine.build_world_model(
                workspace_dir,
                snapshot=repo_snapshot,
                pipeline_data=res_dict
            )
            world_model_gov = ArtifactGovernor.audit_world_model_governance(world_model, workspace_dir=workspace_dir)
            wm_path = os.path.join(workspace_dir, ".agents", "world_model.json")
            WorldModelEngine.save_world_model(world_model, wm_path)

            res_dict["world_model"] = world_model.to_dict()
            res_dict["world_model_governance"] = world_model_gov.to_dict()

            if world_model_gov.is_blocked:
                res_dict["blocked"] = True

        # Authoritative Execution Chain Sequence:
        # validated pipeline -> save artifact -> lock execution epoch -> derive ChangeSet directly from signed epoch -> persist
        if workspace_dir:
            cls.save_versioned_pipeline_artifact(res_dict, workspace_dir)
            if execution_plan:
                ExecutionPlanCompiler.save_execution_plan(execution_plan, workspace_dir)

            # 1. Authoritative Execution Epoch Locking
            epoch_lock = ArtifactGovernor.lock_pipeline_epoch(workspace_dir)

            # 2. Derive AuthorizedChangeSet directly bound to the exact signed epoch
            if not task_gov.is_blocked and tasks and repo_snapshot:
                source_task_hashes = {}
                for t in tasks:
                    th = getattr(t, "task_spec_hash", None)
                    if not th or not isinstance(th, str) or not th.strip():
                        raise ValueError(
                            f"Cannot compile AuthorizedChangeSet: Task '{getattr(t, 'id', 'UNKNOWN')}' is missing mandatory authoritative 'task_spec_hash'. Synthetic derivation is strictly prohibited."
                        )
                    source_task_hashes[t.id] = th.strip()

                if not execution_plan or not getattr(execution_plan, "plan_hash", None) or not str(execution_plan.plan_hash).strip():
                    raise ValueError("Cannot compile AuthorizedChangeSet: ExecutionPlan is missing or lacks mandatory authoritative 'plan_hash'.")

                source_execution_plan_hash = str(execution_plan.plan_hash).strip()

                authorized_changeset = AuthorizedChangeSet(
                    changeset_id=f"CS-{int(datetime.now(timezone.utc).timestamp())}",
                    source_repository_state_hash=repo_snapshot.repository_state_hash,
                    source_execution_plan_hash=source_execution_plan_hash,
                    source_pipeline_state_hash=epoch_lock["pipeline_canonical_hash"],
                    pipeline_epoch_id=epoch_lock["epoch_id"],
                    source_task_hashes=source_task_hashes,
                    source_snapshot_id=repo_snapshot.snapshot_id
                )
                for t in tasks:
                    t_paths = getattr(t, "target_files", []) or []
                    for p in t_paths:
                        norm_p = p.replace("\\", "/").strip().lstrip("/")
                        op = FileMutationOp.CREATE if norm_p not in repo_snapshot.file_manifest else FileMutationOp.MODIFY
                        if norm_p not in authorized_changeset.authorized_changes:
                            authorized_changeset.add_change(AuthorizedFileChange(
                                file_path=norm_p,
                                operation=op,
                                authorized_by_tasks=[t.id],
                                authorized_by_lld=t.parent_lld,
                                expected_source_file_hash=repo_snapshot.file_manifest[norm_p].file_hash if norm_p in repo_snapshot.file_manifest else None
                            ))
                        else:
                            existing = authorized_changeset.authorized_changes[norm_p]
                            if t.id not in existing.authorized_by_tasks:
                                existing.authorized_by_tasks.append(t.id)

                cs_path = os.path.join(workspace_dir, ".agents", "authorized_changeset.json")
                write_json_atomic(cs_path, authorized_changeset.to_dict())
                res_dict["authorized_changeset"] = authorized_changeset.to_dict()
            else:
                authorized_changeset = None
                cs_path = os.path.join(workspace_dir, ".agents", "authorized_changeset.json")
                if os.path.exists(cs_path):
                    try:
                        os.remove(cs_path)
                    except Exception:
                        pass

        return res_dict

    @classmethod
    def save_versioned_pipeline_artifact(cls, res_pipe: Dict[str, Any], workspace_dir: str) -> str:
        """
        Saves pipeline result into an immutable versioned artifact (v7_refinement_pipeline_v{ver}.json)
        with parent lineage version and hash tracking. Deduplicates identical content so serializing the
        same pipeline state twice does NOT increment version or create duplicate artifact files.
        Enforces hardware mutual exclusion (FileLock) for atomic, concurrency-safe version allocation.
        """
        state_dir = os.path.join(workspace_dir, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        lock_file = os.path.join(state_dir, ".pipeline_version.lock")

        from runtime import FileLock
        with FileLock(lock_file):
            existing_versions = []
            if os.path.exists(state_dir):
                for fname in os.listdir(state_dir):
                    if fname.startswith("v7_refinement_pipeline_v") and fname.endswith(".json"):
                        try:
                            v_num = int(fname.replace("v7_refinement_pipeline_v", "").replace(".json", ""))
                            existing_versions.append(v_num)
                        except ValueError:
                            pass

            current_ver = max(existing_versions) if existing_versions else 0

            # Construct normalized content payload for hashing and comparison
            content_payload = {
                "behavior_graph": res_pipe["behavior_graph"].to_dict() if hasattr(res_pipe["behavior_graph"], "to_dict") else res_pipe["behavior_graph"],
                "requirement_graph": res_pipe["requirement_graph"].to_dict() if hasattr(res_pipe["requirement_graph"], "to_dict") else res_pipe["requirement_graph"],
                "dependency_holes": res_pipe.get("dependency_holes", []),
                "hld_design": res_pipe["hld_design"].to_dict() if hasattr(res_pipe["hld_design"], "to_dict") else res_pipe["hld_design"],
                "hld_validation": res_pipe.get("hld_validation", {}),
                "hld_governance": res_pipe.get("hld_governance", {}),
                "debate_result": res_pipe.get("debate_result", {}),
                "lld_components": [c.to_dict() if hasattr(c, "to_dict") else c for c in res_pipe.get("lld_components", [])],
                "lld_governance": res_pipe.get("lld_governance", {}),
                "tasks": [t.to_dict() if hasattr(t, "to_dict") else t for t in res_pipe.get("tasks", [])],
                "task_governance": res_pipe.get("task_governance", {}),
                "planning_snapshot": res_pipe.get("planning_snapshot"),
                "authorized_changeset": res_pipe.get("authorized_changeset"),
                "world_model": res_pipe.get("world_model"),
                "world_model_governance": res_pipe.get("world_model_governance", {}),
                "repository_snapshot": res_pipe.get("repository_snapshot"),
                "repository_snapshot_governance": res_pipe.get("repository_snapshot_governance", {}),
                "blocked": res_pipe.get("blocked", False)
            }

            new_content_json = json.dumps(content_payload, sort_keys=True)
            new_content_hash = hashlib.sha256(new_content_json.encode("utf-8")).hexdigest()

            # Check if current version file exists and has identical content hash
            if current_ver > 0:
                current_file = os.path.join(state_dir, f"v7_refinement_pipeline_v{current_ver}.json")
                if os.path.exists(current_file):
                    try:
                        with open(current_file, "r", encoding="utf-8") as f:
                            curr_data = json.load(f)
                        curr_content = {k: v for k, v in curr_data.items() if k not in ["version", "parent_version", "parent_hash", "version_file"]}
                        curr_content_json = json.dumps(curr_content, sort_keys=True)
                        curr_content_hash = hashlib.sha256(curr_content_json.encode("utf-8")).hexdigest()
                        if new_content_hash == curr_content_hash:
                            # Deduplication hit — skip creating duplicate version file
                            return current_file
                    except Exception:
                        pass

            next_ver = current_ver + 1
            parent_ver = current_ver if current_ver > 0 else None
            parent_hash = None
            if parent_ver:
                parent_file = os.path.join(state_dir, f"v7_refinement_pipeline_v{parent_ver}.json")
                if os.path.exists(parent_file):
                    try:
                        with open(parent_file, "rb") as pf:
                            parent_hash = hashlib.sha256(pf.read()).hexdigest()
                    except Exception:
                        pass

            payload = dict(content_payload)
            payload["version"] = next_ver
            payload["parent_version"] = parent_ver
            payload["parent_hash"] = parent_hash

            # 1. Immutable versioned successor artifact
            versioned_file = os.path.join(state_dir, f"v7_refinement_pipeline_v{next_ver}.json")
            write_json_atomic(versioned_file, payload)

            # 2. Latest version pointer alias
            alias_file = os.path.join(state_dir, "v7_refinement_pipeline.json")
            payload["version_file"] = f"v7_refinement_pipeline_v{next_ver}.json"
            write_json_atomic(alias_file, payload)

            # 3. Update FSM state version tracking
            try:
                from sclass_state import get_state, save_state
                state = get_state(workspace_dir)
                setattr(state, "currentSpecVersion", next_ver)
                setattr(state, "currentDebateVersion", next_ver)
                save_state(state, workspace_dir)
            except Exception:
                pass

            return versioned_file

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


SpecCompiler = SpecificationCompiler

