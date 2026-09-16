"""Test policy contracts and evaluation dataclasses."""
import pytest
from sclass.contracts.policy_contracts import AuthorizationRequest, AuthorizationDecision

def test_authorization_request_validation():
    req = AuthorizationRequest(actor_id="agent-01", action_type="WRITE_FILE", target_resource="/src/main.py", context_attributes={"mode": "strict"})
    assert req.actor_id == "agent-01"
    assert req.action_type == "WRITE_FILE"

def test_authorization_decision_frozen():
    decision = AuthorizationDecision(allowed=True, reason="Rule match", matched_policies=["pol-safe-write"], audit_hash="hash-123")
    assert decision.allowed is True
    with pytest.raises(AttributeError):
        decision.allowed = False
