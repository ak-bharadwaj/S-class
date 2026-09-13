"""
Protocol Contract Tests for S-Class:
1. ACP (Agent Client Protocol) Message Roundtrip
2. MCP (Model Context Protocol) Tools/Call Roundtrip
Validates official JSON-RPC 2.0 protocol specifications, parameter validation,
authorization gating, and schema-compliant response envelopes.
"""

import os
import sys
import pytest

from sclass.integrations.acp.adapter import ACPAdapter
from sclass.integrations.acp.protocol import ACPProtocolTransport, ACPRequest, DEFAULT_PROTOCOL_VERSION
from sclass.integrations.mcp.gateway import MCPGateway
from sclass.integrations.mcp.transport import MCPProtocolTransport
from sclass.integrations.mcp.tools import MCPToolRegistry, MCPToolDefinition
from sclass.integrations.mcp.auth import MCPAuthorizationContext, MCPAuthenticator


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "protocol_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


# ====================================================================
# 1. ACP Protocol Message Roundtrip
# ====================================================================

def test_acp_initialize_and_session_lifecycle_roundtrip(workspace):
    """Verifies complete ACP session lifecycle under official JSON-RPC 2.0 protocol."""
    adapter = ACPAdapter(workspace_dir=workspace, agent_id="test_agent", mode="enforce")

    # 1. initialize
    init_msg = {
        "jsonrpc": "2.0",
        "id": "init-req-1",
        "method": "initialize",
        "params": {
            "capabilities": {"tools": ["run_command", "edit_file"], "prompts": ["debug"]},
            "clientInfo": {"name": "ClaudeCode", "version": "1.2.0"},
        },
    }
    init_resp = adapter.process_acp_message(init_msg)
    assert init_resp["jsonrpc"] == "2.0"
    assert init_resp["id"] == "init-req-1"
    assert "result" in init_resp
    assert init_resp["result"]["protocolVersion"] == DEFAULT_PROTOCOL_VERSION
    session_id = init_resp["result"]["sessionId"]
    assert session_id

    # 2. session/new
    new_sess_msg = {
        "jsonrpc": "2.0",
        "id": "sess-new-1",
        "method": "session/new",
        "params": {"agentId": "claude-subagent", "cwd": workspace},
    }
    new_sess_resp = adapter.process_acp_message(new_sess_msg)
    assert new_sess_resp["id"] == "sess-new-1"
    sub_session_id = new_sess_resp["result"]["sessionId"]
    assert new_sess_resp["result"]["status"] == "active"

    # 3. session/update
    update_msg = {
        "jsonrpc": "2.0",
        "id": "sess-up-1",
        "method": "session/update",
        "params": {"session_id": sub_session_id, "state": {"active_file": "src/app.py"}},
    }
    up_resp = adapter.process_acp_message(update_msg)
    assert up_resp["result"]["status"] == "updated"

    # 4. permission request (allowed)
    perm_msg = {
        "jsonrpc": "2.0",
        "id": "perm-req-1",
        "method": "permission",
        "params": {
            "session_id": sub_session_id,
            "tool": "run_command",
            "target": "tests/",
            "arguments": {"command": "pytest tests/"},
        },
    }
    perm_resp = adapter.process_acp_message(perm_msg)
    assert perm_resp["result"]["outcome"] == "ALLOW"

    # 5. permission request (denied - dangerous command)
    perm_deny_msg = {
        "jsonrpc": "2.0",
        "id": "perm-req-2",
        "method": "permission",
        "params": {
            "session_id": sub_session_id,
            "tool": "run_command",
            "target": "/",
            "arguments": {"command": "rm -rf /"},
        },
    }
    perm_deny_resp = adapter.process_acp_message(perm_deny_msg)
    assert perm_deny_resp["result"]["outcome"] == "DENY"
    assert "SCLASS-SEC-DANGEROUS" in perm_deny_resp["result"]["policy_id"]

    # 6. tool/call (authorized passthrough)
    tool_msg = {
        "jsonrpc": "2.0",
        "id": "tool-call-1",
        "method": "tool/call",
        "params": {
            "session_id": sub_session_id,
            "tool": "run_command",
            "arguments": {"command": "git status"},
        },
    }
    tool_resp = adapter.process_acp_message(tool_msg)
    assert tool_resp["result"]["status"] == "authorized_passthrough"

    # 7. tool/call (denied by policy)
    bad_tool_msg = {
        "jsonrpc": "2.0",
        "id": "tool-call-2",
        "method": "tool/call",
        "params": {
            "session_id": sub_session_id,
            "tool": "run_command",
            "arguments": {"command": "rm -rf /"},
        },
    }
    bad_tool_resp = adapter.process_acp_message(bad_tool_msg)
    assert "error" in bad_tool_resp
    assert bad_tool_resp["error"]["code"] == -32003
    assert "DENIED" in bad_tool_resp["error"]["message"]

    # 8. session/fork
    fork_msg = {
        "jsonrpc": "2.0",
        "id": "fork-1",
        "method": "session/fork",
        "params": {"session_id": sub_session_id},
    }
    fork_resp = adapter.process_acp_message(fork_msg)
    assert fork_resp["result"]["forkedFrom"] == sub_session_id
    forked_id = fork_resp["result"]["sessionId"]

    # 9. cancellation
    cancel_msg = {
        "jsonrpc": "2.0",
        "id": "cancel-1",
        "method": "cancel",
        "params": {"session_id": forked_id},
    }
    cancel_resp = adapter.process_acp_message(cancel_msg)
    assert cancel_resp["result"]["status"] == "cancelled"

    # 10. shutdown
    shutdown_msg = {
        "jsonrpc": "2.0",
        "id": "shut-1",
        "method": "shutdown",
        "params": {"session_id": sub_session_id},
    }
    shut_resp = adapter.process_acp_message(shutdown_msg)
    assert shut_resp["result"]["status"] == "shutdown_complete"


# ====================================================================
# 2. MCP Tools/Call Protocol Roundtrip
# ====================================================================

def test_mcp_tools_call_roundtrip(workspace):
    """Verifies official MCP tools/call transport, policy intercept, execution, and response."""
    registry = MCPToolRegistry()
    registry.register_tool(
        server_id="test_server",
        name="echo_tool",
        description="Echoes input string",
        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
    )

    auth = MCPAuthenticator(allowed_issuers=["local", "sclass"])

    gateway = MCPGateway(
        workspace_dir=workspace,
        server_id="test_server",
        tool_registry=registry,
        authenticator=auth,
        mode="enforce",
    )

    # 1. Successful execution through tool executor
    def echo_executor(name, args):
        return [{"type": "text", "text": f"ECHO: {args.get('message')}"}]

    valid_call = {
        "jsonrpc": "2.0",
        "id": "mcp-call-1",
        "method": "tools/call",
        "params": {
            "name": "echo_tool",
            "arguments": {"message": "Hello S-Class"},
            "authorization_context": {
                "issuer": "sclass",
                "client_identity": "test_mcp_agent",
                "server_identity": "test_server",
                "credential_scope": "tools",
                "is_valid": True,
            },
        },
    }
    resp = gateway.process_message(valid_call, executor=echo_executor)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == "mcp-call-1"
    assert "result" in resp
    assert resp["result"]["status"] == "success"
    assert resp["result"]["content"][0]["text"] == "ECHO: Hello S-Class"
    assert resp["result"]["mcp_identity"]["tool_name"] == "echo_tool"

    # 2. Blocked call - dangerous command policy violation
    dangerous_call = {
        "jsonrpc": "2.0",
        "id": "mcp-call-2",
        "method": "tools/call",
        "params": {
            "name": "run_command",
            "arguments": {"command": "rm -rf /"},
            "authorization_context": {
                "issuer": "sclass",
                "client_identity": "test_mcp_agent",
                "server_identity": "test_server",
                "credential_scope": "tools",
                "is_valid": True,
            },
        },
    }
    deny_resp = gateway.process_message(dangerous_call, executor=echo_executor)
    assert "error" in deny_resp
    assert deny_resp["error"]["code"] == -32003
    assert "DENIED" in deny_resp["error"]["message"]
    assert deny_resp["error"]["data"]["policy_id"] == "SCLASS-SEC-DANGEROUS"

    # 3. Blocked call - untrusted issuer authorization failure
    unauth_call = {
        "jsonrpc": "2.0",
        "id": "mcp-call-3",
        "method": "tools/call",
        "params": {
            "name": "echo_tool",
            "arguments": {"message": "Hello"},
            "authorization_context": {
                "issuer": "untrusted_evil_issuer",
                "client_identity": "attacker",
                "server_identity": "test_server",
                "credential_scope": "tools",
                "is_valid": True,
            },
        },
    }
    unauth_resp = gateway.process_message(unauth_call, executor=echo_executor)
    assert "error" in unauth_resp
    assert unauth_resp["error"]["code"] == -32002
    assert "Authorization failure" in unauth_resp["error"]["message"]

    # 4. tools/list roundtrip
    tools_list_call = {
        "jsonrpc": "2.0",
        "id": "list-1",
        "method": "tools/list",
        "params": {},
    }
    list_resp = gateway.process_message(tools_list_call)
    assert "result" in list_resp
    assert len(list_resp["result"]["tools"]) == 1
    assert list_resp["result"]["tools"][0]["name"] == "echo_tool"
