import os
import sys
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
