import os
import json
import subprocess
import pytest

@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    agents_dir = ws / ".agents"
    agents_dir.mkdir()
    
    # Initialize basic hook config in strict mode
    hooks_config = {
        "enforcement_mode": {
            "antigravity": "block",
            "cursor": "block"
        }
    }
    (agents_dir / "sclass_hooks.json").write_text(json.dumps(hooks_config), encoding="utf-8")
    return ws

def run_hook_runner(workspace, platform, event_type, payload):
    runner_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hook_runner.py"))
    
    cmd = [
        "python", runner_path,
        "--platform", platform,
        "--event-type", event_type,
        "--workspace", str(workspace),
        "--strict"
    ]
    
    result = subprocess.run(
        cmd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False
    )
    return result

def test_antigravity_pretooluse_deny(workspace):
    payload = {
        "tool_name": "write_to_file",
        "tool_args": {
            "content": "password = 'AKIA-SUPER-SECRET-1234'"
        }
    }
    res = run_hook_runner(workspace, "antigravity", "PreToolUse", payload)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out.get("decision") == "deny"
    assert "SCLASS" in out.get("reason", "")

def test_antigravity_pretooluse_allow(workspace):
    payload = {
        "tool_name": "write_to_file",
        "tool_args": {
            "content": "def add(a, b): return a + b"
        }
    }
    res = run_hook_runner(workspace, "antigravity", "PreToolUse", payload)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out.get("decision") == "allow"

def test_antigravity_stop_continue(workspace):
    # Set up orchestration state with uncompleted tasks
    state_file = workspace / ".agents" / "orchestration_state.json"
    state_file.write_text(json.dumps({
        "uncompleted_tasks": 1,
        "test_evidence_receipts": False
    }), encoding="utf-8")
    
    res = run_hook_runner(workspace, "antigravity", "Stop", {})
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out.get("decision") == "continue"
    assert "S-Class Completion Gate Rejected" in out.get("reason", "")

def test_cursor_pretooluse_deny(workspace):
    payload = {
        "tool_name": "write_to_file",
        "tool_args": {
            "content": "password = 'AKIA-SUPER-SECRET-1234'"
        }
    }
    res = run_hook_runner(workspace, "cursor", "preToolUse", payload)
    assert res.returncode == 0
    out = json.loads(res.stdout)
    assert out.get("permission") == "deny"
