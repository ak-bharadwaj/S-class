"""
S-Class Domain: EvidenceReceipt and Evidence Variants.
Preserves cryptographic invariants and enforces post-issuance immutability for ObservedReceipt.
"""

from __future__ import annotations
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

LIFECYCLE_PROPOSED = "proposed"
LIFECYCLE_CLAIMED = "claimed"
LIFECYCLE_OBSERVED = "observed"
LIFECYCLE_INTEGRITY_VERIFIED = "integrity_verified"
LIFECYCLE_CLAIM_VERIFIED = "claim_verified"

_OBSERVATION_TOKEN = object()


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
    _observation_token: Optional[object] = field(default=None, repr=False, compare=False)

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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceReceipt:
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
