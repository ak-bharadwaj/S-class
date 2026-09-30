"""
Heartbeat monitor for fleet coordination leases.
"""
import time
from typing import Dict, Tuple

class HeartbeatMonitor:
    def __init__(self):
        self.active_leases: Dict[str, Tuple[str, float]] = {}

    def register_lease(self, symbol: str, agent_id: str, expiry_timestamp: float):
        self.active_leases[symbol] = (agent_id, expiry_timestamp)

    def prune_expired_leases(self) -> int:
        now = time.time()
        expired = [sym for sym, (_, exp) in self.active_leases.items() if now >= exp]
        for sym in expired:
            del self.active_leases[sym]
        return len(expired)

    def active_count(self) -> int:
        return len(self.active_leases)
