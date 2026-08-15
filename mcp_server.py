"""
S-Class EOS MCP Server Interface

Exposes S-Class EOS FSM engine, strategy planner, evidence verifier, and replay audit tools
over the Model Context Protocol (MCP) stdio interface. Allows S-Class EOS to run seamlessly
across Claude Desktop, Cursor, VS Code, Codex, and Antigravity.
"""

import sys
import os
import json
import logging
from dataclasses import asdict
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime
import doctor
import config_gc
import replay
import security_shield
import sclass_kernel
from sclass_planner import ExecutionPlanner
from planner import MetaPlanner
from strategy import StrategyEngine

logger = logging.getLogger("sclass_mcp_server")


def handle_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Routes MCP tool calls to S-Class EOS python APIs."""
    workspace_dir = arguments.get("workspace_dir", os.getcwd())

    if tool_name == "sclass_initialize":
        goal = arguments.get("goal", "")
        profile = arguments.get("profile")
        runtime.initialize_state(workspace_dir, goal=goal, profile=profile)
        state = runtime.get_state(workspace_dir)
        return {"status": "initialized", "state": asdict(state)}

    elif tool_name == "sclass_get_state":
        state = runtime.get_state(workspace_dir)
        return {"state": asdict(state)}

    elif tool_name == "sclass_dispatch":
        event_name = arguments.get("event_name", "")
        enforce_evidence = arguments.get("enforce_evidence", False)
        res = sclass_kernel.kernel_instance.request_transition(event_name=event_name, workspace_dir=workspace_dir, payload={"enforce_evidence": enforce_evidence})
        state = runtime.get_state(workspace_dir)
        return {"status": "transitioned", "active_phase": state.currentPhase, "active_event": state.activeEvent, "kernel_receipt": res}

    elif tool_name == "sclass_reset_to_triage":
        new_goal = arguments.get("new_goal", "")
        runtime.reset_to_triage(workspace_dir, new_goal=new_goal)
        state = runtime.get_state(workspace_dir)
        return {"status": "reset", "active_phase": state.currentPhase, "workflow_profile": state.workflowProfile}

    elif tool_name == "sclass_memory_search":
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)
        fixes = runtime.MemoryManager.semantic_search(query, workspace_dir=workspace_dir, top_k=top_k)
        return {"query": query, "fixes": fixes}

    elif tool_name == "sclass_doctor":
        doc_report = doctor.run_doctor(workspace_dir)
        return {"doctor_report": asdict(doc_report)}

    elif tool_name == "sclass_gc":
        gc_report = config_gc.run_gc(workspace_dir)
        return {"gc_report": asdict(gc_report)}

    elif tool_name == "sclass_audit_replay":
        replay_report = replay.ReplayEngine.audit_replay(workspace_dir)
        return {"replay_report": asdict(replay_report)}

    elif tool_name == "sclass_security_scan":
        target_file = arguments.get("target_file", "")
        if target_file and os.path.exists(target_file):
            findings = security_shield.SecurityShield.scan_file(target_file)
            report = security_shield.SecurityShield.generate_report(findings)
            return {"security_report": report}
        return {"error": f"Target file '{target_file}' does not exist"}

    elif tool_name == "sclass_strategy_planner":
        goal = arguments.get("goal", "")
        exec_plan = ExecutionPlanner.create_plan(goal, workspace_dir=workspace_dir)
        plan = MetaPlanner.select_profile(goal)
        return {
            "profile": plan.profile.value,
            "rationale": plan.rationale,
            "strategy": exec_plan.to_dict()
        }

    elif tool_name == "sclass_spec_synthesis":
        from spec_synthesis import SpecSynthesisEngine
        raw_intent = arguments.get("raw_intent", "Fullstack App Build")
        spec = SpecSynthesisEngine.run_synthesis(raw_intent=raw_intent, workspace_dir=workspace_dir)
        return {"synthesized_spec": spec.__dict__}

    elif tool_name == "sclass_preflight_scan":
        from workspace_preflight_scanner import WorkspacePreflightScanner
        discovery = WorkspacePreflightScanner.full_project_discovery(workspace_dir)
        return {"project_discovery": discovery}

    elif tool_name == "sclass_advance_fsm":
        advance_res = runtime.FSMGoalSequenceRunner.advance_one_state(workspace_dir)
        return {"advance_result": advance_res}

    elif tool_name == "sclass_run_goal_sequence":
        history = runtime.FSMGoalSequenceRunner.run_full_sequence(workspace_dir)
        state = runtime.get_state(workspace_dir)
        return {
            "status": "SEQUENCE_RUN_FINISHED",
            "active_phase": state.currentPhase,
            "steps_executed": len(history),
            "sequence_history": history
        }

    else:
        raise ValueError(f"Unknown MCP tool: {tool_name}")


def main():
    """Stdio JSON-RPC MCP Server listener loop."""
    logger.info("S-Class EOS MCP Server started on stdio.")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": [
                            {"name": "sclass_initialize", "description": "Initialize S-Class EOS state & strategy"},
                            {"name": "sclass_get_state", "description": "Get current S-Class EOS FSM state"},
                            {"name": "sclass_dispatch", "description": "Dispatch FSM transition event"},
                            {"name": "sclass_reset_to_triage", "description": "Reset workflow to TRIAGE on goal update"},
                            {"name": "sclass_memory_search", "description": "Semantic search in learning memory"},
                            {"name": "sclass_doctor", "description": "Inspect workspace environment health"},
                            {"name": "sclass_gc", "description": "Garbage collect stale state & lock files"},
                            {"name": "sclass_audit_replay", "description": "Audit deterministic execution replay trail"},
                            {"name": "sclass_security_scan", "description": "Scan file for secrets & vulnerabilities"},
                            {"name": "sclass_strategy_planner", "description": "Infer workflow profile and execution strategy"},
                            {"name": "sclass_spec_synthesis", "description": "Synthesize evidence-driven specification and semantic gate"},
                            {"name": "sclass_preflight_scan", "description": "Run 100% upfront workspace AST and project discovery"}
                        ]
                    }
                }
            elif method == "tools/call":
                tool_name = params.get("name", "")
                args = params.get("arguments", {})
                res = handle_tool_call(tool_name, args)
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method '{method}' not found"}
                }

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)}
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
