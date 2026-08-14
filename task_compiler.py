"""
S-Class EOS V7.0 - Upstream-Traceable Task Compiler

Defines:
1. TaskRecord (Executable coding task with full lineage: task -> lld -> hld -> req -> behavior)
2. TaskCompiler (Compiles LLDComponents into sequential, verifiable tasks for the coding agent)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import json

from lld_compiler import LLDComponent, LLDComponentType


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
    """An executable task with complete upstream architectural lineage."""
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
    """Compiles LLDComponents into structured, traceable TaskRecord entries."""

    @classmethod
    def compile_tasks(cls, lld_components: List[LLDComponent]) -> List[TaskRecord]:
        tasks: List[TaskRecord] = []
        task_counter = 1

        for comp in lld_components:
            p_hld = comp.parent.hld_id
            p_reqs = comp.parent.req_ids
            p_behs = comp.parent.behavior_ids

            if comp.component_type == LLDComponentType.CONTROLLER:
                for ep in comp.api_endpoints:
                    t_id = f"TASK-{task_counter:03d}"
                    task_counter += 1
                    tasks.append(TaskRecord(
                        id=t_id,
                        title=f"Implement REST Endpoint: {ep}",
                        description=f"Construct backend handler for {ep} in {comp.name}.",
                        category=TaskCategory.API_ENDPOINT,
                        parent_lld=comp.id,
                        parent_hld=p_hld,
                        parent_reqs=p_reqs,
                        parent_behaviors=p_behs,
                        verification_criteria=[
                            f"Endpoint {ep} responds with HTTP 200/201 on valid payload",
                            "Returns structured error JSON on invalid payload"
                        ]
                    ))

            elif comp.component_type == LLDComponentType.SERVICE:
                t_id = f"TASK-{task_counter:03d}"
                task_counter += 1
                tasks.append(TaskRecord(
                    id=t_id,
                    title=f"Implement Service Logic & State Transitions: {comp.name}",
                    description=f"Implement domain business logic and state machine transitions in {comp.name}.",
                    category=TaskCategory.STATE_TRANSITION,
                    parent_lld=comp.id,
                    parent_hld=p_hld,
                    parent_reqs=p_reqs,
                    parent_behaviors=p_behs,
                    verification_criteria=[
                        "Validates state machine pre-conditions prior to transition",
                        "Persists committed state commitment atomically"
                    ]
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
                        f"Renders interface at route {comp.route}",
                        "Connects action triggers to backend REST endpoints"
                    ]
                ))

        return tasks
