"""
S-Class Trust: Trust Anchors.
Manages immutable anchors binding observations and verifications into cryptographic ledgers.
"""

from __future__ import annotations
import hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class TrustAnchor:
    """Cryptographic anchor securing an observation or verification."""
    anchor_id: str
    target_id: str
    target_hash: str
    previous_hash: str
    anchor_type: str  # "OBSERVATION", "VERIFICATION", "CHECKPOINT"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def compute_anchor_hash(self) -> str:
        payload = f"{self.anchor_id}:{self.target_id}:{self.target_hash}:{self.previous_hash}:{self.anchor_type}:{self.timestamp}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "target_id": self.target_id,
            "target_hash": self.target_hash,
            "previous_hash": self.previous_hash,
            "anchor_type": self.anchor_type,
            "timestamp": self.timestamp,
            "anchor_hash": self.compute_anchor_hash(),
        }
