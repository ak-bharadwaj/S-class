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
            "reasoning_graph": self.reasoning_graph
        }


class LLDCompiler:
    """Compiles HLDDesign, RequirementGraph, and BehaviorGraph into architecture-specific LLD components."""

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
                    matching_reqs = [r.id for r in r_graph.nodes.values() if b_node.id in r.source_behaviors]
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
                        ep = f"POST /api/{ent_stem}s/{{id}}/{verb_noun}" if b_node.behavior_type != BehaviorNodeType.QUERY else f"GET /api/{ent_stem}s/{{id}}"

                    if ep not in mod_endpoints:
                        mod_endpoints.append(ep)

            if not mod_endpoints:
                for ent in (mod.owned_entities or ["core"]):
                    ent_s = ent.lower()
                    if exec_arch == ExecutionArchitecture.CLI_DISPATCHER:
                        mod_endpoints.extend([f"cli://manage-{ent_s}", f"cli://list-{ent_s}"])
                    else:
                        mod_endpoints.extend([f"GET /api/{ent_s}s", f"POST /api/{ent_s}s", f"GET /api/{ent_s}s/{{id}}", f"PUT /api/{ent_s}s/{{id}}"])

            parent_ref = LLDParentRef(
                hld_id=mod.id,
                req_ids=list(set(mod_reqs)),
                behavior_ids=list(set(mod_behaviors))
            )

            # Execution-Architecture Specific Component Generation
            if exec_arch == ExecutionArchitecture.CLI_DISPATCHER:
                lld_components.append(LLDComponent(
                    id=f"cli_{mod.id}",
                    name=f"{mod.name} CLI Command Suite",
                    component_type=LLDComponentType.CLI_DISPATCHER,
                    parent=parent_ref,
                    role="cli_dispatcher",
                    transport=InteractionTransport.CLI_COMMAND,
                    route="cli://subcommands",
                    sub_components=["ArgParser", "SubcommandRouter", "ConfigLoader", "ExitCodeHandler"],
                    api_endpoints=mod_endpoints,
                    validation_rules=["POSIX flag compliance", "Exit code 0 for success, 1 for error, 2 for usage failure"]
                ))

            elif exec_arch == ExecutionArchitecture.DATA_PIPELINE_WORKER:
                lld_components.append(LLDComponent(
                    id=f"pipe_{mod.id}",
                    name=f"{mod.name} Pipeline Stage Worker",
                    component_type=LLDComponentType.PIPELINE_WORKER,
                    parent=parent_ref,
                    role="pipeline_worker",
                    transport=InteractionTransport.EVENT_TOPIC,
                    sub_components=["StreamConsumer", "StageTransformer", "BatchSink"],
                    api_endpoints=mod_endpoints,
                    validation_rules=["At-least-once stream processing", "Dead-letter queue on schema error"]
                ))

            elif exec_arch == ExecutionArchitecture.EVENT_DRIVEN_MICROSERVICE:
                lld_components.append(LLDComponent(
                    id=f"event_{mod.id}",
                    name=f"{mod.name} Event Handler Service",
                    component_type=LLDComponentType.EVENT_HANDLER,
                    parent=parent_ref,
                    role="event_handler",
                    transport=InteractionTransport.EVENT_TOPIC,
                    sub_components=["KafkaMessageConsumer", "DomainEventHandler", "OutboxPublisher"],
                    api_endpoints=mod_endpoints,
                    validation_rules=["Idempotent message handling", "Transactional outbox commitment"]
                ))

            else:
                # FULLSTACK_APP / BACKEND_SERVICE
                lld_components.append(LLDComponent(
                    id=f"ctrl_{mod.id}",
                    name=f"{mod.name} Controller",
                    component_type=LLDComponentType.CONTROLLER,
                    parent=parent_ref,
                    role="backend_controller",
                    transport=InteractionTransport.REST_HTTP,
                    route=f"/api/{mod.owned_entities[0].lower() if mod.owned_entities else 'core'}s",
                    api_endpoints=mod_endpoints,
                    validation_rules=["Verify actor authorization", "Validate request payload schema"]
                ))

                lld_components.append(LLDComponent(
                    id=f"svc_{mod.id}",
                    name=f"{mod.name} Service Layer",
                    component_type=LLDComponentType.SERVICE,
                    parent=parent_ref,
                    role="domain_service",
                    transport=InteractionTransport.INTERNAL_FUNCTION,
                    sub_components=[f"{mod.name}TransactionManager", f"{mod.name}PolicyEvaluator"],
                    validation_rules=["Enforce state pre/post transitions", "Emit audit log side effects"]
                ))

                if exec_arch == ExecutionArchitecture.FULLSTACK_APP:
                    ent_stem = mod.owned_entities[0].capitalize() if mod.owned_entities else "Item"
                    lld_components.append(LLDComponent(
                        id=f"ui_{mod.id}",
                        name=f"{ent_stem} Workflow Interface",
                        component_type=LLDComponentType.UI_SURFACE,
                        parent=parent_ref,
                        role="frontend_interface",
                        transport=InteractionTransport.REST_HTTP,
                        route=f"/{ent_stem.lower()}s",
                        layout="behavioral_workflow_surface",
                        sub_components=[f"{ent_stem}DetailHeader", f"{ent_stem}ActionToolbar", f"{ent_stem}AuditHistoryPanel"],
                        api_endpoints=mod_endpoints,
                        validation_rules=["UI actions trigger backend transport contracts"]
                    ))

        return lld_components
