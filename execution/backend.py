"""
S-Class EOS V11.2 - D6 Execution Backend Protocol Interface.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Protocol, runtime_checkable
from execution.models import TerminationReason, ResourceUsage


@dataclass(frozen=True)
class BackendProcessResult:
    """Raw process result returned by an ExecutionBackend implementation."""
    exit_code: int
    stdout_bytes: bytes
    stderr_bytes: bytes
    stdout_truncated: bool
    stderr_truncated: bool
    started_at: str
    ended_at: str
    termination_reason: TerminationReason
    resource_usage: ResourceUsage
    error_message: Optional[str] = None


@runtime_checkable
class ExecutionBackend(Protocol):
    """Protocol for execution backends (e.g. LocalProcessBackend, container, VM)."""

    def execute_command(
        self,
        command_argv: Sequence[str],
        working_directory: str,
        environment: Optional[Mapping[str, str]] = None,
        timeout_seconds: float = 30.0,
        max_output_bytes: int = 1048576,  # 1 MB default limit
    ) -> BackendProcessResult:
        """Executes a command argv array with strict bounds, timeouts, and process-tree termination."""
        ...
