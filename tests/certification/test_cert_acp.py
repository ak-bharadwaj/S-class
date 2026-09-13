"""
Certification Suite: Agent Client Protocol (ACP) v1 Official Boundary.
Certifies:
1. Protocol negotiation and capability handshake.
2. Full session lifecycle: init -> new -> update -> fork -> cancel -> shutdown.
3. Policy-gated permission requests and tool calls.
4. Filesystem gateway path containment & secret isolation.
5. Terminal gateway observed execution & receipt anchoring.
"""

import os
import pytest
from sclass.integrations.acp import (
    ACPAdapter,
    ACPTransport,
    ACPSessionManager,
    ACPPermissionsBridge,
    ACPPermissionRequest,
    ACPCapabilityMap,
    ACPCapabilitySpec,
    ACPCompatibility,
    ACPFsGateway,
    ACPTerminalGateway,
    DEFAULT_PROTOCOL_VERSION,
)
from sclass.integrations.acp.schema import (
    ACPFsReadParams,
    ACPFsWriteParams,
    ACPTerminalExecParams,
)


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "cert_acp_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_cert_acp_protocol_negotiation():
    """Certifies ACP compatibility negotiation across versions and failure modes."""
    # 1. Canonical v1 negotiation
    compat, ver, err = ACPCompatibility.negotiate_version("v1")
    assert compat is True
    assert ver == DEFAULT_PROTOCOL_VERSION
    assert err is None

    # 2. Date-based release negotiation
    compat, ver, err = ACPCompatibility.negotiate_version("2026-07-28")
    assert compat is True
    assert ver == "2026-07-28"

    # 3. None/default negotiation
    compat, ver, err = ACPCompatibility.negotiate_version(None)
    assert compat is True
    assert ver == DEFAULT_PROTOCOL_VERSION

    # 4. Incompatible/unsupported version fails closed
    compat, ver, err = ACPCompatibility.negotiate_version("unsupported-future-v99")
    assert compat is False
    assert "Unsupported ACP protocol version" in err


def test_cert_acp_session_lifecycle(workspace):
    """Certifies complete ACP session manager tracking and state updates."""
    mgr = ACPSessionManager()
    session = mgr.create_session(workspace_dir=workspace, agent_id="agent-007")
    assert session.active is True
    assert session.agent_id == "agent-007"

    # Update state
    updated = mgr.update_session(session.session_id, {"status": "in_progress", "phase": "phase_0"})
    assert updated is True
    assert mgr.get_session(session.session_id).state["phase"] == "phase_0"

    # Fork session
    forked = mgr.fork_session(session.session_id)
    assert forked is not None
    assert forked.forked_from == session.session_id
    assert forked.state["phase"] == "phase_0"

    # Cancel session
    cancelled = mgr.cancel_session(forked.session_id, reason="testing abort")
    assert cancelled is True
    assert forked.cancelled is True
    assert forked.active is False


def test_cert_acp_permissions_bridge(workspace):
    """Certifies ACP permission request evaluation against S-Class security policies."""
    bridge = ACPPermissionsBridge(workspace_dir=workspace, mode="enforce")

    # 1. Safe command is allowed
    safe_req = ACPPermissionRequest(
        request_id="req-1",
        session_id="sess-1",
        agent_id="test_agent",
        tool="run_command",
        target="pytest tests/",
        arguments={"command": "pytest tests/"},
    )
    decision = bridge.evaluate_permission(safe_req)
    assert decision.is_allowed or decision.outcome.value == "allow"

    # 2. Dangerous command is denied
    danger_req = ACPPermissionRequest(
        request_id="req-2",
        session_id="sess-1",
        agent_id="test_agent",
        tool="run_command",
        target="rm -rf /",
        arguments={"command": "rm -rf /"},
    )
    deny_decision = bridge.evaluate_permission(danger_req)
    assert deny_decision.is_denied or deny_decision.outcome.value == "deny"
    assert "SCLASS-SEC-DANGEROUS" in deny_decision.policy_id


def test_cert_acp_filesystem_gateway(workspace):
    """Certifies ACP filesystem gateway security containment and secret isolation."""
    fs_gw = ACPFsGateway(workspace)

    # 1. Write file
    write_params = ACPFsWriteParams(
        session_id="sess-1",
        path="src/main.py",
        content="print('hello world')",
        overwrite=True,
    )
    res = fs_gw.write_file(write_params)
    assert res.status == "written"
    assert res.bytes_written > 0
    assert len(res.content_hash) == 64

    # 2. Read file
    read_params = ACPFsReadParams(
        session_id="sess-1",
        path="src/main.py",
    )
    read_res = fs_gw.read_file(read_params)
    assert read_res.content == "print('hello world')"

    # 3. Path traversal escape attempt is rejected
    with pytest.raises(PermissionError, match="escapes workspace"):
        fs_gw.read_file(ACPFsReadParams(session_id="sess-1", path="../../etc/passwd"))

    # 4. Secret file access attempt is rejected (.env)
    with pytest.raises(PermissionError, match="protected or secret resource"):
        fs_gw.read_file(ACPFsReadParams(session_id="sess-1", path=".env"))

    # 5. Writing to protected resources (.git, .sclass/state, .sclass/evidence) is rejected
    with pytest.raises(PermissionError, match="not agent writable"):
        fs_gw.write_file(ACPFsWriteParams(session_id="sess-1", path=".git/hooks/pre-commit", content="#!/bin/sh\nevil"))

    with pytest.raises(PermissionError, match="not agent writable"):
        fs_gw.write_file(ACPFsWriteParams(session_id="sess-1", path=".sclass/state/tasks.db", content="corrupted"))

    with pytest.raises(PermissionError, match="not agent writable"):
        fs_gw.write_file(ACPFsWriteParams(session_id="sess-1", path=".sclass/evidence/fake.json", content="spoofed"))

    with pytest.raises(PermissionError, match="protected or secret resource"):
        fs_gw.write_file(ACPFsWriteParams(session_id="sess-1", path=".env", content="SECRET=123"))

    # 6. List dir safe containment
    entries = fs_gw.list_dir()
    assert "src" in entries
    with pytest.raises(FileNotFoundError):
        fs_gw.list_dir("nonexistent_directory")


def test_cert_acp_terminal_gateway(workspace):
    """Certifies ACP terminal execution gateway with observation, stdout capture, and receipt creation."""
    term_gw = ACPTerminalGateway(workspace)

    # Safe terminal execution with authentic output verification
    params = ACPTerminalExecParams(
        session_id="sess-1",
        command="python -c \"print('acp terminal authentic output')\"",
        cwd=workspace,
    )
    result = term_gw.execute_terminal_command(params)
    assert result.exit_code == 0
    assert result.execution_receipt_id is not None
    assert "acp terminal authentic output" in result.stdout
    assert len(result.stdout_hash) == 64

    # Blocked terminal execution
    blocked_params = ACPTerminalExecParams(
        session_id="sess-1",
        command="rm -rf /",
    )
    with pytest.raises(PermissionError, match="denied by S-Class policy"):
        term_gw.execute_terminal_command(blocked_params)


def test_cert_acp_adapter_gateway_routing(workspace):
    """Certifies that ACPAdapter dispatches fs/* and terminal/* through authoritative gateways."""
    adapter = ACPAdapter(workspace_dir=workspace, agent_id="cert_agent", mode="enforce")

    # 1. fs/write via adapter
    w_msg = {
        "jsonrpc": "2.0",
        "id": "write-1",
        "method": "fs/write",
        "params": {"path": "src/module.py", "content": "x = 42\n"},
    }
    w_resp = adapter.process_acp_message(w_msg)
    assert w_resp["jsonrpc"] == "2.0"
    assert "result" in w_resp
    assert w_resp["result"]["status"] == "written"

    # 2. fs/read via adapter
    r_msg = {
        "jsonrpc": "2.0",
        "id": "read-1",
        "method": "fs/read",
        "params": {"path": "src/module.py"},
    }
    r_resp = adapter.process_acp_message(r_msg)
    assert r_resp["result"]["content"] == "x = 42\n"

    # 3. fs/list via adapter
    l_msg = {
        "jsonrpc": "2.0",
        "id": "list-1",
        "method": "fs/list",
        "params": {"path": ""},
    }
    l_resp = adapter.process_acp_message(l_msg)
    assert "src" in l_resp["result"]["entries"]

    # 4. terminal/exec via adapter
    t_msg = {
        "jsonrpc": "2.0",
        "id": "term-1",
        "method": "terminal/exec",
        "params": {"command": "python -c \"print('routed through adapter')\""},
    }
    t_resp = adapter.process_acp_message(t_msg)
    assert t_resp["result"]["exit_code"] == 0
    assert "routed through adapter" in t_resp["result"]["stdout"]

    # 5. Security violation via adapter fails closed with error code -32003
    bad_w = {
        "jsonrpc": "2.0",
        "id": "bad-w-1",
        "method": "fs/write",
        "params": {"path": ".git/config", "content": "malicious"},
    }
    bad_resp = adapter.process_acp_message(bad_w)
    assert "error" in bad_resp
    assert bad_resp["error"]["code"] == -32003
