"""Test quarantine contracts."""
import pytest
from sclass.contracts.quarantine_contracts import QuarantineRecord

def test_quarantine_record():
    rec = QuarantineRecord(agent_id="bad-agent", quarantined_at=500.0, reason="Exfiltration attempt", revoked_leases=["sym-1"], isolation_tier="TOTAL")
    assert rec.agent_id == "bad-agent"
    assert "Exfiltration" in rec.reason
