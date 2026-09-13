"""
S-Class Domain: VerificationResult, VerificationEvent, VerifierScope, and TestSelection.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List


@dataclass(frozen=True)
class VerifierScope:
    """Declared or observed scope of a verifier invocation."""
    target_paths: tuple[str, ...] = field(default_factory=tuple)
    test_targets: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_paths": list(self.target_paths),
            "test_targets": list(self.test_targets),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VerifierScope:
        return cls(
            target_paths=tuple(data.get("target_paths", [])),
            test_targets=tuple(data.get("test_targets", [])),
        )


@dataclass(frozen=True)
class TestSelection:
    """Observed tests and targets executed by a verifier."""
    __test__ = False
    selected_tests: tuple[str, ...] = field(default_factory=tuple)
    test_files: tuple[str, ...] = field(default_factory=tuple)


    def covers_scope(self, claim_scope: Optional[Any]) -> Tuple[bool, Optional[str]]:
        """Verifies whether this test selection satisfies the required claim scope."""
        if not claim_scope or not getattr(claim_scope, "test_targets", None):
            return True, None

        combined = [t.replace("\\", "/").lower() for t in (list(self.selected_tests) + list(self.test_files))]
        for req in claim_scope.test_targets:
            norm_req = req.replace("\\", "/").lower().rstrip("/")
            match = any(norm_req in item for item in combined)
            if not match:
                return False, (
                    f"Required test target '{req}' was not executed in observed test run. "
                    f"Observed targets: {combined}"
                )
        return True, None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_tests": list(self.selected_tests),
            "test_files": list(self.test_files),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TestSelection:
        return cls(
            selected_tests=tuple(data.get("selected_tests", [])),
            test_files=tuple(data.get("test_files", [])),
        )


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
    status: str  # ACCEPT | REJECT | INVALID | INCONCLUSIVE
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
        return self.status == "REJECT"

    @property
    def is_invalid(self) -> bool:
        return self.status == "INVALID"

    @property
    def is_inconclusive(self) -> bool:
        return self.status == "INCONCLUSIVE"

    @property
    def is_unsupported(self) -> bool:
        return self.status == "UNSUPPORTED"


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
            "metadata": dict(self.metadata),
        }
