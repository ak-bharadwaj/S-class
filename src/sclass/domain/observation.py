"""
S-Class Domain: Observation.
Captures independently observed execution facts from the workspace.
"""

from __future__ import annotations
import uuid
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sclass.domain.execution import ExecutionIdentity
from sclass.observation.record import (
    ObservationRecord,
    ProcessTelemetry,
    GitRevisionState,
    WorkspaceDelta,
    FileMutation,
)


@dataclass
class Observation:
    """Independently recorded facts of a process or workspace execution."""
    observation_id: str
    task_id: str
    execution_identity: ExecutionIdentity
    command: str
    exit_code: int
    stdout_hash: str
    stderr_hash: str
    workspace_fingerprint_before: str
    workspace_fingerprint_after: str
    started_at: str
    finished_at: str
    duration_ms: float = 0.0
    files_changed: List[str] = field(default_factory=list)
    raw_stdout: Optional[str] = field(default=None, repr=False)
    raw_stderr: Optional[str] = field(default=None, repr=False)
    metadata: Dict[str, Any] = field(default_factory=dict)
    observation_record: Optional[ObservationRecord] = None

    def compute_hash(self) -> str:
        """Computes cryptographic digest of the observation facts."""
        canonical_str = (
            f"{self.observation_id}|{self.task_id}|{self.execution_identity.compute_identity_hash()}|"
            f"{self.command}|{self.exit_code}|{self.stdout_hash}|{self.stderr_hash}|"
            f"{self.workspace_fingerprint_before}|{self.workspace_fingerprint_after}|"
            f"{self.started_at}|{self.finished_at}|{','.join(sorted(self.files_changed))}"
        )
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "task_id": self.task_id,
            "execution_identity": self.execution_identity.to_dict(),
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout_hash": self.stdout_hash,
            "stderr_hash": self.stderr_hash,
            "workspace_fingerprint_before": self.workspace_fingerprint_before,
            "workspace_fingerprint_after": self.workspace_fingerprint_after,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "files_changed": list(self.files_changed),
            "observation_hash": self.compute_hash(),
            "metadata": self.metadata,
            "observation_record": self.observation_record.to_dict() if self.observation_record else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Observation:
        obs_rec_data = data.get("observation_record")
        obs_rec = ObservationRecord.from_dict(obs_rec_data) if (obs_rec_data and isinstance(obs_rec_data, dict)) else None
        return cls(
            observation_id=data["observation_id"],
            task_id=data.get("task_id", "task_default"),
            execution_identity=ExecutionIdentity.from_dict(data.get("execution_identity", {})),
            command=data.get("command", ""),
            exit_code=data.get("exit_code", 1),
            stdout_hash=data.get("stdout_hash", ""),
            stderr_hash=data.get("stderr_hash", ""),
            workspace_fingerprint_before=data.get("workspace_fingerprint_before", ""),
            workspace_fingerprint_after=data.get("workspace_fingerprint_after", ""),
            started_at=data.get("started_at", datetime.now(timezone.utc).isoformat()),
            finished_at=data.get("finished_at", datetime.now(timezone.utc).isoformat()),
            duration_ms=data.get("duration_ms", 0.0),
            files_changed=list(data.get("files_changed", [])),
            metadata=data.get("metadata", {}),
            observation_record=obs_rec,
        )


__all__ = [
    "Observation",
    "ObservationRecord",
    "ProcessTelemetry",
    "GitRevisionState",
    "WorkspaceDelta",
    "FileMutation",
]

