"""Symbol lease contracts for concurrent agent swarms."""
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SymbolLease:
    symbol_path: str
    holder_agent_id: str
    acquired_at: float
    expires_at: float
    lease_token: str

@dataclass(frozen=True)
class LeaseReleaseRequest:
    symbol_path: str
    holder_agent_id: str
    lease_token: str
