"""
S-Class Verification: Verification Provenance.
Binds claims, observed receipts, detected verifiers, and verification events.
"""

from __future__ import annotations
import hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationEvent, VerificationResult
from sclass.verification.detector import DetectionResult


@dataclass(frozen=True)
class VerificationProvenanceRecord:
    """Immutable audit trail of a verification decision."""
    verification_event_id: str
    claim_id: str
    claim_statement: str
    receipt_id: str
    receipt_hash: str
    detected_verifier: str
    detection_confidence: str
    verdict: str
    reason: str
    repository_fingerprint: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def compute_provenance_hash(self) -> str:
        payload = f"{self.verification_event_id}|{self.claim_id}|{self.receipt_hash}|{self.detected_verifier}|{self.verdict}|{self.repository_fingerprint}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_event_id": self.verification_event_id,
            "claim_id": self.claim_id,
            "claim_statement": self.claim_statement,
            "receipt_id": self.receipt_id,
            "receipt_hash": self.receipt_hash,
            "detected_verifier": self.detected_verifier,
            "detection_confidence": self.detection_confidence,
            "verdict": self.verdict,
            "reason": self.reason,
            "repository_fingerprint": self.repository_fingerprint,
            "timestamp": self.timestamp,
            "provenance_hash": self.compute_provenance_hash(),
        }
