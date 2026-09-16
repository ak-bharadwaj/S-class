"""Evidence contracts for independent observation."""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass(frozen=True)
class RawObservable:
    exit_code: int
    stdout_sha256: str
    stderr_sha256: str
    duration_ms: float
    pid: Optional[int] = None
    argv: Optional[List[str]] = None

@dataclass(frozen=True)
class EvidencePayload:
    action_id: str
    observable: RawObservable
    verifier_id: str
    verified_at_timestamp: float
    metadata: Optional[Dict[str, Any]] = None
