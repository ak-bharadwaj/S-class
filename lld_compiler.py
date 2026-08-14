"""
S-Class EOS V7.0 - LLD Compiler (Pure Refinement, Parent Lineage & Behavior-Derived UI/APIs)

Defines:
1. LLDParentRef (Parent lineage referencing hld_id, req_ids, and behavior_ids)
2. LLDComponent (Controllers, Services, Repositories, Schemas, and UI Surfaces)
3. LLDCompiler (Refinement Compiler deriving behavior UI and REST routes while enforcing Refinement Gate)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import json

from behavior_graph import BehaviorGraph, BehaviorNodeType, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode
from hld_compiler import HLDDesign, HLDModule


class LLDComponentType(str, Enum):
    """Low-level design component types."""
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY = "repository"
    SCHEMA = "schema"
    UI_SURFACE = "ui_surface"


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
            "route": self.route,
            "layout": self.layout,
            "sub_components": self.sub_components,
            "api_endpoints": self.api_endpoints,
            "validation_rules": self.validation_rules,
            "reasoning_graph": self.reasoning_graph
        }


class LLDCompiler:
    """Compiles HLDDesign, RequirementGraph, and BehaviorGraph into LLD components as pure refinement."""

    @classmethod
    def compile_lld(cls, hld: HLDDesign, r_graph: RequirementGraph, b_graph: BehaviorGraph) -> List[LLDComponent]:
        lld_components: List[LLDComponent] = []

        for mod in hld.modules:
            # 1. Compile Controller & REST endpoints derived from behavior capabilities
            mod_endpoints = []
            mod_behaviors = []
            mod_reqs = []

            for cap in mod.owned_capabilities:
                b_node = b_graph.get_node(cap)
                if b_node and b_node.epistemic_status in [EpistemicStatus.EXPLICIT, EpistemicStatus.OBSERVED, EpistemicStatus.DERIVED, EpistemicStatus.CONFIRMED]:
                    mod_behaviors.append(b_node.id)

                    # Find requirements sourcing this behavior
                    matching_reqs = [r.id for r in r_graph.nodes.values() if b_node.id in r.source_behaviors]
                    mod_reqs.extend(matching_reqs)

                    # Derive REST API route from verb and entity lifecycle
                    verb = b_node.name.split()[1].lower() if len(b_node.name.split()) > 1 else "action"
                    ent_stem = b_node.target_entity_id.replace("entity_", "").lower()

                    if verb in ["approve", "sign", "ground", "cancel", "override", "dispense", "calibrate", "reconcile"]:
                        ep = f"POST /api/{ent_stem}s/{{id}}/{verb}"
                    elif verb in ["create", "submit", "issue"]:
                        ep = f"POST /api/{ent_stem}s"
                    elif verb in ["view", "inspect"]:
                        ep = f"GET /api/{ent_stem}s/{{id}}"
                    else:
                        ep = f"POST /api/{ent_stem}s/{{id}}/{verb}"

                    if ep not in mod_endpoints:
                        mod_endpoints.append(ep)

            parent_ref = LLDParentRef(
                hld_id=mod.id,
                req_ids=list(set(mod_reqs)),
                behavior_ids=list(set(mod_behaviors))
            )

            # Controller LLD Component
            ctrl_id = f"ctrl_{mod.id}"
            lld_components.append(LLDComponent(
                id=ctrl_id,
                name=f"{mod.name} Controller",
                component_type=LLDComponentType.CONTROLLER,
                parent=parent_ref,
                role="backend_controller",
                route=f"/api/{mod.owned_entities[0].lower() if mod.owned_entities else 'core'}s",
                api_endpoints=mod_endpoints,
                validation_rules=["Verify actor capability authorization", "Validate request payload schema"]
            ))

            # Service LLD Component
            svc_id = f"svc_{mod.id}"
            lld_components.append(LLDComponent(
                id=svc_id,
                name=f"{mod.name} Service Layer",
                component_type=LLDComponentType.SERVICE,
                parent=parent_ref,
                role="domain_service",
                sub_components=[f"{mod.name}TransactionManager", f"{mod.name}PolicyEvaluator"],
                validation_rules=["Enforce state machine pre/post transitions", "Emit mandatory audit log side effects"]
            ))

            # 2. Behavior-Derived UI Surface (NOT generic CRUD)
            ui_id = f"ui_{mod.id}"
            ent_stem = mod.owned_entities[0].capitalize() if mod.owned_entities else "Item"
            lld_components.append(LLDComponent(
                id=ui_id,
                name=f"{ent_stem} Workflow Interface",
                component_type=LLDComponentType.UI_SURFACE,
                parent=parent_ref,
                role="frontend_interface",
                route=f"/{ent_stem.lower()}s",
                layout="behavioral_workflow_surface",
                sub_components=[f"{ent_stem}DetailHeader", f"{ent_stem}ActionToolbar", f"{ent_stem}AuditHistoryPanel"],
                api_endpoints=mod_endpoints,
                validation_rules=["UI actions must trigger behavior-grounded REST API endpoints"]
            ))

        return lld_components
