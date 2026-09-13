"""
S-Class Domain: VerificationResult and VerificationEvent.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class VerificationEvent:
    """Cryptographically anchored audit record emitted upon claim evaluation."""
    claim_id: str
    receipt_id: str
    receipt_hash: str
    verifier: str
    verification_time: str
    result: str
    reason: str
    repository_fingerprint: str
    previous_ledger_hash: str
    event_id: str = field(default_factory=lambda: f"vevt_{uuid.uuid4().hex[:12]}")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "claim_id": self.claim_id,
            "receipt_id": self.receipt_id,
            "receipt_hash": self.receipt_hash,
            "verifier": self.verifier,
            "verification_time": self.verification_time,
            "result": self.result,
            "reason": self.reason,
            "repository_fingerprint": self.repository_fingerprint,
            "previous_ledger_hash": self.previous_ledger_hash,
            "metadata": dict(self.metadata),
        }


@dataclass
class VerificationResult:
    """The authoritative verdict of an agent claim evaluated against observed evidence."""
    status: str  # ACCEPT | REJECT | INVALID
    claim_id: str
    reason: str
    observed_exit_code: Optional[int] = None
    observed_files_changed: Tuple[str, ...] = field(default_factory=tuple)
    passed_tests: int = 0
    failed_tests: int = 0
    invalidation_reason: Optional[str] = None
    receipt_id: Optional[str] = None
    verification_event: Optional[VerificationEvent] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_accepted(self) -> bool:
        return self.status == "ACCEPT"

    @property
    def is_rejected(self) -> bool:
        return self.status in ("REJECT", "INVALID")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "claim_id": self.claim_id,
            "reason": self.reason,
            "observed_exit_code": self.observed_exit_code,
            "observed_files_changed": list(self.observed_files_changed),
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "invalidation_reason": self.invalidation_reason,
            "receipt_id": self.receipt_id,
            "verification_event": self.verification_event.to_dict() if self.verification_event else None,
            "metadata": self.metadata,
        }
