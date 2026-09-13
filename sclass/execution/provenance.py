"""
S-Class Execution: Process Provenance and Telemetry Alignment.
Maps ExecutionIdentity and ProcessExecutionResult to OpenTelemetry Process semantic conventions
while injecting S-Class trust anchors and redacting sensitive values.
"""

from __future__ import annotations
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass

from sclass.execution.identity import ExecutionIdentity


SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key|secret|token|password|auth|bearer)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),
]


def redact_secrets(text: str) -> str:
    """Redacts common credentials, tokens, and API keys from telemetry strings."""
    if not text:
        return ""
    result = text
    for pat in SECRET_PATTERNS:
        result = pat.sub("[REDACTED_SECRET]", result)
    return result


@dataclass(frozen=True)
class ProcessProvenanceRecord:
    """
    Standardized process provenance record aligned with OpenTelemetry process semantics.
    """
    pid: Optional[int]
    parent_pid: Optional[int]
    executable_path: str
    executable_hash: str
    command: str
    command_args: tuple[str, ...]
    cwd: str
    start_time: str
    exit_code: Optional[int]
    environment_digest: str
    execution_mode: str
    launcher_identity: Optional[str] = None
    wrapper_identity: Optional[str] = None
    task_id: Optional[str] = None
    action_id: Optional[str] = None
    observation_id: Optional[str] = None
    claim_id: Optional[str] = None
    agent: Optional[str] = None

    def to_otel_attributes(self) -> Dict[str, Any]:
        """Converts provenance record to standard OpenTelemetry semantic convention attributes."""
        attrs: Dict[str, Any] = {
            "process.pid": self.pid,
            "process.parent_pid": self.parent_pid,
            "process.executable.name": self.command_args[0] if self.command_args else "",
            "process.executable.path": self.executable_path,
            "process.command": redact_secrets(self.command),
            "process.command_args": [redact_secrets(arg) for arg in self.command_args],
            "process.working_directory": self.cwd,
            "process.creation.time": self.start_time,
            "process.exit.code": self.exit_code,
            "sclass.executable_hash": self.executable_hash,
            "sclass.environment_digest": self.environment_digest,
            "sclass.execution_mode": self.execution_mode,
        }
        if self.launcher_identity:
            attrs["sclass.launcher_identity"] = self.launcher_identity
        if self.wrapper_identity:
            attrs["sclass.wrapper_identity"] = self.wrapper_identity
        if self.task_id:
            attrs["sclass.task_id"] = self.task_id
        if self.action_id:
            attrs["sclass.action_id"] = self.action_id
        if self.observation_id:
            attrs["sclass.observation_id"] = self.observation_id
        if self.claim_id:
            attrs["sclass.claim_id"] = self.claim_id
        if self.agent:
            attrs["sclass.agent"] = self.agent
        return attrs

    @classmethod
    def from_identity(
        cls,
        identity: ExecutionIdentity,
        exit_code: Optional[int] = None,
        task_id: Optional[str] = None,
        action_id: Optional[str] = None,
        observation_id: Optional[str] = None,
        claim_id: Optional[str] = None,
        agent: Optional[str] = None,
    ) -> ProcessProvenanceRecord:
        return cls(
            pid=identity.pid,
            parent_pid=identity.parent_pid,
            executable_path=identity.executable_path,
            executable_hash=identity.executable_hash,
            command=" ".join(identity.actual_argv),
            command_args=identity.actual_argv,
            cwd=identity.cwd,
            start_time=identity.process_start_time,
            exit_code=exit_code,
            environment_digest=identity.environment_digest,
            execution_mode=identity.execution_mode,
            launcher_identity=identity.launcher_identity,
            wrapper_identity=identity.wrapper_identity,
            task_id=task_id,
            action_id=action_id,
            observation_id=observation_id,
            claim_id=claim_id,
            agent=agent,
        )
