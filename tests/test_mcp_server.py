import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_server


def test_mcp_initialize_and_get_state(tmp_path):
    workspace = str(tmp_path)
    
    # Tool call sclass_initialize (Controller only)
    res = mcp_server.handle_tool_call(
        "sclass_initialize",
        {"workspace_dir": workspace, "goal": "Fix rogue closing brace in globals.css"},
        role="controller"
    )
    assert res["status"] == "initialized"
    assert res["state"]["currentPhase"] == "TRIAGE"
    assert res["state"]["workflowProfile"] == "bug_fix"
    
    # Tool call sclass_get_state (Default agent role allowed)
    res2 = mcp_server.handle_tool_call("sclass_get_state", {"workspace_dir": workspace})
    assert res2["state"]["taskId"] == res["state"]["taskId"]


def test_mcp_dispatch_and_reset(tmp_path):
    workspace = str(tmp_path)
    
    mcp_server.handle_tool_call("sclass_initialize", {"workspace_dir": workspace, "goal": "Feature request"}, role="controller")
    
    res = mcp_server.handle_tool_call("sclass_dispatch", {"workspace_dir": workspace, "event_name": "triage_done"}, role="controller")
    assert res["status"] == "transitioned"
    assert res["active_phase"] == "ANALYSIS"
    
    res_reset = mcp_server.handle_tool_call("sclass_reset_to_triage", {"workspace_dir": workspace, "new_goal": "Urgent patch"}, role="controller")
    assert res_reset["status"] == "reset"
    assert res_reset["active_phase"] == "TRIAGE"
    assert res_reset["workflow_profile"] == "hotfix"


def test_mcp_doctor_and_gc(tmp_path):
    workspace = str(tmp_path)
    
    # Doctor is read-only (agent allowed)
    doc_res = mcp_server.handle_tool_call("sclass_doctor", {"workspace_dir": workspace})
    assert "doctor_report" in doc_res
    
    # GC is mutating (controller only)
    gc_res = mcp_server.handle_tool_call("sclass_gc", {"workspace_dir": workspace}, role="controller")
    assert "gc_report" in gc_res


@pytest.mark.anyio
async def test_official_mcp_sdk_server(tmp_path):
    workspace = str(tmp_path)
    server = mcp_server.create_mcp_server(workspace_dir=workspace, role="controller")
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


def test_mcp_default_role_is_agent(tmp_path):
    workspace = str(tmp_path)
    # Calling mutating tool without specifying role MUST default to agent and get blocked
    res_blocked = mcp_server.handle_tool_call("sclass_initialize", {"goal": "Sneaky Init"}, workspace_dir=workspace)
    assert res_blocked.get("status") == "blocked"
    assert "Permission denied" in res_blocked.get("error", "")

    res_blocked_goal = mcp_server.handle_tool_call("sclass_goal", {"goal": "Sneaky Goal"}, workspace_dir=workspace)
    assert res_blocked_goal.get("status") == "blocked"

    # Initialize legitimately with controller role
    mcp_server.handle_tool_call("sclass_initialize", {"goal": "Valid Init"}, workspace_dir=workspace, role="controller")

    # Read-only tools work with default role
    res_state = mcp_server.handle_tool_call("sclass_get_state", {}, workspace_dir=workspace)
    assert "state" in res_state
    assert res_state["state"]["currentPhase"] == "TRIAGE"

    # Official SDK server creation without role defaults to agent
    server = mcp_server.create_mcp_server(workspace_dir=workspace)
    if server is not None:
        tools = list(server._tool_manager._tools.keys())
        assert "sclass_get_state" in tools
        assert "sclass_initialize" not in tools
        assert "sclass_dispatch" not in tools


def test_mcp_path_containment_violation(tmp_path):
    workspace = str(tmp_path)
    outside_dir = os.path.dirname(os.path.dirname(workspace))
    
    # Tool call with escaped workspace_dir should be rejected
    with pytest.raises(ValueError, match="Path containment violation"):
        mcp_server.handle_tool_call("sclass_initialize", {"workspace_dir": outside_dir, "goal": "Attack"}, workspace_dir=workspace, role="controller")

    # Security scan with escaped target_file should be rejected
    outside_file = os.path.join(outside_dir, "secrets.txt")
    with pytest.raises(ValueError, match="Path containment violation"):
        mcp_server.handle_tool_call("sclass_security_scan", {"target_file": outside_file}, workspace_dir=workspace)


def test_mcp_no_pinned_workspace_rejects_escape(tmp_path, monkeypatch):
    """When handle_tool_call is called without a pinned workspace root, restricted system paths are rejected."""
    monkeypatch.delenv("SCLASS_WORKSPACE", raising=False)

    # Caller attempts to pass /etc as workspace_dir with no pinned server root
    with pytest.raises(ValueError, match="Path containment violation"):
        mcp_server.handle_tool_call("sclass_get_state", {"workspace_dir": "/etc"})

    # Caller attempts to pass filesystem root / as workspace_dir with no pinned server root
    with pytest.raises(ValueError, match="Path containment violation"):
        mcp_server.handle_tool_call("sclass_initialize", {"workspace_dir": "/", "goal": "Root Attack"}, role="controller")


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


def test_mcp_installer_backup_preserves_pristine_on_reinstall(tmp_path):
    """Original .bak config must never be overwritten on subsequent installs."""
    import mcp_installer
    workspace = str(tmp_path)
    cursor_dir = os.path.join(workspace, ".cursor")
    os.makedirs(cursor_dir, exist_ok=True)
    mcp_file = os.path.join(cursor_dir, "mcp.json")
    pristine_content = {"mcpServers": {"user_tool": {"command": "node", "args": ["tool.js"]}}}
    with open(mcp_file, "w", encoding="utf-8") as f:
        json.dump(pristine_content, f, indent=2)

    # First install
    mcp_installer.install_mcp_configs(workspace, detected_platforms=["cursor"])
    bak_file = mcp_file + ".bak"
    assert os.path.exists(bak_file)
    with open(bak_file, "r", encoding="utf-8") as f:
        bak_data = json.load(f)
    assert "user_tool" in bak_data["mcpServers"]
    assert "sclass" not in bak_data["mcpServers"]

    # Second install
    mcp_installer.install_mcp_configs(workspace, detected_platforms=["cursor"])
    with open(bak_file, "r", encoding="utf-8") as f:
        bak_data_after_second = json.load(f)
    # The pristine backup must STILL NOT contain sclass
    assert "user_tool" in bak_data_after_second["mcpServers"]
    assert "sclass" not in bak_data_after_second["mcpServers"]


def test_mcp_installer_unparseable_json_warns_and_skips(tmp_path, capsys):
    """Unparseable mcp.json must emit warning naming the file and skip without corrupting."""
    import mcp_installer
    workspace = str(tmp_path)
    cursor_dir = os.path.join(workspace, ".cursor")
    os.makedirs(cursor_dir, exist_ok=True)
    mcp_file = os.path.join(cursor_dir, "mcp.json")
    corrupt_content = "{\n  // unclosed json\n  \"mcpServers\": {\n"
    with open(mcp_file, "w", encoding="utf-8") as f:
        f.write(corrupt_content)

    cfgs = mcp_installer.install_mcp_configs(workspace, detected_platforms=["cursor"])
    assert "cursor" not in cfgs  # Skipped
    # Ensure corrupt file content was NOT overwritten
    with open(mcp_file, "r", encoding="utf-8") as f:
        assert f.read() == corrupt_content

    # Ensure warning was printed naming the file
    captured = capsys.readouterr()
    assert "mcp.json" in captured.err or "mcp.json" in captured.out
    assert "WARNING" in captured.err or "WARNING" in captured.out


def test_mcp_rate_limiting_and_api_versioning(tmp_path):
    workspace = str(tmp_path)
    limiter = mcp_server.ToolCallRateLimiter(max_calls_per_minute=3, burst_limit=2)

    # First call: init
    r1 = mcp_server.handle_tool_call("sclass_initialize", {"workspace_dir": workspace, "goal": "RateLimit Test"}, rate_limiter=limiter, role="controller")
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



