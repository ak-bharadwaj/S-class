import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_server


def test_mcp_initialize_and_get_state(tmp_path):
    workspace = str(tmp_path)
    
    # Tool call sclass_initialize
    res = mcp_server.handle_tool_call(
        "sclass_initialize",
        {"workspace_dir": workspace, "goal": "Fix rogue closing brace in globals.css"}
    )
    assert res["status"] == "initialized"
    assert res["state"]["currentPhase"] == "TRIAGE"
    assert res["state"]["workflowProfile"] == "bug_fix"
    
    # Tool call sclass_get_state
    res2 = mcp_server.handle_tool_call("sclass_get_state", {"workspace_dir": workspace})
    assert res2["state"]["taskId"] == res["state"]["taskId"]


def test_mcp_dispatch_and_reset(tmp_path):
    workspace = str(tmp_path)
    
    mcp_server.handle_tool_call("sclass_initialize", {"workspace_dir": workspace, "goal": "Feature request"})
    
    res = mcp_server.handle_tool_call("sclass_dispatch", {"workspace_dir": workspace, "event_name": "triage_done"})
    assert res["status"] == "transitioned"
    assert res["active_phase"] == "ANALYSIS"
    
    res_reset = mcp_server.handle_tool_call("sclass_reset_to_triage", {"workspace_dir": workspace, "new_goal": "Urgent patch"})
    assert res_reset["status"] == "reset"
    assert res_reset["active_phase"] == "TRIAGE"
    assert res_reset["workflow_profile"] == "hotfix"


def test_mcp_doctor_and_gc(tmp_path):
    workspace = str(tmp_path)
    
    doc_res = mcp_server.handle_tool_call("sclass_doctor", {"workspace_dir": workspace})
    assert "doctor_report" in doc_res
    
    gc_res = mcp_server.handle_tool_call("sclass_gc", {"workspace_dir": workspace})
    assert "gc_report" in gc_res


@pytest.mark.anyio
async def test_official_mcp_sdk_server(tmp_path):
    workspace = str(tmp_path)
    server = mcp_server.create_mcp_server(workspace_dir=workspace)
    assert server is not None
    assert mcp_server.HAS_OFFICIAL_MCP is True

    res = await server.call_tool("sclass_initialize", {"goal": "SDK Test", "workspace_dir": workspace})
    assert res is not None
    assert res.is_error is False
    assert "initialized" in res.content[0].text

    # Verify MCP Resources and Prompts registered
    assert len(server._resource_manager._resources) >= 2
    assert "sclass://orchestration/state" in server._resource_manager._resources
    assert "sclass://orchestration/history" in server._resource_manager._resources

    assert len(server._prompt_manager._prompts) >= 2
    assert "sclass_goal_workflow" in server._prompt_manager._prompts
    assert "sclass_audit_investigation" in server._prompt_manager._prompts


def test_mcp_agent_role_blocks_governance_mutation(tmp_path):
    workspace = str(tmp_path)
    # Controller can initialize
    mcp_server.handle_tool_call("sclass_initialize", {"goal": "Feature test"}, workspace_dir=workspace, role="controller")
    
    # Agent attempting to reset or mutate governance tools is blocked
    res_blocked = mcp_server.handle_tool_call("sclass_reset_to_triage", {"new_goal": "fix typo"}, workspace_dir=workspace, role="agent")
    assert res_blocked.get("status") == "blocked"
    assert "Permission denied" in res_blocked.get("error", "")

    res_blocked2 = mcp_server.handle_tool_call("sclass_gc", {}, workspace_dir=workspace, role="agent")
    assert res_blocked2.get("status") == "blocked"

    # Agent CAN call read-only tools
    res_read = mcp_server.handle_tool_call("sclass_get_state", {}, workspace_dir=workspace, role="agent")
    assert "state" in res_read


def test_mcp_path_containment_violation(tmp_path):
    workspace = str(tmp_path)
    outside_dir = os.path.dirname(os.path.dirname(workspace))
    
    # Tool call with escaped workspace_dir should be rejected
    with pytest.raises(ValueError, match="Path containment violation"):
        mcp_server.handle_tool_call("sclass_initialize", {"workspace_dir": outside_dir, "goal": "Attack"}, workspace_dir=workspace)

    # Security scan with escaped target_file should be rejected
    outside_file = os.path.join(outside_dir, "secrets.txt")
    with pytest.raises(ValueError, match="Path containment violation"):
        mcp_server.handle_tool_call("sclass_security_scan", {"target_file": outside_file}, workspace_dir=workspace)


@pytest.mark.anyio
async def test_official_mcp_server_agent_role_hides_mutating_tools(tmp_path):
    workspace = str(tmp_path)
    server = mcp_server.create_mcp_server(workspace_dir=workspace, role="agent")
    assert server is not None

    tool_names = list(server._tool_manager._tools.keys())
    assert "sclass_get_state" in tool_names
    assert "sclass_security_scan" in tool_names
    assert "sclass_initialize" not in tool_names
    assert "sclass_reset_to_triage" not in tool_names
    assert "sclass_gc" not in tool_names
    assert "sclass_dispatch" not in tool_names


@pytest.mark.anyio
async def test_official_mcp_server_blocks_caller_workspace_override(tmp_path):
    workspace = str(tmp_path)
    outside_dir = os.path.dirname(os.path.dirname(workspace))
    server = mcp_server.create_mcp_server(workspace_dir=workspace, role="controller")
    assert server is not None

    # Caller attempting to pass outside workspace_dir through MCP tool call must be rejected
    with pytest.raises(Exception) as exc1:
        await server.call_tool("sclass_initialize", {"goal": "Test", "workspace_dir": outside_dir})
    assert "Path containment violation" in str(exc1.value) or "Path containment violation" in str(getattr(exc1.value, "__cause__", ""))

    outside_file = os.path.join(outside_dir, "secrets.txt")
    with pytest.raises(Exception) as exc2:
        await server.call_tool("sclass_security_scan", {"target_file": outside_file, "workspace_dir": outside_dir})
    assert "Path containment violation" in str(exc2.value) or "Path containment violation" in str(getattr(exc2.value, "__cause__", ""))


def test_mcp_containment_without_explicit_workspace_arg(tmp_path, monkeypatch):
    workspace = str(tmp_path)
    monkeypatch.setenv("SCLASS_WORKSPACE", workspace)
    outside_dir = os.path.dirname(os.path.dirname(workspace))
    outside_file = os.path.join(outside_dir, "outside_secret.txt")

    # Calling handle_tool_call without workspace_dir should pin to SCLASS_WORKSPACE and reject escape
    with pytest.raises(ValueError, match="Path containment violation"):
        mcp_server.handle_tool_call("sclass_security_scan", {"target_file": outside_file})


def test_mcp_installer_configures_agent_role(tmp_path):
    import mcp_installer
    workspace = str(tmp_path)
    cfgs = mcp_installer.install_mcp_configs(workspace)
    assert "cursor" in cfgs
    
    with open(cfgs["cursor"], "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["mcpServers"]["sclass"]["env"]["SCLASS_MCP_ROLE"] == "agent"
    assert data["mcpServers"]["sclass"]["env"]["SCLASS_WORKSPACE"] == workspace


def test_mcp_rate_limiting_and_api_versioning(tmp_path):
    workspace = str(tmp_path)
    limiter = mcp_server.ToolCallRateLimiter(max_calls_per_minute=3, burst_limit=2)

    # First call: init
    r1 = mcp_server.handle_tool_call("sclass_initialize", {"workspace_dir": workspace, "goal": "RateLimit Test"}, rate_limiter=limiter)
    assert r1.get("status") == "initialized"
    assert r1.get("api_version") == "6.0.0"
    assert r1.get("protocol_version") == "2024-11-05"

    # Second call: get_state (within burst)
    r2 = mcp_server.handle_tool_call("sclass_get_state", {"workspace_dir": workspace}, rate_limiter=limiter)
    assert r2.get("api_version") == "6.0.0"

    # Third call: burst exceeded (burst_limit=2)
    r3 = mcp_server.handle_tool_call("sclass_get_state", {"workspace_dir": workspace}, rate_limiter=limiter)
    assert r3.get("status") == "rate_limited"
    assert "Rate limit exceeded" in r3.get("error")
    assert r3.get("api_version") == "6.0.0"



