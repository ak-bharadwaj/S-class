"""
S-Class Domain: EvidenceReceipt and Evidence Variants.
Preserves cryptographic invariants and enforces post-issuance immutability for ObservedReceipt.
"""

from __future__ import annotations
import os
import json
import hashlib
import uuid
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Type

LIFECYCLE_PROPOSED = "proposed"
LIFECYCLE_CLAIMED = "claimed"
LIFECYCLE_OBSERVED = "observed"
LIFECYCLE_INTEGRITY_VERIFIED = "integrity_verified"
LIFECYCLE_CLAIM_VERIFIED = "claim_verified"

_OBSERVATION_TOKEN = object()


@dataclass(frozen=True)
class EvidenceDependencies:
    """
    Immutable evidence dependency graph specification.
    Captures exact preconditions required for this evidence to remain valid:
    - execution_identity
    - argv
    - workspace_fingerprint
    - relevant_files
    - environment_constraints
    - verifier
    - verifier_output
    """
    execution_identity: Optional[Dict[str, Any]] = None
    argv: tuple[str, ...] = field(default_factory=tuple)
    workspace_fingerprint: str = ""
    relevant_files: tuple[str, ...] = field(default_factory=tuple)
    environment_constraints: Dict[str, str] = field(default_factory=dict)
    verifier: str = ""
    verifier_output_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_identity": self.execution_identity,
            "argv": list(self.argv),
            "workspace_fingerprint": self.workspace_fingerprint,
            "relevant_files": list(self.relevant_files),
            "environment_constraints": dict(self.environment_constraints),
            "verifier": self.verifier,
            "verifier_output_hash": self.verifier_output_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceDependencies:
        return cls(
            execution_identity=data.get("execution_identity"),
            argv=tuple(data.get("argv", [])),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            relevant_files=tuple(data.get("relevant_files", [])),
            environment_constraints=dict(data.get("environment_constraints", {})),
            verifier=data.get("verifier", ""),
            verifier_output_hash=data.get("verifier_output_hash", ""),
        )


@dataclass
class EvidenceReceipt:
    """
    Canonical evidence receipt capturing independent observation facts.
    Agents are never authoritative for receipts.
    """
    receipt_id: str
    task_id: str
    claim_id: str
    agent: str
    action: str
    workspace: str
    base_commit: str = ""
    result_commit: str = ""
    command: str = ""
    exit_code: int = 0
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stdout_hash: str = ""
    stderr_hash: str = ""
    files_changed: List[str] = field(default_factory=list)
    file_hashes: Dict[str, str] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    receipt_hash: Optional[str] = None
    lifecycle_state: str = LIFECYCLE_OBSERVED
    verified: bool = False
    is_observed: bool = False
    execution_kind: str = "generic_command"
    verifier: str = ""
    workspace_fingerprint: str = ""
    dependencies: Optional[EvidenceDependencies] = None
    _observation_token: Optional[object] = field(default=None, repr=False, compare=False)

    def get_dependencies(self) -> EvidenceDependencies:
        """Returns authoritative EvidenceDependencies for this receipt."""
        if self.dependencies is not None:
            return self.dependencies
        meta = self.metadata if isinstance(self.metadata, dict) else {}
        exec_id = meta.get("execution_identity")
        act_argv = tuple(exec_id.get("actual_argv", [])) if (exec_id and isinstance(exec_id, dict)) else tuple(self.command.split())
        env_constraints = {}
        if exec_id and isinstance(exec_id, dict) and "environment_digest" in exec_id:
            env_constraints["environment_digest"] = exec_id["environment_digest"]
        out_hash = self.stdout_hash or self.stderr_hash
        return EvidenceDependencies(
            execution_identity=exec_id,
            argv=act_argv,
            workspace_fingerprint=self.workspace_fingerprint,
            relevant_files=tuple(sorted(list(self.files_changed))),
            environment_constraints=env_constraints,
            verifier=self.verifier,
            verifier_output_hash=out_hash,
        )

    def validate_dependencies(self, workspace_dir: str) -> Tuple[bool, Optional[str]]:
        """
        Evaluates immutable dependency graph against current workspace state.
        If workspace mutation is detected, dependent evidence is invalid.
        """
        from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
        ws = os.path.abspath(workspace_dir)
        deps = self.get_dependencies()
        if deps.workspace_fingerprint:
            curr_snap = compute_workspace_snapshot(ws)
            curr_fp = compute_workspace_fingerprint(curr_snap)
            if curr_fp != deps.workspace_fingerprint:
                return False, f"Workspace mutation detected: files or content modified after observation (fingerprint changed from {deps.workspace_fingerprint[:12]} to {curr_fp[:12]}). Dependent evidence invalidated."
        return True, None

    def compute_hash(self) -> str:
        """
        Computes canonical SHA-256 hash across security-relevant fields.
        """
        # If metadata has execution_identity and authoritative fields, bind them
        meta = self.metadata if isinstance(self.metadata, dict) else {}
        if "execution_identity" in meta and "actual_argv" in meta.get("execution_identity", {}):
            hash_payload = {
                "receipt_id": self.receipt_id,
                "task_id": self.task_id,
                "claim_id": self.claim_id,
                "agent": self.agent,
                "action": self.action,
                "workspace": self.workspace,
                "command": self.command,
                "requested_argv": meta.get("execution_identity", {}).get("requested_argv", []),
                "actual_argv": meta.get("execution_identity", {}).get("actual_argv", []),
                "executable_hash": meta.get("execution_identity", {}).get("executable_hash", ""),
                "execution_mode": meta.get("execution_identity", {}).get("execution_mode", ""),
                "process_start_time": meta.get("execution_identity", {}).get("process_start_time", ""),
                "exit_code": self.exit_code,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "stdout_hash": self.stdout_hash,
                "stderr_hash": self.stderr_hash,
                "files_changed": sorted(list(self.files_changed)),
                "execution_kind": self.execution_kind,
                "verifier": self.verifier,
                "workspace_fingerprint_before": meta.get("workspace_fingerprint_before", self.workspace_fingerprint),
                "workspace_fingerprint": self.workspace_fingerprint,
                "structured_result": meta.get("structured_result"),
            }
            canonical_json = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        # Standard legacy hash calculation
        payload = {
            "receipt_id": self.receipt_id,
            "task_id": self.task_id,
            "claim_id": self.claim_id,
            "agent": self.agent,
            "action": self.action,
            "workspace": self.workspace,
            "base_commit": self.base_commit,
            "result_commit": self.result_commit,
            "command": self.command,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stdout_hash": self.stdout_hash,
            "stderr_hash": self.stderr_hash,
            "files_changed": sorted(list(self.files_changed)),
            "file_hashes": dict(sorted(self.file_hashes.items())),
            "evidence": self.evidence,
            "metadata": self.metadata,
            "execution_kind": self.execution_kind,
            "verifier": self.verifier,
            "workspace_fingerprint": self.workspace_fingerprint,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "task_id": self.task_id,
            "claim_id": self.claim_id,
            "agent": self.agent,
            "action": self.action,
            "workspace": self.workspace,
            "base_commit": self.base_commit,
            "result_commit": self.result_commit,
            "command": self.command,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stdout_hash": self.stdout_hash,
            "stderr_hash": self.stderr_hash,
            "files_changed": list(self.files_changed),
            "file_hashes": dict(self.file_hashes),
            "evidence": self.evidence,
            "metadata": self.metadata,
            "receipt_hash": self.receipt_hash or self.compute_hash(),
            "lifecycle_state": self.lifecycle_state,
            "verified": self.verified,
            "is_observed": self.is_observed,
            "execution_kind": self.execution_kind,
            "verifier": self.verifier,
            "workspace_fingerprint": self.workspace_fingerprint,
            "dependencies": self.get_dependencies().to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceReceipt:
        deps_data = data.get("dependencies")
        deps = EvidenceDependencies.from_dict(deps_data) if (deps_data and isinstance(deps_data, dict)) else None
        receipt = cls(
            receipt_id=data["receipt_id"],
            task_id=data.get("task_id", "task_default"),
            claim_id=data.get("claim_id", "claim_default"),
            agent=data.get("agent", "unknown"),
            action=data.get("action", "unknown"),
            workspace=data.get("workspace", ""),
            base_commit=data.get("base_commit", ""),
            result_commit=data.get("result_commit", ""),
            command=data.get("command", ""),
            exit_code=data.get("exit_code", 1),
            started_at=data.get("started_at", datetime.now(timezone.utc).isoformat()),
            finished_at=data.get("finished_at", datetime.now(timezone.utc).isoformat()),
            stdout_hash=data.get("stdout_hash", ""),
            stderr_hash=data.get("stderr_hash", ""),
            files_changed=list(data.get("files_changed", [])),
            file_hashes=dict(data.get("file_hashes", {})),
            evidence=list(data.get("evidence", [])),
            metadata=dict(data.get("metadata", {})),
            receipt_hash=data.get("receipt_hash"),
            lifecycle_state=data.get("lifecycle_state", LIFECYCLE_OBSERVED),
            verified=data.get("verified", False),
            is_observed=False,  # Deserialized data is never automatically trusted as in-memory observed
            execution_kind=data.get("execution_kind", "generic_command"),
            verifier=data.get("verifier", ""),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            dependencies=deps,
            _observation_token=None,
        )
        return receipt


@dataclass
class ObservedReceipt(EvidenceReceipt):
    """
    An authentic receipt produced strictly by the internal observation engine.
    Once issued, it is strictly immutable. Any modification attempt raises AttributeError.
    """
    _sealed: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_observed", True)
        object.__setattr__(self, "_observation_token", _OBSERVATION_TOKEN)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError(
                f"ObservedReceipt is immutable after issuance. Cannot modify attribute '{name}'."
            )
        super().__setattr__(name, value)


@dataclass
class ProposedEvidence:
    """Evidence proposed by an agent, pending execution."""
    task_id: str
    action: str
    agent: str
    proposed_command: str
    lifecycle_state: str = LIFECYCLE_PROPOSED
    is_observed: bool = False
    _explicitly_unobserved: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "action": self.action,
            "agent": self.agent,
            "proposed_command": self.proposed_command,
            "lifecycle_state": self.lifecycle_state,
            "is_observed": False,
        }


@dataclass
class ClaimedEvidence:
    """Evidence asserted by an agent without independent observation."""
    task_id: str
    claim_id: str
    agent: str
    claimed_exit_code: int = 0
    claimed_files: List[str] = field(default_factory=list)
    lifecycle_state: str = LIFECYCLE_CLAIMED
    is_observed: bool = False
    _explicitly_unobserved: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "claim_id": self.claim_id,
            "agent": self.agent,
            "claimed_exit_code": self.claimed_exit_code,
            "claimed_files": list(self.claimed_files),
            "lifecycle_state": self.lifecycle_state,
            "is_observed": False,
        }


# --- Generic Evidence Architecture (Handoff B) ---


class EvidenceKind(str, Enum):
    """Canonical classification for all S-Class evidence variants."""
    TEST = "test"
    BUILD = "build"
    LINT = "lint"
    SECURITY = "security"
    SEMANTIC = "semantic"
    FILESYSTEM = "filesystem"
    PROCESS = "process"
    GENERIC = "generic"


@dataclass
class Evidence:
    """
    Generic base model for independent evidence produced across the S-Class control plane.
    Every evidence item has an authoritative provenance, timestamp, and optional link
    to an observed cryptographic receipt.
    """
    evidence_id: str = field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:12]}")
    evidence_kind: str = EvidenceKind.GENERIC.value
    source: str = "sclass"
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_observed: bool = False
    receipt_id: Optional[str] = None
    receipt_hash: Optional[str] = None
    workspace_fingerprint: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self, workspace_dir: Optional[str] = None) -> bool:
        """Evaluates whether this evidence remains valid against current workspace state."""
        if not self.workspace_fingerprint or not workspace_dir:
            return True
        from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
        curr_snap = compute_workspace_snapshot(os.path.abspath(workspace_dir))
        curr_fp = compute_workspace_fingerprint(curr_snap)
        return curr_fp == self.workspace_fingerprint

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_kind": self.evidence_kind,
            "source": self.source,
            "collected_at": self.collected_at,
            "is_observed": self.is_observed,
            "receipt_id": self.receipt_id,
            "receipt_hash": self.receipt_hash,
            "workspace_fingerprint": self.workspace_fingerprint,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Evidence:
        kind = data.get("evidence_kind", EvidenceKind.GENERIC.value)
        subclasses = {
            EvidenceKind.TEST.value: TestEvidence,
            EvidenceKind.BUILD.value: BuildEvidence,
            EvidenceKind.LINT.value: LintEvidence,
            EvidenceKind.SECURITY.value: SecurityEvidence,
            EvidenceKind.SEMANTIC.value: SemanticEvidence,
            EvidenceKind.FILESYSTEM.value: FilesystemEvidence,
            EvidenceKind.PROCESS.value: ProcessEvidence,
        }
        target_cls = subclasses.get(kind, cls)
        if target_cls is not cls and hasattr(target_cls, "_from_dict_fields"):
            return target_cls._from_dict_fields(data)

        return cls(
            evidence_id=data.get("evidence_id", f"ev_{uuid.uuid4().hex[:12]}"),
            evidence_kind=kind,
            source=data.get("source", "sclass"),
            collected_at=data.get("collected_at", datetime.now(timezone.utc).isoformat()),
            is_observed=data.get("is_observed", False),
            receipt_id=data.get("receipt_id"),
            receipt_hash=data.get("receipt_hash"),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class TestEvidence(Evidence):
    """Authoritative structured test results observed by test runner verifier."""
    __test__ = False
    evidence_kind: str = EvidenceKind.TEST.value
    test_framework: str = "pytest"
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    total_count: int = 0
    duration_ms: float = 0.0
    failures: List[Dict[str, Any]] = field(default_factory=list)
    coverage: Optional[float] = None

    @property
    def is_passing(self) -> bool:
        return self.failed_count == 0 and (self.passed_count > 0 or self.total_count == 0)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "test_framework": self.test_framework,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "total_count": self.total_count,
            "duration_ms": round(self.duration_ms, 2),
            "failures": list(self.failures),
            "coverage": self.coverage,
            "is_passing": self.is_passing,
        })
        return d

    @classmethod
    def _from_dict_fields(cls, data: Dict[str, Any]) -> TestEvidence:
        return cls(
            evidence_id=data.get("evidence_id", f"ev_{uuid.uuid4().hex[:12]}"),
            evidence_kind=EvidenceKind.TEST.value,
            source=data.get("source", "sclass"),
            collected_at=data.get("collected_at", datetime.now(timezone.utc).isoformat()),
            is_observed=data.get("is_observed", False),
            receipt_id=data.get("receipt_id"),
            receipt_hash=data.get("receipt_hash"),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            metadata=dict(data.get("metadata", {})),
            test_framework=data.get("test_framework", "pytest"),
            passed_count=data.get("passed_count", 0),
            failed_count=data.get("failed_count", 0),
            skipped_count=data.get("skipped_count", 0),
            total_count=data.get("total_count", 0),
            duration_ms=data.get("duration_ms", 0.0),
            failures=list(data.get("failures", [])),
            coverage=data.get("coverage"),
        )


@dataclass
class BuildEvidence(Evidence):
    """Authoritative build results observed by build tool verifier."""
    evidence_kind: str = EvidenceKind.BUILD.value
    build_tool: str = ""
    exit_code: int = 0
    target: str = ""
    artifacts: List[str] = field(default_factory=list)
    warnings_count: int = 0
    errors_count: int = 0

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and self.errors_count == 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "build_tool": self.build_tool,
            "exit_code": self.exit_code,
            "target": self.target,
            "artifacts": list(self.artifacts),
            "warnings_count": self.warnings_count,
            "errors_count": self.errors_count,
            "is_success": self.is_success,
        })
        return d

    @classmethod
    def _from_dict_fields(cls, data: Dict[str, Any]) -> BuildEvidence:
        return cls(
            evidence_id=data.get("evidence_id", f"ev_{uuid.uuid4().hex[:12]}"),
            evidence_kind=EvidenceKind.BUILD.value,
            source=data.get("source", "sclass"),
            collected_at=data.get("collected_at", datetime.now(timezone.utc).isoformat()),
            is_observed=data.get("is_observed", False),
            receipt_id=data.get("receipt_id"),
            receipt_hash=data.get("receipt_hash"),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            metadata=dict(data.get("metadata", {})),
            build_tool=data.get("build_tool", ""),
            exit_code=data.get("exit_code", 0),
            target=data.get("target", ""),
            artifacts=list(data.get("artifacts", [])),
            warnings_count=data.get("warnings_count", 0),
            errors_count=data.get("errors_count", 0),
        )


@dataclass
class LintEvidence(Evidence):
    """Authoritative static linting results observed by linter verifier."""
    evidence_kind: str = EvidenceKind.LINT.value
    linter: str = ""
    violation_count: int = 0
    violations: List[Dict[str, Any]] = field(default_factory=list)
    files_checked: int = 0

    @property
    def is_clean(self) -> bool:
        return self.violation_count == 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "linter": self.linter,
            "violation_count": self.violation_count,
            "violations": list(self.violations),
            "files_checked": self.files_checked,
            "is_clean": self.is_clean,
        })
        return d

    @classmethod
    def _from_dict_fields(cls, data: Dict[str, Any]) -> LintEvidence:
        return cls(
            evidence_id=data.get("evidence_id", f"ev_{uuid.uuid4().hex[:12]}"),
            evidence_kind=EvidenceKind.LINT.value,
            source=data.get("source", "sclass"),
            collected_at=data.get("collected_at", datetime.now(timezone.utc).isoformat()),
            is_observed=data.get("is_observed", False),
            receipt_id=data.get("receipt_id"),
            receipt_hash=data.get("receipt_hash"),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            metadata=dict(data.get("metadata", {})),
            linter=data.get("linter", ""),
            violation_count=data.get("violation_count", 0),
            violations=list(data.get("violations", [])),
            files_checked=data.get("files_checked", 0),
        )


@dataclass
class SecurityEvidence(Evidence):
    """Authoritative security scan results observed by security scanner verifier."""
    evidence_kind: str = EvidenceKind.SECURITY.value
    scanner: str = ""
    findings_count: int = 0
    findings: List[Dict[str, Any]] = field(default_factory=list)
    risk_level: str = "low"
    passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "scanner": self.scanner,
            "findings_count": self.findings_count,
            "findings": list(self.findings),
            "risk_level": self.risk_level,
            "passed": self.passed,
        })
        return d

    @classmethod
    def _from_dict_fields(cls, data: Dict[str, Any]) -> SecurityEvidence:
        return cls(
            evidence_id=data.get("evidence_id", f"ev_{uuid.uuid4().hex[:12]}"),
            evidence_kind=EvidenceKind.SECURITY.value,
            source=data.get("source", "sclass"),
            collected_at=data.get("collected_at", datetime.now(timezone.utc).isoformat()),
            is_observed=data.get("is_observed", False),
            receipt_id=data.get("receipt_id"),
            receipt_hash=data.get("receipt_hash"),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            metadata=dict(data.get("metadata", {})),
            scanner=data.get("scanner", ""),
            findings_count=data.get("findings_count", 0),
            findings=list(data.get("findings", [])),
            risk_level=data.get("risk_level", "low"),
            passed=data.get("passed", True),
        )


@dataclass
class SemanticEvidence(Evidence):
    """Semantic syntax/reference analysis evidence."""
    evidence_kind: str = EvidenceKind.SEMANTIC.value
    symbol: str = ""
    file_path: str = ""
    references_count: int = 0
    impacted_symbols: List[str] = field(default_factory=list)
    scip_document: Optional[str] = None
    ast_node_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "symbol": self.symbol,
            "file_path": self.file_path,
            "references_count": self.references_count,
            "impacted_symbols": list(self.impacted_symbols),
            "scip_document": self.scip_document,
            "ast_node_type": self.ast_node_type,
        })
        return d

    @classmethod
    def _from_dict_fields(cls, data: Dict[str, Any]) -> SemanticEvidence:
        return cls(
            evidence_id=data.get("evidence_id", f"ev_{uuid.uuid4().hex[:12]}"),
            evidence_kind=EvidenceKind.SEMANTIC.value,
            source=data.get("source", "sclass"),
            collected_at=data.get("collected_at", datetime.now(timezone.utc).isoformat()),
            is_observed=data.get("is_observed", False),
            receipt_id=data.get("receipt_id"),
            receipt_hash=data.get("receipt_hash"),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            metadata=dict(data.get("metadata", {})),
            symbol=data.get("symbol", ""),
            file_path=data.get("file_path", ""),
            references_count=data.get("references_count", 0),
            impacted_symbols=list(data.get("impacted_symbols", [])),
            scip_document=data.get("scip_document"),
            ast_node_type=data.get("ast_node_type"),
        )


@dataclass
class FilesystemEvidence(Evidence):
    """Authoritative filesystem mutation evidence observed during execution."""
    evidence_kind: str = EvidenceKind.FILESYSTEM.value
    path: str = ""
    operation: str = "read"  # read, write, create, delete
    file_hash_before: Optional[str] = None
    file_hash_after: Optional[str] = None
    bytes_changed: int = 0
    exists: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "path": self.path,
            "operation": self.operation,
            "file_hash_before": self.file_hash_before,
            "file_hash_after": self.file_hash_after,
            "bytes_changed": self.bytes_changed,
            "exists": self.exists,
        })
        return d

    @classmethod
    def _from_dict_fields(cls, data: Dict[str, Any]) -> FilesystemEvidence:
        return cls(
            evidence_id=data.get("evidence_id", f"ev_{uuid.uuid4().hex[:12]}"),
            evidence_kind=EvidenceKind.FILESYSTEM.value,
            source=data.get("source", "sclass"),
            collected_at=data.get("collected_at", datetime.now(timezone.utc).isoformat()),
            is_observed=data.get("is_observed", False),
            receipt_id=data.get("receipt_id"),
            receipt_hash=data.get("receipt_hash"),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            metadata=dict(data.get("metadata", {})),
            path=data.get("path", ""),
            operation=data.get("operation", "read"),
            file_hash_before=data.get("file_hash_before"),
            file_hash_after=data.get("file_hash_after"),
            bytes_changed=data.get("bytes_changed", 0),
            exists=data.get("exists", True),
        )


@dataclass
class ProcessEvidence(Evidence):
    """Authoritative subprocess execution evidence observed via OS primitives."""
    evidence_kind: str = EvidenceKind.PROCESS.value
    pid: int = 0
    argv: List[str] = field(default_factory=list)
    executable_path: str = ""
    executable_hash: str = ""
    exit_code: int = 0
    stdout_hash: str = ""
    stderr_hash: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "pid": self.pid,
            "argv": list(self.argv),
            "executable_path": self.executable_path,
            "executable_hash": self.executable_hash,
            "exit_code": self.exit_code,
            "stdout_hash": self.stdout_hash,
            "stderr_hash": self.stderr_hash,
            "duration_ms": round(self.duration_ms, 2),
        })
        return d

    @classmethod
    def _from_dict_fields(cls, data: Dict[str, Any]) -> ProcessEvidence:
        return cls(
            evidence_id=data.get("evidence_id", f"ev_{uuid.uuid4().hex[:12]}"),
            evidence_kind=EvidenceKind.PROCESS.value,
            source=data.get("source", "sclass"),
            collected_at=data.get("collected_at", datetime.now(timezone.utc).isoformat()),
            is_observed=data.get("is_observed", False),
            receipt_id=data.get("receipt_id"),
            receipt_hash=data.get("receipt_hash"),
            workspace_fingerprint=data.get("workspace_fingerprint", ""),
            metadata=dict(data.get("metadata", {})),
            pid=data.get("pid", 0),
            argv=list(data.get("argv", [])),
            executable_path=data.get("executable_path", ""),
            executable_hash=data.get("executable_hash", ""),
            exit_code=data.get("exit_code", 0),
            stdout_hash=data.get("stdout_hash", ""),
            stderr_hash=data.get("stderr_hash", ""),
            duration_ms=data.get("duration_ms", 0.0),
        )


def build_evidence_from_receipt(receipt: EvidenceReceipt) -> List[Evidence]:
    """Extracts typed Evidence items from an authentic EvidenceReceipt."""
    results: List[Evidence] = []
    meta = receipt.metadata if isinstance(receipt.metadata, dict) else {}
    exec_id = meta.get("execution_identity", {})

    # Process evidence
    p_ev = ProcessEvidence(
        source="receipt",
        is_observed=receipt.is_observed,
        receipt_id=receipt.receipt_id,
        receipt_hash=receipt.receipt_hash,
        workspace_fingerprint=receipt.workspace_fingerprint,
        metadata={"receipt_id": receipt.receipt_id},
        pid=exec_id.get("pid", 0) if isinstance(exec_id, dict) else 0,
        argv=list(exec_id.get("actual_argv", receipt.command.split())) if isinstance(exec_id, dict) else receipt.command.split(),
        executable_path=exec_id.get("executable_path", "") if isinstance(exec_id, dict) else "",
        executable_hash=exec_id.get("executable_hash", "") if isinstance(exec_id, dict) else "",
        exit_code=receipt.exit_code,
        stdout_hash=receipt.stdout_hash,
        stderr_hash=receipt.stderr_hash,
        duration_ms=meta.get("duration_ms", 0.0),
    )
    results.append(p_ev)

    # Filesystem evidence
    for fpath in receipt.files_changed:
        f_ev = FilesystemEvidence(
            source="receipt",
            is_observed=receipt.is_observed,
            receipt_id=receipt.receipt_id,
            receipt_hash=receipt.receipt_hash,
            workspace_fingerprint=receipt.workspace_fingerprint,
            path=fpath,
            operation="write",
            file_hash_after=receipt.file_hashes.get(fpath),
        )
        results.append(f_ev)

    # Test evidence (if structured results are present)
    struct_res = meta.get("structured_result")
    if struct_res and isinstance(struct_res, dict):
        t_ev = TestEvidence(
            source="receipt",
            is_observed=receipt.is_observed,
            receipt_id=receipt.receipt_id,
            receipt_hash=receipt.receipt_hash,
            workspace_fingerprint=receipt.workspace_fingerprint,
            test_framework=receipt.verifier or "test_runner",
            passed_count=struct_res.get("passed", 0),
            failed_count=struct_res.get("failed", 0),
            skipped_count=struct_res.get("skipped", 0),
            total_count=struct_res.get("total", 0),
            duration_ms=meta.get("duration_ms", 0.0),
            failures=list(struct_res.get("failures", [])),
        )
        results.append(t_ev)

    return results

