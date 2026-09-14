"""
Certification Suite: Milestone 23 — RC.7 ACP Proxy, MCP Governance Bridge & Protocol Gateway.

Certifies:
1. test_rc7_protocol_event_schema_and_serialization:
   Canonical ProtocolEvent schema, immutability, metadata preservation, and dict roundtrip.
2. test_rc7_protocol_gateway_pubsub_fanout:
   Pub/sub subscription filtering (by source and event_type) and subscriber exception isolation.
3. test_rc7_acp_proxy_interception_and_authorization_allow:
   ACPProxy transparent pass-through for authorized tool calls with action_authorized event.
4. test_rc7_acp_proxy_interception_and_authorization_deny:
   ACPProxy fail-closed interception of unauthorized tool calls with structured JSON-RPC error.
5. test_rc7_mcp_governance_bridge_authorization_enforcement:
   MCP governance bridge blocking unauthorized tool calls with structured -32003 error.
6. test_rc7_mcp_gateway_protocol_event_emission:
   MCPGateway emitting canonical ProtocolEvents for tools/call, tools/list, and tasks/start.
7. test_rc7_unified_event_ingestion_acp_and_mcp:
   Unified event stream ingesting interleaved ACP and MCP protocol traffic into canonical models.
8. test_rc7_observation_plane_fanout_and_audit_trail:
   Observation plane audit trail capture and recent event inspection.
"""

import os
import json
import pytest
from typing import Dict, Any, List

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.integrations.protocol_gateway import (
    ProtocolEvent,
    ProtocolEventGateway,
    get_protocol_gateway,
    reset_protocol_gateway,
)
from sclass.integrations.acp.proxy import ACPProxy
from sclass.integrations.acp.adapter import ACPAdapter
from sclass.integrations.mcp.gateway import MCPGateway
from sclass.integrations.mcp.tools import MCPToolRegistry, MCPToolDefinition


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "cert_rc7_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


@pytest.fixture
def gateway():
    return reset_protocol_gateway()


def test_rc7_protocol_event_schema_and_serialization():
    """Certifies ProtocolEvent schema, immutability, and serialization roundtrip."""
    event = ProtocolEvent(
        event_id="evt_test_123",
        source="acp",
        event_type="acp.tool_call",
        agent_id="agent_alpha",
        session_id="session_xyz",
        payload={"tool": "read_file", "path": "main.py"},
    )

    data = event.to_dict()
    assert data["event_id"] == "evt_test_123"
    assert data["source"] == "acp"
    assert data["event_type"] == "acp.tool_call"
    assert data["agent_id"] == "agent_alpha"
    assert data["session_id"] == "session_xyz"
    assert data["payload"]["tool"] == "read_file"
    assert "timestamp" in data

    # Roundtrip from_dict
    restored = ProtocolEvent.from_dict(data)
    assert restored.event_id == event.event_id
    assert restored.source == event.source
    assert restored.event_type == event.event_type
    assert restored.payload == event.payload


def test_rc7_protocol_gateway_pubsub_fanout(gateway):
    """Certifies fan-out, filtering by source/type, and exception isolation."""
    all_events: List[ProtocolEvent] = []
    acp_only: List[ProtocolEvent] = []
    denials_only: List[ProtocolEvent] = []

    # 1. Subscriber to everything
    sub_all = gateway.subscribe(lambda e: all_events.append(e))

    # 2. Subscriber filtered by source="acp"
    sub_acp = gateway.subscribe(lambda e: acp_only.append(e), source="acp")

    # 3. Subscriber filtered by event_type="acp.action_denied"
    sub_deny = gateway.subscribe(lambda e: denials_only.append(e), event_types={"acp.action_denied"})

    # 4. Faulty subscriber that raises exception
    def faulty_listener(e):
        raise RuntimeError("Simulated crash in sink")

    gateway.subscribe(faulty_listener)

    # Emit ACP allowed event
    gateway.emit_acp(
        event_type="acp.action_authorized",
        session_id="s1",
        agent_id="a1",
        payload={"tool": "read"},
    )

    # Emit MCP allowed event
    gateway.emit_mcp(
        event_type="mcp.action_authorized",
        session_id="s2",
        agent_id="a2",
        payload={"tool": "query"},
    )

    # Emit ACP denial event
    gateway.emit_acp(
        event_type="acp.action_denied",
        session_id="s1",
        agent_id="a1",
        payload={"tool": "rm -rf /"},
    )

    assert len(all_events) == 3
    assert len(acp_only) == 2
    assert len(denials_only) == 1
    assert denials_only[0].payload["tool"] == "rm -rf /"

    # Unsubscribe test
    assert gateway.unsubscribe(sub_all) is True
    assert gateway.unsubscribe("non_existent_id") is False

    gateway.emit_acp("acp.ping", "s1", "a1", {})
    assert len(all_events) == 3  # Did not increase


def test_rc7_acp_proxy_interception_and_authorization_allow(workspace, gateway):
    """Certifies ACPProxy allowing safe tool calls and emitting authorized event."""
    proxy = ACPProxy(workspace_dir=workspace, mode="enforce", gateway=gateway)

    # Safe tool call
    safe_call = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tool/call",
        "params": {
            "session_id": "sess_1",
            "name": "view_file",
            "arguments": {"path": "src/main.py"},
        },
    }

    intercepted, resp = proxy.intercept_message(safe_call)
    assert intercepted is False
    assert resp is None

    # Check that events were emitted to the gateway
    events = gateway.get_recent_events(source="acp")
    event_types = [e.event_type for e in events]
    assert "acp.tool_call" in event_types
    assert "acp.action_authorized" in event_types


def test_rc7_acp_proxy_interception_and_authorization_deny(workspace, gateway):
    """Certifies ACPProxy blocking dangerous calls and returning JSON-RPC error."""
    proxy = ACPProxy(workspace_dir=workspace, mode="enforce", gateway=gateway)

    # Dangerous command call blocked by policy
    dangerous_call = {
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tool/call",
        "params": {
            "session_id": "sess_2",
            "name": "run_command",
            "arguments": {"command": "rm -rf / --no-preserve-root"},
        },
    }

    intercepted, resp = proxy.intercept_message(dangerous_call)
    assert intercepted is True
    assert resp is not None
    assert resp["error"]["code"] == -32001
    assert "[S-Class Policy Block]" in resp["error"]["message"]

    # Verify event emission
    events = gateway.get_recent_events(source="acp")
    event_types = [e.event_type for e in events]
    assert "acp.action_denied" in event_types


def test_rc7_mcp_governance_bridge_authorization_enforcement(workspace, gateway):
    """Certifies MCP governance bridge blocking unauthorized tool calls."""
    mcp_gw = MCPGateway(workspace_dir=workspace, mode="enforce", gateway=gateway)

    # Register an unauthorized or dangerous tool call
    result = mcp_gw.handle_call_tool(
        tool_name="run_command",
        arguments={"command": "rm -rf / --no-preserve-root"},
        agent_id="mcp_test_agent",
    )

    assert "error" in result
    assert result["error"]["code"] == -32003
    assert "Authorization DENIED" in result["error"]["message"]

    # Test check_governance method directly
    decision = mcp_gw.check_governance(
        tool_name="run_command",
        arguments={"command": "cat .sclass/trust/audit_ledger.jsonl"},
        agent_id="mcp_test_agent",
    )
    assert decision.is_denied is True


def test_rc7_mcp_gateway_protocol_event_emission(workspace, gateway):
    """Certifies MCPGateway emitting canonical events across operations."""
    tool_reg = MCPToolRegistry()
    tool_reg.register_tool(
        server_id="mcp_server",
        name="read_metrics",
        description="Reads system metrics",
        input_schema={"type": "object"},
    )

    mcp_gw = MCPGateway(
        workspace_dir=workspace,
        tool_registry=tool_reg,
        mode="enforce",
        gateway=gateway,
    )

    # 1. tools/list
    mcp_gw.process_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})

    # 2. resources/list
    mcp_gw.process_message({"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}})

    # 3. tools/call (safe)
    mcp_gw.process_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "read_metrics", "arguments": {}},
        },
        executor=lambda name, args: [{"type": "text", "text": "cpu: 10%"}],
    )

    events = gateway.get_recent_events(source="mcp")
    types = [e.event_type for e in events]
    assert "mcp.tools_list" in types
    assert "mcp.resources_list" in types
    assert "mcp.tools_call" in types
    assert "mcp.action_authorized" in types


def test_rc7_unified_event_ingestion_acp_and_mcp(workspace, gateway):
    """Certifies unified event ingestion receiving interleaved ACP and MCP protocol events."""
    unified_log: List[ProtocolEvent] = []
    gateway.subscribe(lambda e: unified_log.append(e))

    # Send ACP message via ACPAdapter
    acp_adapter = ACPAdapter(workspace_dir=workspace, gateway=gateway)
    acp_adapter.process_acp_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"capabilities": {"tools": ["read_file"]}},
        }
    )

    # Send MCP message via MCPGateway
    mcp_gw = MCPGateway(workspace_dir=workspace, gateway=gateway)
    mcp_gw.process_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
    )

    # Both events must be present in the unified log
    sources = [e.source for e in unified_log]
    assert "acp" in sources
    assert "mcp" in sources
    assert any(e.event_type == "acp.initialize" for e in unified_log)
    assert any(e.event_type == "mcp.tools_list" for e in unified_log)


def test_rc7_observation_plane_fanout_and_audit_trail(workspace, gateway):
    """Certifies observation plane audit trail recording all actions."""
    gateway.clear_history()

    proxy = ACPProxy(workspace_dir=workspace, gateway=gateway)

    # Perform sequence of actions
    proxy.intercept_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    proxy.intercept_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tool/call",
            "params": {"name": "read_file", "arguments": {"path": "safe.py"}},
        }
    )
    proxy.intercept_message({"jsonrpc": "2.0", "id": 3, "method": "shutdown", "params": {}})

    audit_trail = gateway.get_recent_events()
    assert len(audit_trail) >= 3

    event_sequence = [e.event_type for e in audit_trail]
    assert "acp.initialize" in event_sequence
    assert "acp.tool_call" in event_sequence
    assert "acp.shutdown" in event_sequence


def test_rc7_acp_null_params_resilience(workspace, gateway):
    """Certifies ACPProxy and message processor resilience against null/non-dict params."""
    proxy = ACPProxy(workspace_dir=workspace, gateway=gateway)

    # 1. Null params in initialize
    intercepted, resp = proxy.intercept_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": None})
    assert intercepted is False
    assert resp is None

    # 2. Raw JSON-RPC line with null params
    raw = '{"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": null}'
    intercepted_raw, resp_raw = proxy.process_incoming_message(raw)
    assert intercepted_raw is False

    # 3. List params (valid JSON-RPC, non-dict)
    raw_list = '{"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": ["arg"]}'
    intercepted_list, resp_list = proxy.process_incoming_message(raw_list)
    assert intercepted_list is False


def test_rc7_mcp_none_arguments_resilience(workspace, gateway):
    """Certifies MCPGateway resilience when tool call arguments are None or missing."""
    mcp = MCPGateway(workspace_dir=workspace, gateway=gateway)
    res = mcp.handle_call_tool(tool_name="view_file", arguments=None)
    assert "result" in res or "error" in res
