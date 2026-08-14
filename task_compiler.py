"""
S-Class EOS V7.0 - Upstream-Traceable Task Compiler with BDD Contract Verification

Defines:
1. TaskRecord (Executable coding task with full lineage: task -> lld -> hld -> req -> behavior)
2. TaskCompiler (Compiles LLDComponents into BDD contract-derived execution tasks)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import json

from lld_compiler import LLDComponent, LLDComponentType
from requirement_ir import RequirementGraph, RequirementNode


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
    def compile_tasks(cls, lld_components: List[LLDComponent], r_graph: Optional[RequirementGraph] = None) -> List[TaskRecord]:
        tasks: List[TaskRecord] = []
        task_counter = 1

        req_lookup = r_graph.nodes if r_graph else {}

        for comp in lld_components:
            p_hld = comp.parent.hld_id
            p_reqs = comp.parent.req_ids
            p_behs = comp.parent.behavior_ids

            # Find requirement objects for BDD criteria synthesis
            matching_req_objs = [req_lookup[rid] for rid in p_reqs if rid in req_lookup]

            if comp.component_type == LLDComponentType.CONTROLLER:
                for ep in comp.api_endpoints:
                    t_id = f"TASK-{task_counter:03d}"
                    task_counter += 1

                    # Synthesize exact BDD acceptance criteria from requirement pre/post conditions
                    bdd_criteria = []
                    for req in matching_req_objs:
                        actor_str = req.actor
                        pre_str = f"Given {req.target}.status == {req.preconditions[0].split('==')[1].strip()}" if req.preconditions else f"Given {req.target} exists"
                        post_str = f"Then {req.target}.status == {req.postconditions[0].split('==')[1].strip()}" if req.postconditions else f"Then {req.capability} execution commits"

                        bdd_criteria.extend([
                            f"{pre_str}",
                            f"And actor == '{actor_str}'",
                            f"When HTTP '{ep}' is invoked",
                            f"{post_str}",
                            f"And unauthorized actor returns HTTP 403 Forbidden",
                            f"And audit log record is committed to persistent storage"
                        ])

                    if not bdd_criteria:
                        bdd_criteria = [
                            f"Given valid request payload for {ep}",
                            f"When HTTP {ep} is invoked",
                            "Then API returns HTTP 200/201 with structured JSON payload",
                            "And invalid payload returns HTTP 400 Bad Request"
                        ]

                    tasks.append(TaskRecord(
                        id=t_id,
                        title=f"Implement REST Endpoint Contract: {ep}",
                        description=f"Construct backend handler for {ep} in {comp.name}.",
                        category=TaskCategory.API_ENDPOINT,
                        parent_lld=comp.id,
                        parent_hld=p_hld,
                        parent_reqs=p_reqs,
                        parent_behaviors=p_behs,
                        verification_criteria=list(dict.fromkeys(bdd_criteria))
                    ))

            elif comp.component_type == LLDComponentType.SERVICE:
                t_id = f"TASK-{task_counter:03d}"
                task_counter += 1

                bdd_service_criteria = []
                for req in matching_req_objs:
                    if req.preconditions:
                        bdd_service_criteria.append(f"Validates precondition constraint: {req.preconditions[0]}")
                    if req.postconditions:
                        bdd_service_criteria.append(f"Commits postcondition transition: {req.postconditions[0]}")

                if not bdd_service_criteria:
                    bdd_service_criteria = [
                        "Validates state machine pre-conditions prior to transition",
                        "Persists committed state commitment atomically"
                    ]

                tasks.append(TaskRecord(
                    id=t_id,
                    title=f"Implement Service Logic & State Transitions: {comp.name}",
                    description=f"Implement domain business logic and state machine transitions in {comp.name}.",
                    category=TaskCategory.STATE_TRANSITION,
                    parent_lld=comp.id,
                    parent_hld=p_hld,
                    parent_reqs=p_reqs,
                    parent_behaviors=p_behs,
                    verification_criteria=bdd_service_criteria
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
                        "Connects action triggers to backend REST endpoints"
                    ]
                ))

        return tasks
