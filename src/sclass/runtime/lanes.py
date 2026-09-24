"""
S-Class Runtime: Execution Lanes & Session Tree Hierarchy.
Implements the harvested Step-Code lane architecture required by Directive Section 5:
- Lane types: MAIN, PARALLEL, SUBAGENT, WORKFLOW, BACKGROUND.
- Each lane owns:
  lane_id, session_id, task_id, parent_lane_id, workspace_id, current_leaf,
  current_operation, agent identity, model identity, permission context, budget, recovery state.
- Invariant: A child lane never inherits parent authority automatically;
  all child capabilities must be explicitly delegated.
"""

from __future__ import annotations
import uuid
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set

from sclass.core.errors import SecurityViolationError


class LaneType(str, Enum):
    MAIN = "MAIN"
    PARALLEL = "PARALLEL"
    SUBAGENT = "SUBAGENT"
    WORKFLOW = "WORKFLOW"
    BACKGROUND = "BACKGROUND"


class LaneStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"


@dataclass
class LaneBudget:
    """Resource budget allocated to an execution lane."""
    max_tokens: int = 100000
    used_tokens: int = 0
    max_cost_usd: float = 1.0
    used_cost_usd: float = 0.0
    max_operations: int = 50
    completed_operations: int = 0

    @property
    def is_exhausted(self) -> bool:
        return (
            self.used_tokens >= self.max_tokens
            or self.used_cost_usd >= self.max_cost_usd
            or self.completed_operations >= self.max_operations
        )


@dataclass
class ExecutionLane:
    """Authoritative representation of an isolated runtime execution lane."""
    lane_id: str
    lane_type: LaneType
    session_id: str
    task_id: str
    parent_lane_id: Optional[str]
    workspace_id: str
    current_leaf: str
    current_operation: Optional[str]
    agent_identity: str
    model_identity: str
    permission_context: Dict[str, Any]
    budget: LaneBudget
    recovery_state: Dict[str, Any]
    status: LaneStatus = LaneStatus.CREATED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "lane_type": self.lane_type.value,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "parent_lane_id": self.parent_lane_id,
            "workspace_id": self.workspace_id,
            "current_leaf": self.current_leaf,
            "current_operation": self.current_operation,
            "agent_identity": self.agent_identity,
            "model_identity": self.model_identity,
            "permission_context": dict(self.permission_context),
            "budget": asdict(self.budget),
            "recovery_state": dict(self.recovery_state),
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class LaneManager:
    """Manages creation, lifecycle, and strict non-delegation across execution lanes."""

    def __init__(self):
        self._lanes: Dict[str, ExecutionLane] = {}

    def create_main_lane(
        self,
        session_id: str,
        task_id: str,
        workspace_id: str,
        agent_identity: str = "main_agent",
        model_identity: str = "default_model",
        budget: Optional[LaneBudget] = None,
    ) -> ExecutionLane:
        lane_id = f"lane_main_{uuid.uuid4().hex[:8]}"
        lane = ExecutionLane(
            lane_id=lane_id,
            lane_type=LaneType.MAIN,
            session_id=session_id,
            task_id=task_id,
            parent_lane_id=None,
            workspace_id=workspace_id,
            current_leaf="root",
            current_operation=None,
            agent_identity=agent_identity,
            model_identity=model_identity,
            permission_context={"role": "orchestrator", "delegable": True},
            budget=budget or LaneBudget(),
            recovery_state={"checkpoints": []},
            status=LaneStatus.ACTIVE,
        )
        self._lanes[lane_id] = lane
        return lane

    def spawn_child_lane(
        self,
        parent_lane_id: str,
        lane_type: LaneType,
        agent_identity: str,
        delegated_task_id: str,
        delegated_capabilities: List[str],
        delegated_budget: LaneBudget,
        model_identity: str = "default_model",
    ) -> ExecutionLane:
        """
        Spawns a child lane under strict explicit delegation.
        The child NEVER inherits parent authority automatically.
        """
        parent = self._lanes.get(parent_lane_id)
        if not parent:
            raise SecurityViolationError(f"Cannot spawn child lane: parent lane {parent_lane_id} does not exist.")

        # Ensure parent has budget to delegate
        if parent.budget.is_exhausted:
            raise SecurityViolationError(f"Cannot spawn child lane: parent budget is exhausted.")

        # Child lane inherits ONLY explicitly delegated capabilities
        child_permissions = {
            "role": "worker",
            "delegated_from": parent_lane_id,
            "delegated_capabilities": list(delegated_capabilities),
            "delegable": False, # Child cannot delegate further without explicit permission
            "can_certify_evidence": False, # Strict invariant: child cannot certify evidence
        }

        child_id = f"lane_{lane_type.value.lower()}_{uuid.uuid4().hex[:8]}"
        child_lane = ExecutionLane(
            lane_id=child_id,
            lane_type=lane_type,
            session_id=parent.session_id,
            task_id=delegated_task_id,
            parent_lane_id=parent_lane_id,
            workspace_id=parent.workspace_id,
            current_leaf=f"leaf_{child_id}",
            current_operation=None,
            agent_identity=agent_identity,
            model_identity=model_identity,
            permission_context=child_permissions,
            budget=delegated_budget,
            recovery_state={"checkpoints": []},
            status=LaneStatus.ACTIVE,
        )
        self._lanes[child_id] = child_lane
        return child_lane

    def get_lane(self, lane_id: str) -> Optional[ExecutionLane]:
        return self._lanes.get(lane_id)

    def terminate_lane(self, lane_id: str, reason: str = "") -> None:
        lane = self._lanes.get(lane_id)
        if lane:
            lane.status = LaneStatus.TERMINATED
            lane.updated_at = datetime.now(timezone.utc).isoformat()
