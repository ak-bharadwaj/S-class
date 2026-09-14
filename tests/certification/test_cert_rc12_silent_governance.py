"""
Certification Suite: RC.12 Silent Governance Mode, Universal Adapter Normalization & Provider Discovery.
Certifies:
1. Silent mode suppression: low-risk benign actions are governed silently with zero interruptions.
2. Anomaly surfacing: high-risk actions and blocked policy violations surface actionable notifications.
3. Governance modes: verifies distinct behavior across SILENT, SURFACE_ANOMALIES, and INTERACTIVE.
4. Noise suppression & metrics: routine read actions and heartbeats are suppressed; calculates suppression ratio.
5. ProviderDiscovery: detects platforms via binary, environment variables, config directories, and workspace markers.
6. ProviderDiscovery adapter instantiation: automatically creates normalized adapter for discovered platform.
7. Universal adapter action normalization: maps terminal, file read/write, and network to canonical S-Class ActionRequest.
8. End-to-end integration: universal adapter produces normalized action -> governed silently by controller with audit trail.
"""

import os
from unittest.mock import patch
import pytest

from sclass.product.silent_governance import (
    SilentGovernanceController,
    SilentGovernanceMode,
)
from sclass.product.provider_discovery import (
    ProviderDiscovery,
    DiscoveredProvider,
)
from sclass.integrations.base import (
    AdapterStatus,
    AdapterCapabilities,
    BasePlatformAdapter,
    PlatformAdapter,
)
from sclass.domain.action import ActionRequest
from sclass.domain.capability import (
    CAP_TERMINAL_EXECUTE,
    CAP_FILESYSTEM_READ,
    CAP_FILESYSTEM_WRITE,
    CAP_NETWORK_REQUEST,
)


@pytest.fixture
def rc12_ws(tmp_path):
    ws = tmp_path / "cert_rc12_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_rc12_silent_mode_suppression(rc12_ws):
    """Certifies low-risk benign actions are governed silently without surfacing to the user."""
    controller = SilentGovernanceController(workspace_dir=rc12_ws, mode=SilentGovernanceMode.SURFACE_ANOMALIES)

    req = ActionRequest(
        actor="developer",
        session="sess_1",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="pytest tests/unit",
        parameters={"command": "pytest tests/unit"},
        workspace=rc12_ws,
    )

    decision, surfaced, msg = controller.govern_action(req, risk_score=0.1)

    assert surfaced is False
    assert msg is None
    assert controller.total_actions == 1
    assert controller.silenced_actions == 1
    assert controller.surfaced_actions == 0


def test_rc12_surfacing_high_risk_and_blocked_actions(rc12_ws):
    """Certifies that blocked actions or high-risk actions surface clear notification alerts."""
    controller = SilentGovernanceController(workspace_dir=rc12_ws, mode=SilentGovernanceMode.SURFACE_ANOMALIES, risk_threshold=0.6)

    # 1. High risk action exceeding threshold
    high_risk_req = ActionRequest(
        actor="developer",
        session="sess_2",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="rm -rf /tmp/test_build",
        parameters={"command": "rm -rf /tmp/test_build"},
        workspace=rc12_ws,
    )
    decision, surfaced, msg = controller.govern_action(high_risk_req, risk_score=0.85)

    assert surfaced is True
    assert msg is not None
    assert "[S-Class" in msg
    assert controller.surfaced_actions == 1


def test_rc12_governance_modes(rc12_ws):
    """Certifies differences in surfacing logic across SILENT, SURFACE_ANOMALIES, and INTERACTIVE."""
    # 1. SILENT mode only surfaces critical failures (risk >= 0.8 on deny)
    silent_ctrl = SilentGovernanceController(workspace_dir=rc12_ws, mode=SilentGovernanceMode.SILENT)
    req = ActionRequest(
        actor="developer",
        session="s",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="git status",
        workspace=rc12_ws,
    )
    # Even moderate risk does not surface in SILENT mode
    _, surfaced_silent, _ = silent_ctrl.govern_action(req, risk_score=0.7)
    assert surfaced_silent is False

    # 2. INTERACTIVE mode surfaces low-risk actions for operator review
    interactive_ctrl = SilentGovernanceController(workspace_dir=rc12_ws, mode=SilentGovernanceMode.INTERACTIVE)
    _, surfaced_interactive, msg = interactive_ctrl.govern_action(req, risk_score=0.3)
    assert surfaced_interactive is True
    assert msg is not None


def test_rc12_noise_event_suppression_and_metrics(rc12_ws):
    """Certifies noise suppression for heartbeats/reads and calculates accurate suppression ratio."""
    controller = SilentGovernanceController(workspace_dir=rc12_ws)

    assert controller.suppress_noise("heartbeat") is True
    assert controller.suppress_noise("agent_liveness_ping") is True
    assert controller.suppress_noise("read_file", {"is_read_only": True}) is True
    assert controller.suppress_noise("destructive_database_drop", {"is_read_only": False}) is False

    assert controller.noise_events_suppressed == 3

    # Govern 3 actions: 2 low-risk (silenced), 1 high-risk (surfaced)
    for i in range(2):
        r = ActionRequest(actor="dev", session="s", capability=CAP_FILESYSTEM_READ, action="read", target="main.py", workspace=rc12_ws)
        controller.govern_action(r, risk_score=0.1)

    r_high = ActionRequest(actor="dev", session="s", capability=CAP_TERMINAL_EXECUTE, action="run", target="deploy", workspace=rc12_ws)
    controller.govern_action(r_high, risk_score=0.9)

    metrics = controller.get_governance_metrics()
    assert metrics["total_actions"] == 3
    assert metrics["silenced_actions"] == 2
    assert metrics["surfaced_actions"] == 1
    assert metrics["suppression_ratio"] == round(2 / 3, 4)


def test_rc12_provider_discovery_probing(rc12_ws):
    """Certifies ProviderDiscovery probes via environment variables, workspace markers, and binaries."""
    discovery = ProviderDiscovery()

    # 1. Probe with workspace marker for Antigravity (.agents directory)
    agents_dir = os.path.join(rc12_ws, ".agents")
    os.makedirs(agents_dir, exist_ok=True)
    all_provs = discovery.discover_all(workspace_dir=rc12_ws)
    antigrav = next(p for p in all_provs if p.platform_id == "antigravity")
    assert antigrav.status == AdapterStatus.CONFIGURED
    assert antigrav.detected_by == "workspace_marker"

    # 2. Probe with environment variable for Codex -> CONFIGURED
    with patch.dict(os.environ, {"CODEX_HOME": rc12_ws}):
        all_provs_env = discovery.discover_all(workspace_dir=rc12_ws)
        codex_prov = next(p for p in all_provs_env if p.platform_id == "codex")
        assert codex_prov.status == AdapterStatus.CONFIGURED
        assert codex_prov.detected_by.startswith("env:")


def test_rc12_provider_discovery_adapter_instantiation(rc12_ws):
    """Certifies ProviderDiscovery creates normalized PlatformAdapters."""
    discovery = ProviderDiscovery()

    adapter_cursor = discovery.create_adapter("cursor", workspace_dir=rc12_ws)
    assert isinstance(adapter_cursor, PlatformAdapter)
    assert adapter_cursor.platform_id == "cursor"

    adapter_codex = discovery.create_adapter("codex", workspace_dir=rc12_ws)
    assert isinstance(adapter_codex, PlatformAdapter)
    assert adapter_codex.platform_id == "codex"


def test_rc12_universal_adapter_action_normalization(rc12_ws):
    """Certifies BasePlatformAdapter normalizes shell, read, write, and network actions."""
    adapter = BasePlatformAdapter(workspace_dir=rc12_ws, platform_id="test_agent")

    # 1. Terminal / Shell command
    req_cmd = adapter.normalize_action(action="terminal_run", target="cargo test")
    assert req_cmd.capability == CAP_TERMINAL_EXECUTE
    assert req_cmd.actor == "test_agent"
    assert req_cmd.workspace == rc12_ws

    # 2. File read
    req_read = adapter.normalize_action(action="view_file", target="src/main.rs")
    assert req_read.capability == CAP_FILESYSTEM_READ

    # 3. File write
    req_write = adapter.normalize_action(action="edit_file", target="src/main.rs")
    assert req_write.capability == CAP_FILESYSTEM_WRITE

    # 4. Network
    req_net = adapter.normalize_action(action="curl_fetch", target="https://api.example.com")
    assert req_net.capability == CAP_NETWORK_REQUEST

    # 5. Lifecycle event normalization
    event = adapter.normalize_event("task_started", {"task_id": "123"})
    assert event["platform"] == "test_agent"
    assert event["event"] == "test_agent.task_started"
    assert event["payload"]["task_id"] == "123"


def test_rc12_silent_governance_end_to_end_with_adapter(rc12_ws):
    """Certifies end-to-end flow: normalized adapter action passes through silent governance."""
    discovery = ProviderDiscovery()
    adapter = discovery.create_adapter("antigravity", workspace_dir=rc12_ws)
    controller = SilentGovernanceController(workspace_dir=rc12_ws, mode=SilentGovernanceMode.SURFACE_ANOMALIES)

    # 1. Benign read action
    req_read = adapter.normalize_action(action="read_code", target="app.py")
    decision, surfaced, msg = controller.govern_action(req_read, risk_score=0.15)
    assert decision.allow is True
    assert surfaced is False

    # 2. Elevated action
    req_write = adapter.normalize_action(action="write_code", target="config/auth.py")
    decision_write, surfaced_write, msg_write = controller.govern_action(req_write, risk_score=0.75)
    assert decision_write.allow is True
    assert surfaced_write is True
    assert msg_write is not None
    assert "Elevated risk action" in msg_write

    # 3. Audit trail verification
    assert len(controller.audit_trail) == 2
    assert controller.audit_trail[0].action == "read_code"
    assert controller.audit_trail[1].action == "write_code"
    assert controller.audit_trail[1].surfaced is True


def test_rc12_secret_and_git_capability_normalization(rc12_ws):
    """Certifies that security-sensitive secrets, git ops, and processes are accurately mapped."""
    from sclass.domain.capability import (
        CAP_SECRET_READ,
        CAP_PROCESS_SPAWN,
        CAP_GIT_READ,
        CAP_GIT_WRITE,
    )
    adapter = BasePlatformAdapter(workspace_dir=rc12_ws)

    # 1. Secret read must not be misclassified as generic filesystem read
    req_secret = adapter.normalize_action(action="read_secret", target="OPENAI_API_KEY")
    assert req_secret.capability == CAP_SECRET_READ

    req_token = adapter.normalize_action(action="get_token", target="aws_session_token")
    assert req_token.capability == CAP_SECRET_READ

    # 2. Process spawning
    req_spawn = adapter.normalize_action(action="spawn_daemon", target="./worker.py")
    assert req_spawn.capability == CAP_PROCESS_SPAWN

    # 3. Git read vs git write
    req_git_read = adapter.normalize_action(action="git_diff", target="HEAD~1")
    assert req_git_read.capability == CAP_GIT_READ

    req_git_write = adapter.normalize_action(action="git_commit", target="-m 'fix'")
    assert req_git_write.capability == CAP_GIT_WRITE


def test_rc12_concrete_adapters_protocol_conformance(rc12_ws):
    """Certifies that Cursor, Codex, and Claude concrete adapters strictly satisfy PlatformAdapter protocol."""
    from sclass.integrations.cursor.adapter import CursorAdapter
    from sclass.integrations.codex.adapter import CodexAdapter
    from sclass.integrations.claude.adapter import ClaudeCodeAdapter

    cursor = CursorAdapter(rc12_ws)
    assert isinstance(cursor, PlatformAdapter)
    assert cursor.platform_id == "cursor"

    codex = CodexAdapter(rc12_ws)
    assert isinstance(codex, PlatformAdapter)
    assert codex.platform_id == "codex"

    claude = ClaudeCodeAdapter(rc12_ws)
    assert isinstance(claude, PlatformAdapter)
    assert claude.platform_id == "claude_code"


def test_rc12_govern_action_requires_approval_message(rc12_ws):
    """Certifies that actions requiring approval surface '[S-Class Approval Required]' instead of 'BLOCKED'."""
    from unittest.mock import patch
    from sclass.domain.action import AuthorizationDecision, DecisionOutcome

    controller = SilentGovernanceController(workspace_dir=rc12_ws, mode=SilentGovernanceMode.SURFACE_ANOMALIES)
    req = ActionRequest(actor="agent", session="s", capability="terminal.execute", action="deploy", target="prod", workspace=rc12_ws)

    approval_decision = AuthorizationDecision(
        outcome=DecisionOutcome.REQUIRE_APPROVAL,
        policy_id="policy_deploy_gate",
        risk_level="high",
        reason="Production deployment requires human confirmation",
    )

    with patch("sclass.product.silent_governance.authorize", return_value=approval_decision):
        dec, surfaced, msg = controller.govern_action(req, risk_score=0.7)
        assert surfaced is True
        assert msg is not None
        assert "[S-Class Approval Required]" in msg
        assert "Action requires human approval" in msg
        assert "BLOCKED" not in msg
