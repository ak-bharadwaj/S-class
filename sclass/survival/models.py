"""
S-Class Survival v0: Canonical Data Models (sclass/survival/models.py)

Provides deterministic, typed representations for:
- AuthorizationRequest / AuthorizationDecision
- EvidenceReceipt
- Claim / VerificationResult
- AdapterCapabilities
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import hashlib
import json


@dataclass(frozen=True)
class AuthorizationRequest:
    """
    Canonical representation of an incoming agent action proposal.
    Platform-agnostic: adapters normalize vendor events into this structure.
    """
    agent: str                          # e.g., "claude", "cursor", "antigravity", "codex"
    platform: str                       # platform identifier
    action: str                         # e.g., "file_edit", "shell_command", "tool_use", "read_file"
    tool: Optional[str] = None          # tool name if applicable
    target: Optional[str] = None        # file path, command string, or resource target
    parameters: Dict[str, Any] = field(default_factory=dict)
    workspace: str = ""                 # absolute path to workspace root
    task_id: Optional[str] = None       # correlation task identifier
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "platform": self.platform,
            "action": self.action,
            "tool": self.tool,
            "target": self.target,
            "parameters": self.parameters,
            "workspace": self.workspace,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class AuthorizationDecision:
    """
    Authoritative governance verdict returned by S-Class policy engine.
    """
    outcome: str                        # "allow" | "warn" | "deny"
    policy_id: str                      # e.g. "SCLASS-SEC-001", "SCLASS-EVID-001"
    risk_level: str                     # "low" | "medium" | "high" | "critical"
    reason: str                         # explicit rationale, sanitized of secret material
    remediation: str                    # guidance on how to satisfy the policy
    diagnostics: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_allowed(self) -> bool:
        return self.outcome == "allow"

    @property
    def is_denied(self) -> bool:
        return self.outcome == "deny"

    @property
    def is_warn(self) -> bool:
        return self.outcome == "warn"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome,
            "policy_id": self.policy_id,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "remediation": self.remediation,
            "diagnostics": list(self.diagnostics),
        }


@dataclass
class EvidenceReceipt:
    """
    Canonical, tamper-evident evidence receipt capturing independently observed
    execution and repository state. The agent is never authoritative for these fields.
    """
    receipt_id: str
    task_id: str
    claim_id: str
    agent: str
    action: str
    workspace: str
    base_commit: str
    result_commit: str
    command: str
    exit_code: int
    started_at: str
    finished_at: str
    stdout_hash: str
    stderr_hash: str
    files_changed: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.files_changed:
            self.files_changed = sorted([f.replace("\\", "/").strip() for f in self.files_changed if f])

    def compute_hash(self) -> str:
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
            "files_changed": sorted(self.files_changed),
            "verified": self.verified,
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

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
            "files_changed": self.files_changed,
            "evidence": self.evidence,
            "verified": self.verified,
            "metadata": self.metadata,
            "receipt_hash": self.compute_hash(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceReceipt:
        return cls(
            receipt_id=data.get("receipt_id", ""),
            task_id=data.get("task_id", ""),
            claim_id=data.get("claim_id", ""),
            agent=data.get("agent", ""),
            action=data.get("action", ""),
            workspace=data.get("workspace", ""),
            base_commit=data.get("base_commit", ""),
            result_commit=data.get("result_commit", ""),
            command=data.get("command", ""),
            exit_code=data.get("exit_code", -1),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            stdout_hash=data.get("stdout_hash", ""),
            stderr_hash=data.get("stderr_hash", ""),
            files_changed=list(data.get("files_changed", [])),
            evidence=list(data.get("evidence", [])),
            verified=bool(data.get("verified", False)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class Claim:
    """
    Agent-authored assertion regarding completed work or test results.
    Claims are treated as unverified propositions until evaluated against evidence.
    """
    claim_id: str
    task_id: str
    statement: str
    claim_type: str = "completion"      # "test_pass" | "file_change" | "feature" | "completion"
    proposed_evidence: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "task_id": self.task_id,
            "statement": self.statement,
            "claim_type": self.claim_type,
            "proposed_evidence": self.proposed_evidence,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class VerificationResult:
    """
    Outcome of evaluating a Claim against independent EvidenceReceipt.
    """
    status: str                         # "ACCEPT" | "REJECT" | "INVALID"
    claim_id: str
    reason: str
    observed_exit_code: Optional[int] = None
    observed_files_changed: Tuple[str, ...] = field(default_factory=tuple)
    failed_tests: int = 0
    passed_tests: int = 0
    invalidation_reason: Optional[str] = None
    receipt_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_accepted(self) -> bool:
        return self.status == "ACCEPT"

    @property
    def is_rejected(self) -> bool:
        return self.status == "REJECT"

    @property
    def is_invalid(self) -> bool:
        return self.status == "INVALID"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "claim_id": self.claim_id,
            "reason": self.reason,
            "observed_exit_code": self.observed_exit_code,
            "observed_files_changed": list(self.observed_files_changed),
            "failed_tests": self.failed_tests,
            "passed_tests": self.passed_tests,
            "invalidation_reason": self.invalidation_reason,
            "receipt_id": self.receipt_id,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class AdapterCapabilities:
    """
    Explicit capabilities declared by a host agent platform adapter.
    """
    pre_action_enforcement: bool = False
    post_action_observation: bool = False
    approval: bool = False
    verification: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return {
            "pre_action_enforcement": self.pre_action_enforcement,
            "post_action_observation": self.post_action_observation,
            "approval": self.approval,
            "verification": self.verification,
        }
