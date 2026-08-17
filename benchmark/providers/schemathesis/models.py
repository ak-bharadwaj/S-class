"""
S-Class EOS V11.2 - Schemathesis Provider Models & Evidence Contract.
Defines the native S-Class data contracts for API behavioral and contract evidence.
Zero external Schemathesis types escape this module.
"""

import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


class ProviderStatus(str, Enum):
    """Explicit fail-closed epistemic states for Schemathesis provider execution."""
    TARGET_CLEAN = "TARGET_CLEAN"
    TARGET_CONTRACT_VIOLATED = "TARGET_CONTRACT_VIOLATED"
    TOOL_NOT_AVAILABLE = "TOOL_NOT_AVAILABLE"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    INPUT_INVALID = "INPUT_INVALID"
    TIMEOUT = "TIMEOUT"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class ContractViolation:
    """Represents a discrete API contract or schema violation."""
    error_type: str
    message: str
    path: str
    method: str
    status_code: Optional[int] = None
    curl_command: Optional[str] = None
    schema_path: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionStats:
    """Statistical summary of Schemathesis contract execution."""
    endpoints_tested: int = 0
    operations_tested: int = 0
    checks_executed: int = 0
    violations_count: int = 0
    duration_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderExecutionResult:
    """
    S-Class Native Evidence Contract for API Contract Provider Execution.
    No Schemathesis-specific objects are allowed within this structure.
    """
    execution_id: str
    provider_version: str
    schemathesis_version: Optional[str]
    source_sha: str
    schema_hash: str
    target_identifier: str
    target_hash: str
    config_hash: str
    status: ProviderStatus
    exit_code: Optional[int]
    start_time_iso: str
    stop_time_iso: str
    duration_sec: float
    violations: List[ContractViolation] = field(default_factory=list)
    stats: ExecutionStats = field(default_factory=ExecutionStats)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    raw_output_summary: str = ""
    provenance_hash: str = ""

    def __post_init__(self):
        if isinstance(self.status, str):
            self.status = ProviderStatus(self.status)
        if not self.provenance_hash:
            self.provenance_hash = self.compute_provenance_hash()

    def compute_provenance_hash(self) -> str:
        payload = {
            "execution_id": self.execution_id,
            "provider_version": self.provider_version,
            "schemathesis_version": self.schemathesis_version,
            "source_sha": self.source_sha,
            "schema_hash": self.schema_hash,
            "target_identifier": self.target_identifier,
            "target_hash": self.target_hash,
            "config_hash": self.config_hash,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "start_time_iso": self.start_time_iso,
            "stop_time_iso": self.stop_time_iso,
            "duration_sec": self.duration_sec,
            "violations": [v.to_dict() if isinstance(v, ContractViolation) else v for v in self.violations],
            "stats": self.stats.to_dict() if isinstance(self.stats, ExecutionStats) else self.stats,
            "diagnostics": self.diagnostics
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @property
    def passed(self) -> bool:
        """Authority Invariant: Execution is only passed if status is strictly TARGET_CLEAN."""
        return self.status == ProviderStatus.TARGET_CLEAN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "provider_version": self.provider_version,
            "schemathesis_version": self.schemathesis_version,
            "source_sha": self.source_sha,
            "schema_hash": self.schema_hash,
            "target_identifier": self.target_identifier,
            "target_hash": self.target_hash,
            "config_hash": self.config_hash,
            "status": self.status.value,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "start_time_iso": self.start_time_iso,
            "stop_time_iso": self.stop_time_iso,
            "duration_sec": self.duration_sec,
            "violations": [v.to_dict() if isinstance(v, ContractViolation) else v for v in self.violations],
            "stats": self.stats.to_dict() if isinstance(self.stats, ExecutionStats) else self.stats,
            "diagnostics": self.diagnostics,
            "raw_output_summary": self.raw_output_summary,
            "provenance_hash": self.provenance_hash
        }
