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
