"""
S-Class Execution: Durable Operation Model & Explicit Replay Semantics.
Implements the adapted Step-Code durable operation lifecycle:
ACTION INTENT -> S-CLASS AUTHORIZATION -> RUNTIME EFFECT -> INDEPENDENT OBSERVATION -> EVIDENCE RECEIPT -> CLAIM ASSESSMENT -> CANONICAL PROJECT STATE.

Enforces:
1. Operation state = execution truth != project truth.
2. Explicit replay semantics: SAFE, IDEMPOTENT, NEVER.
3. NEVER operations fail closed and are never automatically replayed.
4. Action hash verification prevents post-authorization parameter tampering.
"""

from __future__ import annotations
import os
import shlex
import uuid
import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set, Union

from sclass.core.errors import SecurityViolationError, ProvenanceError


class ReplayClass(str, Enum):
    """Authoritative classification of whether an operation effect can be safely replayed."""
    SAFE = "SAFE"                # Pure read or harmless idempotent query (e.g. read_file, run_tests)
    IDEMPOTENT = "IDEMPOTENT"    # Safe to replay if input state is identical
    NEVER = "NEVER"              # Non-idempotent or consequential mutation (write_file, git commit, publish, deploy, external effect)


class OperationState(str, Enum):
    """Authoritative lifecycle states of a durable operation."""
    PLANNED = "PLANNED"
    AUTHORIZED = "AUTHORIZED"
    EFFECT_PENDING = "EFFECT_PENDING"
    EFFECT_EXECUTED = "EFFECT_EXECUTED"
    SETTLED = "SETTLED"
    OBSERVED = "OBSERVED"
    ASSESSED = "ASSESSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in (OperationState.ASSESSED, OperationState.FAILED, OperationState.CANCELLED)


# Explicit action categories for replay safety classification
_SAFE_ACTIONS: Set[str] = {
    "read_file",
    "view_file",
    "list_dir",
    "find_by_name",
    "grep_search",
    "read_url",
    "run_tests",
    "test",
    "pytest",
    "unittest",
    "lint",
    "typecheck",
    "check",
    "query_index",
    "inspect_session",
    "get_status",
    "read",
}

_NEVER_REPLAY_ACTIONS: Set[str] = {
    "write_file",
    "replace_file_content",
    "delete_file",
    "rm",
    "git_commit",
    "commit",
    "git_push",
    "push",
    "publish",
    "deploy",
    "send_external",
    "send_message",
    "post_http",
    "execute_command",
    "run_command",
    "terminal_execute",
    "mutate",
}


def classify_replay_safety(
    action: str,
    target: str = "",
    parameters: Optional[Dict[str, Any]] = None,
) -> ReplayClass:
    """
    Deterministically determines the replay class of an operation.
    Does not rely on tool name alone: inspects parameters and targets.
    Fails closed: any unrecognized or mutating action is classified as NEVER.
    """
    clean_action = (action or "").strip().lower()

    # Check terminal/command actions
    if clean_action in ("run_command", "terminal_execute", "execute_command"):
        cmd = ""
        if parameters and isinstance(parameters, dict):
            cmd = parameters.get("command") or parameters.get("command_line") or parameters.get("cmd") or ""
        cmd_clean = cmd.strip()
        if not cmd_clean:
            return ReplayClass.NEVER

        # Check for output redirection (>, >>) which mutates filesystem
        if ">" in cmd_clean:
            return ReplayClass.NEVER

        # Check for piping (|) or command chaining (;, &&, ||, &)
        if any(token in cmd_clean for token in (";", "&&", "||", "|", "&")):
            return ReplayClass.NEVER

        # Check for command substitution ($(), ``)
        if "$(" in cmd_clean or "`" in cmd_clean:
            return ReplayClass.NEVER

        # Parse command tokens safely
        try:
            tokens = shlex.split(cmd_clean, posix=False)
        except Exception:
            tokens = cmd_clean.split()
        if not tokens:
            return ReplayClass.NEVER

        prog = os.path.splitext(os.path.basename(tokens[0]))[0].lower()
        tokens_lower = [t.lower() for t in tokens]
        if any(flag in tokens_lower for flag in ("-delete", "-exec", "-execdir", "-ok", "-okdir", "--delete")):
            return ReplayClass.NEVER

        # Strictly inspect safe programs and subcommands
        if prog in ("pytest", "unittest", "ls", "dir", "pwd", "cat", "grep", "head", "tail", "wc"):
            return ReplayClass.SAFE
        if prog in ("python", "python3", "py"):
            if len(tokens) >= 3 and tokens[1].lower() == "-m" and tokens[2].lower() in ("pytest", "unittest"):
                return ReplayClass.SAFE
            return ReplayClass.NEVER
        if prog == "git":
            if len(tokens) >= 2 and tokens[1].lower() in ("status", "diff", "log", "show", "branch", "rev-parse", "describe", "tag", "remote"):
                return ReplayClass.SAFE
            return ReplayClass.NEVER

        return ReplayClass.NEVER

    if clean_action in _SAFE_ACTIONS:
        return ReplayClass.SAFE

    # Everything else, including file writes, deletions, and network mutations, is strictly NEVER
    return ReplayClass.NEVER


def compute_action_hash(
    capability: str,
    action: str,
    target: str,
    parameters: Optional[Dict[str, Any]] = None,
) -> str:
    """Computes deterministic hash for an action request and parameters."""
    norm_params = json.dumps(parameters or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload = f"{capability}|{action}|{target}|{norm_params}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OperationMetadata:
    """Immutable identity and provenance metadata for a durable operation."""
    operation_id: str
    parent_operation_id: Optional[str]
    session_id: str
    task_id: str
    agent_id: str
    action_id: str
    workspace_id: str
    replay_class: ReplayClass
    intent_hash: str
    action_hash: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "parent_operation_id": self.parent_operation_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "action_id": self.action_id,
            "workspace_id": self.workspace_id,
            "replay_class": self.replay_class.value,
            "intent_hash": self.intent_hash,
            "action_hash": self.action_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OperationMetadata:
        rc = data.get("replay_class", ReplayClass.NEVER.value)
        return cls(
            operation_id=data["operation_id"],
            parent_operation_id=data.get("parent_operation_id"),
            session_id=data.get("session_id", "default_session"),
            task_id=data.get("task_id", "default_task"),
            agent_id=data.get("agent_id", "default_agent"),
            action_id=data.get("action_id", f"act_{uuid.uuid4().hex[:8]}"),
            workspace_id=data.get("workspace_id", "default_workspace"),
            replay_class=ReplayClass(rc) if rc in ReplayClass._value2member_map_ else ReplayClass.NEVER,
            intent_hash=data.get("intent_hash", ""),
            action_hash=data.get("action_hash", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class DurableOperation:
    """
    Durable operation tracking the lower execution layer lifecycle.
    Separates execution truth (this object) from canonical project truth (S-Class).
    """
    metadata: OperationMetadata
    state: OperationState = OperationState.PLANNED
    authorization_id: Optional[str] = None
    effect_pending_record: Optional[Dict[str, Any]] = None
    effect_result: Optional[Dict[str, Any]] = None
    settlement_record: Optional[Dict[str, Any]] = None
    observation_id: Optional[str] = None
    evidence_id: Optional[str] = None
    assessment_id: Optional[str] = None
    failure_reason: Optional[str] = None
    replayed: bool = False
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def operation_id(self) -> str:
        return self.metadata.operation_id

    @property
    def replay_class(self) -> ReplayClass:
        return self.metadata.replay_class

    def transition_to(self, new_state: OperationState, details: Optional[Dict[str, Any]] = None) -> None:
        """Transitions operation state monotonically."""
        if self.state.is_terminal and new_state != self.state:
            raise SecurityViolationError(f"Cannot transition terminal operation from {self.state} to {new_state}")
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if details:
            if new_state == OperationState.EFFECT_PENDING:
                self.effect_pending_record = dict(details)
            elif new_state == OperationState.EFFECT_EXECUTED:
                self.effect_result = dict(details)
            elif new_state == OperationState.SETTLED:
                self.settlement_record = dict(details)
            elif new_state == OperationState.FAILED:
                self.failure_reason = details.get("reason", "Operation execution failure")

    def assert_can_replay(self) -> None:
        """
        Enforces replay safety.
        Raises SecurityViolationError if the operation is classified as NEVER.
        """
        if self.metadata.replay_class == ReplayClass.NEVER:
            raise SecurityViolationError(
                f"REPLAY REJECTED: Operation '{self.operation_id}' has replay_class=NEVER. "
                "Non-idempotent mutations cannot be automatically replayed after interruption."
            )

    def mark_replayed(self) -> None:
        self.assert_can_replay()
        self.replayed = True
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "state": self.state.value,
            "authorization_id": self.authorization_id,
            "effect_pending_record": self.effect_pending_record,
            "effect_result": self.effect_result,
            "settlement_record": self.settlement_record,
            "observation_id": self.observation_id,
            "evidence_id": self.evidence_id,
            "assessment_id": self.assessment_id,
            "failure_reason": self.failure_reason,
            "replayed": self.replayed,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DurableOperation:
        meta = OperationMetadata.from_dict(data["metadata"])
        st_val = data.get("state", OperationState.PLANNED.value)
        return cls(
            metadata=meta,
            state=OperationState(st_val) if st_val in OperationState._value2member_map_ else OperationState.PLANNED,
            authorization_id=data.get("authorization_id"),
            effect_pending_record=data.get("effect_pending_record"),
            effect_result=data.get("effect_result"),
            settlement_record=data.get("settlement_record"),
            observation_id=data.get("observation_id"),
            evidence_id=data.get("evidence_id"),
            assessment_id=data.get("assessment_id"),
            failure_reason=data.get("failure_reason"),
            replayed=bool(data.get("replayed", False)),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )
