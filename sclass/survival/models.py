"""
S-Class Survival v0: Canonical Data Models (sclass/survival/models.py)

Provides deterministic, typed representations for:
- AuthorizationRequest / AuthorizationDecision
- EvidenceReceipt
- Claim / VerificationResult
- AdapterCapabilities
"""

from __future__ import annotations
from dataclasses import dataclass, field, InitVar
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import hashlib
import json
import uuid


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


LIFECYCLE_OBSERVED = "OBSERVED"
LIFECYCLE_INTEGRITY_VERIFIED = "INTEGRITY_VERIFIED"
LIFECYCLE_CLAIM_VERIFIED = "CLAIM_VERIFIED"

_OBSERVATION_TOKEN = object()


@dataclass
class EvidenceReceipt:
    """
    Canonical, tamper-evident evidence receipt capturing independently observed
    execution and repository state. The agent is never authoritative for these fields.
    Observation requires a private capability token and cannot be established by
    untrusted construction or JSON deserialization.
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
    started_at: str = ""
    finished_at: str = ""
    stdout_hash: str = ""
    stderr_hash: str = ""
    files_changed: List[str] = field(default_factory=list)
    file_hashes: Dict[str, str] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_observed: InitVar[Any] = None
    lifecycle_state: str = LIFECYCLE_OBSERVED
    verified: bool = False
    receipt_hash: Optional[str] = None
    workspace_fingerprint: str = ""
    _is_observed_hash_value: bool = field(default=False, repr=False, compare=False)
    _explicitly_unobserved: bool = field(default=False, repr=False, compare=False)
    _observation_token: object | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self, is_observed: Any = None) -> None:
        if is_observed is False:
            self._explicitly_unobserved = True
            self._is_observed_hash_value = False
        elif is_observed is True:
            self._explicitly_unobserved = False
            if self._observation_token is _OBSERVATION_TOKEN:
                self._is_observed_hash_value = True

        if self.files_changed is None:
            self.files_changed = []
        else:
            self.files_changed = sorted([f.replace("\\", "/").strip() for f in self.files_changed if f])
        if self.file_hashes is None:
            self.file_hashes = {}
        else:
            self.file_hashes = {k.replace("\\", "/").strip(): v for k, v in sorted(self.file_hashes.items())}
        if self.evidence is None:
            self.evidence = []
        if self.metadata is None:
            self.metadata = {}
        if not self.receipt_hash and isinstance(self.metadata, dict) and "receipt_hash" in self.metadata:
            self.receipt_hash = self.metadata["receipt_hash"]
        if not self.workspace_fingerprint and isinstance(self.metadata, dict) and "workspace_fingerprint" in self.metadata:
            self.workspace_fingerprint = str(self.metadata["workspace_fingerprint"])

    @property
    def is_observed(self) -> bool:
        """Observation requires the private capability token."""
        return self._observation_token is _OBSERVATION_TOKEN

    @is_observed.setter
    def is_observed(self, val: bool) -> None:
        """
        Allows demoting observation state.
        Setting to True without the private capability token is disallowed and ignored.
        """
        if not val:
            self._explicitly_unobserved = True
            self._observation_token = None
            self._is_observed_hash_value = False
        else:
            self._explicitly_unobserved = False

    def compute_hash(self) -> str:
        """
        Computes canonical cryptographic hash covering every security-relevant field.
        Mutable post-verification states (verified, lifecycle_state) are excluded so that
        the observation fingerprint remains immutable throughout its lifecycle.
        """
        clean_meta = {
            k: self.metadata[k]
            for k in sorted(self.metadata.keys())
            if k not in ("receipt_hash", "last_verified", "verification_timestamp")
        } if isinstance(self.metadata, dict) else {}

        clean_ws = (self.workspace or "").replace("\\", "/").rstrip("/")

        hash_obs = bool(self.is_observed or self._is_observed_hash_value)

        payload = {
            "receipt_id": self.receipt_id,
            "task_id": self.task_id,
            "claim_id": self.claim_id,
            "agent": self.agent,
            "action": self.action,
            "workspace": clean_ws,
            "base_commit": self.base_commit,
            "result_commit": self.result_commit,
            "command": self.command,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stdout_hash": self.stdout_hash,
            "stderr_hash": self.stderr_hash,
            "files_changed": sorted([f.replace("\\", "/").strip() for f in (self.files_changed or []) if f]),
            "file_hashes": {k.replace("\\", "/").strip(): v for k, v in sorted(self.file_hashes.items())} if self.file_hashes else {},
            "evidence": self.evidence or [],
            "metadata": clean_meta,
            "is_observed": hash_obs,
        }
        if self.workspace_fingerprint:
            payload["workspace_fingerprint"] = self.workspace_fingerprint
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = {
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
            "file_hashes": self.file_hashes,
            "evidence": self.evidence,
            "metadata": self.metadata,
            "is_observed": self.is_observed,
            "lifecycle_state": self.lifecycle_state,
            "verified": self.verified,
            "receipt_hash": self.receipt_hash or self.compute_hash(),
        }
        if self.workspace_fingerprint:
            d["workspace_fingerprint"] = self.workspace_fingerprint
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceReceipt:
        return cls.from_untrusted_data(data)

    @classmethod
    def from_untrusted_data(cls, data: Dict[str, Any]) -> EvidenceReceipt:
        """
        Reconstructs an EvidenceReceipt from untrusted external or persisted data.
        Persisted data is NEVER proof of observation, so this strictly returns EvidenceReceipt
        (where is_observed is False), never ObservedReceipt.
        """
        r_hash = data.get("receipt_hash") or (data.get("metadata", {}).get("receipt_hash") if isinstance(data.get("metadata"), dict) else None)
        obs_claimed = bool(data.get("is_observed", False))
        ws_fp = data.get("workspace_fingerprint") or (data.get("metadata", {}).get("workspace_fingerprint") if isinstance(data.get("metadata"), dict) else "")
        return EvidenceReceipt(
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
            files_changed=list(data.get("files_changed", []) or []),
            file_hashes=dict(data.get("file_hashes", {}) or {}),
            evidence=list(data.get("evidence", []) or []),
            metadata=dict(data.get("metadata", {}) or {}),
            lifecycle_state=data.get("lifecycle_state", LIFECYCLE_OBSERVED),
            verified=bool(data.get("verified", False)),
            receipt_hash=r_hash,
            workspace_fingerprint=str(ws_fp or ""),
            _is_observed_hash_value=obs_claimed,
            _observation_token=None,
        )


class ObservedReceipt(EvidenceReceipt):
    """
    Independently observed execution receipt generated by trusted S-Class execution runtime.
    Only ObservedReceipts can pass verification gates.
    """
    def __post_init__(self, is_observed: Any = True) -> None:
        self._observation_token = _OBSERVATION_TOKEN
        self._is_observed_hash_value = True
        super().__post_init__(is_observed=is_observed)


@dataclass(frozen=True)
class ProposedEvidence:
    """
    Caller- or agent-proposed evidence assertion.
    Unobserved and untrusted: cannot satisfy independent verification gates.
    """
    statement: str = ""
    exit_code: Optional[int] = None
    files_changed: Tuple[str, ...] = field(default_factory=tuple)
    evidence: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_observed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement": self.statement,
            "exit_code": self.exit_code,
            "files_changed": list(self.files_changed),
            "evidence": [dict(e) for e in self.evidence],
            "metadata": dict(self.metadata),
            "is_observed": False,
        }


ClaimedEvidence = ProposedEvidence


@dataclass(frozen=True)
class Claim:
    """
    Agent-authored assertion regarding completed work or test results.
    Claims are treated as unverified propositions until evaluated against evidence.
    """
    claim_id: str
    task_id: str
    statement: str
    claim_type: str = "completion"      # "test_pass" | "file_change" | "feature" | "documentation" | "completion"
    proposed_evidence: Optional[Any] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        prop_ev = self.proposed_evidence
        if hasattr(prop_ev, "to_dict"):
            prop_ev = prop_ev.to_dict()
        return {
            "claim_id": self.claim_id,
            "task_id": self.task_id,
            "statement": self.statement,
            "claim_type": self.claim_type,
            "proposed_evidence": prop_ev,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class VerificationEvent:
    """
    Authoritative, immutable event recording the outcome of evaluating a Claim
    against an ObservedReceipt within a specific repository state.
    Binds receipt_id, receipt_hash, workspace_fingerprint, claim_id, verification_result,
    and previous_ledger_hash.
    """
    claim_id: str
    receipt_id: str
    verifier: str
    verification_time: str
    result: str                         # "CLAIM_VERIFIED" | "REJECT" | "INVALID"
    reason: str
    repository_fingerprint: str
    receipt_hash: str = ""
    previous_ledger_hash: str = ""
    event_id: str = field(default_factory=lambda: f"vevt_{uuid.uuid4().hex[:12]}")
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def workspace_fingerprint(self) -> str:
        return self.repository_fingerprint

    @property
    def verification_result(self) -> str:
        return self.result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "claim_id": self.claim_id,
            "receipt_id": self.receipt_id,
            "receipt_hash": self.receipt_hash,
            "verifier": self.verifier,
            "verification_time": self.verification_time,
            "result": self.result,
            "verification_result": self.result,
            "reason": self.reason,
            "repository_fingerprint": self.repository_fingerprint,
            "workspace_fingerprint": self.repository_fingerprint,
            "previous_ledger_hash": self.previous_ledger_hash,
            "metadata": dict(self.metadata),
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
    verification_event: Optional[VerificationEvent] = None

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
            "verification_event": self.verification_event.to_dict() if self.verification_event else None,
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
