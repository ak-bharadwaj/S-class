"""
S-Class EOS V11.2 - Schemathesis Provider Models & D0 Evidence Contract.
Defines native S-Class data contracts, worker invocation/output envelopes with keyed HMAC authentication,
and multi-layer verifiable hash chains.
Zero external Schemathesis types escape this module.
"""

import json
import hmac
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
class WorkerInvocationEnvelope:
    """
    Keyed authenticity-bound envelope sent from parent runner to isolated child worker.
    Binds execution identity, nonce challenge, parent secret, source SHA, and target config.
    """
    execution_id: str
    parent_nonce: str
    execution_secret: str
    source_sha: str
    provider_version: str
    target_identifier: str
    target_hash: str
    config_hash: str
    schema_dict: Optional[Dict[str, Any]]
    base_url: Optional[str] = None
    app_module: Optional[str] = None
    app_callable: Optional[str] = None
    max_examples: int = 5
    input_digest: str = ""

    def __post_init__(self):
        if not self.input_digest:
            self.input_digest = self.compute_input_digest()

    def compute_input_digest(self) -> str:
        payload = {
            "execution_id": self.execution_id,
            "parent_nonce": self.parent_nonce,
            "source_sha": self.source_sha,
            "provider_version": self.provider_version,
            "target_identifier": self.target_identifier,
            "target_hash": self.target_hash,
            "config_hash": self.config_hash,
            "schema_dict": self.schema_dict,
            "base_url": self.base_url,
            "app_module": self.app_module,
            "app_callable": self.app_callable,
            "max_examples": self.max_examples
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkerOutputEnvelope:
    """
    Keyed authenticity-bound envelope emitted from child worker to parent runner.
    Contains cryptographic proof of execution signed using the parent's secret via HMAC-SHA256.
    """
    execution_id: str
    parent_nonce: str
    worker_pid: int
    status: str
    exit_code: int
    violations: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    worker_digest: str = ""
    worker_hmac: str = ""

    def __post_init__(self):
        if not self.worker_digest:
            self.worker_digest = self.compute_worker_digest()

    def compute_worker_digest(self) -> str:
        payload = {
            "execution_id": self.execution_id,
            "parent_nonce": self.parent_nonce,
            "worker_pid": self.worker_pid,
            "status": self.status,
            "exit_code": self.exit_code,
            "violations": self.violations,
            "stats": self.stats,
            "diagnostics": self.diagnostics,
            "summary": self.summary
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def compute_worker_hmac(self, secret: str) -> str:
        payload = {
            "execution_id": self.execution_id,
            "parent_nonce": self.parent_nonce,
            "worker_pid": self.worker_pid,
            "status": self.status,
            "exit_code": self.exit_code,
            "violations": self.violations,
            "stats": self.stats,
            "diagnostics": self.diagnostics,
            "summary": self.summary
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderExecutionResult:
    """
    S-Class Native Evidence Contract for API Contract Provider Execution (D0 Specification).
    No Schemathesis-specific objects are allowed within this structure.
    Immutably links input_digest, worker_hmac, and provenance_hash.
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
    execution_nonce: str = ""
    input_digest: str = ""
    worker_digest: str = ""
    worker_hmac: str = ""
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
            "execution_nonce": self.execution_nonce,
            "provider_version": self.provider_version,
            "schemathesis_version": self.schemathesis_version,
            "source_sha": self.source_sha,
            "schema_hash": self.schema_hash,
            "target_identifier": self.target_identifier,
            "target_hash": self.target_hash,
            "config_hash": self.config_hash,
            "input_digest": self.input_digest,
            "worker_digest": self.worker_digest,
            "worker_hmac": self.worker_hmac,
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
            "execution_nonce": self.execution_nonce,
            "provider_version": self.provider_version,
            "schemathesis_version": self.schemathesis_version,
            "source_sha": self.source_sha,
            "schema_hash": self.schema_hash,
            "target_identifier": self.target_identifier,
            "target_hash": self.target_hash,
            "config_hash": self.config_hash,
            "input_digest": self.input_digest,
            "worker_digest": self.worker_digest,
            "worker_hmac": self.worker_hmac,
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
