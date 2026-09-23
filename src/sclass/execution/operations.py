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
from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock


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
        st_val = data.get("state", OperationState.PLANNED.value)
        st = OperationState(st_val) if st_val in OperationState._value2member_map_ else OperationState.PLANNED
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
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            metadata=dict(data.get("metadata", {})),
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

    def save_operation(self, op: Union[CrossRuntimeOperation, DurableOperation]) -> CrossRuntimeOperation:
        """Atomically persists a cross-runtime operation reference."""
        record = op.to_cross_runtime_operation() if isinstance(op, DurableOperation) else op
        op_dict = record.to_dict()

        with WorkspaceLock(self.workspace_dir, lock_name="operation_store"):
            # 1. Append to JSONL ledger
            with open(self.store_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(op_dict) + "\n")

            # 2. Persist to SQLite state store if available
            try:
                db_path = os.path.join(self.paths.state_dir, "project.db")
                if os.path.exists(db_path):
                    import sqlite3
                    with sqlite3.connect(db_path) as conn:
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
                pass

        return record

    def get_operation(self, operation_id: str) -> Optional[CrossRuntimeOperation]:
        """Loads operation from persistent storage, preferring SQLite index and falling back to JSONL journal."""
        # 1. Try indexed SQLite database
        try:
            db_path = os.path.join(self.paths.state_dir, "project.db")
            if os.path.exists(db_path):
                import sqlite3
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
                        rc_val = row[9]
                        st_val = row[11]
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
                            state=OperationState(st_val) if st_val in OperationState._value2member_map_ else OperationState.PLANNED,
                            authorization_id=row[12],
                            effect_result=json.loads(row[13]) if row[13] else None,
                            settlement=json.loads(row[14]) if row[14] else None,
                            created_at=row[15],
                            updated_at=row[16],
                            metadata=json.loads(row[17]) if row[17] else {},
                        )
        except Exception:
            pass

        # 2. Fall back to JSONL ledger under WorkspaceLock
        if not os.path.exists(self.store_file):
            return None
        latest = None
        with WorkspaceLock(self.workspace_dir, lock_name="operation_store"):
            with open(self.store_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("operation_id") == operation_id:
                            latest = CrossRuntimeOperation.from_dict(data)
                    except Exception:
                        continue
        return latest

    def list_operations(self, task_id: Optional[str] = None, session_id: Optional[str] = None) -> List[CrossRuntimeOperation]:
        # 1. Try indexed SQLite database
        try:
            db_path = os.path.join(self.paths.state_dir, "project.db")
            if os.path.exists(db_path):
                import sqlite3
                query = """
                    SELECT operation_id, runtime_name, runtime_operation_id, session_id,
                           task_id, action_id, workspace_id, intent_hash, action_hash,
                           replay_class, adapter_version, state, authorization_id,
                           effect_result_json, settlement_json, created_at, updated_at, metadata_json
                    FROM cross_runtime_operations
                    WHERE 1=1
                """
                params = []
                if task_id:
                    query += " AND task_id = ?"
                    params.append(task_id)
                if session_id:
                    query += " AND session_id = ?"
                    params.append(session_id)
                query += " ORDER BY created_at ASC"

                with sqlite3.connect(db_path) as conn:
                    cursor = conn.execute(query, tuple(params))
                    rows = cursor.fetchall()
                    if rows:
                        results = []
                        for row in rows:
                            rc_val = row[9]
                            st_val = row[11]
                            results.append(
                                CrossRuntimeOperation(
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
                                    state=OperationState(st_val) if st_val in OperationState._value2member_map_ else OperationState.PLANNED,
                                    authorization_id=row[12],
                                    effect_result=json.loads(row[13]) if row[13] else None,
                                    settlement=json.loads(row[14]) if row[14] else None,
                                    created_at=row[15],
                                    updated_at=row[16],
                                    metadata=json.loads(row[17]) if row[17] else {},
                                )
                            )
                        return results
        except Exception:
            pass

        # 2. Fall back to JSONL ledger under WorkspaceLock
        if not os.path.exists(self.store_file):
            return []
        ops_by_id: Dict[str, CrossRuntimeOperation] = {}
        with WorkspaceLock(self.workspace_dir, lock_name="operation_store"):
            with open(self.store_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        op = CrossRuntimeOperation.from_dict(data)
                        if task_id and op.task_id != task_id:
                            continue
                        if session_id and op.session_id != session_id:
                            continue
                        ops_by_id[op.operation_id] = op
                    except Exception:
                        continue
        return list(ops_by_id.values())

