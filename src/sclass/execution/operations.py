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
import logging
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set, Union

logger = logging.getLogger(__name__)

from sclass.core.errors import SecurityViolationError, ProvenanceError, ObservationIntegrityError
from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock


class ReplayClass(str, Enum):
    """Authoritative classification of whether an operation effect can be safely replayed."""
    SAFE = "SAFE"                # Pure read or harmless idempotent query (e.g. read_file, run_tests)
    IDEMPOTENT = "IDEMPOTENT"    # Safe to replay if input state is identical
    NEVER = "NEVER"              # Non-idempotent or consequential mutation (write_file, git commit, publish, deploy, external effect)
    UNKNOWN = "UNKNOWN"          # Indeterminate or unclassified; strictly fails closed (Directive Section 4)


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
    CORRUPT = "CORRUPT"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"

    @property
    def is_terminal(self) -> bool:
        return self in (
            OperationState.ASSESSED,
            OperationState.FAILED,
            OperationState.CANCELLED,
            OperationState.CORRUPT,
            OperationState.RECOVERY_REQUIRED,
        )


_LEGAL_TRANSITIONS: Dict[OperationState, Set[OperationState]] = {
    OperationState.PLANNED: {
        OperationState.AUTHORIZED,
        OperationState.FAILED,
        OperationState.CANCELLED,
        OperationState.CORRUPT,
        OperationState.RECOVERY_REQUIRED,
    },
    OperationState.AUTHORIZED: {
        OperationState.EFFECT_PENDING,
        OperationState.FAILED,
        OperationState.CANCELLED,
        OperationState.CORRUPT,
        OperationState.RECOVERY_REQUIRED,
    },
    OperationState.EFFECT_PENDING: {
        OperationState.EFFECT_EXECUTED,
        OperationState.FAILED,
        OperationState.CANCELLED,
        OperationState.CORRUPT,
        OperationState.RECOVERY_REQUIRED,
    },
    OperationState.EFFECT_EXECUTED: {
        OperationState.SETTLED,
        OperationState.FAILED,
        OperationState.CORRUPT,
        OperationState.RECOVERY_REQUIRED,
    },
    OperationState.SETTLED: {
        OperationState.OBSERVED,
        OperationState.FAILED,
        OperationState.CORRUPT,
        OperationState.RECOVERY_REQUIRED,
    },
    OperationState.OBSERVED: {
        OperationState.ASSESSED,
        OperationState.FAILED,
        OperationState.CORRUPT,
        OperationState.RECOVERY_REQUIRED,
    },
    OperationState.ASSESSED: set(),
    OperationState.FAILED: set(),
    OperationState.CANCELLED: set(),
    OperationState.CORRUPT: set(),
    OperationState.RECOVERY_REQUIRED: set(),
}


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
    workspace_dir: Optional[str] = None,
    expected_content_hash: Optional[str] = None,
    expected_action_hash: Optional[str] = None,
) -> str:
    """
    Computes deterministic hash for an action request and parameters.
    Enforces action-hash integrity:
    1. Authoritative workspace_dir is strictly required for relative targets.
    2. Deterministic target resolution: path separators and redundant segments are normalized.
    3. Workspace boundary traversal is rejected fail-closed with ObservationIntegrityError.
    4. Unreadable or changed targets raise ObservationIntegrityError (no empty string fallback or silent swallow).
    """
    norm_params = json.dumps(parameters or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    
    target_content_hash = ""
    resolved_target = None
    norm_target = target

    if target:
        if workspace_dir:
            workspace_abs = os.path.normpath(os.path.abspath(workspace_dir))
            if os.path.isabs(target):
                resolved_target = os.path.normpath(os.path.abspath(target))
                try:
                    if os.path.commonpath([workspace_abs, resolved_target]) == workspace_abs:
                        norm_target = os.path.relpath(resolved_target, workspace_abs).replace("\\", "/")
                    else:
                        norm_target = resolved_target.replace("\\", "/")
                except ValueError:
                    norm_target = resolved_target.replace("\\", "/")
            else:
                resolved_target = os.path.normpath(os.path.join(workspace_abs, target))
                try:
                    if os.path.commonpath([workspace_abs, resolved_target]) != workspace_abs:
                        raise ObservationIntegrityError(
                            f"Target path '{target}' escapes authoritative workspace boundary '{workspace_dir}'"
                        )
                except ValueError:
                    raise ObservationIntegrityError(
                        f"Target path '{target}' escapes authoritative workspace boundary '{workspace_dir}'"
                    )
                norm_target = os.path.relpath(resolved_target, workspace_abs).replace("\\", "/")
        else:
            if os.path.isabs(target):
                resolved_target = os.path.normpath(os.path.abspath(target))
                norm_target = resolved_target.replace("\\", "/")
            else:
                # Relative target without authoritative workspace_dir
                is_fs_or_path = (
                    capability.startswith("file")
                    or capability.startswith("fs")
                    or capability == "filesystem"
                    or action in ("read_file", "write_file", "delete_file", "edit_file", "list_dir", "touch", "append", "view_file")
                    or target.startswith((".", "/", "\\"))
                    or "/" in target
                    or "\\" in target
                    or (os.path.splitext(target)[1] != "" and len(os.path.splitext(target)[1]) <= 6)
                )
                if is_fs_or_path:
                    raise ObservationIntegrityError(
                        f"Authoritative workspace_dir is required for relative target '{target}'"
                    )
                resolved_target = None
                norm_target = target

    if resolved_target and os.path.exists(resolved_target):
        if os.path.isfile(resolved_target):
            try:
                with open(resolved_target, "rb") as f:
                    target_content_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception as e:
                raise ObservationIntegrityError(
                    f"Target file '{resolved_target}' is unreadable or corrupted: {e}"
                ) from e
        elif os.path.isdir(resolved_target):
            target_content_hash = f"DIR:{hashlib.sha256(norm_target.encode('utf-8')).hexdigest()}"

    if expected_content_hash is not None and target_content_hash != expected_content_hash:
        raise ObservationIntegrityError(
            f"Target '{target}' content changed unexpectedly (TOCTOU violation): expected {expected_content_hash}, got {target_content_hash}"
        )

    payload = f"{capability}|{action}|{norm_target}|{target_content_hash}|{norm_params}"
    calculated_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    if expected_action_hash is not None and calculated_hash != expected_action_hash:
        raise ObservationIntegrityError(
            f"Action hash integrity verification failed: expected {expected_action_hash}, got {calculated_hash}"
        )

    return calculated_hash


@dataclass(frozen=True)
class CrossRuntimeOperation:
    """
    Authoritative cross-runtime operation model (Section 11).
    Replaces runtime-specific durable operations with a neutral, durable reference.
    Binds:
    operation_id, runtime_name, runtime_operation_id, session_id,
    task_id, action_id, workspace_id, intent_hash, action_hash,
    replay_class, adapter_version.
    """
    operation_id: str
    runtime_name: str = "step-code"
    runtime_operation_id: str = ""
    session_id: str = "default_session"
    task_id: str = "default_task"
    action_id: str = ""
    workspace_id: str = "default_workspace"
    intent_hash: str = ""
    action_hash: str = ""
    replay_class: ReplayClass = ReplayClass.NEVER
    adapter_version: str = "1.0.0"
    state: OperationState = OperationState.PLANNED
    authorization_id: Optional[str] = None
    effect_result: Optional[Dict[str, Any]] = None
    settlement: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "runtime_name": self.runtime_name,
            "runtime_operation_id": self.runtime_operation_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "action_id": self.action_id,
            "workspace_id": self.workspace_id,
            "intent_hash": self.intent_hash,
            "action_hash": self.action_hash,
            "replay_class": self.replay_class.value,
            "adapter_version": self.adapter_version,
            "state": self.state.value,
            "authorization_id": self.authorization_id,
            "effect_result": self.effect_result,
            "settlement": self.settlement,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CrossRuntimeOperation:
        rc_val = data.get("replay_class", ReplayClass.NEVER.value)
        rc = ReplayClass(rc_val) if rc_val in ReplayClass._value2member_map_ else ReplayClass.NEVER
        st_val = data.get("state")
        if st_val is not None and st_val in OperationState._value2member_map_:
            st = OperationState(st_val)
        else:
            st = OperationState.CORRUPT
        return cls(
            operation_id=data["operation_id"],
            runtime_name=data.get("runtime_name", "step-code"),
            runtime_operation_id=data.get("runtime_operation_id", ""),
            session_id=data.get("session_id", "default_session"),
            task_id=data.get("task_id", "default_task"),
            action_id=data.get("action_id", ""),
            workspace_id=data.get("workspace_id", "default_workspace"),
            intent_hash=data.get("intent_hash", ""),
            action_hash=data.get("action_hash", ""),
            replay_class=rc,
            adapter_version=data.get("adapter_version", "1.0.0"),
            state=st,
            authorization_id=data.get("authorization_id"),
            effect_result=data.get("effect_result"),
            settlement=data.get("settlement"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=dict(data.get("metadata", {})),
        )

    def transition_to(self, new_state: OperationState, details: Optional[Dict[str, Any]] = None) -> CrossRuntimeOperation:
        """Transitions operation state strictly adhering to the state machine."""
        import dataclasses
        allowed_next = _LEGAL_TRANSITIONS.get(self.state, set())
        if new_state not in allowed_next:
            raise SecurityViolationError(
                f"ILLEGAL OPERATION STATE TRANSITION: Cannot transition operation from {self.state.value} to {new_state.value}. "
                f"Permitted next states from {self.state.value}: {[s.value for s in allowed_next]}."
            )
        new_meta = dict(self.metadata)
        if details:
            new_meta.update(details)
        return dataclasses.replace(
            self,
            state=new_state,
            updated_at=datetime.now(timezone.utc).isoformat(),
            metadata=new_meta,
        )


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
    runtime_name: str = "step-code"
    runtime_operation_id: str = ""
    adapter_version: str = "1.0.0"
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
            "runtime_name": self.runtime_name,
            "runtime_operation_id": self.runtime_operation_id,
            "adapter_version": self.adapter_version,
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
            runtime_name=data.get("runtime_name", "step-code"),
            runtime_operation_id=data.get("runtime_operation_id", ""),
            adapter_version=data.get("adapter_version", "1.0.0"),
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
        """Transitions operation state strictly adhering to the state machine (Requirement 12)."""
        if new_state == self.state:
            return
        allowed_next = _LEGAL_TRANSITIONS.get(self.state, set())
        if new_state not in allowed_next:
            raise SecurityViolationError(
                f"ILLEGAL OPERATION STATE TRANSITION: Cannot transition operation from {self.state.value} to {new_state.value}. "
                f"Permitted next states from {self.state.value}: {[s.value for s in allowed_next]}."
            )
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

    def assert_can_replay(
        self,
        current_workspace_id: Optional[str] = None,
        current_fingerprint: Optional[str] = None,
        current_argv: Optional[List[str]] = None,
        current_env: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Enforces state-aware replay safety (Requirements 20 & 21).
        Replay default is strictly NEVER; only proven SAFE workloads can be replayed.
        """
        if self.metadata.replay_class != ReplayClass.SAFE:
            raise SecurityViolationError(
                f"REPLAY REJECTED: Operation '{self.operation_id}' has replay_class={self.metadata.replay_class.value}. "
                "Replay default is strictly NEVER; only hermetic SAFE workloads can be replayed."
            )

        if current_workspace_id and self.metadata.workspace_id:
            if os.path.normpath(current_workspace_id).lower() != os.path.normpath(self.metadata.workspace_id).lower():
                raise SecurityViolationError(
                    f"REPLAY WORKSPACE MISMATCH: Operation bound to workspace '{self.metadata.workspace_id}', "
                    f"attempted replay in '{current_workspace_id}'."
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
        st_val = data.get("state")
        if st_val is not None and st_val in OperationState._value2member_map_:
            st = OperationState(st_val)
        else:
            st = OperationState.CORRUPT
        return cls(
            metadata=meta,
            state=st,
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

    def to_cross_runtime_operation(self) -> CrossRuntimeOperation:
        """Converts to authoritative cross-runtime operation reference."""
        return CrossRuntimeOperation(
            operation_id=self.metadata.operation_id,
            runtime_name=self.metadata.runtime_name,
            runtime_operation_id=self.metadata.runtime_operation_id,
            session_id=self.metadata.session_id,
            task_id=self.metadata.task_id,
            action_id=self.metadata.action_id,
            workspace_id=self.metadata.workspace_id,
            intent_hash=self.metadata.intent_hash,
            action_hash=self.metadata.action_hash,
            replay_class=self.metadata.replay_class,
            adapter_version=self.metadata.adapter_version,
            state=self.state,
            authorization_id=self.authorization_id,
            effect_result=self.effect_result,
            settlement=self.settlement_record,
            created_at=self.metadata.created_at,
            updated_at=self.updated_at,
        )


class CanonicalOperationStore:
    """
    Authoritative persistent store for cross-runtime operation references.
    Persists operations into canonical storage (.sclass/trust/cross_runtime_operations.jsonl
    and SQLite project.db cross_runtime_operations table) rather than relying on in-memory dicts.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.paths = WorkspacePaths(self.workspace_dir)
        self.paths.ensure_directories()
        self.store_file = os.path.join(self.paths.trust_dir, "cross_runtime_operations.jsonl")
        self.stale_marker_file = os.path.join(self.paths.trust_dir, "derived_index_stale")
        self._derived_index_healthy = True

    @property
    def is_derived_index_healthy(self) -> bool:
        """Returns True if the derived index is healthy and not marked stale on disk."""
        return self._derived_index_healthy and not os.path.exists(self.stale_marker_file)

    def _mark_derived_index_unhealthy(self) -> None:
        self._derived_index_healthy = False
        try:
            with open(self.stale_marker_file, "w", encoding="utf-8") as f:
                f.write(datetime.now(timezone.utc).isoformat())
        except Exception:
            pass

    def _quarantine_trailing_record(self, raw_line: str, reason: str = "") -> None:
        """Quarantines an interrupted/truncated trailing record to preserve forensics without breaking reads."""
        try:
            quarantine_file = os.path.join(self.paths.trust_dir, "quarantined_interrupted_operations.log")
            os.makedirs(os.path.dirname(quarantine_file), exist_ok=True)
            with open(quarantine_file, "a", encoding="utf-8") as qf:
                ts = datetime.now(timezone.utc).isoformat()
                qf.write(f"[{ts}] reason={reason} snippet={raw_line}\n")
        except Exception:
            pass

    def _ensure_clean_trailing_line_before_append(self) -> None:
        """
        Ensures that self.store_file does not end with an interrupted partial line or missing newline.
        If a trailing partial line exists from a prior crashed writer, quarantines it and truncates the file.
        Fails closed with ObservationIntegrityError if any mid-file record is corrupted.
        """
        if not os.path.exists(self.store_file) or os.path.getsize(self.store_file) == 0:
            return

        with open(self.store_file, "r", encoding="utf-8", errors="replace") as f:
            raw_lines = f.readlines()

        non_empty = []
        for idx, raw_line in enumerate(raw_lines):
            line = raw_line.strip()
            if line:
                non_empty.append((idx, line, raw_line))

        if not non_empty:
            with open(self.store_file, "w", encoding="utf-8") as f:
                pass
            return

        last_idx, last_line, last_raw = non_empty[-1]

        # Verify all mid-file records are intact
        for idx, line, _ in non_empty[:-1]:
            try:
                data = json.loads(line)
                if not isinstance(data, dict) or "operation_id" not in data or not data.get("operation_id"):
                    raise ObservationIntegrityError(f"Malformed operation record at line {idx + 1}: {line}")
            except Exception as e:
                if isinstance(e, ObservationIntegrityError):
                    raise
                raise ObservationIntegrityError(
                    f"Corrupted mid-file operation JSONL line at line {idx + 1}: {line}"
                ) from e

        # Check trailing non-empty record
        tail_corrupt = False
        tail_reason = ""
        try:
            data = json.loads(last_line)
            if not isinstance(data, dict) or "operation_id" not in data or not data.get("operation_id"):
                tail_corrupt = True
                tail_reason = "Malformed operation record: missing operation_id or not a dict"
        except Exception as e:
            tail_corrupt = True
            tail_reason = str(e)

        if tail_corrupt:
            self._quarantine_trailing_record(last_line, reason=tail_reason)
            logger.warning(
                f"Quarantining and truncating interrupted trailing line in {self.store_file}: {last_line[:120]}"
            )
            valid_raw_lines = raw_lines[:last_idx]
            with open(self.store_file, "w", encoding="utf-8") as f:
                for vl in valid_raw_lines:
                    f.write(vl if vl.endswith("\n") else vl + "\n")
        else:
            if not raw_lines[-1].endswith("\n"):
                with open(self.store_file, "a", encoding="utf-8") as f:
                    f.write("\n")

    def _read_canonical_operations_from_jsonl(self, lock: bool = True) -> List[CrossRuntimeOperation]:
        """
        Reads canonical operations from JSONL ledger with fail-closed integrity.
        Handles interrupted trailing writes safely and deterministically:
        - Trailing partial or truncated lines (common during abrupt process termination)
          are quarantined and ignored with a warning, preserving all prior valid records.
        - True mid-file corruption or malformed records fail closed with ObservationIntegrityError.
        """
        if not os.path.exists(self.store_file):
            return []

        def _do_read():
            if not os.path.exists(self.store_file):
                return []

            with open(self.store_file, "r", encoding="utf-8", errors="replace") as f:
                raw_lines = f.readlines()

            non_empty = []
            for idx, raw_line in enumerate(raw_lines):
                line = raw_line.strip()
                if line:
                    non_empty.append((idx, line))

            if not non_empty:
                return []

            last_idx, _ = non_empty[-1]
            ops: List[CrossRuntimeOperation] = []

            for idx, line in non_empty:
                is_tail = (idx == last_idx)
                try:
                    data = json.loads(line)
                    if not isinstance(data, dict) or "operation_id" not in data or not data.get("operation_id"):
                        raise ObservationIntegrityError(f"Malformed operation record at line {idx + 1}: {line}")
                    op = CrossRuntimeOperation.from_dict(data)
                    ops.append(op)
                except Exception as e:
                    if not is_tail:
                        if isinstance(e, ObservationIntegrityError):
                            raise
                        raise ObservationIntegrityError(
                            f"Corrupted mid-file operation JSONL line at line {idx + 1}: {line}"
                        ) from e

                    logger.warning(
                        f"Interrupted trailing JSONL write detected in {self.store_file} at line {idx + 1}. "
                        f"Quarantining incomplete trailing line to recover valid records: {line[:120]}"
                    )
                    self._quarantine_trailing_record(line, reason=str(e))

            return ops

        if lock:
            with WorkspaceLock(self.workspace_dir, lock_name="operation_store"):
                return _do_read()
        else:
            return _do_read()

    def save_operation(self, op: Union[CrossRuntimeOperation, DurableOperation]) -> CrossRuntimeOperation:
        """Atomically persists a cross-runtime operation reference."""
        record = op.to_cross_runtime_operation() if isinstance(op, DurableOperation) else op
        op_dict = record.to_dict()

        with WorkspaceLock(self.workspace_dir, lock_name="operation_store"):
            # 1. Append to canonical JSONL ledger
            try:
                self._ensure_clean_trailing_line_before_append()
                with open(self.store_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(op_dict) + "\n")
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        pass
            except Exception as e:
                if isinstance(e, (SecurityViolationError, ObservationIntegrityError)):
                    raise
                raise SecurityViolationError(f"Failed to persist canonical operation to JSONL ledger: {e}") from e

            # 2. Persist to SQLite state store if available (derived index)
            try:
                db_path = os.path.join(self.paths.state_dir, "project.db")
                os.makedirs(self.paths.state_dir, exist_ok=True)
                import sqlite3
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS cross_runtime_operations (
                            operation_id TEXT PRIMARY KEY,
                            runtime_name TEXT,
                            runtime_operation_id TEXT,
                            session_id TEXT,
                            task_id TEXT,
                            action_id TEXT,
                            workspace_id TEXT,
                            intent_hash TEXT,
                            action_hash TEXT,
                            replay_class TEXT,
                            adapter_version TEXT,
                            state TEXT,
                            authorization_id TEXT,
                            effect_result_json TEXT,
                            settlement_json TEXT,
                            created_at TEXT,
                            updated_at TEXT,
                            metadata_json TEXT
                        )
                        """
                    )
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO cross_runtime_operations (
                            operation_id, runtime_name, runtime_operation_id, session_id,
                            task_id, action_id, workspace_id, intent_hash, action_hash,
                            replay_class, adapter_version, state, authorization_id,
                            effect_result_json, settlement_json, created_at, updated_at, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.operation_id,
                            record.runtime_name,
                            record.runtime_operation_id,
                            record.session_id,
                            record.task_id,
                            record.action_id,
                            record.workspace_id,
                            record.intent_hash,
                            record.action_hash,
                            record.replay_class.value,
                            record.adapter_version,
                            record.state.value,
                            record.authorization_id,
                            json.dumps(record.effect_result or {}),
                            json.dumps(record.settlement or {}),
                            record.created_at,
                            record.updated_at,
                            json.dumps(record.metadata),
                        ),
                    )
                    conn.commit()
            except Exception:
                self._mark_derived_index_unhealthy()

        return record

    def _get_operation_from_jsonl(self, operation_id: str) -> Optional[CrossRuntimeOperation]:
        if not os.path.exists(self.store_file):
            return None
        with WorkspaceLock(self.workspace_dir, lock_name="operation_store"):
            ops = self._read_canonical_operations_from_jsonl(lock=False)
            latest = None
            for op in ops:
                if op.operation_id == operation_id:
                    latest = op
            return latest

    def get_operation(self, operation_id: str) -> Optional[CrossRuntimeOperation]:
        """Loads operation from persistent storage, reconciling SQLite index with canonical JSONL journal."""
        canonical_op = self._get_operation_from_jsonl(operation_id)

        # 1. Try indexed SQLite database if derived index is healthy
        if self.is_derived_index_healthy:
            try:
                db_path = os.path.join(self.paths.state_dir, "project.db")
                if os.path.exists(db_path):
                    import sqlite3
                    row = None
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.execute(
                            """
                            SELECT operation_id, runtime_name, runtime_operation_id, session_id,
                                   task_id, action_id, workspace_id, intent_hash, action_hash,
                                   replay_class, adapter_version, state, authorization_id,
                                   effect_result_json, settlement_json, created_at, updated_at, metadata_json
                            FROM cross_runtime_operations
                            WHERE operation_id = ?
                            """,
                            (operation_id,),
                        )
                        row = cursor.fetchone()

                    if row:
                        # Phantom row detection: SQLite row exists, but canonical JSONL has NO record of it
                        if canonical_op is None:
                            self._mark_derived_index_unhealthy()
                            self.rebuild_derived_index()
                            return None

                        st_val = row[11]
                        act_hash = row[8]
                        # If canonical JSONL exists, derived SQLite must NOT contradict canonical state or action_hash (CF-08)
                        if canonical_op.state.value != st_val or canonical_op.action_hash != act_hash:
                            self._mark_derived_index_unhealthy()
                            self.rebuild_derived_index()
                            return canonical_op

                        rc_val = row[9]
                        return CrossRuntimeOperation(
                            operation_id=row[0],
                            runtime_name=row[1],
                            runtime_operation_id=row[2],
                            session_id=row[3],
                            task_id=row[4],
                            action_id=row[5],
                            workspace_id=row[6],
                            intent_hash=row[7],
                            action_hash=row[8],
                            replay_class=ReplayClass(rc_val) if rc_val in ReplayClass._value2member_map_ else ReplayClass.NEVER,
                            adapter_version=row[10],
                            state=OperationState(st_val) if st_val in OperationState._value2member_map_ else OperationState.CORRUPT,
                            authorization_id=row[12],
                            effect_result=json.loads(row[13]) if row[13] else None,
                            settlement=json.loads(row[14]) if row[14] else None,
                            created_at=row[15],
                            updated_at=row[16],
                            metadata=json.loads(row[17]) if row[17] else {},
                        )
            except Exception:
                self._mark_derived_index_unhealthy()

        return canonical_op

    def list_operations(self, task_id: Optional[str] = None, session_id: Optional[str] = None) -> List[CrossRuntimeOperation]:
        """
        Lists operations strictly anchored to canonical JSONL authority.
        SQLite derived index is cryptographically reconciled against canonical ledger
        before any results can be returned.
        """
        db_path = os.path.join(self.paths.state_dir, "project.db")

        # Canonical JSONL ledger is the ground truth authority
        if not os.path.exists(self.store_file):
            if os.path.exists(db_path):
                try:
                    import sqlite3
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.execute(
                            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='cross_runtime_operations'"
                        )
                        if cursor.fetchone()[0] > 0:
                            count_cursor = conn.execute("SELECT count(*) FROM cross_runtime_operations")
                            if count_cursor.fetchone()[0] > 0:
                                self._mark_derived_index_unhealthy()
                                self.rebuild_derived_index()
                except Exception:
                    self._mark_derived_index_unhealthy()
            return []

        canonical_ops: Dict[str, CrossRuntimeOperation] = {}
        with WorkspaceLock(self.workspace_dir, lock_name="operation_store"):
            ops = self._read_canonical_operations_from_jsonl(lock=False)
            for op in ops:
                canonical_ops[op.operation_id] = op

        # If derived index is claimed healthy, reconcile against canonical storage (CF-08)
        if self.is_derived_index_healthy:
            needs_rebuild = False
            try:
                if os.path.exists(db_path):
                    import sqlite3
                    rows = []
                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.execute(
                            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='cross_runtime_operations'"
                        )
                        if cursor.fetchone()[0] > 0:
                            cursor = conn.execute("SELECT operation_id, state, action_hash FROM cross_runtime_operations")
                            rows = cursor.fetchall()
                    for row in rows:
                        op_id, st_val, act_hash = row[0], row[1], row[2]
                        can_op = canonical_ops.get(op_id)
                        # Cryptographic reconciliation: SQLite must never contradict canonical storage
                        if can_op is None or can_op.state.value != st_val or can_op.action_hash != act_hash:
                            needs_rebuild = True
                            break
                    if needs_rebuild:
                        self._mark_derived_index_unhealthy()
                        self.rebuild_derived_index()
            except Exception:
                self._mark_derived_index_unhealthy()
        else:
            # Derived index was marked unhealthy or stale: deterministically rebuild to purge phantoms and restore health
            try:
                self.rebuild_derived_index()
            except Exception:
                self._mark_derived_index_unhealthy()

        filtered_ops = [
            op for op in canonical_ops.values()
            if (not task_id or op.task_id == task_id) and (not session_id or op.session_id == session_id)
        ]
        filtered_ops.sort(key=lambda o: o.created_at)
        return filtered_ops

    def rebuild_derived_index(self) -> int:
        """Rebuilds the SQLite derived index from the canonical JSONL ledger (Req 14)."""
        db_path = os.path.join(self.paths.state_dir, "project.db")
        with WorkspaceLock(self.workspace_dir, lock_name="operation_store"):
            if not os.path.exists(self.store_file):
                if os.path.exists(db_path):
                    try:
                        import sqlite3
                        with sqlite3.connect(db_path) as conn:
                            conn.execute(
                                "CREATE TABLE IF NOT EXISTS cross_runtime_operations (operation_id TEXT PRIMARY KEY)"
                            )
                            conn.execute("DELETE FROM cross_runtime_operations")
                            conn.commit()
                    except Exception:
                        pass
                self._derived_index_healthy = True
                try:
                    if os.path.exists(self.stale_marker_file):
                        os.remove(self.stale_marker_file)
                except Exception:
                    pass
                return 0

            ops = self._read_canonical_operations_from_jsonl(lock=False)

            try:
                os.makedirs(self.paths.state_dir, exist_ok=True)
                import sqlite3
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS cross_runtime_operations (
                            operation_id TEXT PRIMARY KEY,
                            runtime_name TEXT,
                            runtime_operation_id TEXT,
                            session_id TEXT,
                            task_id TEXT,
                            action_id TEXT,
                            workspace_id TEXT,
                            intent_hash TEXT,
                            action_hash TEXT,
                            replay_class TEXT,
                            adapter_version TEXT,
                            state TEXT,
                            authorization_id TEXT,
                            effect_result_json TEXT,
                            settlement_json TEXT,
                            created_at TEXT,
                            updated_at TEXT,
                            metadata_json TEXT
                        )
                        """
                    )
                    # Purge all existing records to eliminate phantom rows
                    conn.execute("DELETE FROM cross_runtime_operations")
                    for record in ops:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO cross_runtime_operations (
                                operation_id, runtime_name, runtime_operation_id, session_id,
                                task_id, action_id, workspace_id, intent_hash, action_hash,
                                replay_class, adapter_version, state, authorization_id,
                                effect_result_json, settlement_json, created_at, updated_at, metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                record.operation_id,
                                record.runtime_name,
                                record.runtime_operation_id,
                                record.session_id,
                                record.task_id,
                                record.action_id,
                                record.workspace_id,
                                record.intent_hash,
                                record.action_hash,
                                record.replay_class.value,
                                record.adapter_version,
                                record.state.value,
                                record.authorization_id,
                                json.dumps(record.effect_result or {}),
                                json.dumps(record.settlement or {}),
                                record.created_at,
                                record.updated_at,
                                json.dumps(record.metadata),
                            ),
                        )
                    conn.commit()
            except Exception as e:
                self._mark_derived_index_unhealthy()
                raise ObservationIntegrityError(f"Failed to rebuild derived SQLite index: {e}") from e

            self._derived_index_healthy = True
            try:
                if os.path.exists(self.stale_marker_file):
                    os.remove(self.stale_marker_file)
            except Exception:
                pass
            return len(ops)


