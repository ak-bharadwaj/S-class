"""
S-Class EOS V11.2 - D6 Execution Models & Process Observation (§8.1, §8.3).
Immutable process observations capturing raw execution facts (not epistemic correctness).
"""

from __future__ import annotations
import enum
import hashlib
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence, Any, Tuple
from domain.models import _validate_pattern, _validate_iso8601, _freeze_nested
from domain.types import HEX_64_PATTERN
from events.serializer import canonicalize_json


class ExecutionStatus(str, enum.Enum):
    """Execution status describing raw process facts, NOT epistemic correctness."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    BACKEND_ERROR = "BACKEND_ERROR"
    GATEWAY_REJECTED = "GATEWAY_REJECTED"


class TerminationReason(str, enum.Enum):
    """Explicit reason for process or gateway termination."""
    EXIT_ZERO = "EXIT_ZERO"
    EXIT_NON_ZERO = "EXIT_NON_ZERO"
    TIMEOUT_EXPIRED = "TIMEOUT_EXPIRED"
    SIGNAL_TERMINATED = "SIGNAL_TERMINATED"
    ENVELOPE_INVALID = "ENVELOPE_INVALID"
    PATH_ESCAPE_DETECTED = "PATH_ESCAPE_DETECTED"
    CAPABILITY_VIOLATION = "CAPABILITY_VIOLATION"
    BACKEND_FAULT = "BACKEND_FAULT"
    WORKSPACE_ERROR = "WORKSPACE_ERROR"
    UNAUTHORIZED_PROVIDER = "UNAUTHORIZED_PROVIDER"
    UNAUTHORIZED_WORKSPACE = "UNAUTHORIZED_WORKSPACE"


class MeasurementStatus(str, enum.Enum):
    """Explicit status indicating whether a resource metric is enforced, observed, or unsupported."""
    ENFORCED = "ENFORCED"
    OBSERVED = "OBSERVED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class ResourceUsage:
    """Immutable resource consumption metrics with explicit measurement status."""
    wall_clock_seconds: float = 0.0
    wall_clock_status: MeasurementStatus = MeasurementStatus.OBSERVED
    output_bytes_status: MeasurementStatus = MeasurementStatus.ENFORCED
    process_tree_termination_status: MeasurementStatus = MeasurementStatus.ENFORCED
    cpu_user_seconds: Optional[float] = None
    cpu_system_seconds: Optional[float] = None
    cpu_status: MeasurementStatus = MeasurementStatus.UNSUPPORTED
    memory_peak_bytes: Optional[int] = None
    memory_status: MeasurementStatus = MeasurementStatus.UNSUPPORTED

    def __post_init__(self):
        if not isinstance(self.wall_clock_status, MeasurementStatus):
            raise TypeError("wall_clock_status must be an instance of MeasurementStatus.")
        if not isinstance(self.output_bytes_status, MeasurementStatus):
            raise TypeError("output_bytes_status must be an instance of MeasurementStatus.")
        if not isinstance(self.process_tree_termination_status, MeasurementStatus):
            raise TypeError("process_tree_termination_status must be an instance of MeasurementStatus.")
        if not isinstance(self.cpu_status, MeasurementStatus):
            raise TypeError("cpu_status must be an instance of MeasurementStatus.")
        if not isinstance(self.memory_status, MeasurementStatus):
            raise TypeError("memory_status must be an instance of MeasurementStatus.")

        if self.wall_clock_seconds < 0:
            raise ValueError("wall_clock_seconds cannot be negative.")
        if self.cpu_user_seconds is not None and self.cpu_user_seconds < 0:
            raise ValueError("cpu_user_seconds cannot be negative.")
        if self.cpu_system_seconds is not None and self.cpu_system_seconds < 0:
            raise ValueError("cpu_system_seconds cannot be negative.")
        if self.memory_peak_bytes is not None and self.memory_peak_bytes < 0:
            raise ValueError("memory_peak_bytes cannot be negative.")


@dataclass(frozen=True)
class ExecutionObservation:
    """Immutable record of process execution facts produced exclusively by D6 Execution Fabric."""
    execution_id: str
    token_id: str
    provider_id: str
    action_digest: str
    context_digest: str
    started_at: str
    ended_at: str
    exit_code: int
    termination_reason: TerminationReason
    stdout_digest: str
    stderr_digest: str
    stdout_bytes_len: int
    stderr_bytes_len: int
    execution_status: ExecutionStatus
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    raw_stdout_sample: str = ""
    raw_stderr_sample: str = ""
    diagnostics: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self):
        if not self.execution_id:
            raise ValueError("execution_id cannot be empty.")
        if not self.token_id:
            raise ValueError("token_id cannot be empty.")
        if not self.provider_id:
            raise ValueError("provider_id cannot be empty.")
        _validate_pattern(self.action_digest, HEX_64_PATTERN, "action_digest")
        _validate_pattern(self.context_digest, HEX_64_PATTERN, "context_digest")
        _validate_iso8601(self.started_at, "started_at")
        _validate_iso8601(self.ended_at, "ended_at")
        _validate_pattern(self.stdout_digest, HEX_64_PATTERN, "stdout_digest")
        _validate_pattern(self.stderr_digest, HEX_64_PATTERN, "stderr_digest")
        if not isinstance(self.termination_reason, TerminationReason):
            raise TypeError("termination_reason must be an instance of TerminationReason.")
        if not isinstance(self.execution_status, ExecutionStatus):
            raise TypeError("execution_status must be an instance of ExecutionStatus.")
        if not isinstance(self.resource_usage, ResourceUsage):
            raise TypeError("resource_usage must be an instance of ResourceUsage.")
        if self.stdout_bytes_len < 0:
            raise ValueError("stdout_bytes_len cannot be negative.")
        if self.stderr_bytes_len < 0:
            raise ValueError("stderr_bytes_len cannot be negative.")
        object.__setattr__(self, "diagnostics", tuple(_freeze_nested(d) for d in self.diagnostics))
