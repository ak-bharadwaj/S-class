"""
S-Class Certification: Handoff B.1.1 Security Closure Adversarial Test Suite.
Verifies the non-negotiable core invariants:
1. NO AUTHORIZATION -> NO EXECUTION
2. NO SANDBOX -> NO SANDBOXED EXECUTION
3. UNKNOWN POLICY STATE -> NO EXECUTION
4. UNKNOWN BACKEND -> NO EXECUTION
5. MISSING REQUIRED EVIDENCE -> NO ACCEPTED CLAIM
Plus exhaustive 11-dimensional capability evaluation and strict resource scoping.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import (
    Capability,
    CapabilityDecision,
    CapabilityEvaluator,
    CAP_TERMINAL_EXECUTE,
    CAP_FILESYSTEM_READ,
    CAP_FILESYSTEM_WRITE,
    CAP_GIT_READ,
    CAP_GIT_WRITE,
    CAP_NETWORK_REQUEST,
    CAP_SECRET_READ,
    CAP_PROCESS_SPAWN,
)
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.evidence import TestEvidence, SecurityEvidence, EvidenceKind
from sclass.domain.verification import VerificationResult
from sclass.execution.backend import (
    SandboxBackend,
    HostProcessBackend,
    SandboxConfigCompiler,
    get_execution_backend,
)
from sclass.execution.sandbox import GVisorSandbox, BubblewrapSandbox, get_sandbox_backend
from sclass.observation.convergence import ObservationConvergence, converge_execution
from sclass.verification.plan import VerificationPlan
from sclass.policy.opa import OPAInputCompiler, OPAClient, OPAPolicyAdapter
from sclass.core.errors import SecurityViolationError
from sclass.trust.ledger import LocalLedger


@pytest.fixture
def test_ws(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "src").mkdir()
    (ws / "src" / "main.py").write_text("print('hello')")
    (ws / "secrets").mkdir()
    (ws / "secrets" / "api.key").write_text("SUPER_SECRET_KEY")
    (ws / ".env").write_text("API_KEY=12345")
    return str(ws)


# ==============================================================================
# INVARIANT 1: NO AUTHORIZATION -> NO EXECUTION
# ==============================================================================

def test_no_authorization_no_execution_none_request(test_ws):
    """Certifies that executing without an ActionRequest raises SecurityViolationError."""
    with pytest.raises(SecurityViolationError) as exc:
        ObservationConvergence.execute_and_observe(request=None)
    assert "NO AUTHORIZATION -> NO EXECUTION" in str(exc.value)


def test_no_authorization_no_execution_denied_by_policy(test_ws):
    """Certifies that any ActionRequest denied by policy raises SecurityViolationError before execution."""
    ledger = LocalLedger(workspace_dir=test_ws)
    initial_count = ledger.get_entry_count()

    req_denied = ActionRequest(
        actor="hostile-agent",
        session="sess_deny",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="rm -rf /",
        parameters={"command": "rm -rf /"},
        workspace=test_ws,
    )

    with pytest.raises(SecurityViolationError) as exc:
        ObservationConvergence.execute_and_observe(
            request=req_denied,
            backend=HostProcessBackend(),
            ledger=ledger,
        )
    assert "NO AUTHORIZATION -> NO EXECUTION" in str(exc.value)
    assert ledger.get_entry_count() == initial_count


def test_no_authorization_no_execution_unapproved_action(test_ws):
    """Certifies that an action requiring approval cannot execute without explicit approval."""
    req = ActionRequest(
        actor="agent-cursor",
        session="sess_approval",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="reboot",
        workspace=test_ws,
    )

    approval_decision = AuthorizationDecision(
        outcome=DecisionOutcome.REQUIRE_APPROVAL,
        policy_id="SCLASS-APPROVAL-REQUIRED",
        risk_level="HIGH",
        reason="Action requires operator approval token",
    )

    with pytest.raises(SecurityViolationError) as exc:
        ObservationConvergence.execute_and_observe(
            request=req,
            authorization=approval_decision,
        )
    assert "NO AUTHORIZATION -> NO EXECUTION" in str(exc.value)


# ==============================================================================
# INVARIANT 2: NO SANDBOX -> NO SANDBOXED EXECUTION
# ==============================================================================

def test_no_sandbox_no_sandboxed_execution_bubblewrap(test_ws):
    """Certifies that when a sandbox is requested and unavailable, execution fails closed."""
    sb = SandboxBackend(backend_type="bubblewrap", fallback_to_host=False)
    with patch.object(sb, "is_available", return_value=False):
        with pytest.raises(SecurityViolationError) as exc:
            sb.execute(command="echo isolated", cwd=test_ws)
        assert "NO SANDBOX -> NO SANDBOXED EXECUTION" in str(exc.value)


def test_no_sandbox_no_sandboxed_execution_gvisor_never_degrades_to_host(test_ws):
    """Certifies that gVisor strictly refuses host degradation even if fallback_to_host=True."""
    sb = SandboxBackend(backend_type="gvisor", fallback_to_host=True)
    with patch.object(sb, "is_available", return_value=False):
        with pytest.raises(SecurityViolationError) as exc:
            sb.execute(command="echo gvisor", cwd=test_ws)
        assert "NO SANDBOX -> NO SANDBOXED EXECUTION" in str(exc.value)
        assert "gVisor" in str(exc.value)


def test_gvisor_sandbox_unit_fails_closed(test_ws):
    """Certifies that GVisorSandbox directly raises SecurityViolationError when runsc is absent."""
    with patch("shutil.which", return_value=None):
        gv = GVisorSandbox()
        assert gv.is_available() is False
        with pytest.raises(SecurityViolationError) as exc:
            gv.wrap_command(["pytest"], test_ws)
        assert "Fail-closed policy prevents uncontained execution" in str(exc.value)


# ==============================================================================
# INVARIANT 3: UNKNOWN POLICY STATE -> NO EXECUTION
# ==============================================================================

def test_unknown_policy_state_no_execution_opa_unavailable(test_ws):
    """Certifies that OPA connection failures / timeouts fail closed with DENY and block execution."""
    req = ActionRequest(
        actor="agent-claude",
        session="s_opa_unavail",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="pytest",
        workspace=test_ws,
    )

    # Point to nonexistent port without fallback
    adapter = OPAPolicyAdapter(endpoint_url="http://127.0.0.1:59999", allow_fallback=False)
    decision = adapter.evaluate(req, workspace_dir=test_ws)
    assert decision.is_allowed is False
    assert decision.outcome == DecisionOutcome.DENY
    assert decision.policy_id == "OPA-UNAVAILABLE"
    assert "UNKNOWN POLICY STATE" in decision.reason

    # Observation convergence blocks it
    with pytest.raises(SecurityViolationError) as exc:
        ObservationConvergence.execute_and_observe(request=req, authorization=decision)
    assert "NO AUTHORIZATION -> NO EXECUTION" in str(exc.value)


def test_unknown_policy_state_no_execution_opa_malformed_response(test_ws):
    """Certifies that malformed OPA responses (missing result, missing allow, unknown type) fail closed."""
    req = ActionRequest(
        actor="agent-codex",
        session="s_opa_mal",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="pytest",
        workspace=test_ws,
    )

    mock_client = MagicMock()
    adapter = OPAPolicyAdapter(client=mock_client, allow_fallback=False)

    # Case A: Missing 'result' key
    mock_client.evaluate_raw.return_value = {"error": "unexpected structure"}
    dec_a = adapter.evaluate(req, workspace_dir=test_ws)
    assert dec_a.outcome == DecisionOutcome.DENY
    assert dec_a.policy_id == "OPA-MALFORMED"
    assert "UNKNOWN POLICY STATE" in dec_a.reason

    # Case B: Dictionary result missing 'allow' boolean key
    mock_client.evaluate_raw.return_value = {"result": {"status": "ok"}}
    dec_b = adapter.evaluate(req, workspace_dir=test_ws)
    assert dec_b.outcome == DecisionOutcome.DENY
    assert dec_b.policy_id == "OPA-MALFORMED"
    assert "UNKNOWN POLICY STATE" in dec_b.reason

    # Case C: Unexpected result type (e.g. integer)
    mock_client.evaluate_raw.return_value = {"result": 12345}
    dec_c = adapter.evaluate(req, workspace_dir=test_ws)
    assert dec_c.outcome == DecisionOutcome.DENY
    assert dec_c.policy_id == "OPA-MALFORMED"


# ==============================================================================
# INVARIANT 4: UNKNOWN BACKEND -> NO EXECUTION
# ==============================================================================

def test_unknown_backend_no_execution():
    """Certifies that requesting an unknown execution backend raises SecurityViolationError."""
    with pytest.raises(SecurityViolationError) as exc:
        get_execution_backend("nonexistent_cloud_sandbox")
    assert "UNKNOWN BACKEND -> NO EXECUTION" in str(exc.value)


# ==============================================================================
# INVARIANT 5: MISSING REQUIRED EVIDENCE -> NO ACCEPTED CLAIM
# ==============================================================================

def test_missing_required_evidence_kinds_no_accepted_claim(test_ws):
    """Certifies that missing declared evidence kinds strictly prevents claim acceptance."""
    claim = Claim(
        claim_id="c_evidence_1",
        task_id="t1",
        statement="Code is built and tested",
        claim_type=ClaimType.TEST_PASS.value,
    )
    plan = VerificationPlan(
        target_claims=[claim],
        required_evidence_kinds=["test", "build"],
    )

    t_ev = TestEvidence(source="pytest", is_observed=True, passed_count=10)
    # Missing 'build' evidence
    results = plan.coordinate([t_ev], workspace_dir=test_ws)
    verdict = results["c_evidence_1"]
    assert verdict.is_accepted is False
    assert verdict.status == "INCONCLUSIVE"
    assert "MISSING REQUIRED EVIDENCE" in verdict.reason


def test_missing_required_verifiers_no_accepted_claim(test_ws):
    """Certifies that missing declared verifiers strictly prevents claim acceptance."""
    claim = Claim(
        claim_id="c_verifier_1",
        task_id="t2",
        statement="Audit complete",
        claim_type=ClaimType.TEST_PASS.value,
    )
    plan = VerificationPlan(
        target_claims=[claim],
        verifier_ids=["semgrep", "trivy"],
    )

    t_ev = TestEvidence(source="pytest", is_observed=True, passed_count=5)
    results = plan.coordinate([t_ev], workspace_dir=test_ws)
    verdict = results["c_verifier_1"]
    assert verdict.is_accepted is False
    assert verdict.status == "INCONCLUSIVE"
    assert "MISSING REQUIRED EVIDENCE" in verdict.reason


def test_empty_evidence_no_accepted_claim(test_ws):
    """Certifies that an empty evidence list can never produce an accepted claim."""
    claim = Claim(
        claim_id="c_empty_1",
        task_id="t3",
        statement="Everything is fine",
        claim_type=ClaimType.TEST_PASS.value,
    )
    plan = VerificationPlan(target_claims=[claim])
    results = plan.coordinate([], workspace_dir=test_ws)
    verdict = results["c_empty_1"]
    assert verdict.is_accepted is False


def test_unobserved_evidence_strictly_rejected(test_ws):
    """Certifies that self-asserted or unobserved evidence causes strict claim rejection."""
    claim = Claim(
        claim_id="c_unobserved_1",
        task_id="t4",
        statement="Tests pass",
        claim_type=ClaimType.TEST_PASS.value,
    )
    plan = VerificationPlan(target_claims=[claim])

    unobserved_ev = TestEvidence(source="agent_self_report", is_observed=False, passed_count=100)
    results = plan.coordinate([unobserved_ev], workspace_dir=test_ws)
    verdict = results["c_unobserved_1"]
    assert verdict.is_accepted is False
    assert verdict.status == "REJECT"
    assert "UNAUTHENTIC EVIDENCE" in verdict.reason


# ==============================================================================
# 6. EXHAUSTIVE RESOURCE SCOPING & PATH WIDENING PREVENTION TESTS
# ==============================================================================

def test_resource_pattern_cannot_be_widened_by_traversal(test_ws):
    """
    Certifies that path traversal tricks (src/../secrets/api.key)
    cannot widen scope or escape resource constraints.
    """
    cap = Capability(
        actor="agent-codex",
        operation=CAP_FILESYSTEM_READ,
        resource="src/**",
        scope="workspace",
        workspace=test_ws,
    )

    traversal_targets = [
        "src/../secrets/api.key",
        "src/../../etc/passwd",
        "secrets/api.key",
        ".env",
        "src/../.env",
    ]
    for target in traversal_targets:
        req = ActionRequest(
            actor="agent-codex",
            session="s_trav",
            capability=CAP_FILESYSTEM_READ,
            action="read_file",
            target=target,
            workspace=test_ws,
        )
        assert cap.allows_request(req, test_ws) is False, f"Target '{target}' should have been rejected"


def test_resource_wildcard_direct_children_vs_recursive(test_ws):
    """Certifies strict distinction between src/* (direct children) and src/** (recursive)."""
    cap_shallow = Capability(
        operation=CAP_FILESYSTEM_READ,
        resource="src/*",
        scope="workspace",
        workspace=test_ws,
    )

    # Direct child allowed
    req_direct = ActionRequest(
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="src/main.py",
        workspace=test_ws,
    )
    assert cap_shallow.allows_request(req_direct, test_ws) is True

    # Deep child rejected under src/*
    req_deep = ActionRequest(
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="src/deep/nested/module.py",
        workspace=test_ws,
    )
    assert cap_shallow.allows_request(req_deep, test_ws) is False


# ==============================================================================
# 7. EXHAUSTIVE 11-DIMENSIONAL CAPABILITY EVALUATION TESTS
# ==============================================================================

def test_capability_evaluator_all_11_dimensions(test_ws):
    """Exhaustively tests all 11 security dimensions on CapabilityEvaluator."""
    cap = Capability(
        actor="agent-claude",
        operation=CAP_TERMINAL_EXECUTE,
        resource="src/**",
        scope="workspace",
        workspace=test_ws,
        arguments={"toolchain": "python3"},
        risk="medium",
        duration=60.0,
        network=False,
        filesystem="read",
        credentials=["DEV_TOKEN"],
        approval=True,
    )

    # Base valid request (satisfying all 11 dimensions)
    req_valid = ActionRequest(
        actor="agent-claude",
        session="s_valid",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="src/main.py",
        parameters={
            "toolchain": "python3",
            "timeout": 30.0,
            "credentials": ["DEV_TOKEN"],
            "approved": True,
            "risk": "low",
        },
        workspace=test_ws,
    )
    dec_valid = cap.evaluate_request(req_valid, test_ws)
    assert dec_valid.allowed is True
    assert len(dec_valid.failed_constraints) == 0

    # Dimension 1: Actor mismatch
    req_bad_actor = ActionRequest(
        actor="agent-evil",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="src/main.py",
        parameters={"toolchain": "python3", "approved": True},
        workspace=test_ws,
    )
    assert any("actor_mismatch" in f for f in cap.evaluate_request(req_bad_actor, test_ws).failed_constraints)

    # Dimension 2: Operation mismatch
    req_bad_op = ActionRequest(
        actor="agent-claude",
        capability=CAP_NETWORK_REQUEST,
        action="fetch",
        target="src/main.py",
        parameters={"toolchain": "python3", "approved": True},
        workspace=test_ws,
    )
    assert any("operation_mismatch" in f for f in cap.evaluate_request(req_bad_op, test_ws).failed_constraints)

    # Dimension 3: Resource mismatch
    req_bad_res = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="secrets/api.key",
        parameters={"toolchain": "python3", "approved": True},
        workspace=test_ws,
    )
    assert any("resource_mismatch" in f for f in cap.evaluate_request(req_bad_res, test_ws).failed_constraints)

    # Dimension 4: Workspace escape
    req_ws_esc = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="../../outside.py",
        parameters={"toolchain": "python3", "approved": True},
        workspace=test_ws,
    )
    assert any("workspace_escape" in f or "resource_mismatch" in f for f in cap.evaluate_request(req_ws_esc, test_ws).failed_constraints)

    # Dimension 5: Arguments mismatch / missing
    req_bad_args = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="src/main.py",
        parameters={"toolchain": "node", "approved": True},
        workspace=test_ws,
    )
    assert any("argument_constraint" in f for f in cap.evaluate_request(req_bad_args, test_ws).failed_constraints)

    # Dimension 6: Filesystem write escalation
    req_fs_write = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="write_file",
        target="src/main.py",
        parameters={"toolchain": "python3", "approved": True, "mode": "write"},
        workspace=test_ws,
    )
    assert any("filesystem_violation" in f for f in cap.evaluate_request(req_fs_write, test_ws).failed_constraints)

    # Dimension 7: Network escalation
    req_net = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="src/main.py",
        parameters={"toolchain": "python3", "approved": True, "network": True},
        workspace=test_ws,
    )
    assert any("network_violation" in f for f in cap.evaluate_request(req_net, test_ws).failed_constraints)

    # Dimension 8: Credential escalation
    req_cred_esc = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="src/main.py",
        parameters={"toolchain": "python3", "approved": True, "credentials": ["PROD_AWS_KEY"]},
        workspace=test_ws,
    )
    assert any("credential_violation" in f for f in cap.evaluate_request(req_cred_esc, test_ws).failed_constraints)

    # Dimension 9: Duration exceeded
    req_dur_esc = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="src/main.py",
        parameters={"toolchain": "python3", "approved": True, "timeout": 120.0},
        workspace=test_ws,
    )
    assert any("duration_exceeded" in f for f in cap.evaluate_request(req_dur_esc, test_ws).failed_constraints)

    # Dimension 10: Risk tier exceeded
    req_risk_esc = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="src/main.py",
        parameters={"toolchain": "python3", "approved": True, "risk": "critical"},
        workspace=test_ws,
    )
    assert any("risk_tier_exceeded" in f for f in cap.evaluate_request(req_risk_esc, test_ws).failed_constraints)

    # Dimension 11: Approval missing
    req_no_appr = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="src/main.py",
        parameters={"toolchain": "python3", "approved": False},
        workspace=test_ws,
    )
    dec_no_appr = cap.evaluate_request(req_no_appr, test_ws)
    assert dec_no_appr.allowed is False
    assert dec_no_appr.requires_approval is True
    assert any("approval_required" in f for f in dec_no_appr.failed_constraints)


# ==============================================================================
# 8. B.1.2 ADVERSARIAL TRUST-BOUNDARY AND PROVENANCE TESTS
# ==============================================================================

def test_fake_caller_authorization_decision_blocked(test_ws):
    """
    Adversarial Attack: Caller manufactures a dummy object with is_allowed=True.
    Invariant: Agent/caller cannot manufacture authorization evidence.
    ObservationConvergence must reject the fake decision and raise SecurityViolationError.
    """
    from sclass.observation.convergence import ObservationConvergence
    from sclass.core.errors import SecurityViolationError

    class FakeDecision:
        is_allowed = True
        outcome = "allow"
        policy_id = "FORGED-POLICY"
        reason = "I authorized myself"

    req = ActionRequest(
        actor="untrusted_agent",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo 'pwned'",
        workspace=test_ws,
    )

    with pytest.raises(SecurityViolationError) as exc_info:
        ObservationConvergence.execute_and_observe(
            request=req,
            authorization=FakeDecision(),
            command="echo 'pwned'",
        )

    assert "unauthentic" in str(exc_info.value).lower() or "not bound" in str(exc_info.value).lower()


def test_authorization_bound_to_request_hash(test_ws):
    """
    Adversarial Attack: Decision minted for Request A is transplanted to execute Request B.
    Invariant: Authorization must be cryptographically bound to canonical request hash.
    ObservationConvergence must detect the hash mismatch and raise SecurityViolationError.
    """
    from sclass.observation.convergence import ObservationConvergence
    from sclass.policy.authorization_service import AuthorizationService
    from sclass.core.errors import SecurityViolationError

    service = AuthorizationService()

    req_a = ActionRequest(
        actor="dev",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo 'harmless'",
        workspace=test_ws,
    )
    decision_a = service.authorize(req_a, workspace_dir=test_ws)
    assert decision_a.is_allowed is True

    # Hostile Request B attempting to reuse Decision A
    req_b = ActionRequest(
        actor="dev",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="rm -rf /",
        workspace=test_ws,
    )

    with pytest.raises(SecurityViolationError) as exc_info:
        ObservationConvergence.execute_and_observe(
            request=req_b,
            authorization=decision_a,
            command="rm -rf /",
        )

    assert "mismatch" in str(exc_info.value).lower() or "not bound" in str(exc_info.value).lower()


def test_tampered_authorization_decision_blocked(test_ws):
    """
    Adversarial Attack: Caller takes a DENY decision and tampers with outcome to ALLOW.
    Invariant: HMAC integrity token verification must fail on tampered decision.
    """
    from sclass.observation.convergence import ObservationConvergence
    from sclass.policy.authorization_service import AuthorizationService
    from sclass.domain.action import DecisionOutcome
    from sclass.core.errors import SecurityViolationError

    service = AuthorizationService()

    req = ActionRequest(
        actor="dev",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="secrets/api.key",
        workspace=test_ws,
    )
    # Mint legitimate decision with authoritative capability
    cap = service.capability_registry.resolve(req, workspace_dir=test_ws)
    sealed = service.seal_decision(
        request=req,
        outcome=DecisionOutcome.DENY,
        policy_id="SEC-DENY",
        risk_level="critical",
        reason="Target is secret",
        capability=cap,
    )

    # Attacker tampers with decision outcome
    tampered = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id=sealed.policy_id,
        risk_level=sealed.risk_level,
        reason=sealed.reason,
        evaluated_at=sealed.evaluated_at,
        issuer=sealed.issuer,
        request_hash=sealed.request_hash,
        capability_hash=sealed.capability_hash,
        policy_version=sealed.policy_version,
        integrity_token=sealed.integrity_token,  # Old token for DENY!
    )

    with pytest.raises(SecurityViolationError) as exc_info:
        ObservationConvergence.execute_and_observe(
            request=req,
            authorization=tampered,
            command="cat secrets/api.key",
        )

    assert "tamper" in str(exc_info.value).lower() or "forged" in str(exc_info.value).lower()


def test_sandbox_backend_fallback_to_host_strictly_refused(monkeypatch, test_ws):
    """
    Invariant: NO SANDBOX -> NO SANDBOXED EXECUTION.
    Even with fallback_to_host=True passed to SandboxBackend, missing sandbox MUST fail closed.
    """
    from sclass.execution.backend import SandboxBackend
    from sclass.core.errors import SecurityViolationError

    # Force bwrap to be unavailable
    monkeypatch.setattr("shutil.which", lambda prog: None)

    backend = SandboxBackend(backend_type="bubblewrap", fallback_to_host=True)
    assert backend.is_available() is False

    with pytest.raises(SecurityViolationError) as exc_info:
        backend.execute(
            command=["echo", "uncontained"],
            cwd=test_ws,
        )

    assert "no sandbox -> no sandboxed execution" in str(exc_info.value).lower()


def test_direct_bubblewrap_wrap_command_fails_closed(monkeypatch):
    """
    Invariant: Lower primitive BubblewrapSandbox.wrap_command() must fail closed
    and raise SecurityViolationError when unavailable, never return raw uncontained command.
    """
    from sclass.execution.sandbox import BubblewrapSandbox
    from sclass.core.errors import SecurityViolationError

    monkeypatch.setattr("shutil.which", lambda prog: None)
    bwrap = BubblewrapSandbox()
    assert bwrap.is_available() is False

    with pytest.raises(SecurityViolationError) as exc_info:
        bwrap.wrap_command(["rm", "-rf", "/tmp/test"], cwd="/tmp")

    assert "no sandbox -> no sandboxed execution" in str(exc_info.value).lower()


def test_direct_container_wrap_command_fails_closed(monkeypatch):
    """
    Invariant: ContainerSandbox.wrap_command() must fail closed when docker/podman is missing.
    """
    from sclass.execution.sandbox import ContainerSandbox
    from sclass.core.errors import SecurityViolationError

    monkeypatch.setattr("shutil.which", lambda prog: None)
    cs = ContainerSandbox()
    assert cs.is_available() is False

    with pytest.raises(SecurityViolationError) as exc_info:
        cs.wrap_command(["echo", "hello"], cwd="/tmp")

    assert "no sandbox -> no sandboxed execution" in str(exc_info.value).lower()


def test_container_wrap_command_authoritatively_applies_network_none(monkeypatch):
    """
    Invariant: ContainerSandbox must authoritatively respect SandboxConfig.network_mode='none'
    and never hardcode '--network host'.
    """
    from sclass.execution.sandbox import ContainerSandbox
    from sclass.execution.backend import SandboxConfig

    monkeypatch.setattr("shutil.which", lambda prog: "/usr/bin/docker" if prog == "docker" else None)
    cs = ContainerSandbox()
    assert cs.is_available() is True

    cfg = SandboxConfig(
        backend_type="container",
        network_mode="none",
        resource_limits={"max_memory_mb": 512},
    )

    args = cs.wrap_command(["pytest"], cwd="/tmp", config=cfg)
    assert "--network" in args
    net_idx = args.index("--network")
    assert args[net_idx + 1] == "none"
    assert "host" not in args
    assert "--memory" in args
    assert "512m" in args


def test_fake_is_observed_evidence_without_provenance_rejected(test_ws):
    """
    Invariant: NO AUTHENTIC EVIDENCE -> NO ACCEPTANCE.
    A forged evidence object claiming is_observed=True without authentic S-Class provenance
    must be demoted to REJECT.
    """
    from sclass.verification.plan import VerificationPlan
    from sclass.domain.claim import Claim

    plan = VerificationPlan(
        plan_id="plan_auth_test",
        target_claims=[Claim(claim_id="clm_fake", task_id="t_auth", statement="All tests pass", claim_type="test_pass")],
        required_evidence_kinds=["test"],
    )

    # Forged object with is_fake flag or unverified hash
    fake_ev = {
        "evidence_kind": "test",
        "source": "pytest",
        "is_observed": True,
        "is_fake": True,
        "passed_count": 10,
    }

    results = plan.coordinate(evidence_items=[fake_ev], workspace_dir=test_ws)
    assert results["clm_fake"].status == "REJECT"
    assert "unauthentic" in results["clm_fake"].reason.lower() or "independently observed" in results["clm_fake"].reason.lower()




def test_fake_approval_token_denied(test_ws):
    """
    Invariant: Presence of an arbitrary approval_token string is not proof of approval.
    Unverified or forged tokens must fail closed with unverified_approval.
    """
    cap = Capability(
        operation=CAP_TERMINAL_EXECUTE,
        approval=True,
    )
    req = ActionRequest(
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="deploy.sh",
        parameters={"approval_token": "arbitrary_fake_token_12345"},
        workspace=test_ws,
    )

    dec = cap.evaluate_request(req, test_ws)
    assert dec.allowed is False
    assert any("unverified_approval" in f for f in dec.failed_constraints)


def test_malformed_risk_fails_closed(test_ws):
    """
    Invariant: UNKNOWN SECURITY METADATA -> DENY.
    Malformed or unrecognized risk levels must fail closed, never default to low risk.
    """
    cap = Capability(
        operation=CAP_TERMINAL_EXECUTE,
        risk="medium",
    )
    req = ActionRequest(
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="test.sh",
        parameters={"risk": "ultra_mega_critical_unknown"},
        workspace=test_ws,
    )

    dec = cap.evaluate_request(req, test_ws)
    assert dec.allowed is False
    assert any("malformed_risk" in f for f in dec.failed_constraints)


def test_malformed_duration_fails_closed(test_ws):
    """
    Invariant: Malformed duration/timeout must fail closed, never silently ignored.
    """
    cap = Capability(
        operation=CAP_TERMINAL_EXECUTE,
        duration=30.0,
    )
    req = ActionRequest(
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="test.sh",
        parameters={"timeout": "not-a-number-duration"},
        workspace=test_ws,
    )

    dec = cap.evaluate_request(req, test_ws)
    assert dec.allowed is False
    assert any("malformed_duration" in f for f in dec.failed_constraints)


def test_credential_target_mismatch_fails_closed(test_ws):
    """
    Invariant: Accessing credentialed target with unauthorized/mismatched credentials must fail closed.
    """
    cap = Capability(
        operation=CAP_SECRET_READ,
        credentials=["DEV_CREDENTIAL"],
    )
    req = ActionRequest(
        capability=CAP_SECRET_READ,
        action="read_file",
        target=".env",
        parameters={"credentials": ["PROD_AWS_SECRET_KEY"]},
        workspace=test_ws,
    )

    dec = cap.evaluate_request(req, test_ws)
    assert dec.allowed is False
    assert any("credential_violation" in f for f in dec.failed_constraints)


def test_exact_verifier_identity_no_substring_spoof(test_ws):
    """
    Invariant: Verifier identity must be canonical and exact.
    Substring matching is strictly forbidden: 'test' must not satisfy required verifier 'pytest'.
    """
    from sclass.verification.plan import VerificationPlan
    from sclass.domain.claim import Claim

    plan = VerificationPlan(
        plan_id="plan_verifier_exact",
        target_claims=[Claim(claim_id="c_test", task_id="t_verifier", statement="Tests passed", claim_type="test_pass")],
        required_evidence_kinds=["test"],
        verifier_ids=["pytest"],
    )

    # Provider is 'test', which contains in 'pytest', but is NOT an exact match
    ev_substring_spoof = TestEvidence(
        source="test",
        is_observed=True,
        passed_count=5,
        failed_count=0,
    )

    results = plan.coordinate(evidence_items=[ev_substring_spoof], workspace_dir=test_ws)
    # Since required verifier 'pytest' was not satisfied by 'test', verdict must be INCONCLUSIVE
    assert results["c_test"].status == "INCONCLUSIVE"
    assert "missing: ['pytest']" in results["c_test"].reason


# ==============================================================================
# 9. B.1.3 ADVERSARIAL SECRET, CAPABILITY RESOLUTION & ENVIRONMENT CLOSURE TESTS
# ==============================================================================

def test_no_valid_auth_secret_fails_closed_in_strict_mode(monkeypatch):
    """
    Invariant: NO VALID AUTH SECRET -> NO EXECUTION.
    In strict security mode (SCLASS_STRICT_SECURITY=1), missing SCLASS_AUTH_SECRET
    must fail closed and raise SecurityViolationError, never use built-in secret.
    """
    from sclass.policy.authorization_service import get_authorization_secret
    from sclass.core.errors import SecurityViolationError

    monkeypatch.setenv("SCLASS_STRICT_SECURITY", "1")
    monkeypatch.delenv("SCLASS_AUTH_SECRET", raising=False)

    with pytest.raises(SecurityViolationError) as exc_info:
        get_authorization_secret()

    assert "no valid auth secret -> no execution" in str(exc_info.value).lower()


def test_no_hardcoded_fallback_secret_in_codebase():
    """
    Certifies that no hardcoded fallback secret string exists anywhere in policy codebase.
    """
    policy_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.normpath(os.path.join(policy_dir, "..", "..", "src", "sclass"))

    forbidden_patterns = [
        "sclass-internal-authoritative-auth-token-secret-v1",
        "default_secret_key",
        "hardcoded_auth_secret",
    ]

    for root, _, files in os.walk(src_dir):
        for fname in files:
            if fname.endswith(".py"):
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    file_content = f.read()
                for pat in forbidden_patterns:
                    assert pat not in file_content, f"Forbidden hardcoded secret pattern '{pat}' found in {fpath}"


def test_no_authoritative_capability_no_execution(test_ws):
    """
    Invariant: NO AUTHORITATIVE CAPABILITY -> NO EXECUTION.
    If no capability is registered or matches the ActionRequest,
    authorization strictly returns DENY and execution raises SecurityViolationError.
    """
    from sclass.policy.capability_resolver import CapabilityRegistry
    from sclass.policy.authorization_service import AuthorizationService
    from sclass.observation.convergence import ObservationConvergence
    from sclass.core.errors import SecurityViolationError

    # Empty registry with no matching capability
    empty_registry = CapabilityRegistry(load_defaults=False)
    service = AuthorizationService(capability_registry=empty_registry)

    req = ActionRequest(
        actor="unregistered_agent",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo 'unauthorized'",
        workspace=test_ws,
    )

    # 1. Authorize fails closed with NO-CAPABILITY
    dec = service.authorize(req, workspace_dir=test_ws)
    assert dec.is_allowed is False
    assert dec.outcome == DecisionOutcome.DENY
    assert dec.policy_id == "NO-CAPABILITY"
    assert "NO AUTHORITATIVE CAPABILITY -> NO EXECUTION" in dec.reason

    # 2. Execution choke point raises SecurityViolationError
    with pytest.raises(SecurityViolationError) as exc_info:
        ObservationConvergence.execute_and_observe(
            request=req,
            command="echo 'unauthorized'",
            backend=HostProcessBackend(),
            capability=None,
            capability_registry=empty_registry,
        )
    assert "no authoritative capability -> no execution" in str(exc_info.value).lower()


def test_decision_capability_hash_tamper_rejected(test_ws):
    """
    Adversarial Attack: Decision minted for Capability A (low risk read)
    is presented to execute under Capability B (high risk execute).
    Invariant: Cryptographic capability hash binding must reject transplanted decisions.
    """
    from sclass.policy.authorization_service import AuthorizationService, verify_decision_integrity

    service = AuthorizationService()

    cap_a = Capability(
        actor="agent-claude",
        operation=CAP_FILESYSTEM_READ,
        resource="src/**",
        scope="workspace",
        workspace=test_ws,
    )
    cap_b = Capability(
        actor="agent-claude",
        operation=CAP_TERMINAL_EXECUTE,
        resource="src/**",
        scope="workspace",
        workspace=test_ws,
    )

    req = ActionRequest(
        actor="agent-claude",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="src/main.py",
        workspace=test_ws,
    )

    # Register legitimate Cap A in authoritative registry
    service.capability_registry.register(cap_a)

    # Mint legitimate decision for Cap A
    decision = service.authorize(req, capability=cap_a, workspace_dir=test_ws)
    assert decision.is_allowed is True

    # Attacker tries to verify decision under Cap B
    valid, reason = verify_decision_integrity(decision, req, capability=cap_b)
    assert valid is False
    assert "capability hash mismatch" in reason.lower()


def test_decision_outdated_policy_version_rejected(test_ws):
    """
    Invariant: DECISION BOUND TO CURRENT POLICY VERSION.
    Decisions issued under outdated policy version must fail freshness verification.
    """
    from sclass.policy.authorization_service import AuthorizationService, verify_decision_integrity

    service_v1 = AuthorizationService(policy_version="1.0.0")
    req = ActionRequest(
        actor="dev",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="pytest",
        workspace=test_ws,
    )

    decision_v1 = service_v1.authorize(req, workspace_dir=test_ws)
    assert decision_v1.is_allowed is True

    # Policy updates to 1.0.1
    valid, reason = verify_decision_integrity(decision_v1, req, expected_policy_version="1.0.1")
    assert valid is False
    assert "policy version mismatch" in reason.lower()


def test_approval_token_base64_iso_timestamp_and_expiration(test_ws):
    """
    Certifies that approval token encoding:
    1. Parses cleanly with ISO timestamps containing colons (:).
    2. Enforces cryptographic HMAC signature.
    3. Fails closed when expired.
    4. Rejects forged or tampered tokens.
    """
    import time
    from sclass.policy.authorization_service import AuthorizationService

    service = AuthorizationService()
    req = ActionRequest(
        actor="dev",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="deploy.sh",
        workspace=test_ws,
    )

    # Mint approval token with 1 second TTL
    token = service.mint_approval_token(req, approver="security_officer", ttl_seconds=1.0)
    assert "." in token
    assert service.verify_approval_token(token, req) is True

    # Tampered token fails
    tampered_token = token[:-4] + "dead"
    assert service.verify_approval_token(tampered_token, req) is False

    # Token for different request fails
    req_other = ActionRequest(
        actor="dev",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="malicious.sh",
        workspace=test_ws,
    )
    assert service.verify_approval_token(token, req_other) is False

    # Expired token fails
    time.sleep(1.1)
    assert service.verify_approval_token(token, req) is False


def test_sandbox_environment_isolation_strips_parent_secrets(monkeypatch, test_ws):
    """
    Invariant: SANDBOX ENVIRONMENT ISOLATION.
    Parent process environment variables (such as API keys or secret credentials)
    must NEVER leak into sandboxed child execution.
    """
    from sclass.execution.backend import SandboxConfigCompiler
    from sclass.execution.process import ProcessRunner
    from sclass.execution.sandbox import HostSandbox

    monkeypatch.setenv("SCLASS_TEST_PARENT_SECRET", "super_secret_classified_key_12345")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "AKIAIOSFODNN7SECRET")

    req = ActionRequest(
        actor="agent",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo hello",
        workspace=test_ws,
    )

    # Compile sandbox configuration
    cfg = SandboxConfigCompiler.compile(request=req, workspace_dir=test_ws)

    # 1. Config environment whitelist must NOT contain parent secrets
    assert "SCLASS_TEST_PARENT_SECRET" not in cfg.env_whitelist
    assert "AWS_SECRET_ACCESS_KEY" not in cfg.env_whitelist

    # 2. ProcessRunner executed with config must use whitelist-only env
    runner = ProcessRunner(sandbox=HostSandbox())
    res = runner.run(["python", "-c", "import os; print('SECRET_FOUND=' + str('SCLASS_TEST_PARENT_SECRET' in os.environ))"], cwd=test_ws, config=cfg)
    assert res.exit_code == 0
    assert "SECRET_FOUND=False" in res.stdout


def test_get_sandbox_backend_fails_closed_without_fallback():
    """
    Invariant: get_sandbox_backend() must NOT expose an allow_fallback option that degrades to HostSandbox.
    Unknown or unsupported backends must raise SecurityViolationError.
    """
    import inspect
    from sclass.execution.sandbox import get_sandbox_backend, BubblewrapSandbox, HostSandbox
    from sclass.core.errors import SecurityViolationError

    sig = inspect.signature(get_sandbox_backend)
    assert "allow_fallback" not in sig.parameters

    # Explicit host returns HostSandbox
    assert isinstance(get_sandbox_backend("host"), HostSandbox)

    # Bubblewrap returns BubblewrapSandbox
    assert isinstance(get_sandbox_backend("bubblewrap"), BubblewrapSandbox)

    # Unknown backend strictly raises SecurityViolationError
    with pytest.raises(SecurityViolationError) as exc_info:
        get_sandbox_backend("unknown_cloud_hypervisor")
    assert "unknown backend -> no execution" in str(exc_info.value).lower()


# ==============================================================================
# B.1.4 — Authoritative Capability Boundary Certification Tests
# Invariant: NO CALLER-SUPPLIED CAPABILITY MAY BECOME AUTHORITY
# ==============================================================================

def test_forged_permissive_capability_cannot_authorize_execution(test_ws):
    """
    Invariant: NO CALLER-SUPPLIED CAPABILITY MAY BECOME AUTHORITY.
    Attacker crafts an arbitrary permissive Capability and passes it to execution APIs.
    System must ignore/reject caller-supplied capability and strictly deny execution.
    """
    from sclass.policy.capability_resolver import CapabilityRegistry
    from sclass.policy.authorization_service import AuthorizationService
    from sclass.domain.action import DecisionOutcome

    # Clean registry with zero capabilities
    empty_registry = CapabilityRegistry(load_defaults=False)
    auth_service = AuthorizationService(capability_registry=empty_registry)

    req = ActionRequest(
        actor="untrusted-agent",
        capability=CAP_FILESYSTEM_WRITE,
        action="write_file",
        target="src/backdoor.py",
        workspace=test_ws,
    )

    forged_cap = Capability(
        id="forged-root-superadmin",
        actor="*",
        operation="*",
        resource="**",
        scope="workspace",
        risk="critical",
        duration=999999.0,
        network=True,
        filesystem="read_write",
        credentials=["*"],
        version="99.9.9",
    )

    # 1. Attacker attempts to pass forged capability to execute_and_observe
    with pytest.raises(SecurityViolationError) as exc_info:
        ObservationConvergence.execute_and_observe(
            request=req,
            capability=forged_cap,
            auth_service=auth_service,
        )
    err_msg = str(exc_info.value)
    assert (
        "NO AUTHORITATIVE CAPABILITY -> NO EXECUTION" in err_msg
        or "NO CALLER-SUPPLIED CAPABILITY MAY BECOME AUTHORITY" in err_msg
    )

    # 2. Attacker attempts to pass forged capability directly to authorize()
    decision = auth_service.authorize(req, capability=forged_cap, workspace_dir=test_ws)
    assert decision.is_allowed is False
    assert decision.outcome == DecisionOutcome.DENY
    assert decision.policy_id in ("FORGED-CAPABILITY", "NO-CAPABILITY")


def test_caller_supplied_overprivileged_capability_denied(test_ws):
    """
    Invariant: Caller cannot elevate permissions by supplying an over-privileged capability.
    Registry authorizes only read operations. Caller supplies write capability.
    Must fail closed.
    """
    from sclass.policy.capability_resolver import CapabilityRegistry
    from sclass.policy.authorization_service import AuthorizationService
    from sclass.domain.action import DecisionOutcome

    registry = CapabilityRegistry(load_defaults=False)
    read_cap = Capability(
        id="cap:read-only",
        version="1.0.0",
        actor="dev-agent",
        operation=CAP_FILESYSTEM_READ,
        resource="src/**",
        scope="workspace",
        risk="low",
        filesystem="read",
    )
    registry.register(read_cap)
    auth_service = AuthorizationService(capability_registry=registry)

    req = ActionRequest(
        actor="dev-agent",
        capability=CAP_FILESYSTEM_WRITE,
        action="write_file",
        target="src/protected.py",
        workspace=test_ws,
    )

    overprivileged_cap = Capability(
        id="cap:write-privileged",
        version="1.0.0",
        actor="dev-agent",
        operation=CAP_FILESYSTEM_WRITE,
        resource="**",
        scope="workspace",
        risk="critical",
        filesystem="read_write",
    )

    # Attempting to authorize with external over-privileged capability fails
    decision = auth_service.authorize(req, capability=overprivileged_cap, workspace_dir=test_ws)
    assert decision.is_allowed is False
    assert decision.outcome == DecisionOutcome.DENY

    # Attempting to execute with external over-privileged capability fails closed
    with pytest.raises(SecurityViolationError):
        ObservationConvergence.execute_and_observe(
            request=req,
            capability=overprivileged_cap,
            auth_service=auth_service,
        )


def test_capability_swapped_after_authorization_rejected(test_ws):
    """
    Invariant: Capability identity and version bound to decision cannot be swapped post-authorization.
    Decision authorized for read operation cannot be presented for execution of another request.
    """
    from sclass.policy.capability_resolver import CapabilityRegistry
    from sclass.policy.authorization_service import AuthorizationService

    registry = CapabilityRegistry(load_defaults=False)
    cap_read = Capability(
        id="cap:read",
        version="1.0.0",
        actor="agent-claude",
        operation=CAP_FILESYSTEM_READ,
        resource="src/**",
        scope="workspace",
        risk="low",
        filesystem="read",
    )
    cap_exec = Capability(
        id="cap:exec",
        version="1.0.0",
        actor="agent-claude",
        operation=CAP_TERMINAL_EXECUTE,
        resource="**",
        scope="workspace",
        risk="medium",
        filesystem="read_write",
    )
    registry.register(cap_read)
    registry.register(cap_exec)
    auth_service = AuthorizationService(capability_registry=registry)

    req_read = ActionRequest(
        actor="agent-claude",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="src/main.py",
        workspace=test_ws,
    )
    decision = auth_service.authorize(req_read, workspace_dir=test_ws)
    assert decision.is_allowed is True
    assert decision.capability_id == "cap:read"

    # Attacker attempts to use the decision to execute a terminal command
    req_exec = ActionRequest(
        actor="agent-claude",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="python -c 'print(1)'",
        workspace=test_ws,
    )
    with pytest.raises(SecurityViolationError) as exc_info:
        ObservationConvergence.execute_and_observe(
            request=req_exec,
            authorization=decision,
            auth_service=auth_service,
        )
    assert "request hash mismatch" in str(exc_info.value).lower() or "capability hash mismatch" in str(exc_info.value).lower()


def test_registry_capability_mutation_invalidates_prior_authorization(test_ws):
    """
    Invariant: REGISTRY CAPABILITY MUTATION INVALIDATES PRIOR AUTHORIZATION.
    A decision authorized under capability v1.0.0 is invalidated if the registry
    capability is mutated (version bump, restriction, or replacement).
    """
    from sclass.policy.capability_resolver import CapabilityRegistry
    from sclass.policy.authorization_service import AuthorizationService

    registry = CapabilityRegistry(load_defaults=False)
    cap_v1 = Capability(
        id="cap:runner",
        version="1.0.0",
        actor="agent-worker",
        operation=CAP_TERMINAL_EXECUTE,
        resource="**",
        scope="workspace",
        risk="medium",
        filesystem="read_write",
    )
    registry.register(cap_v1)
    auth_service = AuthorizationService(capability_registry=registry)

    req = ActionRequest(
        actor="agent-worker",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="python -c \"print('mutated')\"",
        workspace=test_ws,
    )

    # 1. Authorize under v1.0.0
    decision_v1 = auth_service.authorize(req, workspace_dir=test_ws)
    assert decision_v1.is_allowed is True
    assert decision_v1.capability_version == "1.0.0"

    # 2. Mutate registry capability (e.g. security team bumps capability version to 1.0.1 and tightens scope)
    cap_v2 = Capability(
        id="cap:runner",
        version="1.0.1",
        actor="agent-worker",
        operation=CAP_TERMINAL_EXECUTE,
        resource="**",
        scope="workspace",
        risk="high",
        filesystem="read_write",
    )
    replaced = registry.replace("cap:runner", cap_v2)
    assert replaced is True
    assert registry.generation > 1

    # 3. Presenting the old decision_v1 for execution MUST FAIL CLOSED
    with pytest.raises(SecurityViolationError) as exc_info:
        ObservationConvergence.execute_and_observe(
            request=req,
            authorization=decision_v1,
            auth_service=auth_service,
        )
    err_msg = str(exc_info.value).lower()
    assert "capability hash mismatch" in err_msg or "capability version mismatch" in err_msg


def test_stale_capability_identity_rejected(test_ws):
    """
    Invariant: STALE CAPABILITY IDENTITY REJECTED.
    A decision authorized under a capability that has since been revoked/unregistered
    from the authoritative registry cannot be used for execution.
    """
    from sclass.policy.capability_resolver import CapabilityRegistry
    from sclass.policy.authorization_service import AuthorizationService

    registry = CapabilityRegistry(load_defaults=False)
    ephemeral_cap = Capability(
        id="cap:ephemeral:revoke-me",
        version="1.0.0",
        actor="agent-worker",
        operation=CAP_TERMINAL_EXECUTE,
        resource="**",
        scope="workspace",
        risk="medium",
        filesystem="read_write",
    )
    registry.register(ephemeral_cap)
    auth_service = AuthorizationService(capability_registry=registry)

    req = ActionRequest(
        actor="agent-worker",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="python -c \"print('revoked')\"",
        workspace=test_ws,
    )

    # Authorize decision while capability exists
    decision = auth_service.authorize(req, workspace_dir=test_ws)
    assert decision.is_allowed is True

    # Revoke capability from authoritative registry
    unregistered = registry.unregister("cap:ephemeral:revoke-me")
    assert unregistered is True

    # Attempt execution with prior decision now fails closed
    with pytest.raises(SecurityViolationError) as exc_info:
        ObservationConvergence.execute_and_observe(
            request=req,
            authorization=decision,
            auth_service=auth_service,
        )
    assert "no authoritative capability -> no execution" in str(exc_info.value).lower()

