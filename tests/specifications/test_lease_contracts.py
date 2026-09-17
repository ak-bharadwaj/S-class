"""Test symbol lease contracts."""
import pytest
from sclass.contracts.lease_contracts import SymbolLease, LeaseReleaseRequest

def test_symbol_lease_creation():
    lease = SymbolLease(
        symbol_path="src/auth.py::authenticate",
        holder_agent_id="agent_alpha",
        acquired_at=1000.0,
        expires_at=1060.0,
        lease_token="tok-999"
    )
    assert lease.symbol_path == "src/auth.py::authenticate"
    assert lease.expires_at > lease.acquired_at

def test_lease_release_request_matching():
    rel = LeaseReleaseRequest(symbol_path="src/main.py", holder_agent_id="ag1", lease_token="tok-1")
    assert rel.holder_agent_id == "ag1"
