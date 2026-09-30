"""
Unit tests verifying symbol lease conflict detection in multi-agent fleet scenarios.
"""
import pytest
import time

class LeaseManager:
    def __init__(self):
        self.leases = {}

    def acquire_lease(self, agent_id: str, symbol: str, ttl_sec: float = 60.0) -> bool:
        now = time.time()
        if symbol in self.leases:
            holder, expiry = self.leases[symbol]
            if now < expiry and holder != agent_id:
                return False
        self.leases[symbol] = (agent_id, now + ttl_sec)
        return True

def test_lease_acquisition_and_collision():
    lm = LeaseManager()
    assert lm.acquire_lease("agent_A", "auth.py::login_user") is True
    assert lm.acquire_lease("agent_B", "auth.py::login_user") is False
    assert lm.acquire_lease("agent_A", "auth.py::login_user") is True
