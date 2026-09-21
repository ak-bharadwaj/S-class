"""Quarantine contracts for isolating misbehaving agents."""
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class QuarantineRecord:
    agent_id: str
    quarantined_at: float
    reason: str
    revoked_leases: List[str]
    isolation_tier: str
