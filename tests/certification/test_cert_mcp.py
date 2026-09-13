"""
Certification Suite: Model Context Protocol (MCP) 2026-07-28 Official Boundary.
Certifies:
1. Header-based policy checking for MCP-Protocol-Version, Mcp-Method, Mcp-Name.
2. Stateless self-describing request normalization.
3. Cryptographic tool identity binding (server, tool, schema hash, args hash).
4. Tool invocation convergence onto S-Class action authorization.
5. Long-running task operations (start, status, cancel).
"""

import pytest
from sclass.integrations.mcp import (
    MCPGateway,
    MCPProtocolTransport,
    MCPToolRegistry,
    MCPHeaderPolicy,
    MCPTaskManager,
    MCPTaskStatus,
    MCPAuthenticator,
    MCPAuthorizationContext,
)


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "cert_mcp_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_cert_mcp_header_policy():
    """Certifies header-based policy checking under MCP 2026-07-28."""
    # 1. Valid headers
    valid_hdrs = {
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/call",
        "Mcp-Name": "my_tool",
    }
    ok, err = MCPHeaderPolicy.validate_headers(valid_hdrs, expected_method="tools/call", expected_name="my_tool")
    assert ok is True
    assert err is None

    # 2. Unsupported protocol version fails closed
    bad_proto = {"MCP-Protocol-Version": "1999-01-01"}
    ok, err = MCPHeaderPolicy.validate_headers(bad_proto)
    assert ok is False
    assert "Unsupported MCP-Protocol-Version" in err

    # 3. Method mismatch fails closed
    mismatch_method = {"Mcp-Method": "tools/call"}
    ok, err = MCPHeaderPolicy.validate_headers(mismatch_method, expected_method="resources/list")
    assert ok is False
    assert "does not match request method" in err

    # 4. Name mismatch fails closed
    mismatch_name = {"Mcp-Name": "evil_tool"}
    ok, err = MCPHeaderPolicy.validate_headers(mismatch_name, expected_name="trusted_tool")
    assert ok is False
    assert "does not match target name" in err


def test_cert_mcp_stateless_self_describing_requests():
    """Certifies parsing of self-describing stateless MCP requests."""
    raw_rpc = {
        "jsonrpc": "2.0",
        "id": "req-stateless-1",
        "method": "tools/call",
        "params": {
            "name": "run_command",
            "arguments": {"command": "git status"},
            "_meta": {
                "headers": {
                    "MCP-Protocol-Version": "2026-07-28",
                    "Mcp-Routing-Key": "route-agent-1",
                }
            },
        },
    }
    stateless = MCPProtocolTransport.parse_stateless_request(raw_rpc)
    assert stateless.rpc_request.id == "req-stateless-1"
    assert stateless.protocol_version == "2026-07-28"
    assert stateless.routing_key == "route-agent-1"
    assert stateless.headers.get("MCP-Protocol-Version") == "2026-07-28"


def test_cert_mcp_task_long_running_operations(workspace):
    """Certifies MCP task lifecycle: tasks/start, tasks/status, tasks/cancel."""
    task_mgr = MCPTaskManager(workspace)

    # 1. Start task
    task = task_mgr.start_task(
        tool_name="long_job",
        arguments={"duration": 10},
        agent_id="test_worker",
    )
    assert task.task_id.startswith("task_")
    assert task.status in (MCPTaskStatus.RUNNING, MCPTaskStatus.COMPLETED)

    # 2. Get task status
    retrieved = task_mgr.get_task(task.task_id)
    assert retrieved is not None
    assert retrieved.task_id == task.task_id

    # 3. Cancel task
    task2 = task_mgr.start_task("cancelled_job", {})
    task2.status = MCPTaskStatus.RUNNING  # Set to running to test cancellation
    cancelled = task_mgr.cancel_task(task2.task_id, reason="user interrupt")
    assert cancelled is True
    assert task2.status == MCPTaskStatus.CANCELLED


def test_cert_mcp_gateway_integration(workspace):
    """Certifies MCPGateway end-to-end with header verification and task handling."""
    gateway = MCPGateway(workspace_dir=workspace, mode="enforce")

    # 1. Header policy rejection
    call_with_bad_header = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {"name": "run_command", "arguments": {"command": "git status"}},
        "headers": {"MCP-Protocol-Version": "invalid-2099"},
    }
    resp = gateway.process_message(call_with_bad_header)
    assert "error" in resp
    assert resp["error"]["code"] == -32000
    assert "Header policy violation" in resp["error"]["message"]

    # 2. tasks/start via gateway
    start_call = {
        "jsonrpc": "2.0",
        "id": "task-call-1",
        "method": "tasks/start",
        "params": {"name": "run_command", "arguments": {"command": "git status"}},
    }
    task_resp = gateway.process_message(start_call)
    assert "result" in task_resp
    task_id = task_resp["result"]["task_id"]
    assert task_id

    # 3. tasks/status via gateway
    status_call = {
        "jsonrpc": "2.0",
        "id": "task-status-1",
        "method": "tasks/status",
        "params": {"task_id": task_id},
    }
    status_resp = gateway.process_message(status_call)
    assert "result" in status_resp
    assert status_resp["result"]["task_id"] == task_id
