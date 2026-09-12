"""
Unit tests for S-Class V12 Slash Commands (/goal, /boost, /learn),
CLI dispatchers, and epistemic hardening regression fixes.
(tests/test_slash_commands.py)
"""

import os
import json
import tempfile
import pytest
from sdk_interface import SClassSDK
from sclass_cli import run_cli
from codebase_graph_db import CodebaseGraphDB
from graph_traversal import GraphTraversalEngine
from verifier import audit_image_bytes
import mcp_server


def make_test_png(width: int = 1920, height: int = 1080) -> bytes:
    import struct
    header = b'\x89PNG\r\n\x1a\n'
    ihdr_type = b'IHDR'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack('>I', len(ihdr_data)) + ihdr_type + ihdr_data + b'\x00\x00\x00\x00'
    idat_payload = bytes([(i * 37 + (i % 13) * 17) % 256 for i in range(20000)])
    idat_chunk = struct.pack('>I', len(idat_payload)) + b'IDAT' + idat_payload + b'\x00\x00\x00\x00'
    iend_chunk = b'\x00\x00\x00\x00IEND\xaeB`\x82'
    return header + ihdr_chunk + idat_chunk + iend_chunk


def test_sdk_execute_goal():
    with tempfile.TemporaryDirectory() as tmpdir:
        sdk = SClassSDK(workspace_dir=tmpdir)
        res = sdk.execute_goal(goal="Build Academic Portal", profile="full", max_steps=2)
        assert res["mode"] == "goal"
        assert res["goal"] == "Build Academic Portal"
        assert res["steps_executed"] >= 1
        assert os.path.exists(os.path.join(tmpdir, ".agents", "session_handoff.json"))
        assert os.path.exists(os.path.join(tmpdir, "CONTINUE_HERE.md"))


def test_sdk_execute_boost():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a sample python file to index
        src_file = os.path.join(tmpdir, "service.py")
        with open(src_file, "w") as f:
            f.write("def process_data():\n    return 42\n")

        sdk = SClassSDK(workspace_dir=tmpdir)
        res = sdk.execute_boost(goal_or_task="Fast-Track Service Build", max_steps=2)
        assert res["mode"] == "boost"
        assert res["goal"] == "Fast-Track Service Build"
        assert res["steps_executed"] >= 1
        assert "nodes_indexed" in res


def test_sdk_execute_learn():
    with tempfile.TemporaryDirectory() as tmpdir:
        sdk = SClassSDK(workspace_dir=tmpdir)
        res = sdk.execute_learn(
            pattern="AUTH_TOKEN_EXPIRED",
            fix_description="Refresh access token before retrying API request",
            file_path="api/client.py",
            solution_code="refresh_token()",
            promote_candidates=True,
        )
        assert res["mode"] == "learn"
        assert res["learned_record"] is not None
        assert res["learned_record"]["pattern"] == "AUTH_TOKEN_EXPIRED"

        # Verify persistent files created
        mem_file = os.path.join(tmpdir, ".agents", "learning_memory.json")
        assert os.path.exists(mem_file)
        cand_file = os.path.join(tmpdir, ".agents", "knowledge_candidates.json")
        assert os.path.exists(cand_file)


def test_sdk_execute_slash_command_dispatch():
    with tempfile.TemporaryDirectory() as tmpdir:
        sdk = SClassSDK(workspace_dir=tmpdir)

        # /goal
        g_res = sdk.execute_slash_command("/goal Test Feature Alpha")
        assert g_res.get("mode") == "goal"

        # /status
        s_res = sdk.execute_slash_command("/status")
        assert "currentPhase" in s_res

        # /advance
        a_res = sdk.execute_slash_command("/advance")
        assert a_res.get("status") in ("ADVANCED", "COMPLETED", "BLOCKED")

        # /learn
        l_res = sdk.execute_slash_command("/learn SLOW_QUERY")
        assert l_res.get("mode") == "learn"

        # /grill
        grill_res = sdk.execute_slash_command("/grill")
        assert "overall_passed" in grill_res

        # /doubt and /inquire
        doubt_res = sdk.execute_slash_command("/doubt auth")
        assert "symbols" in doubt_res
        assert "matching_symbols_count" in doubt_res

        inquire_res = sdk.execute_slash_command("/inquire auth")
        assert "symbols" in inquire_res

        # Unknown command
        u_res = sdk.execute_slash_command("/unknown_xyz")
        assert "error" in u_res


def test_sclass_cli_dispatcher():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save cwd
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            # /status on uninitialized dir
            code = run_cli(["/status"])
            assert code == 0

            # /goal
            code = run_cli(["/goal", "Build Microservice X"])
            assert code == 0

            # /boost
            code = run_cli(["boost", "Accelerate Endpoint Y"])
            assert code == 0

            # /learn
            code = run_cli(["/learn", "TIMEOUT_ERROR", "Increase HTTP timeout to 10s"])
            assert code == 0

            # /grill (returns 0 if passed, 1 if critical defects found)
            code = run_cli(["/grill"])
            assert code in (0, 1)

            # /doubt & /inquire
            code = run_cli(["/doubt", "auth"])
            assert code == 0
            code = run_cli(["/inquire", "auth"])
            assert code == 0

            # Unknown
            code = run_cli(["/fake_cmd"])
            assert code == 1
        finally:
            os.chdir(old_cwd)


def test_mcp_server_slash_tools():
    with tempfile.TemporaryDirectory() as tmpdir:
        # sclass_goal
        res_goal = mcp_server.handle_tool_call("sclass_goal", {"goal": "MCP Goal Test"}, workspace_dir=tmpdir)
        assert res_goal.get("mode") == "goal"

        # sclass_boost
        res_boost = mcp_server.handle_tool_call("sclass_boost", {"task": "MCP Boost Test"}, workspace_dir=tmpdir)
        assert res_boost.get("mode") == "boost"

        # sclass_learn
        res_learn = mcp_server.handle_tool_call("sclass_learn", {"pattern": "ERR_CONN", "fix_description": "Add retry"}, workspace_dir=tmpdir)
        assert res_learn.get("mode") == "learn"


def test_graph_traversal_cte_no_substring_false_cycle():
    """
    Regression test for Recursive CTE cycle detection:
    Ensure nodes whose names are substrings of other nodes (e.g. 'node1' and 'node10')
    are NOT falsely marked as cycles.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_graph.db")
        db = CodebaseGraphDB(db_path=db_path)

        # Create nodes: root -> node10 -> node1 -> sink
        db.upsert_node("root", "root", "FUNCTION")
        db.upsert_node("node10", "node10", "FUNCTION")
        db.upsert_node("node1", "node1", "FUNCTION")
        db.upsert_node("sink", "sink", "FUNCTION")

        db.upsert_edge("root", "node10", "CALLS")
        db.upsert_edge("node10", "node1", "CALLS")
        db.upsert_edge("node1", "sink", "CALLS")

        traversal = GraphTraversalEngine(graph_db=db)
        blast = traversal.blast_radius("root", max_hops=4)

        impacted_ids = [n["id"] for n in blast["impacted_nodes"]]
        # node1 must NOT be skipped due to 'node1' being a substring of 'node10'!
        assert "node10" in impacted_ids
        assert "node1" in impacted_ids
        assert "sink" in impacted_ids
        assert blast["total_impacted"] == 3


def test_audit_image_bytes_rejection_boundary():
    """
    Regression test: ensures corrupted or sub-dimension images are strictly rejected.
    """
    # 1. Invalid short data
    valid, w, h, std, dist = audit_image_bytes(b"too_short")
    assert valid is False

    # 2. Corrupted PNG (starts with PNG header but has zero payload)
    corrupted_png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 16
    valid, w, h, std, dist = audit_image_bytes(corrupted_png)
    # Even if parsed, dimensions should be None or 0 and std_dev 0
    assert w is None or w < 320

    # 3. Valid high-variance PNG
    valid_png = make_test_png(1920, 1080)
    valid, w, h, std, dist = audit_image_bytes(valid_png)
    assert valid is True
    assert w == 1920
    assert h == 1080
    assert std >= 15.0
    assert dist >= 15


def test_cli_external_workspace_targeting():
    """
    Verifies that CLI can target an external workspace without chdir,
    and all state/artifact writes land in the external workspace.
    """
    with tempfile.TemporaryDirectory() as caller_dir, tempfile.TemporaryDirectory() as target_dir:
        old_cwd = os.getcwd()
        os.chdir(caller_dir)
        try:
            # 1. Run /status targeting target_dir with -w flag
            code = run_cli(["-w", target_dir, "/status"])
            assert code == 0

            # 2. Run /goal targeting target_dir with --workspace flag
            code = run_cli(["--workspace", target_dir, "/goal", "Implement External Worker Task"])
            assert code == 0

            # Target directory MUST contain the state and handoff files
            target_state = os.path.join(target_dir, ".agents", "orchestration_state.json")
            target_handoff = os.path.join(target_dir, ".agents", "session_handoff.json")
            target_continue = os.path.join(target_dir, "CONTINUE_HERE.md")
            assert os.path.exists(target_state), "State file must exist in target directory"
            assert os.path.exists(target_handoff), "Handoff file must exist in target directory"
            assert os.path.exists(target_continue), "CONTINUE_HERE.md must exist in target directory"

            # Caller directory MUST NOT have received any state files
            caller_agents = os.path.join(caller_dir, ".agents")
            assert not os.path.exists(caller_agents), "Caller directory must not have .agents folder written"
        finally:
            os.chdir(old_cwd)


def test_cli_workspace_flag_variants():
    """
    Verifies flag variations: trailing flag, --target, -C, and SCLASS_WORKSPACE env var.
    """
    with tempfile.TemporaryDirectory() as target_dir:
        # 1. Trailing flag
        code = run_cli(["/status", "-w", target_dir])
        assert code == 0

        # 2. --target flag
        code = run_cli(["--target", target_dir, "/status"])
        assert code == 0

        # 3. -C git-style flag
        code = run_cli(["-C", target_dir, "/status"])
        assert code == 0

        # 4. SCLASS_WORKSPACE env var
        old_env = os.environ.get("SCLASS_WORKSPACE")
        os.environ["SCLASS_WORKSPACE"] = target_dir
        try:
            code = run_cli(["/status"])
            assert code == 0
        finally:
            if old_env is None:
                os.environ.pop("SCLASS_WORKSPACE", None)
            else:
                os.environ["SCLASS_WORKSPACE"] = old_env

