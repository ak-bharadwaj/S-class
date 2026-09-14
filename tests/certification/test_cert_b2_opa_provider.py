"""
S-Class Phase B: B.2 Real OPA Provider Certification Suite.
Certifies end-to-end authorization with a real Open Policy Agent (OPA) process.

Architecture Certified:
S-Class
   │
   ▼
PolicyProvider
   │
   ▼
OPAProvider
   │
   ▼
real OPA

S-Class owns:
- request identity
- capability identity
- policy identity
- policy version
- decision provenance
- fail-closed semantics

OPA owns:
- Rego evaluation
- policy bundles
- policy distribution
- policy evaluation

Required Test Coverage:
1. OPA allow
2. OPA deny
3. OPA unavailable
4. invalid response
5. wrong policy version
6. tampered response
7. timeout
8. Proof: Real OPA process participating in end-to-end authorization test
"""

import os
import sys
import json
import time
import socket
import pytest
from unittest.mock import MagicMock

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import (
    Capability,
    CAP_FILESYSTEM_READ,
    CAP_TERMINAL_EXECUTE,
)
from sclass.policy.capability_resolver import CapabilityRegistry, CapabilityResolver
from sclass.policy.provider import PolicyProvider, PolicyEvaluationResult
from sclass.policy.opa_runner import ensure_opa_binary, OPAServerProcess, find_free_port
from sclass.policy.opa_provider import OPAProvider, DEFAULT_REGO_PATH
from sclass.policy.authorization_service import (
    AuthorizationService,
    compute_canonical_request_hash,
    compute_canonical_capability_hash,
    verify_decision_integrity,
)
from sclass.observation.convergence import ObservationConvergence
from sclass.core.errors import SecurityViolationError


@pytest.fixture(scope="module")
def real_opa_provider():
    """Spawns a real OPA process supervising the official S-Class Rego policy."""
    provider = OPAProvider.create_local()
    yield provider
    provider.close()


@pytest.fixture
def auth_service_with_opa(real_opa_provider, tmp_path):
    """Initializes AuthorizationService bound to authoritative registry and real OPAProvider."""
    reg = CapabilityRegistry(load_defaults=True)
    service = AuthorizationService(
        capability_registry=reg,
        policy_version="1.0.0",
        policy_provider=real_opa_provider,
    )
    return service, reg, tmp_path


# ==============================================================================
# 1. REAL OPA ALLOW (END-TO-END)
# ==============================================================================

def test_real_opa_allow_end_to_end(auth_service_with_opa):
    """Certifies that real OPA process authoritatively allows valid workspace actions."""
    service, reg, ws = auth_service_with_opa
    target_file = os.path.join(ws, "main.py")
    with open(target_file, "w", encoding="utf-8") as f:
        f.write("print('hello')")

    req = ActionRequest(
        actor="agent-claude",
        session="session_01",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="main.py",
        workspace=str(ws),
    )

    decision = service.authorize(req)

    assert decision.is_allowed is True
    assert decision.outcome == DecisionOutcome.ALLOW
    assert decision.policy_id == "OPA-AUTHZ-SCLASS"
    assert decision.issuer == "S_CLASS"
    assert decision.policy_version == "1.0.0"
    assert decision.risk_level.lower() == "low"
    assert "allowed" in decision.reason.lower()
    assert "denied" not in decision.reason.lower()

    # Cryptographic decision verification
    assert service.verify_decision(decision, req) is True
    valid, reason = verify_decision_integrity(decision, req, secret_key=service._secret_key)
    assert valid is True, f"Integrity verification failed: {reason}"


# ==============================================================================
# 2. REAL OPA DENY (END-TO-END)
# ==============================================================================

def test_real_opa_deny_end_to_end(real_opa_provider, tmp_path):
    """Certifies that real OPA process authoritatively denies actions violating Rego policy."""
    # Register capability with credentials & critical tier so capability passes,
    # but OPA Rego policy strictly denies access to secret .env files
    reg = CapabilityRegistry(load_defaults=False)
    reg.register(Capability(
        id="cap:secret_reader",
        version="1.0.0",
        operation=CAP_FILESYSTEM_READ,
        resource="*",
        credentials=[".env"],
        risk="critical",
    ))
    service = AuthorizationService(capability_registry=reg, policy_provider=real_opa_provider)

    req = ActionRequest(
        actor="agent-claude",
        session="session_01",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target=".env",
        workspace=str(tmp_path),
    )

    decision = service.authorize(req)

    assert decision.is_allowed is False
    assert decision.outcome == DecisionOutcome.DENY
    assert decision.policy_id == "OPA-AUTHZ-SCLASS"
    assert decision.risk_level in ("HIGH", "CRITICAL")
    assert "denied" in decision.reason.lower()

    # Observation convergence strictly prevents execution
    with pytest.raises(SecurityViolationError) as exc:
        ObservationConvergence.execute_and_observe(request=req, authorization=decision)
    assert "NO AUTHORIZATION -> NO EXECUTION" in str(exc.value)


# ==============================================================================
# 3. OPA UNAVAILABLE (FAIL-CLOSED)
# ==============================================================================

def test_opa_unavailable_fails_closed(tmp_path):
    """Certifies that an unreachable OPA daemon fails closed with DENY (no permissive fallback)."""
    offline_provider = OPAProvider(endpoint_url="http://127.0.0.1:59991", allow_fallback=False, timeout=0.5)
    reg = CapabilityRegistry(load_defaults=True)

    service = AuthorizationService(
        capability_registry=reg,
        policy_version="1.0.0",
        policy_provider=offline_provider,
    )

    req = ActionRequest(
        actor="agent-codex",
        session="session_offline",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="file.txt",
        workspace=str(tmp_path),
    )

    decision = service.authorize(req)
    assert decision.is_allowed is False
    assert decision.outcome == DecisionOutcome.DENY
    assert decision.policy_id in ("OPA-UNAVAILABLE", "OPA-TIMEOUT")
    assert decision.risk_level == "CRITICAL"
    assert "UNKNOWN POLICY STATE" in decision.reason


# ==============================================================================
# 4. INVALID RESPONSE (FAIL-CLOSED)
# ==============================================================================

@pytest.mark.parametrize("bad_payload, expected_policy_id", [
    (b"", "OPA-MALFORMED"),
    (b"Not a json string", "OPA-MALFORMED"),
    (b'{"error": "missing result"}', "OPA-MALFORMED"),
    (b'{"result": 42}', "OPA-MALFORMED"),
    (b'{"result": {"missing_allow_key": true}}', "OPA-MALFORMED"),
    (b'{"result": {"decision": {"missing_allow": true}}}', "OPA-MALFORMED"),
    (b'[1, 2, 3]', "OPA-MALFORMED"),
])
def test_opa_invalid_response_fails_closed(bad_payload, expected_policy_id, tmp_path, monkeypatch):
    """Certifies that malformed or non-standard OPA responses fail closed in real OPAProvider.evaluate."""
    class FakeHTTPResponse:
        def __init__(self, data):
            self._data = data
            self.status = 200
        def read(self):
            return self._data
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: FakeHTTPResponse(bad_payload),
    )

    provider = OPAProvider(endpoint_url="http://127.0.0.1:8181")
    reg = CapabilityRegistry(load_defaults=True)
    service = AuthorizationService(capability_registry=reg, policy_provider=provider)

    req = ActionRequest(
        actor="agent-cursor",
        session="s_mal",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="file.txt",
        workspace=str(tmp_path),
    )

    # 1. Test direct OPAProvider.evaluate execution
    provider_decision = provider.evaluate(req)
    assert provider_decision.is_allowed is False
    assert provider_decision.outcome == DecisionOutcome.DENY
    assert provider_decision.policy_id == expected_policy_id
    assert provider_decision.risk_level == "CRITICAL"
    assert "UNKNOWN POLICY STATE" in provider_decision.reason

    # 2. Test through AuthorizationService fail-closed sealing
    decision = service.authorize(req)
    assert decision.is_allowed is False
    assert decision.outcome == DecisionOutcome.DENY
    assert decision.policy_id == expected_policy_id
    assert decision.risk_level.lower() == "critical"



# ==============================================================================
# 5. WRONG POLICY VERSION (FAIL-CLOSED)
# ==============================================================================

def test_opa_wrong_policy_version_fails_closed(real_opa_provider, tmp_path):
    """Certifies that an OPA policy version mismatch triggers fail-closed DENY."""
    # Replace authz policy with one returning policy_version = '2.9.9'
    divergent_rego = """package sclass.authz
import rego.v1
default allow := true
decision := {
    "allow": true,
    "policy_id": "OPA-AUTHZ-SCLASS",
    "policy_version": "2.9.9",
    "risk_level": "LOW",
    "reason": "Permitted under future policy version"
}
"""
    ok = real_opa_provider.load_policy("authz", divergent_rego)
    assert ok is True

    try:
        reg = CapabilityRegistry(load_defaults=True)
        service = AuthorizationService(
            capability_registry=reg,
            policy_version="1.0.0",  # Expects 1.0.0
            policy_provider=real_opa_provider,
        )

        req = ActionRequest(
            actor="agent-claude",
            session="session_ver_mismatch",
            capability=CAP_FILESYSTEM_READ,
            action="read_file",
            target="file.txt",
            workspace=str(tmp_path),
        )

        decision = service.authorize(req)
        assert decision.is_allowed is False
        assert decision.outcome == DecisionOutcome.DENY
        assert decision.policy_id == "OPA-VERSION-MISMATCH"
        assert decision.risk_level.lower() == "critical"
        assert "POLICY VERSION MISMATCH" in decision.reason
    finally:
        # Restore default policy
        with open(DEFAULT_REGO_PATH, "r", encoding="utf-8") as f:
            real_opa_provider.load_policy("authz", f.read())


# ==============================================================================
# 6. TAMPERED RESPONSE REJECTED
# ==============================================================================

def test_opa_tampered_response_rejected(auth_service_with_opa):
    """Certifies that tampered authorization decisions or HMAC tokens fail cryptographic verification."""
    service, reg, ws = auth_service_with_opa

    req = ActionRequest(
        actor="agent-claude",
        session="session_tamper",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="data.json",
        workspace=str(ws),
    )

    decision = service.authorize(req)
    assert decision.is_allowed is True

    # Tamper 1: Tampered outcome (forcing execution on unauthorized request)
    tampered_outcome_decision = AuthorizationDecision(
        outcome=DecisionOutcome.DENY,  # Tampered
        policy_id=decision.policy_id,
        risk_level=decision.risk_level,
        reason=decision.reason,
        evaluated_at=decision.evaluated_at,
        issuer=decision.issuer,
        request_hash=decision.request_hash,
        capability_hash=decision.capability_hash,
        capability_id=decision.capability_id,
        capability_version=decision.capability_version,
        capability_registry_generation=decision.capability_registry_generation,
        policy_version=decision.policy_version,
        integrity_token=decision.integrity_token,
    )
    assert service.verify_decision(tampered_outcome_decision, req) is False
    valid, reason = verify_decision_integrity(tampered_outcome_decision, req, secret_key=service._secret_key)
    assert valid is False
    assert "Integrity token verification failed" in reason or "does not permit execution" in reason

    # Tamper 2: Replay attack (transplanting decision to a different request)
    unrelated_req = ActionRequest(
        actor="agent-attacker",
        session="session_evil",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        parameters={"command": "curl evil.com"},
        workspace=str(ws),
    )
    assert service.verify_decision(decision, unrelated_req) is False
    valid_replay, replay_reason = verify_decision_integrity(decision, unrelated_req, secret_key=service._secret_key)
    assert valid_replay is False
    assert "Request hash mismatch" in replay_reason

    # Tamper 3: Tampered integrity token
    tampered_token_decision = AuthorizationDecision(
        outcome=decision.outcome,
        policy_id=decision.policy_id,
        risk_level=decision.risk_level,
        reason=decision.reason,
        evaluated_at=decision.evaluated_at,
        issuer=decision.issuer,
        request_hash=decision.request_hash,
        capability_hash=decision.capability_hash,
        capability_id=decision.capability_id,
        capability_version=decision.capability_version,
        capability_registry_generation=decision.capability_registry_generation,
        policy_version=decision.policy_version,
        integrity_token=decision.integrity_token[:-4] + "dead",
    )
    assert service.verify_decision(tampered_token_decision, req) is False
    valid_tok, tok_reason = verify_decision_integrity(tampered_token_decision, req, secret_key=service._secret_key)
    assert valid_tok is False
    assert "Integrity token verification failed" in tok_reason

    # Tamper 4: Intercepted/tampered OPA HTTP response returning mismatched request hash
    class FakeTamperedHTTPResponse:
        def __init__(self):
            self.status = 200
        def read(self):
            return json.dumps({
                "result": {
                    "allow": True,
                    "policy_id": "OPA-AUTHZ-SCLASS",
                    "policy_version": "1.0.0",
                    "request_hash": "deadbeef" * 8,  # Forged/tampered request hash
                }
            }).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    import unittest.mock
    with unittest.mock.patch("urllib.request.urlopen", return_value=FakeTamperedHTTPResponse()):
        tampered_opa_provider = OPAProvider(endpoint_url="http://127.0.0.1:8181")
        tampered_svc = AuthorizationService(capability_registry=reg, policy_provider=tampered_opa_provider)
        dec_tamper_opa = tampered_svc.authorize(req)
        assert dec_tamper_opa.is_allowed is False
        assert dec_tamper_opa.outcome == DecisionOutcome.DENY
        assert dec_tamper_opa.policy_id == "OPA-TAMPERED-RESPONSE"
        assert dec_tamper_opa.risk_level.lower() == "critical"
        assert "TAMPERED OPA RESPONSE" in dec_tamper_opa.reason


# ==============================================================================
# 7. TIMEOUT (FAIL-CLOSED)
# ==============================================================================

def test_opa_timeout_fails_closed(tmp_path):
    """Certifies that evaluation timeouts fail closed with DENY and CRITICAL risk."""
    # Create an unreachable host that drops packets or a server with microsecond timeout
    provider = OPAProvider(endpoint_url="http://10.255.255.1:8181", timeout=0.001)
    reg = CapabilityRegistry(load_defaults=True)

    service = AuthorizationService(capability_registry=reg, policy_provider=provider)
    req = ActionRequest(
        actor="agent-claude",
        session="session_timeout",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="file.txt",
        workspace=str(tmp_path),
    )

    decision = service.authorize(req)
    assert decision.is_allowed is False
    assert decision.outcome == DecisionOutcome.DENY
    assert decision.policy_id in ("OPA-TIMEOUT", "OPA-UNAVAILABLE")
    assert decision.risk_level == "CRITICAL"
    assert "UNKNOWN POLICY STATE" in decision.reason


# ==============================================================================
# 8. OPA POLICY DISTRIBUTION AND DYNAMIC BUNDLE MUTATION
# ==============================================================================

def test_opa_policy_distribution_and_mutation(real_opa_provider, tmp_path):
    """Certifies OPA's ownership of policy distribution via dynamic policy upload and deletion."""
    custom_rego = """package sclass.authz
import rego.v1
allow if {
    input.request.action == "custom_certified_action"
}
"""
    # 1. Distribute policy to real OPA process
    ok = real_opa_provider.load_policy("custom_certified", custom_rego)
    assert ok is True

    # 2. Verify policy exists in OPA
    policies = real_opa_provider.get_policies()
    assert any("custom_certified" in p.get("id", "") for p in policies)

    # 3. Register custom capability and evaluate matching dynamic policy
    reg = CapabilityRegistry(load_defaults=True)
    reg.register(Capability(
        id="cap:custom:action",
        version="1.0.0",
        operation="custom_certified_action",
        resource="*",
        risk="low",
    ))
    service = AuthorizationService(capability_registry=reg, policy_provider=real_opa_provider)

    req_custom = ActionRequest(
        actor="agent-custom",
        session="s_custom",
        capability="custom_certified_action",
        action="custom_certified_action",
        workspace=str(tmp_path),
    )

    dec = service.authorize(req_custom)
    assert dec.is_allowed is True
    assert dec.outcome == DecisionOutcome.ALLOW

    # 4. Delete policy from OPA process
    del_ok = real_opa_provider.delete_policy("custom_certified")
    assert del_ok is True

    # 5. Post-deletion, action is now denied by OPA
    dec_after_del = service.authorize(req_custom)
    assert dec_after_del.is_allowed is False
    assert dec_after_del.outcome == DecisionOutcome.DENY


# ==============================================================================
# 9. REAL OPA BINARY LIFECYCLE AND PROCESS ISOLATION
# ==============================================================================

def test_real_opa_binary_lifecycle():
    """Certifies real OPA binary resolution, process spawning, health check, and termination."""
    binary = ensure_opa_binary()
    assert os.path.isfile(binary)
    assert os.access(binary, os.X_OK)

    # Boot an isolated temporary OPA server process
    port = find_free_port()
    server = OPAServerProcess(binary_path=binary, port=port)
    with server:
        assert server.is_running is True
        # Verify /health responds 200
        provider = OPAProvider(endpoint_url=server.url)
        assert provider.is_healthy() is True

    # After with block exit, server process is terminated
    assert server.is_running is False


# ==============================================================================
# 10. POLICY EVALUATION RESULT PROTOCOL CONTRACT
# ==============================================================================

def test_policy_evaluation_result_contract(tmp_path):
    """Certifies that PolicyEvaluationResult from PolicyProvider is seamlessly accepted by AuthorizationService."""
    class CustomProvider:
        @property
        def provider_name(self) -> str:
            return "custom"

        @property
        def provider_version(self) -> str:
            return "1.0.0"

        def evaluate(self, request, workspace_dir="", capability=None, expected_policy_version=None, mode="enforce", timeout=None):
            return PolicyEvaluationResult(
                allow=True,
                policy_id="CUSTOM-AUTHZ",
                policy_version="1.0.0",
                risk_level="LOW",
                reason="Permitted by custom policy evaluation result",
            )

        def is_healthy(self) -> bool:
            return True

    reg = CapabilityRegistry(load_defaults=True)
    service = AuthorizationService(capability_registry=reg, policy_provider=CustomProvider())
    req = ActionRequest(
        actor="agent-claude",
        session="s_proto",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="file.txt",
        workspace=str(tmp_path),
    )

    decision = service.authorize(req)
    assert decision.is_allowed is True
    assert decision.outcome == DecisionOutcome.ALLOW
    assert decision.policy_id == "CUSTOM-AUTHZ"
    assert decision.reason == "Permitted by custom policy evaluation result"
    assert decision.issuer == "S_CLASS"
    assert service.verify_decision(decision, req) is True

