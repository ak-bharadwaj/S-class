"""
S-Class Execution: Canonical Normalized Runtime Event Contract.
Normalizes heterogeneous events across runtime harnesses (Step-Code, Claude Code, Codex, Custom)
into a strictly-typed, cryptographically verifiable event structure.

Invariants:
1. Runtime events are untrusted inputs/signals, never canonical project truth (Law L2).
2. All consequential events carry cryptographic provenance and identity hashes (Law L5).
3. Any tampering with event payload or metadata fails closed (Law L8).
"""

from __future__ import annotations
import uuid
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union

from sclass.execution.operations import ReplayClass
from sclass.core.errors import ObservationIntegrityError, SecurityViolationError


@dataclass(frozen=True)
class RuntimeEvent:
    """
    Canonical normalized event model emitted by execution harnesses into S-Class.
    """
    event_id: str
    operation_id: str
    parent_operation_id: Optional[str]
    session_id: str
    task_id: str
    action_id: str
    agent_id: str
    workspace_id: str
    event_type: str
    sequence: int
    timestamp: str
    intent_hash: str
    action_hash: str
    replay_class: ReplayClass
    runtime: str              # "step-code", "claude-code", "codex", "native", "custom"
    provider: str             # "host", "sandbox", "container", etc.
    workspace_fingerprint_before: Optional[str]
    workspace_fingerprint_after: Optional[str]
    payload: Dict[str, Any]
    source: str               # "harness", "agent", "tool", "observer"
    event_hash: str = field(init=False)

    def __init__(
        self,
        event_id: Optional[str] = None,
        operation_id: str = "",
        parent_operation_id: Optional[str] = None,
        session_id: str = "default_session",
        task_id: str = "default_task",
        action_id: str = "",
        agent_id: str = "default_agent",
        workspace_id: str = "default_workspace",
        event_type: str = "runtime_event",
        sequence: int = 1,
        timestamp: Optional[str] = None,
        intent_hash: str = "",
        action_hash: str = "",
        replay_class: Union[ReplayClass, str] = ReplayClass.NEVER,
        runtime: str = "step-code",
        provider: str = "native",
        workspace_fingerprint_before: Optional[str] = None,
        workspace_fingerprint_after: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "harness",
        event_hash: Optional[str] = None,
    ):
        ev_id = event_id or f"evt_{uuid.uuid4().hex[:12]}"
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        rc = ReplayClass(replay_class) if isinstance(replay_class, str) else replay_class
        p_dict = dict(payload or {})

        object.__setattr__(self, "event_id", ev_id)
        object.__setattr__(self, "operation_id", operation_id)
        object.__setattr__(self, "parent_operation_id", parent_operation_id)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "action_id", action_id)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "workspace_id", workspace_id)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "sequence", sequence)
        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(self, "intent_hash", intent_hash)
        object.__setattr__(self, "action_hash", action_hash)
        object.__setattr__(self, "replay_class", rc)
        object.__setattr__(self, "runtime", runtime)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "workspace_fingerprint_before", workspace_fingerprint_before)
        object.__setattr__(self, "workspace_fingerprint_after", workspace_fingerprint_after)
        object.__setattr__(self, "payload", p_dict)
        object.__setattr__(self, "source", source)

        computed_hash = self.compute_hash()
        if event_hash and event_hash != computed_hash:
            raise ObservationIntegrityError(
                f"Tampered runtime event hash: provided '{event_hash}' does not match computed '{computed_hash}'"
            )
        object.__setattr__(self, "event_hash", computed_hash)

    def compute_hash(self) -> str:
        """Deterministically computes SHA-256 hash across canonical event fields."""
        norm_payload = json.dumps(self.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        content = (
            f"{self.event_id}|{self.operation_id}|{self.session_id}|{self.task_id}|"
            f"{self.action_id}|{self.agent_id}|{self.workspace_id}|{self.event_type}|"
            f"{self.sequence}|{self.timestamp}|{self.intent_hash}|{self.action_hash}|"
            f"{self.replay_class.value}|{self.runtime}|{self.provider}|"
            f"{self.workspace_fingerprint_before or ''}|{self.workspace_fingerprint_after or ''}|"
            f"{norm_payload}|{self.source}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Validates that event contents match the cryptographic hash."""
        return self.compute_hash() == self.event_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "operation_id": self.operation_id,
            "parent_operation_id": self.parent_operation_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "workspace_id": self.workspace_id,
            "event_type": self.event_type,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "intent_hash": self.intent_hash,
            "action_hash": self.action_hash,
            "replay_class": self.replay_class.value,
            "runtime": self.runtime,
            "provider": self.provider,
            "workspace_fingerprint_before": self.workspace_fingerprint_before,
            "workspace_fingerprint_after": self.workspace_fingerprint_after,
            "payload": dict(self.payload),
            "source": self.source,
            "event_hash": self.event_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RuntimeEvent:
        return cls(
            event_id=data["event_id"],
            operation_id=data.get("operation_id", ""),
            parent_operation_id=data.get("parent_operation_id"),
            session_id=data.get("session_id", "default_session"),
            task_id=data.get("task_id", "default_task"),
            action_id=data.get("action_id", ""),
            agent_id=data.get("agent_id", "default_agent"),
            workspace_id=data.get("workspace_id", "default_workspace"),
            event_type=data.get("event_type", "runtime_event"),
            sequence=int(data.get("sequence", 1)),
            timestamp=data.get("timestamp"),
            intent_hash=data.get("intent_hash", ""),
            action_hash=data.get("action_hash", ""),
            replay_class=data.get("replay_class", ReplayClass.NEVER.value),
            runtime=data.get("runtime", "step-code"),
            provider=data.get("provider", "native"),
            workspace_fingerprint_before=data.get("workspace_fingerprint_before"),
            workspace_fingerprint_after=data.get("workspace_fingerprint_after"),
            payload=data.get("payload", {}),
            source=data.get("source", "harness"),
            event_hash=data.get("event_hash"),
        )
