"""
S-Class EOS V8.0 - LLD Compiler (Execution Architecture, Multi-Transport Models & Refinement)

Defines:
1. ExecutionArchitecture (FULLSTACK_APP, BACKEND_SERVICE, CLI_DISPATCHER, DATA_PIPELINE_WORKER, EVENT_DRIVEN_MICROSERVICE)
2. InteractionTransport (REST_HTTP, CLI_COMMAND, EVENT_TOPIC, INTERNAL_FUNCTION)
3. LLDParentRef (Parent lineage referencing hld_id, req_ids, and behavior_ids)
4. LLDComponent (Architecture-specific components derived dynamically without boilerplate templates)
5. LLDCompiler (Refinement Compiler deriving component hierarchies and multi-transport interaction models)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import json
import hashlib

from behavior_graph import BehaviorGraph, BehaviorNodeType, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode
from hld_compiler import HLDDesign, HLDModule


class ExecutionArchitecture(str, Enum):
    """Dynamic execution architecture models."""
    FULLSTACK_APP = "fullstack_app"
    BACKEND_SERVICE = "backend_service"
    CLI_DISPATCHER = "cli_dispatcher"
    DATA_PIPELINE_WORKER = "data_pipeline_worker"
    EVENT_DRIVEN_MICROSERVICE = "event_driven_microservice"


class InteractionTransport(str, Enum):
    """Multi-transport interaction contracts."""
    REST_HTTP = "rest_http"
    CLI_COMMAND = "cli_command"
    EVENT_TOPIC = "event_topic"
    INTERNAL_FUNCTION = "internal_function"


class LLDComponentType(str, Enum):
    """Low-level design component types."""
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY = "repository"
    SCHEMA = "schema"
    UI_SURFACE = "ui_surface"
    CLI_DISPATCHER = "cli_dispatcher"
    PIPELINE_WORKER = "pipeline_worker"
    EVENT_HANDLER = "event_handler"


class OperationClass(str, Enum):
    """Formal semantic operation classes."""
    COMMAND_MUTATION = "COMMAND_MUTATION"
    READ_QUERY = "READ_QUERY"
    EVENT_PROCESSING = "EVENT_PROCESSING"
    STATE_TRANSITION = "STATE_TRANSITION"


@dataclass
class CapabilityBinding:
    """Formal binding between Behavior, Requirement, and LLD Component capability responsibility."""
    behavior_id: str
    requirement_ids: List[str]
    operation_class: OperationClass
    target_entity: str
    hld_capability: str
    lld_component_id: str
    allowed_component_types: List[LLDComponentType]
    prohibited_component_roles: List[str] = field(default_factory=list)
    source_behavior_hash: str = ""
    source_requirement_hash: str = ""
    source_hld_hash: str = ""
    source_behavior_graph_version: str = "v1"
    source_requirement_graph_version: str = "v1"
    source_hld_module_id: str = ""
    source_hld_version: int = 1
    binding_hash: str = ""

    def compute_hash(self) -> str:
        """Computes deterministic SHA-256 hash over ALL security-relevant binding fields, source hashes, and source version identities."""
        payload = {
            "behavior_id": self.behavior_id,
            "requirement_ids": sorted(self.requirement_ids),
            "operation_class": self.operation_class.value,
            "target_entity": self.target_entity,
            "hld_capability": self.hld_capability,
            "lld_component_id": self.lld_component_id,
            "allowed_component_types": sorted([ct.value for ct in self.allowed_component_types]),
            "prohibited_component_roles": sorted(self.prohibited_component_roles),
            "source_behavior_hash": self.source_behavior_hash,
            "source_requirement_hash": self.source_requirement_hash,
            "source_hld_hash": self.source_hld_hash,
            "source_behavior_graph_version": self.source_behavior_graph_version,
            "source_requirement_graph_version": self.source_requirement_graph_version,
            "source_hld_module_id": self.source_hld_module_id,
            "source_hld_version": self.source_hld_version
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "behavior_id": self.behavior_id,
            "requirement_ids": self.requirement_ids,
            "operation_class": self.operation_class.value,
            "target_entity": self.target_entity,
            "hld_capability": self.hld_capability,
            "lld_component_id": self.lld_component_id,
            "allowed_component_types": [ct.value for ct in self.allowed_component_types],
            "prohibited_component_roles": self.prohibited_component_roles,
            "source_behavior_hash": self.source_behavior_hash,
            "source_requirement_hash": self.source_requirement_hash,
            "source_hld_hash": self.source_hld_hash,
            "source_behavior_graph_version": self.source_behavior_graph_version,
            "source_requirement_graph_version": self.source_requirement_graph_version,
            "source_hld_module_id": self.source_hld_module_id,
            "source_hld_version": self.source_hld_version,
            "binding_hash": self.binding_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = True) -> 'CapabilityBinding':
        if strict:
            if not data.get("behavior_id"):
                raise ValueError("Missing mandatory 'behavior_id' in CapabilityBinding serialized data")
            if not data.get("lld_component_id"):
                raise ValueError("Missing mandatory 'lld_component_id' in CapabilityBinding serialized data")
            if "operation_class" not in data or not data["operation_class"]:
                raise ValueError("Missing mandatory 'operation_class' in CapabilityBinding serialized data (ZERO DEFAULT TOLERATED)")

        op_raw = data.get("operation_class")
        if not op_raw:
            raise ValueError("Missing mandatory 'operation_class' in CapabilityBinding serialized data")
        try:
            op_cls = OperationClass(op_raw)
        except (ValueError, KeyError):
            raise ValueError(f"Invalid 'operation_class' '{op_raw}' in CapabilityBinding serialized data")

        return cls(
            behavior_id=data.get("behavior_id", ""),
            requirement_ids=list(data.get("requirement_ids", [])),
            operation_class=op_cls,
            target_entity=data.get("target_entity", ""),
            hld_capability=data.get("hld_capability", ""),
            lld_component_id=data.get("lld_component_id", ""),
            allowed_component_types=[LLDComponentType(ct) for ct in data.get("allowed_component_types", [])],
            prohibited_component_roles=list(data.get("prohibited_component_roles", [])),
            source_behavior_hash=data.get("source_behavior_hash", ""),
            source_requirement_hash=data.get("source_requirement_hash", ""),
            source_hld_hash=data.get("source_hld_hash", ""),
            source_behavior_graph_version=data.get("source_behavior_graph_version", ""),
            source_requirement_graph_version=data.get("source_requirement_graph_version", ""),
            source_hld_module_id=data.get("source_hld_module_id", ""),
            source_hld_version=int(data.get("source_hld_version", 0)),
            binding_hash=data.get("binding_hash", "")
        )


@dataclass
class LLDParentRef:
    """Upstream parent lineage links establishing 100% change propagation traceability."""
    hld_id: str
    req_ids: List[str]
    behavior_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hld_id": self.hld_id,
            "req_ids": self.req_ids,
            "behavior_ids": self.behavior_ids
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLDParentRef':
        return cls(
            hld_id=data.get("hld_id", "HLD-001"),
            req_ids=data.get("req_ids", []),
            behavior_ids=data.get("behavior_ids", [])
        )


@dataclass
class LLDComponent:
    """A detailed low-level design component derived strictly from HLD and Grounded Behaviors."""
    id: str
    name: str
    component_type: LLDComponentType
    parent: LLDParentRef
    role: str
    transport: InteractionTransport = InteractionTransport.REST_HTTP
    route: Optional[str] = None
    layout: str = "standard_view"
    sub_components: List[str] = field(default_factory=list)
    api_endpoints: List[str] = field(default_factory=list)
    validation_rules: List[str] = field(default_factory=list)
    reasoning_graph: List[Dict[str, Any]] = field(default_factory=list)
    allowed_operation_classes: List[OperationClass] = field(default_factory=list)
    owned_entities: List[str] = field(default_factory=list)
    owned_capabilities: List[str] = field(default_factory=list)
    capability_bindings: List[CapabilityBinding] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "component_type": self.component_type.value,
            "parent": self.parent.to_dict(),
            "role": self.role,
            "transport": self.transport.value,
            "route": self.route,
            "layout": self.layout,
            "sub_components": self.sub_components,
            "api_endpoints": self.api_endpoints,
            "validation_rules": self.validation_rules,
            "reasoning_graph": self.reasoning_graph,
            "allowed_operation_classes": [oc.value for oc in self.allowed_operation_classes],
            "owned_entities": self.owned_entities,
            "owned_capabilities": self.owned_capabilities,
            "capability_bindings": [cb.to_dict() for cb in self.capability_bindings]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLDComponent':
        return cls(
            id=data["id"],
            name=data["name"],
            component_type=LLDComponentType(data["component_type"]),
            parent=LLDParentRef.from_dict(data["parent"]) if isinstance(data.get("parent"), dict) else data["parent"],
            role=data.get("role", "component"),
            transport=InteractionTransport(data.get("transport", InteractionTransport.REST_HTTP.value)),
            route=data.get("route"),
            layout=data.get("layout", "standard_view"),
            sub_components=list(data.get("sub_components", [])),
            api_endpoints=list(data.get("api_endpoints", [])),
            validation_rules=list(data.get("validation_rules", [])),
            reasoning_graph=list(data.get("reasoning_graph", [])),
            allowed_operation_classes=[OperationClass(oc) for oc in data.get("allowed_operation_classes", [])],
            owned_entities=list(data.get("owned_entities", [])),
            owned_capabilities=list(data.get("owned_capabilities", [])),
            capability_bindings=[CapabilityBinding.from_dict(cb) for cb in data.get("capability_bindings", [])]
        )


class LLDCompiler:
    """Compiles HLDDesign, RequirementGraph, and BehaviorGraph into architecture-specific LLD components."""

    @classmethod
    def build_capability_bindings_for_component(
        cls,
        behavior_ids: List[str],
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph,
        mod: HLDModule,
        comp_id: str,
        comp_type: LLDComponentType,
        comp_role: str,
        comp_layout: str = "standard_view"
    ) -> List[CapabilityBinding]:
        """Derives exact, component-specific CapabilityBindings matching HLD capability semantics and allowed types."""
        bindings: List[CapabilityBinding] = []
        for b_id in behavior_ids:
            b_node = b_graph.get_node(b_id)
            if not b_node:
                continue

            if b_node.behavior_type == BehaviorNodeType.COMMAND:
                op_class = OperationClass.COMMAND_MUTATION
            elif b_node.behavior_type == BehaviorNodeType.QUERY:
                op_class = OperationClass.READ_QUERY
            elif b_node.behavior_type == BehaviorNodeType.SIDE_EFFECT:
                op_class = OperationClass.EVENT_PROCESSING
            elif b_node.behavior_type == BehaviorNodeType.STATE_TRANSITION:
                op_class = OperationClass.STATE_TRANSITION
            else:
                # Unknown / unclassified BehaviorNodeType -> DO NOT default to STATE_TRANSITION! Skip to fail closed.
                continue

            # Exact matching requirement IDs
            matching_req_ids = [r.id for r in r_graph.nodes.values() if b_node.id in getattr(r, "source_behaviors", [])]

            # Exact HLD capability: must be an owned_capability from mod that matches requirement capability or behavior stem.
            # ZERO UNGROUNDED FALLBACKS (NO substring matching, NO defaulting to mod.owned_capabilities[0] or b_node.id)!
            req_caps = [r.capability for r in r_graph.nodes.values() if b_node.id in getattr(r, "source_behaviors", []) and r.capability in mod.owned_capabilities]
            if req_caps:
                exact_hld_cap = req_caps[0]
            elif b_node.id in mod.owned_capabilities:
                exact_hld_cap = b_node.id
            else:
                exact_hld_cap = ""

            # Precise allowed component types & prohibited roles per OperationClass
            if op_class == OperationClass.COMMAND_MUTATION:
                allowed_types = [LLDComponentType.CONTROLLER, LLDComponentType.SERVICE, LLDComponentType.UI_SURFACE, LLDComponentType.CLI_DISPATCHER]
                prohibited_roles = ["read_model", "query_service", "read_only_view", "audit_viewer", "pipeline_worker", "event_handler"]
            elif op_class == OperationClass.READ_QUERY:
                allowed_types = [LLDComponentType.CONTROLLER, LLDComponentType.SERVICE, LLDComponentType.UI_SURFACE, LLDComponentType.CLI_DISPATCHER]
                prohibited_roles = ["pipeline_worker", "event_handler", "batch_sink"]
            elif op_class == OperationClass.EVENT_PROCESSING:
                allowed_types = [LLDComponentType.EVENT_HANDLER, LLDComponentType.PIPELINE_WORKER, LLDComponentType.SERVICE]
                prohibited_roles = ["read_only_view", "read_model", "ui_surface", "backend_controller", "cli_dispatcher"]
            else:  # STATE_TRANSITION
                allowed_types = [LLDComponentType.SERVICE, LLDComponentType.EVENT_HANDLER, LLDComponentType.CONTROLLER, LLDComponentType.CLI_DISPATCHER, LLDComponentType.PIPELINE_WORKER]
                prohibited_roles = ["read_only_view", "read_model", "query_service", "audit_viewer"]

            # If UI surface has a passive/read-only layout or role, it is prohibited from COMMAND_MUTATION
            passive_layouts = {"read_only", "query_view", "dashboard_view", "telemetry_view", "inspector_view", "viewer"}
            passive_roles = {"read_only_view", "read_model", "dashboard_viewer", "audit_viewer", "telemetry_viewer", "query_service"}
            if comp_type == LLDComponentType.UI_SURFACE and op_class == OperationClass.COMMAND_MUTATION and (comp_layout in passive_layouts or comp_role in passive_roles):
                prohibited_roles.append(comp_role or "frontend_interface")

            # Source artifact / graph integrity hashes establishing upstream provenance
            source_beh_hash = b_node.compute_canonical_hash()

            matching_req_nodes = [r for r in r_graph.nodes.values() if b_node.id in getattr(r, "source_behaviors", [])]
            req_payload = {
                "behavior_id": b_node.id,
                "requirement_hashes": sorted([r.canonical_hash() for r in matching_req_nodes])
            }
            source_req_hash = hashlib.sha256(json.dumps(req_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

            source_hld_hash = mod.compute_canonical_hash()

            b_graph_ver = str(getattr(b_graph, "version", "1"))
            r_graph_ver = str(getattr(r_graph, "version", "1"))
            hld_ver = int(getattr(mod, "version", 1))

            b_binding = CapabilityBinding(
                behavior_id=b_id,
                requirement_ids=matching_req_ids,
                operation_class=op_class,
                target_entity=b_node.target_entity_id,
                hld_capability=exact_hld_cap,
                lld_component_id=comp_id,
                allowed_component_types=allowed_types,
                prohibited_component_roles=prohibited_roles,
                source_behavior_hash=source_beh_hash,
                source_requirement_hash=source_req_hash,
                source_hld_hash=source_hld_hash,
                source_behavior_graph_version=b_graph_ver,
                source_requirement_graph_version=r_graph_ver,
                source_hld_module_id=mod.id,
                source_hld_version=hld_ver,
                binding_hash=""
            )
            b_binding.binding_hash = b_binding.compute_hash()
            bindings.append(b_binding)
        return bindings

    @classmethod
    def determine_execution_architecture(cls, archetypes: Optional[List[Any]], hld: HLDDesign) -> ExecutionArchitecture:
        arch_set = set((a.value if hasattr(a, "value") else str(a)).lower() for a in (archetypes or []))
        if "cli_tool" in arch_set:
            return ExecutionArchitecture.CLI_DISPATCHER
        if "data_pipeline" in arch_set:
            return ExecutionArchitecture.DATA_PIPELINE_WORKER
        if "microservice" in arch_set or "Microservices" in hld.architecture_style:
            return ExecutionArchitecture.EVENT_DRIVEN_MICROSERVICE
        if "backend_api" in arch_set:
            return ExecutionArchitecture.BACKEND_SERVICE
        return ExecutionArchitecture.FULLSTACK_APP

    @classmethod
    def compile_lld(
        cls,
        hld: HLDDesign,
        r_graph: RequirementGraph,
        b_graph: BehaviorGraph,
        archetypes: Optional[List[str]] = None
    ) -> List[LLDComponent]:
        lld_components: List[LLDComponent] = []
        exec_arch = cls.determine_execution_architecture(archetypes, hld)

        for mod in hld.modules:
            mod_endpoints = []
            mod_behaviors = []
            mod_reqs = []

            for cap in mod.owned_capabilities:
                b_node = b_graph.get_node(cap)
                if b_node and b_node.epistemic_status in [EpistemicStatus.EXPLICIT, EpistemicStatus.OBSERVED, EpistemicStatus.DERIVED, EpistemicStatus.CONFIRMED]:
                    mod_behaviors.append(b_node.id)
                    matching_reqs = [r.id for r in r_graph.nodes.values() if b_node.id in r.source_behaviors or r.capability == cap or r.target in mod.owned_entities]
                    mod_reqs.extend(matching_reqs)

                    tokens = b_node.name.split()
                    verb = tokens[1].lower() if len(tokens) > 1 else "action"
                    ent_stem = b_node.target_entity_id.replace("entity_", "").lower()

                    VERB_TO_NOUN = {
                        "waive": "waivers",
                        "waives": "waivers",
                        "borrow": "loans",
                        "borrows": "loans",
                        "block": "restrictions",
                        "blocks": "restrictions",
                        "accrue": "accruals",
                        "accrues": "accruals",
                        "paid": "payments",
                        "paids": "payments",
                        "further": "extensions",
                        "furthers": "extensions",
                        "daily": "schedules",
                        "dailies": "schedules"
                    }
                    verb_noun = VERB_TO_NOUN.get(verb, verb)
                    if exec_arch == ExecutionArchitecture.CLI_DISPATCHER:
                        ep = f"cli://{verb}-{ent_stem}"
                    elif exec_arch in [ExecutionArchitecture.DATA_PIPELINE_WORKER, ExecutionArchitecture.EVENT_DRIVEN_MICROSERVICE]:
                        ep = f"event://{ent_stem}-events/{verb}"
                    else:
                        IRREGULAR_PLURALS = {
                            "alumni": "alumni", "alumnus": "alumni", "staff": "staff", "faculty": "faculty",
                            "data": "data", "equipment": "equipment", "telemetry": "telemetry", "category": "categories"
                        }
                        if ent_stem in IRREGULAR_PLURALS:
                            ent_plural = IRREGULAR_PLURALS[ent_stem]
                        elif ent_stem.endswith('s') or ent_stem.endswith('ss'):
                            ent_plural = ent_stem
                        elif ent_stem.endswith('y') and len(ent_stem) > 2 and ent_stem[-2] not in 'aeiou':
                            ent_plural = f"{ent_stem[:-1]}ies"
                        else:
                            ent_plural = f"{ent_stem}s"
                        ep = f"POST /api/{ent_plural}/{{id}}/{verb_noun}" if b_node.behavior_type != BehaviorNodeType.QUERY else f"GET /api/{ent_plural}/{{id}}"

                    if ep not in mod_endpoints:
                        mod_endpoints.append(ep)

            if not mod_endpoints:
                mod_endpoints.append("PROPOSED_CANDIDATE: NO_ENDPOINT_EVIDENCE")

            sorted_behaviors = sorted(list(set(mod_behaviors)))
            sorted_reqs = sorted(list(set(mod_reqs)))

            parent_ref = LLDParentRef(
                hld_id=mod.id,
                req_ids=sorted_reqs,
                behavior_ids=sorted_behaviors
            )

            # Execution-Architecture Specific Component Generation with exact component-bound CapabilityBindings
            if exec_arch == ExecutionArchitecture.CLI_DISPATCHER:
                comp_id = f"cli_{mod.id}"
                cli_endpoints = [ep for ep in mod_endpoints if "PROPOSED_CANDIDATE" not in ep]
                bindings = cls.build_capability_bindings_for_component(
                    sorted_behaviors, r_graph, b_graph, mod, comp_id, LLDComponentType.CLI_DISPATCHER, "cli_dispatcher", "cli_subcommand_dispatch"
                )
                lld_components.append(LLDComponent(
                    id=comp_id,
                    name=f"{mod.name} CLI Command Suite",
                    component_type=LLDComponentType.CLI_DISPATCHER,
                    parent=parent_ref,
                    role="cli_dispatcher",
                    transport=InteractionTransport.CLI_COMMAND,
                    route="cli://subcommands",
                    layout="cli_subcommand_dispatch",
                    sub_components=["ArgParser", "SubcommandRouter", "ConfigLoader", "ExitCodeHandler"],
                    api_endpoints=cli_endpoints,
                    validation_rules=["POSIX flag compliance", "Exit code 0 for success, 1 for error, 2 for usage failure"],
                    allowed_operation_classes=[OperationClass.COMMAND_MUTATION, OperationClass.READ_QUERY, OperationClass.STATE_TRANSITION],
                    owned_entities=list(mod.owned_entities),
                    owned_capabilities=list(mod.owned_capabilities),
                    capability_bindings=bindings
                ))

            elif exec_arch == ExecutionArchitecture.DATA_PIPELINE_WORKER:
                comp_id = f"pipe_{mod.id}"
                bindings = cls.build_capability_bindings_for_component(
                    sorted_behaviors, r_graph, b_graph, mod, comp_id, LLDComponentType.PIPELINE_WORKER, "pipeline_worker"
                )
                lld_components.append(LLDComponent(
                    id=comp_id,
                    name=f"{mod.name} Pipeline Stage Worker",
                    component_type=LLDComponentType.PIPELINE_WORKER,
                    parent=parent_ref,
                    role="pipeline_worker",
                    transport=InteractionTransport.EVENT_TOPIC,
                    sub_components=["StreamConsumer", "StageTransformer", "BatchSink"],
                    api_endpoints=mod_endpoints,
                    validation_rules=["At-least-once stream processing", "Dead-letter queue on schema error"],
                    allowed_operation_classes=[OperationClass.EVENT_PROCESSING, OperationClass.STATE_TRANSITION],
                    owned_entities=list(mod.owned_entities),
                    owned_capabilities=list(mod.owned_capabilities),
                    capability_bindings=bindings
                ))

            elif exec_arch == ExecutionArchitecture.EVENT_DRIVEN_MICROSERVICE:
                comp_id = f"event_{mod.id}"
                bindings = cls.build_capability_bindings_for_component(
                    sorted_behaviors, r_graph, b_graph, mod, comp_id, LLDComponentType.EVENT_HANDLER, "event_handler"
                )
                lld_components.append(LLDComponent(
                    id=comp_id,
                    name=f"{mod.name} Event Handler Service",
                    component_type=LLDComponentType.EVENT_HANDLER,
                    parent=parent_ref,
                    role="event_handler",
                    transport=InteractionTransport.EVENT_TOPIC,
                    sub_components=["KafkaMessageConsumer", "DomainEventHandler", "OutboxPublisher"],
                    api_endpoints=mod_endpoints,
                    validation_rules=["Idempotent message handling", "Transactional outbox commitment"],
                    allowed_operation_classes=[OperationClass.EVENT_PROCESSING, OperationClass.STATE_TRANSITION],
                    owned_entities=list(mod.owned_entities),
                    owned_capabilities=list(mod.owned_capabilities),
                    capability_bindings=bindings
                ))

            else:
                # FULLSTACK_APP / BACKEND_SERVICE
                ent_raw = mod.owned_entities[0] if mod.owned_entities else 'core'
                p_ent = ent_raw.lower()
                IRREGULAR_PLURALS = {
                    "alumni": "alumni", "alumnus": "alumni", "staff": "staff", "faculty": "faculty",
                    "data": "data", "equipment": "equipment", "telemetry": "telemetry", "category": "categories"
                }
                if p_ent in IRREGULAR_PLURALS:
                    p_route = IRREGULAR_PLURALS[p_ent]
                elif p_ent.endswith('s') or p_ent.endswith('ss'):
                    p_route = p_ent
                elif p_ent.endswith('y') and len(p_ent) > 2 and p_ent[-2] not in 'aeiou':
                    p_route = f"{p_ent[:-1]}ies"
                else:
                    p_route = f"{p_ent}s"

                ctrl_id = f"ctrl_{mod.id}"
                ctrl_bindings = cls.build_capability_bindings_for_component(
                    sorted_behaviors, r_graph, b_graph, mod, ctrl_id, LLDComponentType.CONTROLLER, "backend_controller"
                )
                lld_components.append(LLDComponent(
                    id=ctrl_id,
                    name=f"{mod.name} Controller",
                    component_type=LLDComponentType.CONTROLLER,
                    parent=parent_ref,
                    role="backend_controller",
                    transport=InteractionTransport.REST_HTTP,
                    route=f"/api/{p_route}",
                    api_endpoints=mod_endpoints,
                    validation_rules=["Verify actor authorization", "Validate request payload schema"],
                    allowed_operation_classes=[OperationClass.COMMAND_MUTATION, OperationClass.READ_QUERY, OperationClass.STATE_TRANSITION],
                    owned_entities=list(mod.owned_entities),
                    owned_capabilities=list(mod.owned_capabilities),
                    capability_bindings=ctrl_bindings
                ))

                svc_id = f"svc_{mod.id}"
                svc_bindings = cls.build_capability_bindings_for_component(
                    sorted_behaviors, r_graph, b_graph, mod, svc_id, LLDComponentType.SERVICE, "domain_service"
                )
                lld_components.append(LLDComponent(
                    id=svc_id,
                    name=f"{mod.name} Service Layer",
                    component_type=LLDComponentType.SERVICE,
                    parent=parent_ref,
                    role="domain_service",
                    transport=InteractionTransport.INTERNAL_FUNCTION,
                    sub_components=[f"{mod.name}TransactionManager", f"{mod.name}PolicyEvaluator"],
                    validation_rules=["Enforce state pre/post transitions", "Emit audit log side effects"],
                    allowed_operation_classes=[OperationClass.COMMAND_MUTATION, OperationClass.READ_QUERY, OperationClass.STATE_TRANSITION, OperationClass.EVENT_PROCESSING],
                    owned_entities=list(mod.owned_entities),
                    owned_capabilities=list(mod.owned_capabilities),
                    capability_bindings=svc_bindings
                ))

                if exec_arch == ExecutionArchitecture.FULLSTACK_APP:
                    ent_stem = mod.owned_entities[0].capitalize() if mod.owned_entities else "Item"
                    stem_clean = ent_stem.lower()
                    if stem_clean in IRREGULAR_PLURALS:
                        ui_route = IRREGULAR_PLURALS[stem_clean]
                    elif stem_clean.endswith('s') or stem_clean.endswith('ss'):
                        ui_route = stem_clean
                    elif stem_clean.endswith('y') and len(stem_clean) > 2 and stem_clean[-2] not in 'aeiou':
                        ui_route = f"{stem_clean[:-1]}ies"
                    else:
                        ui_route = f"{stem_clean}s"

                    ui_id = f"ui_{mod.id}"
                    ui_bindings = cls.build_capability_bindings_for_component(
                        sorted_behaviors, r_graph, b_graph, mod, ui_id, LLDComponentType.UI_SURFACE, "frontend_interface", "behavioral_workflow_surface"
                    )
                    lld_components.append(LLDComponent(
                        id=ui_id,
                        name=f"{ent_stem} Workflow Interface",
                        component_type=LLDComponentType.UI_SURFACE,
                        parent=parent_ref,
                        role="frontend_interface",
                        transport=InteractionTransport.REST_HTTP,
                        route=f"/{ui_route}",
                        layout="behavioral_workflow_surface",
                        sub_components=[f"{ent_stem}DetailHeader", f"{ent_stem}ActionToolbar", f"{ent_stem}AuditHistoryPanel"],
                        api_endpoints=mod_endpoints,
                        validation_rules=["UI actions trigger backend transport contracts"],
                        allowed_operation_classes=[OperationClass.COMMAND_MUTATION, OperationClass.READ_QUERY],
                        owned_entities=list(mod.owned_entities),
                        owned_capabilities=list(mod.owned_capabilities),
                        capability_bindings=ui_bindings
                    ))

        return lld_components
