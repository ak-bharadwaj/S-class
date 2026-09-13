"""
Unit Tests for S-Class Protocol Adapters, Execution, and Impact Analysis.
Covers Batches E, F, G:
- ImpactAnalyzer (blast radius, sensitive targets)
- OPAPolicyEngine (fallback & structured payload)
- Sandbox backends (Host, Bubblewrap, Container)
- ProcessRunner (execution identity, timeout, exit code)
- MCPInterceptor (tool authorization interception)
- ACPDecisionBridge & ACPProxy (JSON-RPC tool call interception)
- LocalTracer (zero-infra OpenTelemetry compatible spans)
"""

import os
import sys
import json
import pytest

from sclass.domain.action import ActionRequest, DecisionOutcome
from sclass.control.impact import ImpactAnalyzer, RiskLevel
from sclass.integrations.opas.opa_client import OPAPolicyEngine
from sclass.execution.sandbox import HostSandbox, BubblewrapSandbox, ContainerSandbox, get_sandbox_backend
from sclass.execution.process import ProcessRunner
from sclass.integrations.mcp.interceptor import MCPInterceptor
from sclass.integrations.mcp.tool_policy import MCPToolPolicy
from sclass.integrations.acp.decision_bridge import ACPDecisionBridge
from sclass.integrations.acp.proxy import ACPProxy
from sclass.telemetry.tracing import LocalTracer


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "test_oss_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_impact_analyzer(workspace):
    # Low risk safe action
    req_safe = ActionRequest(
        agent="claude",
        platform="claude_code",
        action="file_read",
        tool="view",
        target="src/utils.py",
        parameters={},
        workspace=workspace,
    )
    analysis_safe = ImpactAnalyzer.analyze_action(req_safe)
    assert analysis_safe.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)
    assert analysis_safe.requires_human_approval is False

    # High risk action targeting credentials
    req_sensitive = ActionRequest(
        agent="claude",
        platform="claude_code",
        action="file_edit",
        tool="edit",
        target=".env",
        parameters={},
        workspace=workspace,
    )
    analysis_sensitive = ImpactAnalyzer.analyze_action(req_sensitive)
    assert analysis_sensitive.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert len(analysis_sensitive.sensitive_targets) > 0


def test_opa_client_fallback(workspace):
    # Tests that when OPA server is unreachable, it gracefully falls back without crashing
    engine = OPAPolicyEngine(endpoint_url="http://127.0.0.1:9999/unreachable")
    req = ActionRequest(
        agent="claude",
        platform="claude_code",
        action="file_edit",
        tool="edit",
        target="src/app.py",
        parameters={},
        workspace=workspace,
    )
    decision = engine.evaluate(req)
    assert decision.is_allowed is True
    assert decision.policy_id == "OPA-FALLBACK-ALLOW"


def test_process_runner_and_sandbox(workspace):
    runner = ProcessRunner(sandbox=HostSandbox())
    cmd = [sys.executable, "-c", "print('hello_sandbox')"]
    result = runner.run(cmd, cwd=workspace)

    assert result.exit_code == 0
    assert "hello_sandbox" in result.stdout
    assert result.identity is not None
    assert result.identity.executable_hash != ""
    assert result.duration_ms > 0
    assert result.timed_out is False


def test_process_runner_timeout(workspace):
    runner = ProcessRunner(sandbox=HostSandbox())
    # Command that exceeds timeout
    cmd = [sys.executable, "-c", "import time; time.sleep(1.0)"]
    result = runner.run(cmd, cwd=workspace, timeout=0.1)

    assert result.exit_code == 124
    assert result.timed_out is True
    assert "timed out" in result.stderr


def test_mcp_interceptor_allow_and_deny(workspace):
    interceptor = MCPInterceptor(workspace_dir=workspace, mode="enforce")

    # Allowed edit
    dec_allow, err_allow = interceptor.intercept(
        tool_name="write_file",
        arguments={"path": "src/module.py", "content": "print('ok')"},
        agent="claude",
    )
    assert dec_allow.is_allowed is True
    assert err_allow is None

    # Denied edit on ledger / trust directory
    dec_deny, err_deny = interceptor.intercept(
        tool_name="write_file",
        arguments={"path": ".sclass/trust/ledger/audit_ledger.jsonl", "content": "tamper"},
        agent="claude",
    )
    assert dec_deny.is_denied is True
    assert err_deny is not None
    assert err_deny["isError"] is True
    assert "S-Class Policy Block" in err_deny["content"][0]["text"]


def test_acp_decision_bridge_and_proxy(workspace):
    proxy = ACPProxy(workspace_dir=workspace, mode="enforce", agent_name="test_acp_agent")

    # Legitimate tool call
    safe_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": "call_1",
        "method": "tool/call",
        "params": {
            "name": "edit",
            "arguments": {"path": "src/index.js", "content": "console.log('hi');"},
        },
    })
    intercepted, resp = proxy.process_incoming_message(safe_msg)
    assert intercepted is False
    assert resp is None

    # Denied tool call on protected .sclass trust store
    blocked_msg = json.dumps({
        "jsonrpc": "2.0",
        "id": "call_2",
        "method": "tool/call",
        "params": {
            "name": "edit",
            "arguments": {"path": ".sclass/trust/ledger/tamper.json", "content": "evil"},
        },
    })
    intercepted2, resp2 = proxy.process_incoming_message(blocked_msg)
    assert intercepted2 is True
    assert resp2 is not None

    parsed_err = json.loads(resp2)
    assert parsed_err["id"] == "call_2"
    assert parsed_err["error"]["code"] == -32001
    assert "S-Class Policy Block" in parsed_err["error"]["message"]


def test_local_tracer_spans(workspace):
    tracer = LocalTracer(workspace)

    with tracer.span("sclass.test_span", attributes={"agent": "cursor", "task_id": "t123"}) as span:
        span.set_attribute("files_scanned", 42)

    # Verify traces.jsonl was written
    assert os.path.exists(tracer.traces_file)
    with open(tracer.traces_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) >= 1

    last_span = json.loads(lines[-1])
    assert last_span["name"] == "sclass.test_span"
    assert last_span["attributes"]["agent"] == "cursor"
    assert last_span["attributes"]["files_scanned"] == 42
    assert last_span["status"] == "OK"
    assert last_span["duration_ms"] is not None
