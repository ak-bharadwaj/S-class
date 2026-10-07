"""
Unit tests for S-Class V13 Cross-Platform Hook Adapters (adapters/).
Verifies:
- Config generation for Claude Code, Cursor, Codex, Antigravity, Copilot, Windsurf
- Round-trip JSON syntax & key validation
- Platform detection & deterministic 48h WARN trigger
"""

import os
import json
from datetime import datetime, timezone, timedelta
import pytest

from adapters import detect_platforms, PlatformInfo
from adapters.claude_code import ClaudeCodeAdapter
from adapters.cursor import CursorAdapter
from adapters.codex_cli import CodexCliAdapter
from adapters.antigravity import AntigravityAdapter
from adapters.copilot import CopilotAdapter
from adapters.windsurf import WindsurfAdapter


@pytest.fixture
def clean_workspace(tmp_path):
    ws = tmp_path / "test_env"
    ws.mkdir()
    return str(ws)


def test_claude_code_adapter_generates_valid_config(clean_workspace):
    adapter = ClaudeCodeAdapter(workspace_dir=clean_workspace)
    cfg_file = adapter.install_hooks()
    assert os.path.exists(cfg_file)

    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "hooks" in data
    assert "PreToolUse" in data["hooks"]
    hook_entry = data["hooks"]["PreToolUse"][0]
    assert hook_entry["matcher"] == ".*"
    assert "hook_runner.py" in hook_entry["hooks"][0]["command"]
    assert hook_entry["hooks"][0]["timeout"] == 120


def test_cursor_adapter_generates_discrete_schemas(clean_workspace):
    adapter = CursorAdapter(workspace_dir=clean_workspace)
    cfg_file = adapter.install_hooks()
    assert os.path.exists(cfg_file)

    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["version"] == 1
    hooks = data["hooks"]
    assert "beforeReadFile" in hooks
    assert "beforeShellExecution" in hooks
    assert "beforeMCPExecution" in hooks
    assert "preToolUse" in hooks
    assert "beforeSubmitPrompt" in hooks
    assert "afterFileEdit" in hooks


def test_codex_cli_adapter_generates_valid_config(clean_workspace):
    adapter = CodexCliAdapter(workspace_dir=clean_workspace)
    cfg_file = adapter.install_hooks()
    assert os.path.exists(cfg_file)

    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    hooks = data["hooks"]
    assert "PreToolUse" in hooks
    assert "PermissionRequest" in hooks
    assert "commandWindows" in hooks["PreToolUse"][0]["hooks"][0]


def test_antigravity_adapter_uses_gemini_native_dialect(clean_workspace):
    adapter = AntigravityAdapter(workspace_dir=clean_workspace)
    cfg_file = adapter.install_hooks(strict=True)
    assert os.path.exists(cfg_file)

    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "sclass-enforcement-guard" in data
    guard = data["sclass-enforcement-guard"]
    assert "PreToolUse" in guard
    assert "Stop" in guard


def test_copilot_adapter_generates_executable_and_advisory(clean_workspace):
    adapter = CopilotAdapter(workspace_dir=clean_workspace)
    hook_file = adapter.install_hooks()
    inst_file = adapter.generate_instructions()

    assert os.path.exists(hook_file)
    assert os.path.exists(inst_file)

    with open(hook_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    pre_tool = data["hooks"]["preToolUse"][0]
    assert "powershell" in pre_tool
    assert "bash" in pre_tool
    assert "edit|create|apply_patch" in pre_tool["matcher"]


def test_windsurf_adapter_generates_hooks_and_rules(clean_workspace):
    adapter = WindsurfAdapter(workspace_dir=clean_workspace)
    hook_file = adapter.install_hooks()
    rules_file = adapter.generate_rules()

    assert os.path.exists(hook_file)
    assert os.path.exists(rules_file)

    with open(hook_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    hooks = data["hooks"]
    assert "pre_write_code" in hooks
    assert "pre_run_command" in hooks
    assert "post_write_code" in hooks


def test_detect_platforms_and_deterministic_48h_warn_threshold(clean_workspace):
    # Setup mock .claude and .cursor directories
    os.makedirs(os.path.join(clean_workspace, ".claude"), exist_ok=True)
    os.makedirs(os.path.join(clean_workspace, ".cursor"), exist_ok=True)
    os.makedirs(os.path.join(clean_workspace, ".agents"), exist_ok=True)

    # 1. Fresh install (< 48 hours): should be UNVERIFIED
    cfg_path = os.path.join(clean_workspace, ".agents", "sclass_hooks.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": 1,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "enforcement_mode": {"claude_code": "warn", "cursor": "warn"},
            "last_verified": {"claude_code": None, "cursor": None}
        }, f)

    detections = detect_platforms(clean_workspace)
    assert "claude_code" in detections
    assert "cursor" in detections
    assert detections["claude_code"].verification_status == "UNVERIFIED"
    assert detections["cursor"].verification_status == "UNVERIFIED"

    # 2. Aging install past 48h with zero receipts: should escalate to WARN
    old_time = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": 1,
            "installed_at": old_time,
            "enforcement_mode": {"claude_code": "warn", "cursor": "warn"},
            "last_verified": {"claude_code": None, "cursor": None}
        }, f)

    detections = detect_platforms(clean_workspace)
    assert detections["claude_code"].verification_status == "WARN"
    assert detections["cursor"].verification_status == "WARN"

    # 3. Genuine tool receipt lands: should flip to PASS
    verified_time = datetime.now(timezone.utc).isoformat()
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": 1,
            "installed_at": old_time,
            "enforcement_mode": {"claude_code": "warn", "cursor": "warn"},
            "last_verified": {"claude_code": verified_time, "cursor": None}
        }, f)

    detections = detect_platforms(clean_workspace)
    assert detections["claude_code"].verification_status == "PASS"
    assert detections["claude_code"].verified is True
    assert detections["cursor"].verification_status == "WARN"


def test_execute_init_command_deploys_runner_and_mcp_and_claude_rules(clean_workspace):
    from sclass_cli import execute_init_command

    # Mark workspace as having Cursor and Claude Code
    os.makedirs(os.path.join(clean_workspace, ".cursor"), exist_ok=True)
    os.makedirs(os.path.join(clean_workspace, ".claude"), exist_ok=True)

    res = execute_init_command(workspace_dir=clean_workspace)
    assert res["status"] == "SUCCESS"

    # 1. Verify runner files are deployed to clean_workspace
    assert os.path.exists(os.path.join(clean_workspace, "hook_runner.py"))
    assert os.path.exists(os.path.join(clean_workspace, "hook_core.py"))
    assert os.path.exists(os.path.join(clean_workspace, "hook_rules.py"))

    # 2. Verify MCP registration files
    cursor_mcp = os.path.join(clean_workspace, ".cursor", "mcp.json")
    assert os.path.exists(cursor_mcp)
    with open(cursor_mcp, "r", encoding="utf-8") as f:
        mcp_data = json.load(f)
    assert "sclass" in mcp_data["mcpServers"]
    assert "mcp_server.py" in mcp_data["mcpServers"]["sclass"]["args"][0]

    claude_mcp = os.path.join(clean_workspace, ".claude", "mcp.json")
    assert os.path.exists(claude_mcp)

    # 3. Verify Claude Code rule parity (.claude/rules/sclass-governance.md)
    claude_rule = os.path.join(clean_workspace, ".claude", "rules", "sclass-governance.md")
    assert os.path.exists(claude_rule)
    with open(claude_rule, "r", encoding="utf-8") as f:
        rule_text = f.read()
    assert "S-Class Epistemic Governance" in rule_text
    assert "Zero Hallucinated APIs" in rule_text
    assert "Blast Radius Discipline" in rule_text


def test_non_destructive_installer_merging(tmp_path):
    ws = str(tmp_path)
    cursor_dir = os.path.join(ws, ".cursor")
    os.makedirs(cursor_dir, exist_ok=True)
    cursor_mcp = os.path.join(cursor_dir, "mcp.json")

    # User's existing config with comments and another server
    initial_content = """{
        // User's custom MCP database server
        "mcpServers": {
            "my-custom-db": {
                "command": "node",
                "args": ["server.js"]
            }
        }
    }"""
    with open(cursor_mcp, "w", encoding="utf-8") as f:
        f.write(initial_content)

    from mcp_installer import install_mcp_configs
    install_mcp_configs(workspace_dir=ws, detected_platforms=["cursor"])

    # Backup file must exist
    assert os.path.exists(cursor_mcp + ".bak")

    # User's custom server must STILL be present
    with open(cursor_mcp, "r", encoding="utf-8") as f:
        updated = json.load(f)
    assert "my-custom-db" in updated["mcpServers"]
    assert "sclass" in updated["mcpServers"]

    # Also test Claude Code adapter preserves user hooks
    claude_dir = os.path.join(ws, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    claude_settings = os.path.join(claude_dir, "settings.local.json")
    with open(claude_settings, "w", encoding="utf-8") as f:
        f.write("""{
            // User linter hook
            "hooks": {
                "PreToolUse": [
                    {"matcher": ".*", "hooks": [{"type": "command", "command": "run_linter.sh"}]}
                ]
            }
        }""")

    from adapters.claude_code import ClaudeCodeAdapter
    ClaudeCodeAdapter(workspace_dir=ws).install_hooks()

    assert os.path.exists(claude_settings + ".bak")
    with open(claude_settings, "r", encoding="utf-8") as f:
        c_data = json.load(f)
    pre_hooks = c_data["hooks"]["PreToolUse"]
    # Both user hook and sclass hook must be present!
    commands = [h["hooks"][0]["command"] for h in pre_hooks]
    assert any("run_linter.sh" in cmd for cmd in commands)
    assert any("hook_runner" in cmd for cmd in commands)


