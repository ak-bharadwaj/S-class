"""
Adversarial Test: Attack J - MCP Tool Spoofing Defense.
Proves that an MCP tool call claiming a safe operation but writing to a protected resource
is authoritatively blocked by S-Class policy.
"""

from sclass.integrations.mcp.adapter import MCPAdapter


def test_attack_j_mcp_safe_tool_targeting_protected_resource_denied(adv_workspace):
    """
    Attack J:
    MCP tool is named 'save_note' (ostensibly harmless), but its arguments
    target a file inside .sclass/trust/.
    Result: Authorization DENY with security error response.
    """
    adapter = MCPAdapter(workspace_dir=adv_workspace)

    decision, tool_id, err_resp = adapter.handle_tool_call(
        tool_name="save_note",
        arguments={
            "path": ".sclass/trust/audit_ledger.jsonl",
            "content": "forged_data",
        },
    )

    assert decision.is_denied
    assert err_resp is not None
    assert err_resp["isError"] is True
    assert "protected resource" in str(err_resp).lower()
