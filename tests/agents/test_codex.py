"""
Real Agent Matrix: OpenAI Codex Platform Adapter Tests.
Verifies Codex interactions:
- shell commands
- file changes
- permission requests
- MCP tool calls
- subagent dispatch
- review events
- handoff packages
"""

from sclass.integrations.codex.adapter import CodexAdapter


def test_codex_complete_matrix(tmp_path):
    adapter = CodexAdapter(workspace_dir=str(tmp_path), mode="enforce")

    # 1. Shell command
    cmd_allow = adapter.on_command("pytest tests/unit")
    assert cmd_allow.is_allowed

    cmd_deny = adapter.on_command("rm -rf /")
    assert cmd_deny.is_denied

    # 2. File change
    fc_allow = adapter.on_file_change("src/model.py", action="write_file")
    assert fc_allow.is_allowed

    fc_deny = adapter.on_file_change(".sclass/trust/root.json", action="write_file")
    assert fc_deny.is_denied

    # 3. Permission request
    perm_res = adapter.on_permission("bash", {"command": "git diff"})
    assert perm_res["result"]["outcome"] in ("ALLOW", "APPROVAL")

    # 4. MCP call through gateway
    mcp_res = adapter.on_mcp_call("list_dir", {"target": "src/"})
    assert "result" in mcp_res

    # 5. Subagent dispatch
    subagent_dec = adapter.on_subagent_dispatch("refactor_subagent", "Clean up imports")
    assert subagent_dec.is_allowed

    # 6. Review event
    rev_res = adapter.on_review_event("Codex review complete. 0 issues found.")
    assert rev_res["status"] == "acknowledged"

    # 7. Handoff
    pkg = adapter.create_handoff("codex_project", next_action="Deploy to staging")
    assert pkg.next_action == "Deploy to staging"
    assert pkg.package_hash != ""
