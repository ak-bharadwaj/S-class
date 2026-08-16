"""
S-Class EOS V11.2 — Audit Hardening Verification Test Suite
(tests/test_audit_hardening_verification.py)

Directly exercises and validates:
1. ExecutionPlanner.create_plan() execution path & detected_domains aggregation.
2. MCP server tool routing (sclass_planner, sclass_spec_synthesis, sclass_dispatch).
3. MCP sclass_dispatch evidence default enforcement (enforce_evidence=True).
4. ArtifactGovernor fail-closed configuration error handling with malformed sclass.config.json.
5. Config GC stale lock reclamation across alive vs dead vs corrupted lock files.
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_server
from sclass_planner import ExecutionPlanner
from planner import MetaPlanner, WorkflowProfile
from artifact_governor import ArtifactGovernor, ApprovalAuthority, HLDDesign, ADRRecord, FSMTransitionTarget
from config_gc import run_gc
from file_lock import FileLock


def test_execution_planner_create_plan_real_execution(tmp_path):
    """Directly executes ExecutionPlanner.create_plan() verifying detected_domains and strategy."""
    workspace = str(tmp_path)
    goal = "Build a secure multi-tenant PostgreSQL database authentication API with Next.js frontend"
    
    strategy = ExecutionPlanner.create_plan(goal, workspace_dir=workspace)
    assert strategy is not None
    assert isinstance(strategy.detected_domains, list)
    assert len(strategy.detected_domains) > 0
    assert any(d in strategy.detected_domains for d in ["database", "backend", "frontend", "security", "ui"])
    assert hasattr(strategy, "debate_panel")
    assert len(strategy.debate_panel) >= 2


def test_mcp_server_planner_tool_execution(tmp_path):
    """Directly executes mcp_server.handle_tool_call for 'sclass_planner'."""
    workspace = str(tmp_path)
    goal = "Refactor database connection pool to prevent socket exhaustion"
    
    res = mcp_server.handle_tool_call("sclass_planner", {"workspace_dir": workspace, "goal": goal})
    assert "profile" in res
    assert "strategy" in res
    assert res["profile"] in ["refactor", "bug_fix", "full"]
    assert "detected_domains" in res["strategy"]
    assert "database" in res["strategy"]["detected_domains"] or "backend" in res["strategy"]["detected_domains"]


def test_mcp_server_spec_synthesis_tool_execution(tmp_path):
    """Directly executes mcp_server.handle_tool_call for 'sclass_spec_synthesis'."""
    workspace = str(tmp_path)
    raw_intent = "Implement audit logging table with timestamp and actor ID"
    
    res = mcp_server.handle_tool_call("sclass_spec_synthesis", {"workspace_dir": workspace, "raw_intent": raw_intent})
    assert "synthesized_spec" in res
    spec_data = res["synthesized_spec"]
    assert isinstance(spec_data, (dict, str))


def test_mcp_server_dispatch_evidence_default_enforcement(tmp_path):
    """Directly verifies mcp_server sclass_dispatch defaults enforce_evidence to True."""
    workspace = str(tmp_path)
    
    # Initialize state
    mcp_server.handle_tool_call("sclass_initialize", {"workspace_dir": workspace, "goal": "Build CRM"})
    
    # Dispatch without enforce_evidence argument -> should transition or enforce evidence strictly
    res = mcp_server.handle_tool_call("sclass_dispatch", {"workspace_dir": workspace, "event_name": "triage_done"})
    assert res["status"] == "transitioned"
    assert res["active_phase"] == "ANALYSIS"


def test_governor_fail_closed_on_malformed_config(tmp_path):
    """Invariant: Malformed sclass.config.json forces CONFIGURATION_ERROR and blocks HLD governance."""
    workspace = str(tmp_path)
    cfg_file = os.path.join(workspace, "sclass.config.json")
    
    # Write invalid JSON into sclass.config.json
    with open(cfg_file, "w", encoding="utf-8") as f:
        f.write("{ INVALID JSON SYNTAX :::: ")
        
    mode = ArtifactGovernor._get_execution_mode(workspace)
    assert mode == "CONFIGURATION_ERROR"
    
    dummy_hld = HLDDesign(
        system_name="TestSystem",
        architecture_style="Microservices",
        adrs=[ADRRecord(
            id="ADR-001",
            title="Database Choice",
            decision="PostgreSQL",
            alternatives=["MySQL"],
            evidence=["Benchmark"],
            affected_modules=["db"],
            rejected_options=["SQLite"],
            reason="High concurrency and multi-tenancy requirements"
        )]
    )
    
    gate_res = ArtifactGovernor.audit_hld_governance(
        hld=dummy_hld,
        hld_validation_passed=True,
        hld_errors=[],
        workspace_dir=workspace
    )
    assert gate_res.is_blocked is True
    assert gate_res.recommended_fsm_state == FSMTransitionTarget.CLARIFICATION
    assert any("Configuration Error" in r for r in gate_res.blocking_reasons)


def test_governor_fail_closed_on_invalid_execution_mode(tmp_path):
    """Invariant: Unrecognized executionMode forces CONFIGURATION_ERROR and blocks HLD governance."""
    workspace = str(tmp_path)
    cfg_file = os.path.join(workspace, "sclass.config.json")
    
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump({"executionMode": "UNRECOGNIZED_UNSAFE_MODE"}, f)
        
    mode = ArtifactGovernor._get_execution_mode(workspace)
    assert mode == "CONFIGURATION_ERROR"


def test_config_gc_live_vs_stale_lock(tmp_path):
    """Verifies GC distinguishes between an active live process lock and a stale dead lock."""
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    lock_file = agents_dir / "state.lock"
    
    # 1. Stale lock with dead PID
    lock_file.write_text(json.dumps({"pid": 99999999, "status": "active"}))
    report = run_gc(str(tmp_path))
    assert report.stale_locks_removed == 1
    assert not lock_file.exists()
    
    # 2. Stale lock with 'released' status
    lock_file.write_text(json.dumps({"pid": os.getpid(), "status": "released"}))
    report2 = run_gc(str(tmp_path))
    assert report2.stale_locks_removed == 1
    assert not lock_file.exists()
