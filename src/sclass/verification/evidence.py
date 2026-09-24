"""
S-Class Verification: Authoritative Evidence Pipeline.
Connects sensory observations to typed verification assessments:
ObservationReceipt -> Verifier Engine -> Verified Evidence Receipt -> Canonical Claim State.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sclass.observation.receipt import EvidenceReceipt
from sclass.domain.claim import ClaimType


@dataclass(frozen=True)
class VerifiedEvidence:
    """Authoritative verified evidence tying an observation receipt to a claim requirement."""
    evidence_id: str
    task_id: str
    claim_type: ClaimType
    verifier_id: str
    observation_receipt_id: str
    passed: bool
    details: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "task_id": self.task_id,
            "claim_type": self.claim_type.value,
            "verifier_id": self.verifier_id,
            "observation_receipt_id": self.observation_receipt_id,
            "passed": self.passed,
            "details": dict(self.details),
            "timestamp": self.timestamp,
        }
