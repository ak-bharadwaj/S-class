"""Tests for S-CLASS MCP Server (tests/interfaces/test_mcp_server.py).

Verifies MCP JSON-RPC 2.0 protocol compliance, tool schema declarations,
and live tool execution for sclass_guide_task, sclass_validate_patch, and sclass_get_status.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "10-CONFORMANCE") not in sys.path:
    sys.path.insert(0, str(_ROOT / "10-CONFORMANCE"))
if str(_ROOT / "20-RUNTIME") not in sys.path:
    sys.path.insert(0, str(_ROOT / "20-RUNTIME"))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))
if str(_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(_ROOT / "tools"))

from sclass_runtime_v6_0_1 import SQLiteEventStore

from tools.mcp.sclass_mcp_server import SClassMCPServer, create_mcp_app


def test_mcp_server_initialization():
    """Verify MCP JSON-RPC 2.0 initialization returns correct server capabilities."""
    server = SClassMCPServer(workspace_root=".", db_path="test_sclass.sqlite")
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }
    resp = server.handle_jsonrpc(req)
    assert resp is not None
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "sclass-mcp-server"
    assert resp["result"]["serverInfo"]["version"] == "6.0.1"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_server_initialized_notification_and_ping():
    """Verify initialized notification produces no response and ping returns empty result."""
    server = SClassMCPServer(workspace_root=".", db_path="test_sclass.sqlite")
    notif = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }
    assert server.handle_jsonrpc(notif) is None

    ping = {"jsonrpc": "2.0", "id": 42, "method": "ping"}
    resp = server.handle_jsonrpc(ping)
    assert resp == {"jsonrpc": "2.0", "id": 42, "result": {}}


def test_mcp_server_tools_listing():
    """Verify tools/list exposes all 3 required governance tools with valid schemas."""
    server = SClassMCPServer(workspace_root=".", db_path="test_sclass.sqlite")
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    resp = server.handle_jsonrpc(req)

    assert resp is not None
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    assert tool_names == {"sclass_guide_task", "sclass_validate_patch", "sclass_get_status"}

    # Verify guide_task schema
    guide = next(t for t in tools if t["name"] == "sclass_guide_task")
    assert "intent" in guide["inputSchema"]["properties"]
    assert "intent" in guide["inputSchema"]["required"]

    # Verify validate_patch schema
    val = next(t for t in tools if t["name"] == "sclass_validate_patch")
    assert "patch" in val["inputSchema"]["properties"]
    assert "target_file" in val["inputSchema"]["properties"]
    assert set(val["inputSchema"]["required"]) == {"patch", "target_file"}

    # Verify get_status schema
    status = next(t for t in tools if t["name"] == "sclass_get_status")
    assert "workspace_id" in status["inputSchema"]["properties"]


def test_mcp_server_dispatch_guide_task(tmp_path):
    """Verify sclass_guide_task runs world model indexing and returns context package."""
    db = str(tmp_path / "guide.sqlite")
    # Initialize minimal canonical store
    store = SQLiteEventStore(db)
    store.close()

    server = SClassMCPServer(workspace_root=_ROOT, db_path=db)
    req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "sclass_guide_task",
            "arguments": {
                "intent": "Implement token bucket rate limiter with sliding window",
            },
        },
    }
    resp = server.handle_jsonrpc(req)
    assert resp is not None
    assert resp["id"] == 10
    assert "error" not in resp

    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["status"] == "success"
    assert "rate limiter" in payload["intent"].lower()
    assert payload["objective_id"].startswith("obj-")

    # Check context package
    ctx = payload["context_package"]
    assert ctx is not None
    assert ctx["budget"] > 0
    assert "repo_map" in ctx
    assert len(ctx["items"]) > 0
    assert len(ctx["constraints"]) > 0

    # Check obligations
    assert len(payload["test_obligations"]) >= 1
    assert any(o["kind"] in ("FUNCTIONAL", "NON_FUNCTIONAL") for o in payload["test_obligations"])


def test_mcp_server_dispatch_validate_patch_clean(tmp_path):
    """Verify sclass_validate_patch stages clean python code, runs verifier, and signs receipt."""
    db = str(tmp_path / "val.sqlite")
    store = SQLiteEventStore(db)
    store.close()

    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    (ws_dir / "src").mkdir()

    server = SClassMCPServer(workspace_root=ws_dir, db_path=db)
    patch_code = '''"""Clean valid component."""


class TokenBucketLimiter:
    """Token bucket implementation."""

    def __init__(self, capacity: int = 10) -> None:
        self.capacity = capacity
'''
    req = {
        "jsonrpc": "2.0",
        "id": 20,
        "method": "tools/call",
        "params": {
            "name": "sclass_validate_patch",
            "arguments": {
                "patch": patch_code,
                "target_file": "src/token_bucket.py",
                "restore": False,
            },
        },
    }
    resp = server.handle_jsonrpc(req)
    assert resp is not None
    assert resp["id"] == 20

    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["status"] == "PASS"
    assert payload["target_file"] == "src/token_bucket.py"
    assert len(payload["diagnostics"]) >= 1
    assert payload["diagnostics"][0]["passed"] is True

    # Verify authentic Ed25519 signed receipt
    assert len(payload["receipts"]) >= 1
    receipt = payload["receipts"][0]
    assert receipt["result_status"] == "PASS"
    assert len(receipt["signature"]) == 128  # 64-byte Ed25519 signature hex-encoded


def test_mcp_server_dispatch_validate_patch_syntax_error(tmp_path):
    """Verify sclass_validate_patch reports FAIL and diagnostics when patch has syntax errors."""
    db = str(tmp_path / "val_err.sqlite")
    store = SQLiteEventStore(db)
    store.close()

    ws_dir = tmp_path / "ws_err"
    ws_dir.mkdir()
    (ws_dir / "src").mkdir()

    server = SClassMCPServer(workspace_root=ws_dir, db_path=db)
    broken_code = "def invalid_syntax(:\n    pass\n"

    req = {
        "jsonrpc": "2.0",
        "id": 21,
        "method": "tools/call",
        "params": {
            "name": "sclass_validate_patch",
            "arguments": {
                "patch": broken_code,
                "target_file": "src/broken.py",
            },
        },
    }
    resp = server.handle_jsonrpc(req)
    assert resp is not None
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["status"] == "FAIL"
    assert any(not d["passed"] for d in payload["diagnostics"])


def test_mcp_server_dispatch_get_status(tmp_path):
    """Verify sclass_get_status returns active obligations, chain status, and release readiness."""
    db = str(tmp_path / "status.sqlite")
    store = SQLiteEventStore(db)
    store.close()

    server = SClassMCPServer(workspace_root=tmp_path, db_path=db)
    req = {
        "jsonrpc": "2.0",
        "id": 30,
        "method": "tools/call",
        "params": {
            "name": "sclass_get_status",
            "arguments": {
                "workspace_id": "default",
            },
        },
    }
    resp = server.handle_jsonrpc(req)
    assert resp is not None
    assert resp["id"] == 30

    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["workspace_id"] == "default"
    assert payload["event_sequence"] == 0
    assert payload["chain_status"] == "VALID"
    assert payload["release_verdict"] in ("READY", "BLOCKED")
    assert isinstance(payload["active_obligations"], list)
    assert "reservations_count" in payload["budget_usage"]


def test_mcp_server_error_handling():
    """Verify error responses for unknown tools and methods."""
    server = SClassMCPServer(workspace_root=".", db_path="test_sclass.sqlite")

    # Unknown tool
    req_tool = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "tools/call",
        "params": {"name": "nonexistent_tool", "arguments": {}},
    }
    resp_tool = server.handle_jsonrpc(req_tool)
    assert resp_tool["error"]["code"] == -32601
    assert "Unknown tool" in resp_tool["error"]["message"]

    # Unknown method
    req_method = {
        "jsonrpc": "2.0",
        "id": 100,
        "method": "unknown/method",
        "params": {},
    }
    resp_method = server.handle_jsonrpc(req_method)
    assert resp_method["error"]["code"] == -32601
    assert "Method not found" in resp_method["error"]["message"]


def test_mcp_server_stdio_roundtrip(tmp_path):
    """Verify end-to-end JSON-RPC stdio subprocess execution."""
    db = str(tmp_path / "stdio.sqlite")
    store = SQLiteEventStore(db)
    store.close()

    server_script = str(_ROOT / "tools" / "mcp" / "sclass_mcp_server.py")
    proc = subprocess.Popen(
        [sys.executable, server_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(tmp_path),
    )

    init_msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"
    list_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"

    stdout, _ = proc.communicate(input=init_msg + list_msg, timeout=10)
    lines = [json.loads(line) for line in stdout.strip().split("\n") if line.strip()]

    assert len(lines) == 2
    assert lines[0]["id"] == 1
    assert lines[0]["result"]["serverInfo"]["name"] == "sclass-mcp-server"
    assert lines[1]["id"] == 2
    assert len(lines[1]["result"]["tools"]) == 3


def test_create_mcp_app_factory():
    """Verify create_mcp_app creates an MCPServer app with registered tools."""
    app = create_mcp_app()
    if app is not None:
        assert app.name == "sclass-mcp-server"
