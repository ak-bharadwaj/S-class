"""
Certification Suite: Official Model Context Protocol (MCP) Integration (B.5).

Certifies the official MCP server and its integration with the Platform Optimization Core:
1. tool discovery: Official client discovers registered tools via session.list_tools()
2. tool invocation: Official client invokes tools via session.call_tool()
3. authorized tool: Authorized execution completes, observed by S-Class, sealed in LocalLedger
4. unauthorized tool: Attempt to access protected trust roots or unauthorized capabilities blocked fail-closed
5. malicious tool result: Fabricated claims or falsified test results rejected by verification
6. tool timeout: Commands exceeding timeout are aborted fail-closed and recorded in receipt
7. tool failure: Non-zero exit codes captured faithfully in receipt and reported as error
8. verification failure: Workspace mutation after observation invalidates receipt and rejects claim
9. platform optimization wiring: sclass_profile tool exposes active platform profile and control policy
10. streamable HTTP and SSE transport ASGI application validity
"""

import os
import sys
import json
import pytest
from typing import Dict, Any

from sclass.integrations.mcp.official import (
    SClassMCPServer,
    create_sclass_mcp_server,
    open_in_memory_session,
)
from sclass.trust.ledger import LocalLedger


@pytest.fixture
def b5_workspace(tmp_path):
    ws = tmp_path / "cert_b5_mcp_ws"
    ws.mkdir(parents=True, exist_ok=True)
    sample = ws / "sample.txt"
    sample.write_text("hello world from b5 workspace", encoding="utf-8")
    return str(ws)


@pytest.mark.anyio
async def test_b5_mcp_tool_discovery(b5_workspace):
    """Certifies that official MCP ClientSession discovers all registered S-Class tools with valid schemas."""
    server = create_sclass_mcp_server(workspace_dir=b5_workspace)

    async with server.open_client_session() as session:
        tools_res = await session.list_tools()
        assert tools_res is not None
        tool_names = [t.name for t in tools_res.tools]

        # Verify all mandatory tools discovered
        expected_tools = [
            "run_command",
            "read_file",
            "write_file",
            "list_dir",
            "sclass_verify",
            "sclass_initialize",
            "sclass_get_state",
            "sclass_profile",
        ]
        for exp in expected_tools:
            assert exp in tool_names, f"Expected tool '{exp}' not discovered in {tool_names}"

        # Verify run_command schema contains command parameter
        run_cmd_tool = next(t for t in tools_res.tools if t.name == "run_command")
        schema = getattr(run_cmd_tool, "input_schema", getattr(run_cmd_tool, "inputSchema", {}))
        assert "command" in schema.get("properties", {})


@pytest.mark.anyio
async def test_b5_mcp_tool_invocation(b5_workspace):
    """Certifies that official MCP ClientSession invokes tools and returns conformant CallToolResult."""
    server = create_sclass_mcp_server(workspace_dir=b5_workspace)

    async with server.open_client_session() as session:
        res = await session.call_tool("list_dir", {"path": "."})
        assert res is not None
        assert res.is_error is False
        assert len(res.content) > 0
        assert "sample.txt" in res.content[0].text


@pytest.mark.anyio
async def test_b5_mcp_authorized_tool(b5_workspace):
    """
    Certifies authorized tool execution:
    MCP Request -> ActionRequest -> Authorization -> Execution -> Observation -> Verification -> MCP Response.
    Verifies that an immutable ObservedReceipt is committed to LocalLedger.
    """
    server = create_sclass_mcp_server(workspace_dir=b5_workspace)

    async with server.open_client_session() as session:
        cmd = 'python -c "print(\\"OFFICIAL_MCP_B5_VERIFIED\\")"'
        res = await session.call_tool("run_command", {"command": cmd})

        assert res.is_error is False
        assert "OFFICIAL_MCP_B5_VERIFIED" in res.content[0].text
        assert res.meta is not None
        receipt_id = res.meta.get("receipt_id")
        receipt_hash = res.meta.get("receipt_hash")
        assert receipt_id is not None
        assert receipt_hash is not None

        # Verify receipt was atomically recorded in LocalLedger
        ledger = LocalLedger(b5_workspace)
        is_valid, err = ledger.verify_integrity()
        assert is_valid is True, f"Ledger integrity compromised: {err}"

        entries = ledger.read_all()
        obs_entries = [e for e in entries if e.get("event", "").upper() == "OBSERVATION"]
        assert len(obs_entries) >= 1
        last_obs = obs_entries[-1]["payload"]
        assert last_obs["receipt_id"] == receipt_id
        assert last_obs["receipt_hash"] == receipt_hash


@pytest.mark.anyio
async def test_b5_mcp_unauthorized_tool(b5_workspace):
    """
    Certifies that tool calls attempting to access or modify protected S-Class trust roots
    are authoritatively blocked fail-closed with is_error=True and 0 executions.
    """
    server = create_sclass_mcp_server(workspace_dir=b5_workspace)

    async with server.open_client_session() as session:
        # 1. Attempt to read protected ledger file
        res_read = await session.call_tool("read_file", {"path": ".sclass/trust/audit_ledger.jsonl"})
        assert res_read.is_error is True
        assert "[S-Class Security Block]" in res_read.content[0].text
        assert "SCLASS-MCP-PROT" in res_read.content[0].text

        # 2. Attempt to write to protected trust root
        res_write = await session.call_tool(
            "write_file",
            {"path": ".sclass/trust/tampered_ledger.jsonl", "content": "forged_entry"},
        )
        assert res_write.is_error is True
        assert "[S-Class Security Block]" in res_write.content[0].text
        assert not os.path.exists(os.path.join(b5_workspace, ".sclass", "trust", "tampered_ledger.jsonl"))

        # 3. Attempt to run command targeting protected trust root
        res_cmd = await session.call_tool(
            "run_command",
            {"command": "rm -rf .sclass/trust/audit_ledger.jsonl"},
        )
        assert res_cmd.is_error is True
        assert "[S-Class Security Block]" in res_cmd.content[0].text


@pytest.mark.anyio
async def test_b5_mcp_malicious_tool_result(b5_workspace):
    """
    Certifies that fabricated claims or falsified receipts submitted via MCP
    are authoritatively rejected by S-Class verification.
    """
    server = create_sclass_mcp_server(workspace_dir=b5_workspace)

    async with server.open_client_session() as session:
        # Attack A: Claim success without valid receipt
        res_fake = await session.call_tool(
            "sclass_verify",
            {"claim_text": "All tests passed cleanly", "receipt_id": "forged_receipt_id_xyz"},
        )
        assert res_fake.is_error is True
        assert "[S-Class Verification Rejected]" in res_fake.content[0].text
        assert "no independently observed evidence receipt" in res_fake.content[0].text

        # Attack B: Claim success on a failing execution
        cmd_fail = 'python -c "__import__(\\"sys\\").exit(1)"'
        res_run = await session.call_tool("run_command", {"command": cmd_fail})
        assert res_run.is_error is True
        failed_receipt_id = res_run.meta.get("receipt_id")
        assert failed_receipt_id is not None

        # Now agent maliciously claims all tests passed pointing to this receipt
        res_malicious_claim = await session.call_tool(
            "sclass_verify",
            {"claim_text": "All 18 tests passed without failure", "receipt_id": failed_receipt_id},
        )
        assert res_malicious_claim.is_error is True
        assert "[S-Class Verification Rejected]" in res_malicious_claim.content[0].text
        assert "failure" in res_malicious_claim.content[0].text.lower() or "exit code" in res_malicious_claim.content[0].text.lower()


@pytest.mark.anyio
async def test_b5_mcp_tool_timeout(b5_workspace):
    """Certifies that long-running commands exceeding the specified timeout are aborted fail-closed."""
    server = create_sclass_mcp_server(workspace_dir=b5_workspace)

    async with server.open_client_session() as session:
        cmd_sleep = 'python -c "__import__(\\"time\\").sleep(10)"'
        res = await session.call_tool("run_command", {"command": cmd_sleep, "timeout": 0.5})

        assert res.is_error is True
        assert "[S-Class Tool Timeout]" in res.content[0].text
        assert "timed out after 0.5 seconds" in res.content[0].text
        assert res.meta.get("timed_out") is True


@pytest.mark.anyio
async def test_b5_mcp_tool_failure(b5_workspace):
    """Certifies that commands failing with non-zero exit codes are captured faithfully in the ledger."""
    server = create_sclass_mcp_server(workspace_dir=b5_workspace)

    async with server.open_client_session() as session:
        cmd_err = 'python -c "(print(\\"FATAL_ERROR_IN_B5\\", file=__import__(\\"sys\\").stderr), __import__(\\"sys\\").exit(9))"'
        res = await session.call_tool("run_command", {"command": cmd_err})

        assert res.is_error is True
        assert "[S-Class Tool Failure]" in res.content[0].text
        assert "exited with code 9" in res.content[0].text
        assert "FATAL_ERROR_IN_B5" in res.content[0].text
        assert res.meta.get("exit_code") == 9

        # Verify failure receipt was sealed in LocalLedger
        ledger = LocalLedger(b5_workspace)
        entries = ledger.read_all()
        obs_entries = [e for e in entries if e.get("event", "").upper() == "OBSERVATION"]
        assert len(obs_entries) >= 1
        last_obs = obs_entries[-1]["payload"]
        assert last_obs["exit_code"] == 9


@pytest.mark.anyio
async def test_b5_mcp_verification_failure_on_mutation(b5_workspace):
    """
    Certifies that if the workspace is mutated after an observation receipt is minted,
    subsequent claim verification strictly REJECTS due to staleness/mutation.
    """
    server = create_sclass_mcp_server(workspace_dir=b5_workspace)

    async with server.open_client_session() as session:
        # 1. Run command that succeeds
        cmd = 'python -c "print(\\"initial run\\")"'
        res = await session.call_tool("run_command", {"command": cmd})
        assert res.is_error is False
        receipt_id = res.meta["receipt_id"]

        # 2. Mutate workspace behind the scenes
        mutated_file = os.path.join(b5_workspace, "sample.txt")
        with open(mutated_file, "a", encoding="utf-8") as f:
            f.write("\nUNOBSERVED_SECRET_MUTATION")

        # 3. Attempt to verify claim against prior receipt
        res_verify = await session.call_tool(
            "sclass_verify",
            {"claim_text": "Code matches observation", "receipt_id": receipt_id},
        )
        assert res_verify.is_error is True
        assert "[S-Class Verification Rejected]" in res_verify.content[0].text
        assert "modified after observation" in res_verify.content[0].text.lower() or "mutation" in res_verify.content[0].text.lower()


@pytest.mark.anyio
async def test_b5_mcp_platform_optimization_wiring(b5_workspace):
    """Certifies that S-Class MCP server surfaces active platform profile and control policy."""
    # Create server configured with Codex actor
    server_codex = create_sclass_mcp_server(workspace_dir=b5_workspace, agent_id="codex_agent")

    async with server_codex.open_client_session() as session:
        res = await session.call_tool("sclass_profile", {})
        assert res.is_error is False
        report = json.loads(res.content[0].text)

        assert report["platform_id"] == "codex"
        assert "long-horizon autonomy" in report["native_strengths"]
        assert any("long" in str(p).lower() for p in report["preserved_capabilities"])


def test_b5_mcp_streamable_http_and_sse_apps(b5_workspace):
    """Certifies that official streamable HTTP and SSE ASGI apps are properly instantiated."""
    server = create_sclass_mcp_server(workspace_dir=b5_workspace)

    http_app = server.streamable_http_app()
    sse_app = server.sse_app()

    assert http_app is not None
    assert sse_app is not None

    http_route_paths = [r.path for r in http_app.routes]
    sse_route_paths = [r.path for r in sse_app.routes]

    assert "/mcp" in http_route_paths
    assert "/sse" in sse_route_paths
    assert "/messages" in sse_route_paths
