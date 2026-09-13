"""
S-Class Certification: Handoff B.1 Security-Grade Action Plane Adversarial Test Suite.
Verifies multidimensional capability constraints, elimination of resource scoping bypasses,
fail-closed sandbox containment, gVisor protection, observation authorization gating,
verification plan evidence completeness, and OPA adapter integration.
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
# 1. CAPABILITY MULTIDIMENSIONAL SECURITY & BYPASS TESTS
# ==============================================================================

def test_resource_scoping_bypass_eliminated(test_ws):
    """
    Certifies that scoping a capability to 'src/**' strictly forbids access
    to other workspace paths (e.g. secrets/api.key), preventing the wildcard bypass.
    """
    cap = Capability(
        actor="agent-claude",
        operation=CAP_FILESYSTEM_READ,
        resource="src/**",
        scope="workspace",
        workspace=test_ws,
    )

    # Legitimate access inside src/**
    req_valid = ActionRequest(
        actor="agent-claude",
        session="s1",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="src/main.py",
        workspace=test_ws,
    )
    assert cap.allows_request(req_valid, test_ws) is True

    # Hostile access targeting secrets/api.key inside workspace
    req_hostile = ActionRequest(
        actor="agent-claude",
        session="s2",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="secrets/api.key",
        workspace=test_ws,
    )
    decision = cap.evaluate_request(req_hostile, test_ws)
    assert decision.allowed is False
    assert any("resource_mismatch" in c for c in decision.failed_constraints)
    assert cap.allows_request(req_hostile, test_ws) is False


def test_path_escape_directory_traversal(test_ws):
    """Certifies that ../ directory traversal past workspace root is strictly blocked."""
    cap = Capability(
        actor="agent-codex",
        operation=CAP_FILESYSTEM_READ,
        resource="*",
        scope="workspace",
        workspace=test_ws,
    )

    req_escape = ActionRequest(
        actor="agent-codex",
        session="s_esc",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="../../etc/shadow",
        workspace=test_ws,
    )
    decision = cap.evaluate_request(req_escape, test_ws)
    assert decision.allowed is False
    assert any("workspace_escape" in c or "resource_mismatch" in c for c in decision.failed_constraints)


def test_network_escalation_enforcement(test_ws):
    """Certifies that a capability with network=False strictly rejects network actions."""
    cap = Capability(
        actor="agent-codex",
        operation="*",
        network=False,
        workspace=test_ws,
    )

    req_net = ActionRequest(
        actor="agent-codex",
        session="s_net",
        capability=CAP_NETWORK_REQUEST,
        action="fetch",
        target="https://api.external.com/exfiltrate",
        parameters={"network": True},
        workspace=test_ws,
    )
    decision = cap.evaluate_request(req_net, test_ws)
    assert decision.allowed is False
    assert any("network_violation" in c for c in decision.failed_constraints)


def test_credential_escalation_enforcement(test_ws):
    """Certifies that targeting credentials not in the capability whitelist is rejected."""
    cap = Capability(
        actor="agent-cursor",
        operation=CAP_SECRET_READ,
        credentials=["PUBLIC_TEST_TOKEN"],
        workspace=test_ws,
    )

    req_cred = ActionRequest(
        actor="agent-cursor",
        session="s_cred",
        capability=CAP_SECRET_READ,
        action="get_secret",
        target="AWS_SECRET_ACCESS_KEY",
        parameters={"credentials": ["AWS_SECRET_ACCESS_KEY"]},
        workspace=test_ws,
    )
    decision = cap.evaluate_request(req_cred, test_ws)
    assert decision.allowed is False
    assert any("credential_violation" in c for c in decision.failed_constraints)


def test_filesystem_write_escalation_enforcement(test_ws):
    """Certifies that a read-only filesystem capability rejects write/modify operations."""
    cap = Capability(
        actor="agent-claude",
        operation="*",
        filesystem="read",
        workspace=test_ws,
    )

    req_write = ActionRequest(
        actor="agent-claude",
        session="s_write",
        capability=CAP_FILESYSTEM_WRITE,
        action="write_file",
        target="src/main.py",
        parameters={"mode": "write", "content": "malicious payload"},
        workspace=test_ws,
    )
    decision = cap.evaluate_request(req_write, test_ws)
    assert decision.allowed is False
    assert any("filesystem_violation" in c for c in decision.failed_constraints)


def test_duration_bypass_enforcement(test_ws):
    """Certifies that operations requesting timeouts exceeding max duration are rejected."""
    cap = Capability(
        actor="agent-opencode",
        operation=CAP_TERMINAL_EXECUTE,
        duration=30.0,
        workspace=test_ws,
    )

    req_duration = ActionRequest(
        actor="agent-opencode",
        session="s_dur",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="python heavy_job.py",
        parameters={"timeout": 300.0},
        workspace=test_ws,
    )
    decision = cap.evaluate_request(req_duration, test_ws)
    assert decision.allowed is False
    assert any("duration_exceeded" in c for c in decision.failed_constraints)


def test_approval_bypass_enforcement(test_ws):
    """Certifies that operations requiring approval are blocked unless explicit token provided."""
    cap = Capability(
        actor="agent-cursor",
        operation=CAP_TERMINAL_EXECUTE,
        approval=True,
        workspace=test_ws,
    )

    req_unapproved = ActionRequest(
        actor="agent-cursor",
        session="s_appr",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="deploy.sh",
        parameters={},
        workspace=test_ws,
    )
    decision = cap.evaluate_request(req_unapproved, test_ws)
    assert decision.allowed is False
    assert decision.requires_approval is True
    assert any("approval_required" in c for c in decision.failed_constraints)

    # With approval token
    req_approved = ActionRequest(
        actor="agent-cursor",
        session="s_appr",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="deploy.sh",
        parameters={"approved": True, "approval_token": "TOK_123"},
        workspace=test_ws,
    )
    assert cap.allows_request(req_approved, test_ws) is True


# ==============================================================================
# 2. SANDBOX FAIL-CLOSED & GVISOR PROTECTION TESTS
# ==============================================================================

def test_sandbox_default_fails_closed_when_unavailable(test_ws):
    """
    Certifies that SandboxBackend defaults to fallback_to_host=False
    and raises SecurityViolationError when sandbox technology is missing.
    """
    # Create SandboxBackend with bubblewrap (on Windows or systems without bwrap)
    sb = SandboxBackend(backend_type="bubblewrap")
    assert sb.fallback_to_host is False

    req = ActionRequest(
        actor="agent-codex",
        session="s_sb",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo test",
        workspace=test_ws,
    )

    # Force is_available to False to test behavior deterministically
    with patch.object(sb, "is_available", return_value=False):
        with pytest.raises(SecurityViolationError) as exc:
            sb.execute(command="echo test", cwd=test_ws, request=req)
        assert "Fail-closed policy denies host fallback" in str(exc.value)


def test_gvisor_never_substitutes_host(test_ws):
    """
    Certifies that requesting gVisor sandbox never substitutes HostLauncher or HostSandbox,
    and fails closed if runsc is absent.
    """
    sb = SandboxBackend(backend_type="gvisor", fallback_to_host=False)
    assert sb.name == "sandbox:gvisor"
    assert isinstance(sb._underlying_sandbox, GVisorSandbox)

    # If runsc is not installed
    with patch("shutil.which", return_value=None):
        gv = GVisorSandbox()
        assert gv.is_available() is False
        with pytest.raises(SecurityViolationError) as exc:
            gv.wrap_command(["echo", "hi"], test_ws)
        assert "Fail-closed policy prevents uncontained execution" in str(exc.value)

        # Execution backend fails closed
        with pytest.raises(SecurityViolationError):
            sb.execute(command="echo hi", cwd=test_ws)


# ==============================================================================
# 3. OBSERVATION CONVERGENCE AUTHORIZATION GATING TESTS
# ==============================================================================

def test_observation_convergence_rejects_unauthorized_action(test_ws):
    """
    Certifies that ObservationConvergence.execute_and_observe enforces
    ActionRequest -> Authorization -> ALLOW before any backend execution.
    """
    ledger = LocalLedger(workspace_dir=test_ws)
    initial_entries = ledger.get_entry_count()

    # Hostile request attempting to destroy root directory
    req_dangerous = ActionRequest(
        actor="agent-malicious",
        session="s_danger",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="rm -rf /",
        parameters={"command": "rm -rf /"},
        workspace=test_ws,
    )

    with pytest.raises(SecurityViolationError) as exc:
        ObservationConvergence.execute_and_observe(
            request=req_dangerous,
            backend=HostProcessBackend(),
            ledger=ledger,
        )
    assert "ActionRequest unauthorized under policy" in str(exc.value)
    # Ensure ledger and execution were not triggered
    assert ledger.get_entry_count() == initial_entries


def test_observation_convergence_with_explicit_denied_decision(test_ws):
    """Certifies that an explicit DENY AuthorizationDecision immediately blocks execution."""
    req = ActionRequest(
        actor="agent-claude",
        session="s_expl",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="pytest",
        workspace=test_ws,
    )

    denied_decision = AuthorizationDecision(
        outcome=DecisionOutcome.DENY,
        policy_id="POLICY-CUSTOM-DENY",
        risk_level="HIGH",
        reason="Administrative lockout",
    )

    with pytest.raises(SecurityViolationError) as exc:
        converge_execution(
            request=req,
            authorization=denied_decision,
        )
    assert "POLICY-CUSTOM-DENY" in str(exc.value)


# ==============================================================================
# 4. VERIFICATION PLAN MULTI-VERIFIER & EVIDENCE ENFORCEMENT TESTS
# ==============================================================================

def test_verification_plan_enforces_required_evidence_kinds(test_ws):
    """
    Certifies that VerificationPlan.coordinate marks claims as INCONCLUSIVE
    if declared required_evidence_kinds are missing.
    """
    claim = Claim(
        claim_id="claim_auth_1",
        task_id="task_auth_1",
        statement="Authentication module is tested and secure",
        claim_type=ClaimType.TEST_PASS.value,
    )

    plan = VerificationPlan(
        plan_id="vplan_strict_1",
        goal="Verify auth completeness",
        target_claims=[claim],
        required_evidence_kinds=["test", "security"],
    )

    # Provide only test evidence, missing security evidence
    t_ev = TestEvidence(
        source="pytest",
        is_observed=True,
        passed_count=10,
        failed_count=0,
        total_count=10,
    )

    results = plan.coordinate(evidence_items=[t_ev], workspace_dir=test_ws)
    verdict = results["claim_auth_1"]
    assert verdict.status == "INCONCLUSIVE"
    assert "missing" in verdict.reason.lower()
    assert "security" in verdict.reason.lower()

    # Now provide both test and security evidence
    s_ev = SecurityEvidence(
        source="semgrep",
        is_observed=True,
        scanner="semgrep",
        findings_count=0,
        passed=True,
    )

    results_complete = plan.coordinate(evidence_items=[t_ev, s_ev], workspace_dir=test_ws)
    verdict_complete = results_complete["claim_auth_1"]
    assert verdict_complete.status == "ACCEPT"


def test_verification_plan_enforces_verifier_ids(test_ws):
    """
    Certifies that VerificationPlan.coordinate marks claims as INCONCLUSIVE
    if declared verifier_ids are not represented among evidence sources.
    """
    claim = Claim(
        claim_id="claim_test_1",
        task_id="task_test_1",
        statement="Code passes tests with security audit",
        claim_type=ClaimType.TEST_PASS.value,
    )

    plan = VerificationPlan(
        plan_id="vplan_verifiers_1",
        target_claims=[claim],
        verifier_ids=["semgrep_audit"],
    )

    t_ev = TestEvidence(source="pytest", is_observed=True, passed_count=5)
    results = plan.coordinate(evidence_items=[t_ev], workspace_dir=test_ws)
    verdict = results["claim_test_1"]
    assert verdict.status == "INCONCLUSIVE"
    assert "semgrep_audit" in verdict.reason


# ==============================================================================
# 5. OPA POLICY ADAPTER TESTS
# ==============================================================================

def test_opa_input_compiler(test_ws):
    """Certifies that OPAInputCompiler compiles canonical structured JSON matching Rego schemas."""
    cap = Capability(
        actor="agent-claude",
        operation=CAP_FILESYSTEM_READ,
        resource="src/**",
        workspace=test_ws,
    )
    req = ActionRequest(
        actor="agent-claude",
        session="s_opa",
        capability=CAP_FILESYSTEM_READ,
        action="read_file",
        target="src/main.py",
        parameters={"encoding": "utf-8"},
        workspace=test_ws,
    )

    opa_doc = OPAInputCompiler.compile(req, workspace_dir=test_ws, capability=cap)
    assert "input" in opa_doc
    inp = opa_doc["input"]
    assert inp["request"]["actor"] == "agent-claude"
    assert inp["request"]["action"] == "read_file"
    assert inp["capability"]["resource"] == "src/**"
    assert inp["workspace"]["target_is_within"] is True


def test_opa_adapter_evaluation_and_fallback(test_ws):
    """Certifies OPAPolicyAdapter evaluates decisions and gracefully falls back."""
    req = ActionRequest(
        actor="agent-codex",
        session="s_opa_fb",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="pytest",
        workspace=test_ws,
    )

    adapter = OPAPolicyAdapter(allow_fallback=True)
    # Port 8181 is not running in test; verifies fallback to DefaultPolicyEngine evaluates cleanly
    decision = adapter.evaluate(req, workspace_dir=test_ws)
    assert isinstance(decision, AuthorizationDecision)
    assert decision.is_allowed is True

    # Test with mock OPAClient returning explicit DENY
    mock_client = MagicMock()
    mock_client.evaluate_raw.return_value = {
        "result": {
            "allow": False,
            "policy_id": "REGO-DISALLOW-EXT",
            "reason": "Explicitly blocked by custom corporate Rego policy",
        }
    }
    adapter_mock = OPAPolicyAdapter(client=mock_client, allow_fallback=False)
    denied = adapter_mock.evaluate(req, workspace_dir=test_ws)
    assert denied.is_allowed is False
    assert denied.outcome == DecisionOutcome.DENY
    assert denied.policy_id == "REGO-DISALLOW-EXT"
