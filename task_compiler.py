"""
S-Class EOS V8.0 - Epistemic Upstream-Traceable Task Compiler with Contract Verification

Defines:
1. TaskRecord (Executable coding task with full lineage: task -> lld -> hld -> req -> behavior)
2. TaskCompiler (Compiles LLDComponents into BDD contract-derived execution tasks, conditioning 403/audit criteria strictly on evidence)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import json

from lld_compiler import LLDComponent, LLDComponentType
from requirement_ir import RequirementGraph, RequirementNode, NFRCategory
from behavior_graph import BehaviorGraph, BehaviorNodeType, BehaviorRelationType


class TaskCategory(str, Enum):
    """Category of execution tasks."""
    API_ENDPOINT = "api_endpoint"
    AUTHORIZATION_GUARD = "authorization_guard"
    STATE_TRANSITION = "state_transition"
    AUDIT_LOG = "audit_log"
    UI_COMPONENT = "ui_component"
    INTEGRATION_TEST = "integration_test"


@dataclass
class TaskRecord:
    """An executable task with complete upstream architectural lineage and BDD acceptance criteria."""
    id: str
    title: str
    description: str
    category: TaskCategory
    parent_lld: str
    parent_hld: str
    parent_reqs: List[str]
    parent_behaviors: List[str]
    verification_criteria: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "parent_lld": self.parent_lld,
            "parent_hld": self.parent_hld,
            "parent_reqs": self.parent_reqs,
            "parent_behaviors": self.parent_behaviors,
            "verification_criteria": self.verification_criteria
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskRecord':
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            category=TaskCategory(data["category"]),
            parent_lld=data.get("parent_lld", ""),
            parent_hld=data.get("parent_hld", ""),
            parent_reqs=data.get("parent_reqs", []),
            parent_behaviors=data.get("parent_behaviors", []),
            verification_criteria=data.get("verification_criteria", [])
        )


class TaskCompiler:
    """Compiles LLDComponents and RequirementGraph into BDD contract-derived TaskRecord entries."""

    @classmethod
    def compile_tasks(
        cls,
        lld_components: List[LLDComponent],
        r_graph: Optional[RequirementGraph] = None,
        b_graph: Optional[BehaviorGraph] = None
    ) -> List[TaskRecord]:
        tasks: List[TaskRecord] = []
        task_counter = 1

        req_lookup = r_graph.nodes if r_graph else {}

        for comp in lld_components:
            p_hld = comp.parent.hld_id
            p_reqs = comp.parent.req_ids
            p_behs = comp.parent.behavior_ids

            matching_req_objs = [req_lookup[rid] for rid in p_reqs if rid in req_lookup]

            if comp.component_type in [LLDComponentType.CONTROLLER, LLDComponentType.SERVICE]:
                for ep in comp.api_endpoints:
                    t_id = f"TASK-{task_counter:03d}"
                    task_counter += 1

                    bdd_criteria = []
                    for req in matching_req_objs:
                        actor_str = req.actor
                        pre_str = f"Given {req.target}.status == {req.preconditions[0].split('==')[1].strip()}" if req.preconditions else f"Given {req.target} exists"
                        post_str = f"Then {req.target}.status == {req.postconditions[0].split('==')[1].strip()}" if req.postconditions else f"Then {req.capability} execution commits"

                        base_bdd = [
                            f"{pre_str}",
                            f"And actor == '{actor_str}'",
                            f"When transport action '{ep}' is invoked",
                            f"{post_str}"
                        ]

                        # Check if authorization evidence exists before adding 403 assertion (PERFORMS != AUTHORIZED_FOR)
                        has_auth_evidence = False
                        if b_graph:
                            b_node = b_graph.get_node(req.capability)
                            if b_node:
                                incoming = b_graph._reverse_adjacency.get(b_node.id, [])
                                has_auth_evidence = any(e.relation == BehaviorRelationType.AUTHORIZED_FOR for e in incoming)

                        ev_text = " ".join(e.content for e in (req.evidence or [])) if req.evidence else ""
                        if has_auth_evidence or "role:" in ev_text.lower():
                            base_bdd.append(f"And unauthorized actor returns HTTP 403 Forbidden")

                        # Check if audit evidence exists before adding audit persistence assertion
                        has_audit_evidence = False
                        if b_graph:
                            b_node = b_graph.get_node(req.capability)
                            if b_node:
                                outgoing = b_graph._adjacency.get(b_node.id, [])
                                has_audit_evidence = any(e.relation == BehaviorRelationType.EMITS_SIDE_EFFECT for e in outgoing)
                        if req.nfr_category == NFRCategory.AUDITABILITY:
                            has_audit_evidence = True

                        if has_audit_evidence:
                            base_bdd.append("And audit log record is committed to persistent storage")

                        bdd_criteria.extend(base_bdd)

                    if not bdd_criteria:
                        bdd_criteria = [
                            f"Given valid request payload for {ep}",
                            f"When transport action {ep} is invoked",
                            "Then handler executes successfully and returns expected payload contract"
                        ]

                    tasks.append(TaskRecord(
                        id=t_id,
                        title=f"Implement Component Contract: {ep}",
                        description=f"Construct component logic for {ep} in {comp.name}.",
                        category=TaskCategory.API_ENDPOINT if comp.component_type == LLDComponentType.CONTROLLER else TaskCategory.STATE_TRANSITION,
                        parent_lld=comp.id,
                        parent_hld=p_hld,
                        parent_reqs=p_reqs,
                        parent_behaviors=p_behs,
                        verification_criteria=list(dict.fromkeys(bdd_criteria))
                    ))

            elif comp.component_type == LLDComponentType.UI_SURFACE:
                t_id = f"TASK-{task_counter:03d}"
                task_counter += 1
                tasks.append(TaskRecord(
                    id=t_id,
                    title=f"Construct Behavioral UI Surface: {comp.name}",
                    description=f"Build modern React/Next.js frontend surface for {comp.name} at route {comp.route}.",
                    category=TaskCategory.UI_COMPONENT,
                    parent_lld=comp.id,
                    parent_hld=p_hld,
                    parent_reqs=p_reqs,
                    parent_behaviors=p_behs,
                    verification_criteria=[
                        f"Renders behavioral workflow surface at route {comp.route}",
                        "Connects action triggers to backend transport contracts"
                    ]
                ))

        return tasks
