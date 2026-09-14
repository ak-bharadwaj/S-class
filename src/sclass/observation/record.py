"""
S-Class Observation: Independent Observation Record & Telemetry Schema (RC.3 / Layer E).
Captures authentic, unadulterated OS reality:
- OS process telemetry (PID, binary hash, start/end timestamps, CPU metrics)
- Granular workspace deltas (added, modified, deleted files, content hashes, bytes)
- Git revision state (HEAD commit, branch, porcelain status, diff stats)
- OpenTelemetry semantic spans with secret redaction

Zero agent self-report content; derives 100% from OS execution reality (Laws L1, L2, L4, L5).
"""

from __future__ import annotations
import os
import re
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union


SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{40,}"),
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),
]


def redact_observation_secrets(value: Any) -> Any:
    """Recursively redacts sensitive credentials and tokens from observation metadata."""
    if isinstance(value, str):
        result = value
        for pat in SECRET_PATTERNS:
            result = pat.sub("[REDACTED_SECRET]", result)
        return result
    elif isinstance(value, dict):
        return {k: redact_observation_secrets(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        redacted = [redact_observation_secrets(item) for item in value]
        return tuple(redacted) if isinstance(value, tuple) else redacted
    return value


@dataclass(frozen=True)
class ProcessTelemetry:
    """Authentic OS-level process execution metrics captured via OS primitives."""
    pid: int
    executable_path: str
    executable_hash: str  # SHA-256
    requested_argv: tuple[str, ...] = field(default_factory=tuple)
    actual_argv: tuple[str, ...] = field(default_factory=tuple)
    process_start_time: str = ""  # ISO 8601
    process_end_time: str = ""    # ISO 8601
    duration_ms: float = 0.0
    cpu_user_ms: Optional[float] = None
    cpu_kernel_ms: Optional[float] = None

    def __post_init__(self) -> None:
        if isinstance(self.requested_argv, (list, set)):
            object.__setattr__(self, "requested_argv", tuple(self.requested_argv))
        if isinstance(self.actual_argv, (list, set)):
            object.__setattr__(self, "actual_argv", tuple(self.actual_argv))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "executable_path": self.executable_path,
            "executable_hash": self.executable_hash,
            "requested_argv": list(self.requested_argv),
            "actual_argv": list(self.actual_argv),
            "process_start_time": self.process_start_time,
            "process_end_time": self.process_end_time,
            "duration_ms": round(self.duration_ms, 2),
            "cpu_user_ms": self.cpu_user_ms,
            "cpu_kernel_ms": self.cpu_kernel_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProcessTelemetry:
        return cls(
            pid=int(data.get("pid", 0)),
            executable_path=str(data.get("executable_path", "")),
            executable_hash=str(data.get("executable_hash", "")),
            requested_argv=tuple(data.get("requested_argv", ())),
            actual_argv=tuple(data.get("actual_argv", ())),
            process_start_time=str(data.get("process_start_time", "")),
            process_end_time=str(data.get("process_end_time", "")),
            duration_ms=float(data.get("duration_ms", 0.0)),
            cpu_user_ms=float(data["cpu_user_ms"]) if data.get("cpu_user_ms") is not None else None,
            cpu_kernel_ms=float(data["cpu_kernel_ms"]) if data.get("cpu_kernel_ms") is not None else None,
        )


@dataclass(frozen=True)
class GitRevisionState:
    """Git working tree revision status at observation time."""
    is_git_repository: bool
    revision_before: Optional[str] = None  # HEAD commit hash before action
    revision_after: Optional[str] = None   # HEAD commit hash after action
    branch: Optional[str] = None
    dirty_files: tuple[str, ...] = field(default_factory=tuple)
    untracked_files: tuple[str, ...] = field(default_factory=tuple)
    diff_stat: Optional[str] = None
    diff_hash: Optional[str] = None

    def __post_init__(self) -> None:
        if isinstance(self.dirty_files, (list, set)):
            object.__setattr__(self, "dirty_files", tuple(sorted(self.dirty_files)))
        if isinstance(self.untracked_files, (list, set)):
            object.__setattr__(self, "untracked_files", tuple(sorted(self.untracked_files)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_git_repository": self.is_git_repository,
            "revision_before": self.revision_before,
            "revision_after": self.revision_after,
            "branch": self.branch,
            "dirty_files": list(self.dirty_files),
            "untracked_files": list(self.untracked_files),
            "diff_stat": self.diff_stat,
            "diff_hash": self.diff_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GitRevisionState:
        return cls(
            is_git_repository=bool(data.get("is_git_repository", False)),
            revision_before=data.get("revision_before"),
            revision_after=data.get("revision_after"),
            branch=data.get("branch"),
            dirty_files=tuple(data.get("dirty_files", ())),
            untracked_files=tuple(data.get("untracked_files", ())),
            diff_stat=data.get("diff_stat"),
            diff_hash=data.get("diff_hash"),
        )


@dataclass(frozen=True)
class FileMutation:
    """Individual file-level mutation delta."""
    path: str
    status: str  # "added", "modified", "deleted"
    hash_before: Optional[str] = None
    hash_after: Optional[str] = None
    bytes_before: int = 0
    bytes_after: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "hash_before": self.hash_before,
            "hash_after": self.hash_after,
            "bytes_before": self.bytes_before,
            "bytes_after": self.bytes_after,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FileMutation:
        return cls(
            path=str(data.get("path", "")),
            status=str(data.get("status", "modified")),
            hash_before=data.get("hash_before"),
            hash_after=data.get("hash_after"),
            bytes_before=int(data.get("bytes_before", 0)),
            bytes_after=int(data.get("bytes_after", 0)),
        )


@dataclass(frozen=True)
class WorkspaceDelta:
    """Cryptographic delta of workspace changes."""
    tree_fingerprint_before: str
    tree_fingerprint_after: str
    files_added: tuple[str, ...] = field(default_factory=tuple)
    files_modified: tuple[str, ...] = field(default_factory=tuple)
    files_deleted: tuple[str, ...] = field(default_factory=tuple)
    mutations: tuple[FileMutation, ...] = field(default_factory=tuple)
    total_bytes_changed: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.files_added, (list, set)):
            object.__setattr__(self, "files_added", tuple(sorted(self.files_added)))
        if isinstance(self.files_modified, (list, set)):
            object.__setattr__(self, "files_modified", tuple(sorted(self.files_modified)))
        if isinstance(self.files_deleted, (list, set)):
            object.__setattr__(self, "files_deleted", tuple(sorted(self.files_deleted)))
        if isinstance(self.mutations, (list, set)):
            norm_muts = []
            for m in self.mutations:
                if isinstance(m, dict):
                    norm_muts.append(FileMutation.from_dict(m))
                else:
                    norm_muts.append(m)
            object.__setattr__(self, "mutations", tuple(norm_muts))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tree_fingerprint_before": self.tree_fingerprint_before,
            "tree_fingerprint_after": self.tree_fingerprint_after,
            "files_added": list(self.files_added),
            "files_modified": list(self.files_modified),
            "files_deleted": list(self.files_deleted),
            "mutations": [m.to_dict() for m in self.mutations],
            "total_bytes_changed": self.total_bytes_changed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkspaceDelta:
        muts = [FileMutation.from_dict(m) for m in data.get("mutations", [])]
        return cls(
            tree_fingerprint_before=str(data.get("tree_fingerprint_before", "")),
            tree_fingerprint_after=str(data.get("tree_fingerprint_after", "")),
            files_added=tuple(data.get("files_added", ())),
            files_modified=tuple(data.get("files_modified", ())),
            files_deleted=tuple(data.get("files_deleted", ())),
            mutations=tuple(muts),
            total_bytes_changed=int(data.get("total_bytes_changed", 0)),
        )


@dataclass(frozen=True)
class ObservationRecord:
    """
    Authoritative independent observation fact record (RC.3 / Layer E).
    Zero agent self-report content; derives 100% from OS reality.
    """
    record_id: str
    task_id: str
    claim_id: str
    command: str
    exit_code: int
    stdout_hash: str  # SHA-256
    stderr_hash: str  # SHA-256
    stdout_bytes: int
    stderr_bytes: int
    process: ProcessTelemetry
    workspace: WorkspaceDelta
    git: GitRevisionState
    semantic_spans: tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_stdout: Optional[str] = field(default=None, repr=False)
    raw_stderr: Optional[str] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self.semantic_spans, (list, set)):
            object.__setattr__(self, "semantic_spans", tuple(self.semantic_spans))

    def compute_hash(self) -> str:
        """Computes deterministic canonical SHA-256 digest of immutable observation facts."""
        payload = {
            "record_id": self.record_id,
            "task_id": self.task_id,
            "claim_id": self.claim_id,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout_hash": self.stdout_hash,
            "stderr_hash": self.stderr_hash,
            "executable_hash": self.process.executable_hash,
            "actual_argv": list(self.process.actual_argv),
            "tree_fingerprint_before": self.workspace.tree_fingerprint_before,
            "tree_fingerprint_after": self.workspace.tree_fingerprint_after,
            "git_revision_before": self.git.revision_before,
            "git_revision_after": self.git.revision_after,
            "files_added": list(self.workspace.files_added),
            "files_modified": list(self.workspace.files_modified),
            "files_deleted": list(self.workspace.files_deleted),
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "task_id": self.task_id,
            "claim_id": self.claim_id,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout_hash": self.stdout_hash,
            "stderr_hash": self.stderr_hash,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "process": self.process.to_dict(),
            "workspace": self.workspace.to_dict(),
            "git": self.git.to_dict(),
            "semantic_spans": list(self.semantic_spans),
            "created_at": self.created_at,
            "record_hash": self.compute_hash(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ObservationRecord:
        proc_data = data.get("process", {})
        ws_data = data.get("workspace", {})
        git_data = data.get("git", {})
        return cls(
            record_id=str(data["record_id"]),
            task_id=str(data.get("task_id", "task_default")),
            claim_id=str(data.get("claim_id", "claim_default")),
            command=str(data.get("command", "")),
            exit_code=int(data.get("exit_code", 1)),
            stdout_hash=str(data.get("stdout_hash", "")),
            stderr_hash=str(data.get("stderr_hash", "")),
            stdout_bytes=int(data.get("stdout_bytes", 0)),
            stderr_bytes=int(data.get("stderr_bytes", 0)),
            process=ProcessTelemetry.from_dict(proc_data) if isinstance(proc_data, dict) else proc_data,
            workspace=WorkspaceDelta.from_dict(ws_data) if isinstance(ws_data, dict) else ws_data,
            git=GitRevisionState.from_dict(git_data) if isinstance(git_data, dict) else git_data,
            semantic_spans=tuple(data.get("semantic_spans", ())),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
            raw_stdout=data.get("raw_stdout"),
            raw_stderr=data.get("raw_stderr"),
        )


__all__ = [
    "ProcessTelemetry",
    "GitRevisionState",
    "FileMutation",
    "WorkspaceDelta",
    "ObservationRecord",
    "redact_observation_secrets",
]
