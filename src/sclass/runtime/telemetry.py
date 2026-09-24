"""
S-Class Runtime: Typed Telemetry Subsystem.
Harvests the typed telemetry structure from Step-Code (Directive Section 15).
Exposes typed events:
- session_started
- turn_completed
- tool_call_completed
- permission_decision
- permission_approval_result
- compaction_finished
- mcp_server_connected
- mcp_server_failed
- subagent_task_created
- subagent_task_finished
- workflow_started
- workflow_finished
- workflow_budget_exceeded
- goal_continued
- error_raised

Fundamental Invariant:
Telemetry represents operational observability, NEVER authority.
Telemetry events cannot establish task completion or satisfy technical obligations.
"""

from __future__ import annotations
import os
import json
import uuid
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class TelemetryEventType(str, Enum):
    SESSION_STARTED = "session_started"
    TURN_COMPLETED = "turn_completed"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    PERMISSION_DECISION = "permission_decision"
    PERMISSION_APPROVAL_RESULT = "permission_approval_result"
    COMPACTION_FINISHED = "compaction_finished"
    MCP_SERVER_CONNECTED = "mcp_server_connected"
    MCP_SERVER_FAILED = "mcp_server_failed"
    SUBAGENT_TASK_CREATED = "subagent_task_created"
    SUBAGENT_TASK_FINISHED = "subagent_task_finished"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_FINISHED = "workflow_finished"
    WORKFLOW_BUDGET_EXCEEDED = "workflow_budget_exceeded"
    GOAL_CONTINUED = "goal_continued"
    ERROR_RAISED = "error_raised"


@dataclass(frozen=True)
class TelemetryEvent:
    """Immutable typed telemetry record."""
    event_id: str
    event_type: TelemetryEventType
    session_id: str
    task_id: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


class RuntimeTelemetryLedger:
    """
    Append-only storage for runtime observability events.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.log_dir = os.path.join(self.workspace_dir, ".sclass", "telemetry")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_path = os.path.join(self.log_dir, "runtime_telemetry.jsonl")
        self._events: List[TelemetryEvent] = []

    def emit(
        self,
        event_type: TelemetryEventType,
        session_id: str,
        task_id: str,
        payload: Dict[str, Any],
    ) -> TelemetryEvent:
        event = TelemetryEvent(
            event_id=f"telem_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            session_id=session_id,
            task_id=task_id,
            payload=payload,
        )
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict()) + "\n")
        self._events.append(event)
        return event

    def get_events(self, event_type: Optional[TelemetryEventType] = None) -> List[TelemetryEvent]:
        if not os.path.exists(self.log_path):
            return [e for e in self._events if event_type is None or e.event_type == event_type]
        records: List[TelemetryEvent] = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line.strip())
                    et = TelemetryEventType(data["event_type"])
                    if event_type is None or et == event_type:
                        records.append(
                            TelemetryEvent(
                                event_id=data["event_id"],
                                event_type=et,
                                session_id=data["session_id"],
                                task_id=data["task_id"],
                                payload=data["payload"],
                                timestamp=data["timestamp"],
                            )
                        )
        return records

    @staticmethod
    def cannot_establish_authority() -> bool:
        """
        Authoritative assertion: Telemetry cannot establish success or project truth.
        Always returns True to emphasize non-authority status.
        """
        return True
