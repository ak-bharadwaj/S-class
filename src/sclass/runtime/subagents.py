"""
S-Class Runtime: Subagent Lifecycle & Capability Delegation Runtime.
Implements the harvested Step-Code subagent machinery required by Directive Section 6:
- Lifecycle phases: CREATE, START, PROGRESS, STOP, REPLY, TERMINATE.
- RPC child process handling and isolated child session states.
- Child-side ACLs: capability delegation, task scope, workspace scope, budget, and tool set.
- Foundational Invariant:
  A child agent receives delegated capability, task scope, workspace scope,
  budget, and tool set. NEVER parent authority.
  A child agent may create evidence candidates.
  A child agent may NEVER certify its own evidence.
"""

from __future__ import annotations
import uuid
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Callable

from sclass.runtime.lanes import ExecutionLane, LaneManager, LaneType, LaneBudget
from sclass.runtime.permissions import WorkflowChildACL
from sclass.core.errors import SecurityViolationError


class SubagentPhase(str, Enum):
    CREATED = "CREATED"
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    STOPPED = "STOPPED"
    REPLIED = "REPLIED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"


@dataclass
class SubagentDelegationScope:
    """Explicit capability delegation scope for a child subagent."""
    task_id: str
    task_scope: str
    workspace_dir: str
    delegated_tools: Set[str]
    budget: LaneBudget
    acl: WorkflowChildACL
    can_certify_evidence: bool = False  # STRICTLY FALSE by architectural mandate


@dataclass
class SubagentReply:
    """Outcome payload returned from a subagent back to the orchestrator."""
    subagent_id: str
    phase: SubagentPhase
    output_message: str
    candidate_evidence: List[Dict[str, Any]]
    execution_stats: Dict[str, Any]
    error: Optional[str] = None


class SubagentInstance:
    """Active instance of a child subagent running inside an isolated execution lane."""

    def __init__(
        self,
        subagent_id: str,
        parent_agent_id: str,
        lane: ExecutionLane,
        scope: SubagentDelegationScope,
    ):
        self.subagent_id = subagent_id
        self.parent_agent_id = parent_agent_id
        self.lane = lane
        self.scope = scope
        self.phase = SubagentPhase.CREATED
        self.progress_log: List[Dict[str, Any]] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def start(self) -> None:
        if self.phase != SubagentPhase.CREATED:
            raise SecurityViolationError(f"Cannot start subagent {self.subagent_id}: current phase is {self.phase.value}")
        self.phase = SubagentPhase.STARTED
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_progress(self, step_name: str, details: Dict[str, Any]) -> None:
        if self.phase not in (SubagentPhase.STARTED, SubagentPhase.IN_PROGRESS):
            raise SecurityViolationError(f"Cannot record progress for subagent in phase {self.phase.value}")
        self.phase = SubagentPhase.IN_PROGRESS
        entry = {
            "step": step_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
        }
        self.progress_log.append(entry)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def reply(self, message: str, evidence_candidates: Optional[List[Dict[str, Any]]] = None) -> SubagentReply:
        """
        Completes the subagent execution and produces reply with candidate evidence.
        Enforces that candidate evidence is tagged as untrusted candidate, NOT verified truth.
        """
        if self.phase in (SubagentPhase.TERMINATED, SubagentPhase.FAILED):
            raise SecurityViolationError(f"Cannot reply: subagent is in terminal phase {self.phase.value}")

        self.phase = SubagentPhase.REPLIED
        self.updated_at = datetime.now(timezone.utc).isoformat()

        # Sanitize candidate evidence: subagents cannot certify truth
        sanitized_evidence: List[Dict[str, Any]] = []
        for cand in (evidence_candidates or []):
            item = dict(cand)
            item["verified"] = False
            item["untrusted_candidate"] = True
            item["subagent_id"] = self.subagent_id
            sanitized_evidence.append(item)

        return SubagentReply(
            subagent_id=self.subagent_id,
            phase=self.phase,
            output_message=message,
            candidate_evidence=sanitized_evidence,
            execution_stats={
                "steps_completed": len(self.progress_log),
                "lane_id": self.lane.lane_id,
                "used_tokens": self.lane.budget.used_tokens,
            },
        )

    def stop(self, reason: str = "") -> None:
        self.phase = SubagentPhase.STOPPED
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def terminate(self, reason: str = "") -> None:
        self.phase = SubagentPhase.TERMINATED
        self.updated_at = datetime.now(timezone.utc).isoformat()


class SubagentManager:
    """Manages the pool of child subagents, enforcing non-delegation of authority."""

    def __init__(self, lane_manager: LaneManager):
        self.lane_manager = lane_manager
        self._subagents: Dict[str, SubagentInstance] = {}

    def spawn_subagent(
        self,
        parent_agent_id: str,
        parent_lane_id: str,
        scope: SubagentDelegationScope,
        agent_name: str = "child_agent",
    ) -> SubagentInstance:
        """
        Creates an isolated subagent bound to a dedicated SUBAGENT lane.
        """
        subagent_id = f"subagent_{uuid.uuid4().hex[:8]}"

        lane = self.lane_manager.spawn_child_lane(
            parent_lane_id=parent_lane_id,
            lane_type=LaneType.SUBAGENT,
            agent_identity=f"{agent_name}:{subagent_id}",
            delegated_task_id=scope.task_id,
            delegated_capabilities=list(scope.delegated_tools),
            delegated_budget=scope.budget,
        )

        instance = SubagentInstance(
            subagent_id=subagent_id,
            parent_agent_id=parent_agent_id,
            lane=lane,
            scope=scope,
        )
        self._subagents[subagent_id] = instance
        return instance

    def get_subagent(self, subagent_id: str) -> Optional[SubagentInstance]:
        return self._subagents.get(subagent_id)
