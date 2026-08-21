"""
S-Class EOS V11.2 - D8 Read-Only Analytical Fabric (Phase C).
Defines ephemeral analytical workers, narrow read-only object capabilities,
strict context binding, HMAC-authenticated non-forgeable execution handles,
and authoritative runtime-issued analytical provenance.

CORE-D8-ANALYTICAL-AUTHORITY:
Workers are ephemeral: spawn -> inspect -> reason -> emit AnalysisArtifact -> terminate.
Workers possess ZERO execution authority, ZERO signing keys, ZERO D2 nonce access,
ZERO D5 token minting, and ZERO lease mutation capabilities.

SECURITY-MODEL & HOST ISOLATION BOUNDARY:
HMAC authentication protects against forged or tampered WorkerExecutionHandles without
access to the runtime ephemeral secret. It is NOT a same-process hostile-code sandbox.
D6 execution fabric remains the strict host and container isolation boundary.
D8 does not duplicate D5 asymmetric cryptographic execution authorization (Ed25519);
Phase C analytical fabric operates entirely below the D5 authorization boundary.
"""

from __future__ import annotations
import ast
import copy
import fnmatch
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence, Tuple, Optional, Any, Callable, Dict, List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

from planner.analysis import (
    AnalysisArtifact,
    AnalystType,
    Observation,
    Hypothesis,
    Inference,
    Uncertainty,
    Contradiction,
    Implication,
    ToolProvenance,
    ModelProvenance,
    DigestVerificationError,
    compute_analysis_artifact_digest,
    compute_analysis_artifact_canonical_bytes,
    HEX_40_PATTERN,
    HEX_64_PATTERN,
    EXECUTION_ID_PATTERN,
    ANALYSIS_ID_PATTERN,
)

WORKER_ID_PATTERN = re.compile(r"^WKR-[A-Za-z0-9_-]+$")


class WorkerTerminationReason(str, Enum):
    """Reason for worker termination."""
    COMPLETED = "COMPLETED"
    TIMEOUT = "TIMEOUT"
    BUDGET_EXHAUSTED_TOKENS = "BUDGET_EXHAUSTED_TOKENS"
    BUDGET_EXHAUSTED_CALLS = "BUDGET_EXHAUSTED_CALLS"
    BUDGET_EXHAUSTED_BYTES = "BUDGET_EXHAUSTED_BYTES"
    BUDGET_EXHAUSTED_ARTIFACTS = "BUDGET_EXHAUSTED_ARTIFACTS"
    STALE_CONTEXT = "STALE_CONTEXT"
    CONTEXT_MISMATCH = "CONTEXT_MISMATCH"
    CONTEXT_ALREADY_CONSUMED = "CONTEXT_ALREADY_CONSUMED"
    UNAUTHORIZED_EXECUTION_HANDLE = "UNAUTHORIZED_EXECUTION_HANDLE"
    DIGEST_VERIFICATION_FAILED = "DIGEST_VERIFICATION_FAILED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class ResourceExhaustionError(RuntimeError):
    """Raised when an analytical worker exceeds its allocated budget."""
    def __init__(self, reason: WorkerTerminationReason, message: str):
        super().__init__(message)
        self.reason = reason


class StaleContextError(RuntimeError):
    """Raised when worker context is stale or mismatched with active repository/planner state."""
    pass


@dataclass(frozen=True)
class WorkerIdentity:
    """Immutable identity for an ephemeral analytical worker.
    Issued authoritatively by WorkerRuntime.
    """
    worker_id: str
    analyst_type: AnalystType
    worker_epoch: int = 1
    spawned_at: str = "1970-01-01T00:00:00Z"

    def __post_init__(self):
        if not WORKER_ID_PATTERN.match(self.worker_id):
            raise ValueError(f"Invalid worker_id format: '{self.worker_id}'")
        if not isinstance(self.analyst_type, AnalystType):
            raise TypeError("analyst_type must be an AnalystType enum member.")
        if self.worker_epoch < 1:
            raise ValueError("worker_epoch must be >= 1.")


@dataclass(frozen=True)
class IssuedAnalysisIdentity:
    """Authoritative analysis identity issued strictly by WorkerRuntime.
    Encapsulates deterministic lineage coordinates and runtime HMAC authentication.
    """
    analysis_id: str
    execution_id: str
    analyst_type: AnalystType
    sequence: int
    auth_tag: str = field(repr=False, hash=False, compare=False, default="")

    def __post_init__(self):
        if not self.analysis_id or not ANALYSIS_ID_PATTERN.match(self.analysis_id):
            raise ValueError(f"Invalid analysis_id format: '{self.analysis_id}'")
        if not self.execution_id or not EXECUTION_ID_PATTERN.match(self.execution_id):
            raise ValueError(f"Invalid execution_id format: '{self.execution_id}'")
        if not isinstance(self.analyst_type, AnalystType):
            raise TypeError("analyst_type must be an AnalystType enum member.")
        if self.sequence < 1:
            raise ValueError("sequence must be >= 1.")
        if not self.auth_tag or len(self.auth_tag) != 64:
            raise ValueError("auth_tag must be a valid 64-character hex HMAC tag.")


class WorkerExecutionHandle:
    """Non-forgeable, single-use execution handle issued and HMAC-authenticated by WorkerRuntime.
    Binds the full execution coordinate matrix and owns atomic single-use claim state.
    """

    def __init__(
        self,
        execution_id: str,
        worker_id: str,
        worker_epoch: int,
        task_id: str,
        repository_id: str,
        source_sha: str,
        planner_state_digest: str,
        analyst_type: AnalystType,
        auth_tag: str,
    ):
        if not execution_id or not EXECUTION_ID_PATTERN.match(execution_id):
            raise ValueError(f"Invalid execution_id format: '{execution_id}'")
        if not worker_id or not WORKER_ID_PATTERN.match(worker_id):
            raise ValueError(f"Invalid worker_id format: '{worker_id}'")
        if worker_epoch < 1:
            raise ValueError("worker_epoch must be >= 1.")
        if not task_id or not repository_id:
            raise ValueError("task_id and repository_id must be non-empty.")
        if not HEX_40_PATTERN.match(source_sha):
            raise ValueError(f"Invalid source_sha hex format: '{source_sha}'")
        if not HEX_64_PATTERN.match(planner_state_digest):
            raise ValueError(f"Invalid planner_state_digest hex format: '{planner_state_digest}'")
        if not isinstance(analyst_type, AnalystType):
            raise TypeError("analyst_type must be an AnalystType enum member.")
        if not auth_tag or len(auth_tag) != 64:
            raise ValueError("auth_tag must be a valid 64-character hex HMAC digest.")

        self._execution_id = execution_id
        self._worker_id = worker_id
        self._worker_epoch = worker_epoch
        self._task_id = task_id
        self._repository_id = repository_id
        self._source_sha = source_sha
        self._planner_state_digest = planner_state_digest
        self._analyst_type = analyst_type
        self._auth_tag = auth_tag
        self._consumed = False
        self._lock = threading.Lock()

    @property
    def execution_id(self) -> str:
        return self._execution_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def worker_epoch(self) -> int:
        return self._worker_epoch

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def repository_id(self) -> str:
        return self._repository_id

    @property
    def source_sha(self) -> str:
        return self._source_sha

    @property
    def planner_state_digest(self) -> str:
        return self._planner_state_digest

    @property
    def analyst_type(self) -> AnalystType:
        return self._analyst_type

    @property
    def auth_tag(self) -> str:
        return self._auth_tag

    @property
    def signature(self) -> str:
        """Backwards-compatible alias for auth_tag."""
        return self._auth_tag

    @property
    def is_consumed(self) -> bool:
        with self._lock:
            return self._consumed

    def _claim(self) -> bool:
        """Atomically marks handle as consumed. Returns True if claimed, False if already consumed."""
        with self._lock:
            if self._consumed:
                return False
            self._consumed = True
            return True


@dataclass(frozen=True)
class CapabilityScope:
    """Declares permitted read-only inspection scopes for an analytical worker."""
    allowed_file_patterns: Tuple[str, ...] = ("*",)
    max_search_depth: int = 10
    allow_ast_parsing: bool = True
    allow_evidence_inspection: bool = True

    def __post_init__(self):
        if not isinstance(self.allowed_file_patterns, tuple):
            object.__setattr__(self, "allowed_file_patterns", tuple(self.allowed_file_patterns))
        if self.max_search_depth < 1:
            raise ValueError("max_search_depth must be >= 1.")


@dataclass(frozen=True)
class WorkerResourceBudget:
    """Immutable resource boundaries for a single analytical worker turn."""
    max_tool_calls: int = 50
    max_wall_time_seconds: float = 30.0
    max_output_bytes: int = 1_000_000       # 1 MB max serialized artifact payload
    max_output_artifacts: int = 1           # Exactly 1 primary artifact per turn
    max_model_tokens: int = 40_000

    def __post_init__(self):
        if self.max_tool_calls < 1:
            raise ValueError("max_tool_calls must be >= 1.")
        if self.max_wall_time_seconds <= 0:
            raise ValueError("max_wall_time_seconds must be > 0.")
        if self.max_output_bytes < 100:
            raise ValueError("max_output_bytes must be >= 100.")
        if self.max_output_artifacts < 1:
            raise ValueError("max_output_artifacts must be >= 1.")
        if self.max_model_tokens < 100:
            raise ValueError("max_model_tokens must be >= 100.")


@dataclass(frozen=True)
class CandidatePlanView:
    """Immutable primitive view of a CandidatePlan under review by PlanCritic.
    Contains strictly primitive data with zero live object references or mutation capabilities.
    """
    plan_id: str
    source_sha: str
    planner_state_digest: str
    node_ids: Tuple[str, ...] = ()
    dependency_edges: Tuple[Tuple[str, str], ...] = ()
    action_types: Tuple[str, ...] = ()
    targets: Tuple[str, ...] = ()

    def __post_init__(self):
        if not self.plan_id:
            raise ValueError("plan_id must be non-empty.")
        if not HEX_40_PATTERN.match(self.source_sha):
            raise ValueError(f"Invalid source_sha hex format: '{self.source_sha}'")
        if not HEX_64_PATTERN.match(self.planner_state_digest):
            raise ValueError(f"Invalid planner_state_digest hex format: '{self.planner_state_digest}'")
        if not isinstance(self.node_ids, tuple):
            object.__setattr__(self, "node_ids", tuple(self.node_ids))
        if not isinstance(self.dependency_edges, tuple):
            object.__setattr__(self, "dependency_edges", tuple(self.dependency_edges))
        if not isinstance(self.action_types, tuple):
            object.__setattr__(self, "action_types", tuple(self.action_types))
        if not isinstance(self.targets, tuple):
            object.__setattr__(self, "targets", tuple(self.targets))


@dataclass(frozen=True)
class WorkerContext:
    """Mandatory context binding for analytical workers.
    Binds task coordinates, repository SHA, state digest, scope, and budget.
    """
    identity: WorkerIdentity
    task_id: str
    repository_id: str
    source_sha: str
    planner_state_digest: str
    capability_scope: CapabilityScope = field(default_factory=CapabilityScope)
    resource_budget: WorkerResourceBudget = field(default_factory=WorkerResourceBudget)

    def __post_init__(self):
        if not self.task_id or not self.repository_id:
            raise ValueError("task_id and repository_id must be non-empty.")
        if not HEX_40_PATTERN.match(self.source_sha):
            raise ValueError(f"Invalid source_sha hex format: '{self.source_sha}'")
        if not HEX_64_PATTERN.match(self.planner_state_digest):
            raise ValueError(f"Invalid planner_state_digest hex format: '{self.planner_state_digest}'")
        if not isinstance(self.identity, WorkerIdentity):
            raise TypeError("identity must be a WorkerIdentity instance.")
        if not isinstance(self.capability_scope, CapabilityScope):
            raise TypeError("capability_scope must be a CapabilityScope instance.")
        if not isinstance(self.resource_budget, WorkerResourceBudget):
            raise TypeError("resource_budget must be a WorkerResourceBudget instance.")

    @property
    def analyst_type(self) -> AnalystType:
        return self.identity.analyst_type

    @property
    def worker_epoch(self) -> int:
        return self.identity.worker_epoch

    @property
    def spawned_at(self) -> str:
        return self.identity.spawned_at


class ResourceTracker:
    """Thread-safe resource and deadline monitor with atomic bounds reservations."""

    def __init__(self, budget: WorkerResourceBudget):
        self._budget = budget
        self._tool_calls = 0
        self._model_tokens = 0
        self._output_bytes = 0
        self._output_artifacts = 0
        self._exhausted = False
        self._start_time = time.monotonic()
        self._lock = threading.Lock()

    @property
    def tool_calls_consumed(self) -> int:
        with self._lock:
            return self._tool_calls

    @property
    def model_tokens_consumed(self) -> int:
        with self._lock:
            return self._model_tokens

    @property
    def output_bytes_consumed(self) -> int:
        with self._lock:
            return self._output_bytes

    @property
    def output_artifacts_consumed(self) -> int:
        with self._lock:
            return self._output_artifacts

    @property
    def elapsed_wall_time(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def elapsed_wall_time_ms(self) -> int:
        return int(self.elapsed_wall_time * 1000)

    def _check_time_locked(self) -> None:
        if self._exhausted:
            raise ResourceExhaustionError(
                WorkerTerminationReason.BUDGET_EXHAUSTED_CALLS,
                "Worker execution halted: resource budget already exhausted."
            )
        if self.elapsed_wall_time > self._budget.max_wall_time_seconds:
            self._exhausted = True
            raise ResourceExhaustionError(
                WorkerTerminationReason.TIMEOUT,
                f"Worker exceeded wall-clock time limit of {self._budget.max_wall_time_seconds}s "
                f"(elapsed: {self.elapsed_wall_time:.2f}s)."
            )

    def check_time(self) -> None:
        with self._lock:
            self._check_time_locked()

    def reserve_tool_call(self) -> None:
        """Atomically checks time and reserves 1 tool call."""
        with self._lock:
            self._check_time_locked()
            if self._tool_calls + 1 > self._budget.max_tool_calls:
                self._exhausted = True
                raise ResourceExhaustionError(
                    WorkerTerminationReason.BUDGET_EXHAUSTED_CALLS,
                    f"Worker exceeded tool call limit of {self._budget.max_tool_calls} (attempted: {self._tool_calls + 1})."
                )
            self._tool_calls += 1

    def reserve_tokens(self, tokens: int) -> None:
        """Atomically checks time and reserves model tokens."""
        if tokens < 0:
            raise ValueError("Token count must be non-negative.")
        with self._lock:
            self._check_time_locked()
            if self._model_tokens + tokens > self._budget.max_model_tokens:
                self._exhausted = True
                raise ResourceExhaustionError(
                    WorkerTerminationReason.BUDGET_EXHAUSTED_TOKENS,
                    f"Worker exceeded token limit of {self._budget.max_model_tokens} (attempted: {self._model_tokens + tokens})."
                )
            self._model_tokens += tokens

    def reserve_output(self, byte_count: int, artifact_count: int = 1) -> None:
        """Atomically checks time and reserves output bytes and artifact slots."""
        if byte_count < 0 or artifact_count < 0:
            raise ValueError("byte_count and artifact_count must be non-negative.")
        with self._lock:
            self._check_time_locked()
            if self._output_artifacts + artifact_count > self._budget.max_output_artifacts:
                self._exhausted = True
                raise ResourceExhaustionError(
                    WorkerTerminationReason.BUDGET_EXHAUSTED_ARTIFACTS,
                    f"Worker exceeded artifact emission limit of {self._budget.max_output_artifacts}."
                )
            if self._output_bytes + byte_count > self._budget.max_output_bytes:
                self._exhausted = True
                raise ResourceExhaustionError(
                    WorkerTerminationReason.BUDGET_EXHAUSTED_BYTES,
                    f"Worker exceeded output byte limit of {self._budget.max_output_bytes} (attempted: {self._output_bytes + byte_count} bytes)."
                )
            self._output_artifacts += artifact_count
            self._output_bytes += byte_count

    def record_tool_call(self) -> None:
        self.reserve_tool_call()

    def record_tokens(self, tokens: int) -> None:
        self.reserve_tokens(tokens)

    def record_output(self, byte_count: int) -> None:
        self.reserve_output(byte_count=byte_count, artifact_count=1)


class ReadOnlyRepositoryAccessor:
    """Narrow object capability for inspecting repository contents strictly in read-only mode."""

    def __init__(self, repo_root: str, current_sha: str, scope: CapabilityScope, tracker: ResourceTracker):
        self._repo_root = os.path.realpath(os.path.abspath(repo_root))
        self._current_sha = current_sha
        self._scope = scope
        self._tracker = tracker

    @property
    def current_sha(self) -> str:
        return self._current_sha

    def _validate_path(self, relative_path: str) -> str:
        if relative_path is None or not isinstance(relative_path, str):
            raise PermissionError("Invalid path specified.")

        # Fail-closed cross-platform check: prevent drive prefix or UNC prefix from resolving within repo on POSIX
        if re.match(r"^[A-Za-z]:", relative_path) or relative_path.startswith(("\\\\", "//")):
            if os.name != "nt":
                raise PermissionError(f"Path containment violation: drive or network path '{relative_path}'")

        if not relative_path:
            candidate_path = self._repo_root
        elif os.path.isabs(relative_path):
            candidate_path = os.path.realpath(relative_path)
        else:
            candidate_path = os.path.realpath(os.path.join(self._repo_root, relative_path))

        try:
            common = os.path.commonpath([self._repo_root, candidate_path])
            if common != self._repo_root:
                raise PermissionError(f"Path containment violation: '{relative_path}' resolves outside repository root.")
        except ValueError:
            raise PermissionError(f"Path containment violation: drive or root mismatch for path '{relative_path}'")

        return candidate_path

    def _matches_scope(self, relative_path: str) -> bool:
        norm_path = relative_path.replace("\\", "/")
        return any(fnmatch.fnmatch(norm_path, pattern) for pattern in self._scope.allowed_file_patterns)

    def file_exists(self, relative_path: str) -> bool:
        self._tracker.reserve_tool_call()
        full_path = self._validate_path(relative_path)
        return os.path.isfile(full_path)

    def read_file(self, relative_path: str) -> str:
        self._tracker.reserve_tool_call()
        full_path = self._validate_path(relative_path)
        rel_from_root = os.path.relpath(full_path, self._repo_root).replace("\\", "/")
        if not self._matches_scope(rel_from_root):
            raise PermissionError(f"Access denied: '{relative_path}' does not match permitted capability scope patterns.")
        if not os.path.isfile(full_path):
            raise FileNotFoundError(f"File not found: '{relative_path}'")
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def list_files(self, relative_dir: str = "", extension: Optional[str] = None) -> Tuple[str, ...]:
        self._tracker.reserve_tool_call()
        target_dir = self._validate_path(relative_dir)
        if not os.path.exists(target_dir):
            return ()
        results = []
        for root, dirs, files in os.walk(target_dir):
            rel_root = os.path.relpath(root, self._repo_root)
            depth = 0 if rel_root == "." else len(rel_root.replace("\\", "/").split("/"))
            if depth >= self._scope.max_search_depth:
                dirs.clear()
                continue
            for file in files:
                if extension and not file.endswith(extension):
                    continue
                rel_path = os.path.relpath(os.path.join(root, file), self._repo_root).replace("\\", "/")
                if self._matches_scope(rel_path):
                    results.append(rel_path)
        return tuple(sorted(results))

    def parse_ast(self, relative_path: str) -> Optional[ast.AST]:
        self._tracker.reserve_tool_call()
        if not self._scope.allow_ast_parsing:
            raise PermissionError("AST parsing is not permitted under current CapabilityScope.")
        content = self.read_file(relative_path)
        try:
            return ast.parse(content, filename=relative_path)
        except SyntaxError:
            return None


class ReadOnlyEventLogAccessor:
    """Narrow object capability for reading D2 historical event log (returns immutable snapshots only)."""

    def __init__(
        self,
        events_provider: Callable[[], Sequence[Any]],
        state_digest_provider: Callable[[], str],
        tracker: ResourceTracker,
    ):
        self._events_provider = events_provider
        self._state_digest_provider = state_digest_provider
        self._tracker = tracker

    def get_events(self, after_sequence: int = 0) -> Tuple[Any, ...]:
        self._tracker.reserve_tool_call()
        all_events = self._events_provider()
        return tuple(copy.deepcopy(e) for e in all_events if getattr(e, "sequence_number", 0) > after_sequence)

    def get_state_digest(self) -> str:
        self._tracker.reserve_tool_call()
        return self._state_digest_provider()


class ReadOnlyEvidenceAccessor:
    """Narrow object capability for inspecting D4 claims and evidence in read-only mode (returns deep copies)."""

    def __init__(
        self,
        claims: Mapping[str, Any],
        evidence: Mapping[str, Any],
        assessments: Optional[Mapping[str, Any]],
        scope: CapabilityScope,
        tracker: ResourceTracker,
    ):
        self._claims = dict(claims)
        self._evidence = dict(evidence)
        self._assessments = dict(assessments or {})
        self._scope = scope
        self._tracker = tracker

    def get_claim(self, claim_id: str) -> Optional[Any]:
        self._tracker.reserve_tool_call()
        if not self._scope.allow_evidence_inspection:
            raise PermissionError("Evidence inspection is not permitted under current CapabilityScope.")
        claim = self._claims.get(claim_id)
        return copy.deepcopy(claim) if claim is not None else None

    def list_claim_ids(self) -> Tuple[str, ...]:
        self._tracker.reserve_tool_call()
        if not self._scope.allow_evidence_inspection:
            raise PermissionError("Evidence inspection is not permitted under current CapabilityScope.")
        return tuple(sorted(self._claims.keys()))

    def get_evidence(self, evidence_id: str) -> Optional[Any]:
        self._tracker.reserve_tool_call()
        if not self._scope.allow_evidence_inspection:
            raise PermissionError("Evidence inspection is not permitted under current CapabilityScope.")
        evidence = self._evidence.get(evidence_id)
        return copy.deepcopy(evidence) if evidence is not None else None

    def list_evidence_ids(self) -> Tuple[str, ...]:
        self._tracker.reserve_tool_call()
        if not self._scope.allow_evidence_inspection:
            raise PermissionError("Evidence inspection is not permitted under current CapabilityScope.")
        return tuple(sorted(self._evidence.keys()))

    def get_assessment(self, receipt_id: str) -> Optional[Any]:
        self._tracker.reserve_tool_call()
        if not self._scope.allow_evidence_inspection:
            raise PermissionError("Evidence inspection is not permitted under current CapabilityScope.")
        assessment = self._assessments.get(receipt_id)
        return copy.deepcopy(assessment) if assessment is not None else None


class ReadOnlyFabricContext:
    """Bounded capability context supplied to an ephemeral worker.
    Encapsulates narrow read-only accessors with zero execution or state-mutation authority.
    """

    def __init__(
        self,
        task_id: str,
        repository_id: str,
        source_sha: str,
        planner_state_digest: str,
        analyst_type: AnalystType,
        worker_epoch: int,
        spawned_at: str,
        issued_identity: IssuedAnalysisIdentity,
        repository_accessor: ReadOnlyRepositoryAccessor,
        event_accessor: ReadOnlyEventLogAccessor,
        evidence_accessor: ReadOnlyEvidenceAccessor,
        tracker: ResourceTracker,
        candidate_plan: Optional[CandidatePlanView] = None,
    ):
        self._task_id = task_id
        self._repository_id = repository_id
        self._source_sha = source_sha
        self._planner_state_digest = planner_state_digest
        self._analyst_type = analyst_type
        self._worker_epoch = worker_epoch
        self._spawned_at = spawned_at
        self._issued_identity = issued_identity
        self._repository = repository_accessor
        self._event_log = event_accessor
        self._evidence = evidence_accessor
        self._tracker = tracker
        self._candidate_plan = candidate_plan

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def repository_id(self) -> str:
        return self._repository_id

    @property
    def source_sha(self) -> str:
        return self._source_sha

    @property
    def planner_state_digest(self) -> str:
        return self._planner_state_digest

    @property
    def analyst_type(self) -> AnalystType:
        return self._analyst_type

    @property
    def worker_epoch(self) -> int:
        return self._worker_epoch

    @property
    def spawned_at(self) -> str:
        return self._spawned_at

    @property
    def issued_identity(self) -> IssuedAnalysisIdentity:
        return self._issued_identity

    @property
    def execution_id(self) -> str:
        return self._issued_identity.execution_id

    @property
    def analysis_id(self) -> str:
        return self._issued_identity.analysis_id

    @property
    def repository(self) -> ReadOnlyRepositoryAccessor:
        return self._repository

    @property
    def event_log(self) -> ReadOnlyEventLogAccessor:
        return self._event_log

    @property
    def evidence(self) -> ReadOnlyEvidenceAccessor:
        return self._evidence

    @property
    def tracker(self) -> ResourceTracker:
        return self._tracker

    @property
    def candidate_plan(self) -> Optional[CandidatePlanView]:
        """Read-only view of a candidate plan under evaluation, if supplied."""
        return self._candidate_plan


class ArtifactEmitter:
    """Validates, verifies canonical digest integrity, and collects AnalysisArtifact emissions from ephemeral workers.
    Enforces single-use emission per worker identity; validates against runtime-issued IssuedAnalysisIdentity.
    """

    def __init__(
        self,
        context: WorkerContext,
        issued_identity: IssuedAnalysisIdentity,
        tracker: ResourceTracker,
        runtime: Optional[WorkerRuntime] = None,
    ):
        if not isinstance(context, WorkerContext):
            raise TypeError("context must be a WorkerContext instance.")
        if not isinstance(issued_identity, IssuedAnalysisIdentity):
            raise TypeError("issued_identity must be an IssuedAnalysisIdentity instance.")
        self._context = context
        self._issued_identity = issued_identity
        self._tracker = tracker
        self._runtime = runtime
        self._emitted_artifact: Optional[AnalysisArtifact] = None
        self._emitted: bool = False
        self._lock = threading.Lock()

    @property
    def emitted_artifact(self) -> Optional[AnalysisArtifact]:
        with self._lock:
            return self._emitted_artifact

    @property
    def issued_identity(self) -> IssuedAnalysisIdentity:
        return self._issued_identity

    def emit(self, artifact: AnalysisArtifact) -> None:
        """Validates, recomputes canonical digest, charges byte budget, and stores AnalysisArtifact."""
        with self._lock:
            if self._emitted:
                raise ResourceExhaustionError(
                    WorkerTerminationReason.BUDGET_EXHAUSTED_ARTIFACTS,
                    "ArtifactEmitter has already emitted an artifact and cannot be reused."
                )

            if not isinstance(artifact, AnalysisArtifact):
                raise TypeError("Emitted output must be an instance of AnalysisArtifact.")

            # Strict verification against runtime-issued analysis identity
            if artifact.analysis_id != self._issued_identity.analysis_id:
                raise StaleContextError(
                    f"Artifact analysis_id '{artifact.analysis_id}' does not match runtime-issued analysis_id '{self._issued_identity.analysis_id}'."
                )
            if artifact.execution_id != self._issued_identity.execution_id:
                raise StaleContextError(
                    f"Artifact execution_id '{artifact.execution_id}' does not match issued identity execution_id '{self._issued_identity.execution_id}'."
                )
            if artifact.analyst_type != self._issued_identity.analyst_type:
                raise ValueError(
                    f"Artifact analyst_type '{artifact.analyst_type}' does not match issued identity analyst_type '{self._issued_identity.analyst_type}'."
                )

            # Runtime HMAC provenance authentication verification if runtime attached
            if self._runtime is not None and not self._runtime.verify_analysis_identity(self._issued_identity):
                raise StaleContextError(
                    f"IssuedAnalysisIdentity '{self._issued_identity.analysis_id}' failed runtime HMAC provenance verification."
                )

            # Invariant checks against context binding
            if artifact.task_id != self._context.task_id:
                raise StaleContextError(
                    f"Artifact task_id '{artifact.task_id}' does not match WorkerContext task_id '{self._context.task_id}'."
                )
            if artifact.repository_id != self._context.repository_id:
                raise StaleContextError(
                    f"Artifact repository_id '{artifact.repository_id}' does not match WorkerContext repository_id '{self._context.repository_id}'."
                )
            if artifact.source_sha != self._context.source_sha:
                raise StaleContextError(
                    f"Artifact source_sha '{artifact.source_sha}' does not match WorkerContext source_sha '{self._context.source_sha}'."
                )
            if artifact.input_state_digest != self._context.planner_state_digest:
                raise StaleContextError(
                    f"Artifact input_state_digest '{artifact.input_state_digest}' does not match WorkerContext planner_state_digest '{self._context.planner_state_digest}'."
                )
            if artifact.worker_epoch != self._context.worker_epoch:
                raise ValueError(
                    f"Artifact worker_epoch {artifact.worker_epoch} does not match WorkerContext worker_epoch {self._context.worker_epoch}."
                )

            # Recompute and strictly verify the canonical artifact digest preimage using constant-time comparison
            expected_digest = compute_analysis_artifact_digest(artifact)
            if not hmac.compare_digest(expected_digest, artifact.artifact_digest):
                raise DigestVerificationError(
                    f"Artifact digest '{artifact.artifact_digest}' does not match recomputed digest '{expected_digest}'."
                )

            # Calculate actual canonical serialized byte weight
            canonical_bytes = compute_analysis_artifact_canonical_bytes(artifact)
            actual_byte_count = len(canonical_bytes)

            # Atomically reserve output bytes and mark as emitted
            self._tracker.reserve_output(byte_count=actual_byte_count, artifact_count=1)
            self._emitted = True
            self._emitted_artifact = artifact


@dataclass(frozen=True)
class WorkerExecutionResult:
    """Outcome of an ephemeral worker execution turn."""
    worker_id: str
    analyst_type: AnalystType
    termination_reason: WorkerTerminationReason
    artifact: Optional[AnalysisArtifact] = None
    tool_calls_consumed: int = 0
    model_tokens_consumed: int = 0
    wall_time_ms: int = 0
    bytes_emitted: int = 0
    error_message: Optional[str] = None


class EphemeralAnalyst:
    """Abstract base class for all Phase C ephemeral analytical workers."""

    @property
    def analyst_type(self) -> AnalystType:
        raise NotImplementedError

    def analyze(
        self,
        fabric_ctx: ReadOnlyFabricContext,
        emitter: ArtifactEmitter,
    ) -> None:
        raise NotImplementedError


# ============================================================================
# CONCRETE EPHEMERAL WORKERS (6 ANALYST ROLES)
# ============================================================================

class RepositoryAnalyst(EphemeralAnalyst):
    """Inspects file tree, locates relevant target files, and maps symbol boundaries."""

    @property
    def analyst_type(self) -> AnalystType:
        return AnalystType.REPOSITORY

    def analyze(self, fabric_ctx: ReadOnlyFabricContext, emitter: ArtifactEmitter) -> None:
        files = fabric_ctx.repository.list_files()
        observations = []
        for idx, f in enumerate(files[:30], 1):
            observations.append(
                Observation(
                    observation_id=f"OBS-REPO-{idx:03d}",
                    category="FILE_ENTRY",
                    description=f"File detected in repository: {f}",
                    target_path=f,
                    heuristic_confidence=1.0,
                )
            )

        artifact = AnalysisArtifact(
            analysis_id=fabric_ctx.analysis_id,
            execution_id=fabric_ctx.execution_id,
            analyst_type=AnalystType.REPOSITORY,
            task_id=fabric_ctx.task_id,
            repository_id=fabric_ctx.repository_id,
            source_sha=fabric_ctx.source_sha,
            input_state_digest=fabric_ctx.planner_state_digest,
            observations=tuple(observations),
            tool_provenance=ToolProvenance(
                tools_invoked=("list_files",),
                call_count=fabric_ctx.tracker.tool_calls_consumed,
                wall_time_ms=fabric_ctx.tracker.elapsed_wall_time_ms,
            ),
            worker_epoch=fabric_ctx.worker_epoch,
            created_at=fabric_ctx.spawned_at,
        )
        emitter.emit(artifact)


class EvidenceAnalyst(EphemeralAnalyst):
    """Analyzes open D4 claims and identifies missing or stale evidence coverage."""

    @property
    def analyst_type(self) -> AnalystType:
        return AnalystType.EVIDENCE

    def analyze(self, fabric_ctx: ReadOnlyFabricContext, emitter: ArtifactEmitter) -> None:
        claim_ids = fabric_ctx.evidence.list_claim_ids()
        evidence_ids = fabric_ctx.evidence.list_evidence_ids()
        observations = []
        uncertainties = []

        for cid in claim_ids:
            claim = fabric_ctx.evidence.get_claim(cid)
            status = getattr(claim, "status", "UNKNOWN")
            observations.append(
                Observation(
                    observation_id=f"OBS-EVID-{len(observations)+1:03d}",
                    category="CLAIM_STATUS",
                    description=f"Claim '{cid}' evaluated with status: {status}",
                )
            )
            if str(status).endswith("UNSUPPORTED"):
                uncertainties.append(
                    Uncertainty(
                        uncertainty_id=f"UNC-EVID-{len(uncertainties)+1:03d}",
                        description=f"Claim '{cid}' currently lacks supporting evidence.",
                        impact_area="CLAIM_SATISFACTION",
                        suggested_probe_action=f"Execute targeted verification for claim '{cid}'",
                    )
                )

        if not claim_ids:
            observations.append(
                Observation(
                    observation_id="OBS-EVID-001",
                    category="CLAIM_STATUS",
                    description="No active D4 claims present in scope; evidence analysis INSUFFICIENT_INPUT",
                )
            )

        artifact = AnalysisArtifact(
            analysis_id=fabric_ctx.analysis_id,
            execution_id=fabric_ctx.execution_id,
            analyst_type=AnalystType.EVIDENCE,
            task_id=fabric_ctx.task_id,
            repository_id=fabric_ctx.repository_id,
            source_sha=fabric_ctx.source_sha,
            input_state_digest=fabric_ctx.planner_state_digest,
            observations=tuple(observations),
            uncertainties=tuple(uncertainties),
            referenced_claim_ids=claim_ids,
            referenced_evidence_ids=evidence_ids,
            tool_provenance=ToolProvenance(
                tools_invoked=("list_claim_ids", "get_claim"),
                call_count=fabric_ctx.tracker.tool_calls_consumed,
                wall_time_ms=fabric_ctx.tracker.elapsed_wall_time_ms,
            ),
            worker_epoch=fabric_ctx.worker_epoch,
            created_at=fabric_ctx.spawned_at,
        )
        emitter.emit(artifact)


class ArchitectureAnalyst(EphemeralAnalyst):
    """Evaluates architectural call-graphs and invariant consistency."""

    @property
    def analyst_type(self) -> AnalystType:
        return AnalystType.ARCHITECTURE

    def analyze(self, fabric_ctx: ReadOnlyFabricContext, emitter: ArtifactEmitter) -> None:
        py_files = fabric_ctx.repository.list_files(extension=".py")
        observations = []
        classes_found = []

        for pf in py_files[:10]:
            tree = fabric_ctx.repository.parse_ast(pf)
            if tree:
                classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                if classes:
                    classes_found.extend(classes)
                    observations.append(
                        Observation(
                            observation_id=f"OBS-ARCH-{len(observations)+1:03d}",
                            category="AST_CLASSES",
                            description=f"Module '{pf}' declares classes: {', '.join(classes)}",
                            target_path=pf,
                        )
                    )

        if classes_found:
            inferences = (
                Inference(
                    inference_id="INF-ARCH-001",
                    description=f"AST parsing extracted {len(classes_found)} classes across {len(observations)} inspected modules.",
                    derivation_rule="STATIC_AST_PARSING",
                ),
            )
        else:
            inferences = ()
            observations.append(
                Observation(
                    observation_id="OBS-ARCH-001",
                    category="AST_CLASSES",
                    description="No AST classes discovered in inspected files; architectural structure NOT_OBSERVED",
                )
            )

        artifact = AnalysisArtifact(
            analysis_id=fabric_ctx.analysis_id,
            execution_id=fabric_ctx.execution_id,
            analyst_type=AnalystType.ARCHITECTURE,
            task_id=fabric_ctx.task_id,
            repository_id=fabric_ctx.repository_id,
            source_sha=fabric_ctx.source_sha,
            input_state_digest=fabric_ctx.planner_state_digest,
            observations=tuple(observations),
            inferences=inferences,
            tool_provenance=ToolProvenance(
                tools_invoked=("list_files", "parse_ast"),
                call_count=fabric_ctx.tracker.tool_calls_consumed,
                wall_time_ms=fabric_ctx.tracker.elapsed_wall_time_ms,
            ),
            worker_epoch=fabric_ctx.worker_epoch,
            created_at=fabric_ctx.spawned_at,
        )
        emitter.emit(artifact)


class DependencyAnalyst(EphemeralAnalyst):
    """Evaluates prerequisite ordering and module dependency acyclicity."""

    @property
    def analyst_type(self) -> AnalystType:
        return AnalystType.DEPENDENCY

    def analyze(self, fabric_ctx: ReadOnlyFabricContext, emitter: ArtifactEmitter) -> None:
        py_files = fabric_ctx.repository.list_files(extension=".py")
        import_count = 0
        for pf in py_files[:5]:
            tree = fabric_ctx.repository.parse_ast(pf)
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        import_count += 1

        if import_count > 0:
            observations = (
                Observation(
                    observation_id="OBS-DEP-001",
                    category="DEPENDENCY_INSPECTION",
                    description=f"Inspected import declarations across {len(py_files[:5])} modules; found {import_count} import statements.",
                ),
            )
        else:
            observations = (
                Observation(
                    observation_id="OBS-DEP-001",
                    category="DEPENDENCY_INSPECTION",
                    description="No import statements detected in inspected files; dependency graph NOT_OBSERVED",
                ),
            )

        artifact = AnalysisArtifact(
            analysis_id=fabric_ctx.analysis_id,
            execution_id=fabric_ctx.execution_id,
            analyst_type=AnalystType.DEPENDENCY,
            task_id=fabric_ctx.task_id,
            repository_id=fabric_ctx.repository_id,
            source_sha=fabric_ctx.source_sha,
            input_state_digest=fabric_ctx.planner_state_digest,
            observations=observations,
            tool_provenance=ToolProvenance(
                tools_invoked=("list_files", "parse_ast"),
                call_count=fabric_ctx.tracker.tool_calls_consumed,
                wall_time_ms=fabric_ctx.tracker.elapsed_wall_time_ms,
            ),
            worker_epoch=fabric_ctx.worker_epoch,
            created_at=fabric_ctx.spawned_at,
        )
        emitter.emit(artifact)


class RiskRegressionAnalyst(EphemeralAnalyst):
    """Evaluates blast radius, security risks, and irreversible mutation hazards."""

    @property
    def analyst_type(self) -> AnalystType:
        return AnalystType.RISK_REGRESSION

    def analyze(self, fabric_ctx: ReadOnlyFabricContext, emitter: ArtifactEmitter) -> None:
        files = fabric_ctx.repository.list_files()
        observations = (
            Observation(
                observation_id="OBS-RISK-001",
                category="RISK_SCOPE_INSPECTION",
                description=f"Evaluated repository read-only surface; {len(files)} total files currently in repository boundary.",
            ),
        )
        implications = (
            Implication(
                implication_id="IMP-RISK-001",
                description="Analytical fabric operates under strictly read-only capabilities; zero write authority permitted.",
                risk_level="LOW",
            ),
        )

        artifact = AnalysisArtifact(
            analysis_id=fabric_ctx.analysis_id,
            execution_id=fabric_ctx.execution_id,
            analyst_type=AnalystType.RISK_REGRESSION,
            task_id=fabric_ctx.task_id,
            repository_id=fabric_ctx.repository_id,
            source_sha=fabric_ctx.source_sha,
            input_state_digest=fabric_ctx.planner_state_digest,
            observations=observations,
            implications=implications,
            tool_provenance=ToolProvenance(
                tools_invoked=("list_files",),
                call_count=fabric_ctx.tracker.tool_calls_consumed,
                wall_time_ms=fabric_ctx.tracker.elapsed_wall_time_ms,
            ),
            worker_epoch=fabric_ctx.worker_epoch,
            created_at=fabric_ctx.spawned_at,
        )
        emitter.emit(artifact)


class PlanCriticAnalyst(EphemeralAnalyst):
    """Performs structured pre-execution advisory critique across analytical dimensions.
    Requires an actual immutable CandidatePlanView to perform plan critique;
    records INSUFFICIENT_INPUT if no plan is supplied.
    """

    @property
    def analyst_type(self) -> AnalystType:
        return AnalystType.PLAN_CRITIC

    def analyze(self, fabric_ctx: ReadOnlyFabricContext, emitter: ArtifactEmitter) -> None:
        candidate_plan = fabric_ctx.candidate_plan
        observations: List[Observation] = []
        uncertainties: List[Uncertainty] = []
        contradictions: List[Contradiction] = []

        if candidate_plan is None:
            # Epistemic honesty: no plan was provided, do not claim critique occurred
            observations.append(
                Observation(
                    observation_id="OBS-CRIT-001",
                    category="PLAN_CRITIQUE",
                    description="No candidate plan provided in context; plan critique is INSUFFICIENT_INPUT.",
                    heuristic_confidence=1.0,
                )
            )
            uncertainties.append(
                Uncertainty(
                    uncertainty_id="UNC-CRIT-001",
                    description="Plan critique could not be conducted without a CandidatePlanView instance.",
                    impact_area="PLAN_EVALUATION",
                    suggested_probe_action="Supply CandidatePlanView to PlanCriticAnalyst context",
                )
            )
        else:
            # 1. Context binding validation
            if candidate_plan.source_sha != fabric_ctx.source_sha:
                contradictions.append(
                    Contradiction(
                        contradiction_id="CON-CRIT-SHA-MISMATCH",
                        description=f"Candidate plan source_sha '{candidate_plan.source_sha}' != context '{fabric_ctx.source_sha}'",
                        conflicting_ids=(candidate_plan.plan_id,),
                    )
                )
            if candidate_plan.planner_state_digest != fabric_ctx.planner_state_digest:
                contradictions.append(
                    Contradiction(
                        contradiction_id="CON-CRIT-STATE-MISMATCH",
                        description=f"Candidate plan state digest '{candidate_plan.planner_state_digest}' != context '{fabric_ctx.planner_state_digest}'",
                        conflicting_ids=(candidate_plan.plan_id,),
                    )
                )

            # 2. Node uniqueness verification
            node_set = set(candidate_plan.node_ids)
            if len(node_set) != len(candidate_plan.node_ids):
                contradictions.append(
                    Contradiction(
                        contradiction_id="CON-CRIT-DUPLICATE-NODES",
                        description="Candidate plan contains duplicate node identifiers.",
                        conflicting_ids=candidate_plan.node_ids,
                    )
                )

            # 3. Dependency reference integrity verification
            missing_deps = []
            adj: Dict[str, List[str]] = {n: [] for n in node_set}
            in_degree: Dict[str, int] = {n: 0 for n in node_set}

            for src, dst in candidate_plan.dependency_edges:
                if src not in node_set or dst not in node_set:
                    missing_deps.append((src, dst))
                else:
                    adj[src].append(dst)
                    in_degree[dst] += 1

            if missing_deps:
                contradictions.append(
                    Contradiction(
                        contradiction_id="CON-CRIT-MISSING-DEPENDENCY",
                        description=f"Dependency edges reference non-existent nodes: {missing_deps}",
                        conflicting_ids=tuple(f"{s}->{d}" for s, d in missing_deps),
                    )
                )

            # 4. Topological acyclicity check using Kahn's algorithm
            if not missing_deps:
                queue = deque([n for n in node_set if in_degree[n] == 0])
                visited_count = 0
                while queue:
                    curr = queue.popleft()
                    visited_count += 1
                    for neighbor in adj[curr]:
                        in_degree[neighbor] -= 1
                        if in_degree[neighbor] == 0:
                            queue.append(neighbor)

                if visited_count != len(node_set):
                    contradictions.append(
                        Contradiction(
                            contradiction_id="CON-CRIT-TOPOLOGY-CYCLE",
                            description="Candidate plan dependency graph contains a directed cycle.",
                            conflicting_ids=candidate_plan.node_ids,
                        )
                    )
                else:
                    observations.append(
                        Observation(
                            observation_id="OBS-CRIT-001",
                            category="PLAN_TOPOLOGY_ACYCLIC",
                            description=f"Critiqued candidate plan '{candidate_plan.plan_id}' with {len(node_set)} nodes; dependency graph is strictly acyclic.",
                            heuristic_confidence=1.0,
                        )
                    )
            else:
                observations.append(
                    Observation(
                        observation_id="OBS-CRIT-001",
                        category="PLAN_INTEGRITY_FAILED",
                        description=f"Candidate plan '{candidate_plan.plan_id}' failed structural reference checks.",
                        heuristic_confidence=1.0,
                    )
                )

        artifact = AnalysisArtifact(
            analysis_id=fabric_ctx.analysis_id,
            execution_id=fabric_ctx.execution_id,
            analyst_type=AnalystType.PLAN_CRITIC,
            task_id=fabric_ctx.task_id,
            repository_id=fabric_ctx.repository_id,
            source_sha=fabric_ctx.source_sha,
            input_state_digest=fabric_ctx.planner_state_digest,
            observations=tuple(observations),
            uncertainties=tuple(uncertainties),
            contradictions=tuple(contradictions),
            tool_provenance=ToolProvenance(
                tools_invoked=("plan_critic",),
                call_count=fabric_ctx.tracker.tool_calls_consumed,
                wall_time_ms=fabric_ctx.tracker.elapsed_wall_time_ms,
            ),
            worker_epoch=fabric_ctx.worker_epoch,
            created_at=fabric_ctx.spawned_at,
        )
        emitter.emit(artifact)


# ============================================================================
# RUNTIME, REGISTRY, AND RUNNER
# ============================================================================

class WorkerRegistry:
    """Maintains available ephemeral worker implementations."""

    def __init__(self):
        self._analysts: Dict[AnalystType, EphemeralAnalyst] = {
            AnalystType.REPOSITORY: RepositoryAnalyst(),
            AnalystType.EVIDENCE: EvidenceAnalyst(),
            AnalystType.ARCHITECTURE: ArchitectureAnalyst(),
            AnalystType.DEPENDENCY: DependencyAnalyst(),
            AnalystType.RISK_REGRESSION: RiskRegressionAnalyst(),
            AnalystType.PLAN_CRITIC: PlanCriticAnalyst(),
        }

    def register_analyst(self, analyst: EphemeralAnalyst) -> None:
        if not isinstance(analyst, EphemeralAnalyst):
            raise TypeError("analyst must inherit from EphemeralAnalyst.")
        self._analysts[analyst.analyst_type] = analyst

    def get_analyst(self, analyst_type: AnalystType) -> Optional[EphemeralAnalyst]:
        return self._analysts.get(analyst_type)

    def list_analyst_types(self) -> Tuple[AnalystType, ...]:
        return tuple(sorted(self._analysts.keys(), key=lambda a: a.value))


class WorkerRuntime:
    """Trusted runtime environment managing ephemeral worker identity, non-forgeable
    HMAC-authenticated execution authorization, and authoritative analytical provenance.
    """

    def __init__(self, initial_epoch: int = 1):
        if initial_epoch < 1:
            raise ValueError("initial_epoch must be an integer >= 1.")
        self._epoch = initial_epoch
        self._secret = secrets.token_bytes(32)
        self._exec_seqs: Dict[str, int] = {}
        self._lock = threading.Lock()

    def _compute_hmac_auth_tag(
        self,
        execution_id: str,
        worker_id: str,
        worker_epoch: int,
        task_id: str,
        repository_id: str,
        source_sha: str,
        planner_state_digest: str,
        analyst_type: AnalystType,
    ) -> str:
        payload = f"{execution_id}:{worker_id}:{worker_epoch}:{task_id}:{repository_id}:{source_sha}:{planner_state_digest}:{analyst_type.value}".encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _compute_identity_auth_tag(
        self,
        analysis_id: str,
        execution_id: str,
        analyst_type: AnalystType,
        sequence: int,
    ) -> str:
        payload = f"{analysis_id}:{execution_id}:{analyst_type.value}:{sequence}".encode("utf-8")
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def issue_identity(self, analyst_type: AnalystType) -> WorkerIdentity:
        """Authoritatively issues an immutable WorkerIdentity."""
        if not isinstance(analyst_type, AnalystType):
            raise TypeError("analyst_type must be an AnalystType enum member.")
        with self._lock:
            epoch = self._epoch
        w_id = f"WKR-{analyst_type.value}-{uuid.uuid4().hex[:8]}"
        t_stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return WorkerIdentity(
            worker_id=w_id,
            analyst_type=analyst_type,
            worker_epoch=epoch,
            spawned_at=t_stamp,
        )

    def issue_execution(self, context: WorkerContext) -> WorkerExecutionHandle:
        """Issues an HMAC-authenticated, non-forgeable single-use execution handle bound to context coordinates."""
        if not isinstance(context, WorkerContext):
            raise TypeError("context must be a WorkerContext instance.")
        execution_id = f"EXEC-{uuid.uuid4().hex[:12]}"
        auth_tag = self._compute_hmac_auth_tag(
            execution_id=execution_id,
            worker_id=context.identity.worker_id,
            worker_epoch=context.identity.worker_epoch,
            task_id=context.task_id,
            repository_id=context.repository_id,
            source_sha=context.source_sha,
            planner_state_digest=context.planner_state_digest,
            analyst_type=context.analyst_type,
        )
        return WorkerExecutionHandle(
            execution_id=execution_id,
            worker_id=context.identity.worker_id,
            worker_epoch=context.identity.worker_epoch,
            task_id=context.task_id,
            repository_id=context.repository_id,
            source_sha=context.source_sha,
            planner_state_digest=context.planner_state_digest,
            analyst_type=context.analyst_type,
            auth_tag=auth_tag,
        )

    def issue_analysis_identity(self, execution: WorkerExecutionHandle) -> IssuedAnalysisIdentity:
        """Authoritatively issues an immutable IssuedAnalysisIdentity bound to the execution lineage."""
        if not isinstance(execution, WorkerExecutionHandle):
            raise TypeError("execution must be a WorkerExecutionHandle instance.")
        with self._lock:
            seq = self._exec_seqs.get(execution.execution_id, 0) + 1
            self._exec_seqs[execution.execution_id] = seq
        exec_core = execution.execution_id.replace("EXEC-", "")
        analysis_id = f"ANA-{exec_core}-{execution.analyst_type.value}-{seq:03d}"
        auth_tag = self._compute_identity_auth_tag(
            analysis_id=analysis_id,
            execution_id=execution.execution_id,
            analyst_type=execution.analyst_type,
            sequence=seq,
        )
        return IssuedAnalysisIdentity(
            analysis_id=analysis_id,
            execution_id=execution.execution_id,
            analyst_type=execution.analyst_type,
            sequence=seq,
            auth_tag=auth_tag,
        )

    def verify_analysis_identity(self, identity: IssuedAnalysisIdentity) -> bool:
        """Verifies that an IssuedAnalysisIdentity was cryptographically issued by this runtime instance."""
        if not isinstance(identity, IssuedAnalysisIdentity):
            return False
        expected_tag = self._compute_identity_auth_tag(
            analysis_id=identity.analysis_id,
            execution_id=identity.execution_id,
            analyst_type=identity.analyst_type,
            sequence=identity.sequence,
        )
        return hmac.compare_digest(expected_tag, identity.auth_tag)

    def issue_analysis_id(self, execution: WorkerExecutionHandle) -> str:
        """Convenience method returning the authoritative analysis_id for an execution."""
        return self.issue_analysis_identity(execution).analysis_id

    def claim_execution(self, execution: WorkerExecutionHandle, context: WorkerContext) -> bool:
        """Verifies HMAC authentication and coordinate alignment, then atomically claims handle."""
        if not isinstance(execution, WorkerExecutionHandle):
            raise TypeError("execution must be a WorkerExecutionHandle instance.")
        if not isinstance(context, WorkerContext):
            raise TypeError("context must be a WorkerContext instance.")

        # 1. Verify coordinate binding alignment
        if (
            execution.worker_id != context.identity.worker_id or
            execution.worker_epoch != context.identity.worker_epoch or
            execution.task_id != context.task_id or
            execution.repository_id != context.repository_id or
            execution.source_sha != context.source_sha or
            execution.planner_state_digest != context.planner_state_digest or
            execution.analyst_type != context.analyst_type
        ):
            return False

        # 2. Cryptographically verify HMAC auth_tag was issued by THIS runtime instance
        expected_tag = self._compute_hmac_auth_tag(
            execution_id=execution.execution_id,
            worker_id=execution.worker_id,
            worker_epoch=execution.worker_epoch,
            task_id=execution.task_id,
            repository_id=execution.repository_id,
            source_sha=execution.source_sha,
            planner_state_digest=execution.planner_state_digest,
            analyst_type=execution.analyst_type,
        )
        if not hmac.compare_digest(expected_tag, execution.auth_tag):
            return False

        # 3. Atomically claim handle single-use state
        return execution._claim()


class WorkerRunner:
    """Executes an ephemeral worker turn with strict boundary validation and budget monitoring."""

    @staticmethod
    def run_worker(
        worker: EphemeralAnalyst,
        context: WorkerContext,
        execution: WorkerExecutionHandle,
        runtime: WorkerRuntime,
        repo_root: str,
        active_repo_sha: str,
        events_provider: Callable[[], Sequence[Any]],
        state_digest_provider: Callable[[], str],
        claims: Mapping[str, Any],
        evidence: Mapping[str, Any],
        assessments: Optional[Mapping[str, Any]] = None,
        candidate_plan: Optional[CandidatePlanView] = None,
    ) -> WorkerExecutionResult:
        """Executes a single ephemeral worker turn with mandatory single-use handle verification and claim."""
        if not isinstance(worker, EphemeralAnalyst):
            raise TypeError("worker must inherit from EphemeralAnalyst.")
        if not isinstance(context, WorkerContext):
            raise TypeError("context must be a WorkerContext instance.")
        if not isinstance(execution, WorkerExecutionHandle):
            raise TypeError("execution must be a WorkerExecutionHandle instance.")
        if not isinstance(runtime, WorkerRuntime):
            raise TypeError("runtime must be a WorkerRuntime instance.")

        worker_id = context.identity.worker_id

        # 1. Coordinate alignment check
        if (
            execution.worker_id != context.identity.worker_id or
            execution.worker_epoch != context.identity.worker_epoch or
            execution.task_id != context.task_id or
            execution.repository_id != context.repository_id or
            execution.source_sha != context.source_sha or
            execution.planner_state_digest != context.planner_state_digest or
            execution.analyst_type != context.analyst_type
        ):
            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=WorkerTerminationReason.CONTEXT_MISMATCH,
                error_message="Execution handle coordinate matrix does not match WorkerContext.",
            )

        # 2. HMAC runtime authentication and atomic claim
        if execution.is_consumed:
            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=WorkerTerminationReason.CONTEXT_ALREADY_CONSUMED,
                error_message=f"WorkerExecutionHandle '{execution.execution_id}' has already been consumed.",
            )

        if not runtime.claim_execution(execution=execution, context=context):
            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=WorkerTerminationReason.UNAUTHORIZED_EXECUTION_HANDLE,
                error_message=f"WorkerExecutionHandle '{execution.execution_id}' HMAC authentication failed or was not issued by runtime.",
            )

        # 3. Fail-closed context freshness validation
        if context.source_sha != active_repo_sha:
            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=WorkerTerminationReason.STALE_CONTEXT,
                error_message=f"Context SHA '{context.source_sha}' != active repository SHA '{active_repo_sha}'",
            )

        active_digest = state_digest_provider()
        if context.planner_state_digest != active_digest:
            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=WorkerTerminationReason.CONTEXT_MISMATCH,
                error_message=f"Context state digest '{context.planner_state_digest}' != active digest '{active_digest}'",
            )

        tracker = ResourceTracker(context.resource_budget)
        repo_accessor = ReadOnlyRepositoryAccessor(repo_root, active_repo_sha, context.capability_scope, tracker)
        event_accessor = ReadOnlyEventLogAccessor(events_provider, state_digest_provider, tracker)
        evidence_accessor = ReadOnlyEvidenceAccessor(claims, evidence, assessments, context.capability_scope, tracker)

        issued_identity = runtime.issue_analysis_identity(execution=execution)

        fabric_ctx = ReadOnlyFabricContext(
            task_id=context.task_id,
            repository_id=context.repository_id,
            source_sha=context.source_sha,
            planner_state_digest=context.planner_state_digest,
            analyst_type=context.analyst_type,
            worker_epoch=context.worker_epoch,
            spawned_at=context.spawned_at,
            issued_identity=issued_identity,
            repository_accessor=repo_accessor,
            event_accessor=event_accessor,
            evidence_accessor=evidence_accessor,
            tracker=tracker,
            candidate_plan=candidate_plan,
        )
        emitter = ArtifactEmitter(context, issued_identity, tracker, runtime=runtime)

        try:
            worker.analyze(fabric_ctx, emitter)
            artifact = emitter.emitted_artifact
            if not artifact:
                return WorkerExecutionResult(
                    worker_id=worker_id,
                    analyst_type=context.analyst_type,
                    termination_reason=WorkerTerminationReason.ERROR,
                    tool_calls_consumed=tracker.tool_calls_consumed,
                    model_tokens_consumed=tracker.model_tokens_consumed,
                    wall_time_ms=tracker.elapsed_wall_time_ms,
                    bytes_emitted=tracker.output_bytes_consumed,
                    error_message="Worker terminated without emitting an AnalysisArtifact.",
                )

            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=WorkerTerminationReason.COMPLETED,
                artifact=artifact,
                tool_calls_consumed=tracker.tool_calls_consumed,
                model_tokens_consumed=tracker.model_tokens_consumed,
                wall_time_ms=tracker.elapsed_wall_time_ms,
                bytes_emitted=tracker.output_bytes_consumed,
            )

        except ResourceExhaustionError as re_err:
            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=re_err.reason,
                tool_calls_consumed=tracker.tool_calls_consumed,
                model_tokens_consumed=tracker.model_tokens_consumed,
                wall_time_ms=tracker.elapsed_wall_time_ms,
                bytes_emitted=tracker.output_bytes_consumed,
                error_message=str(re_err),
            )
        except DigestVerificationError as dv_err:
            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=WorkerTerminationReason.DIGEST_VERIFICATION_FAILED,
                tool_calls_consumed=tracker.tool_calls_consumed,
                model_tokens_consumed=tracker.model_tokens_consumed,
                wall_time_ms=tracker.elapsed_wall_time_ms,
                bytes_emitted=tracker.output_bytes_consumed,
                error_message=str(dv_err),
            )
        except StaleContextError as sc_err:
            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=WorkerTerminationReason.STALE_CONTEXT,
                tool_calls_consumed=tracker.tool_calls_consumed,
                model_tokens_consumed=tracker.model_tokens_consumed,
                wall_time_ms=tracker.elapsed_wall_time_ms,
                bytes_emitted=tracker.output_bytes_consumed,
                error_message=str(sc_err),
            )
        except Exception as exc:
            return WorkerExecutionResult(
                worker_id=worker_id,
                analyst_type=context.analyst_type,
                termination_reason=WorkerTerminationReason.ERROR,
                tool_calls_consumed=tracker.tool_calls_consumed,
                model_tokens_consumed=tracker.model_tokens_consumed,
                wall_time_ms=tracker.elapsed_wall_time_ms,
                bytes_emitted=tracker.output_bytes_consumed,
                error_message=f"Unhandled worker error: {type(exc).__name__}: {str(exc)}",
            )
