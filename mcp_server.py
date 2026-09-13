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
from dataclasses import asdict, is_dataclass
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

try:
    from mcp.server.mcpserver import MCPServer
    HAS_OFFICIAL_MCP = True
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer
        HAS_OFFICIAL_MCP = True
    except ImportError:
        HAS_OFFICIAL_MCP = False
        MCPServer = None

logger = logging.getLogger("sclass_mcp_server")


def create_mcp_server(workspace_dir: Optional[str] = None) -> Optional[Any]:
    """
    Creates and returns an official Model Context Protocol (MCP) server instance
    using the official mcp SDK (MCPServer / FastMCP).
    """
    if not HAS_OFFICIAL_MCP or MCPServer is None:
        return None

    ws = workspace_dir or os.getcwd()
    server = MCPServer("sclass-governor", instructions="S-Class Governance and Control Plane MCP Server")

    @server.tool(name="sclass_initialize", description="Initialize S-Class EOS state & strategy")
    def sclass_initialize_tool(goal: str = "", profile: Optional[str] = None, workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_initialize", {"goal": goal, "profile": profile}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_get_state", description="Get current S-Class EOS FSM state")
    def sclass_get_state_tool(workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_get_state", {}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_dispatch", description="Dispatch FSM transition event")
    def sclass_dispatch_tool(event_name: str, enforce_evidence: bool = False, workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_dispatch", {"event_name": event_name, "enforce_evidence": enforce_evidence}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_reset_to_triage", description="Reset workflow to TRIAGE on goal update")
    def sclass_reset_to_triage_tool(new_goal: str = "", workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_reset_to_triage", {"new_goal": new_goal}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_memory_search", description="Semantic search in learning memory")
    def sclass_memory_search_tool(query: str, top_k: int = 5, workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_memory_search", {"query": query, "top_k": top_k}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_doctor", description="Inspect workspace environment health")
    def sclass_doctor_tool(workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_doctor", {}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_gc", description="Garbage collect stale state & lock files")
    def sclass_gc_tool(workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_gc", {}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_audit_replay", description="Audit deterministic execution replay trail")
    def sclass_audit_replay_tool(workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_audit_replay", {}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_security_scan", description="Scan file for secrets & vulnerabilities")
    def sclass_security_scan_tool(target_file: str, workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_security_scan", {"target_file": target_file}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_strategy_planner", description="Infer workflow profile and execution strategy")
    def sclass_strategy_planner_tool(goal: str, workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_strategy_planner", {"goal": goal}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_planner", description="Alias for sclass_strategy_planner")
    def sclass_planner_tool(goal: str, workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_planner", {"goal": goal}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_spec_synthesis", description="Synthesize evidence-driven specification and semantic gate")
    def sclass_spec_synthesis_tool(goal: str = "Fullstack App Build", workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_spec_synthesis", {"raw_intent": goal}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_preflight_scan", description="Run 100% upfront workspace AST and project discovery")
    def sclass_preflight_scan_tool(workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_preflight_scan", {}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_advance_fsm", description="Advance FSM one step forward")
    def sclass_advance_fsm_tool(workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_advance_fsm", {}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_goal", description="Execute full autonomous goal sequence (/goal)")
    def sclass_goal_tool(goal: str, profile: str = "full", max_steps: int = 10, workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_goal", {"goal": goal, "profile": profile, "max_steps": max_steps}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_boost", description="Execute high-velocity swarm execution (/boost)")
    def sclass_boost_tool(goal_or_task: str, max_steps: int = 5, workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_boost", {"goal_or_task": goal_or_task, "max_steps": max_steps}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    @server.tool(name="sclass_learn", description="Capture or inspect learned principles and promote candidates (/learn)")
    def sclass_learn_tool(pattern: Optional[str] = None, fix_description: Optional[str] = None, workspace_dir: Optional[str] = None) -> str:
        res = handle_tool_call("sclass_learn", {"pattern": pattern, "fix_description": fix_description}, workspace_dir=workspace_dir or ws)
        return json.dumps(res, indent=2)

    # === MCP Resources ===
    @server.resource("sclass://orchestration/state")
    def get_orchestration_state_resource() -> str:
        """Exposes current authoritative FSM orchestration state as an MCP resource."""
        state = runtime.get_state(ws)
        return json.dumps(asdict(state), indent=2)

    @server.resource("sclass://orchestration/history")
    def get_orchestration_history_resource() -> str:
        """Exposes complete FSM state transition and decision audit history."""
        state = runtime.get_state(ws)
        return json.dumps(state.transitionHistory, indent=2)

    # === MCP Prompts ===
    @server.prompt(name="sclass_goal_workflow", description="Autonomous goal execution playbook under S-Class governance")
    def sclass_goal_workflow_prompt(goal: str = "Implement feature with end-to-end testing"):
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"You are executing under S-Class governance microkernel.\nTarget Goal: {goal}\n\nPlease inspect current state via sclass://orchestration/state, synthesize spec via sclass_spec_synthesis, and advance through FSM phases with rigorous evidence verification."
                }
            }
        ]

    @server.prompt(name="sclass_audit_investigation", description="Replay audit and evidence verification investigation")
    def sclass_audit_investigation_prompt():
        replay_res = replay.ReplayEngine.audit_replay(ws)
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"Perform an audit investigation on S-Class execution trail.\nReplay Report:\n{json.dumps(asdict(replay_res), indent=2)}"
                }
            }
        ]

    return server


def handle_tool_call(tool_name: str, arguments: Dict[str, Any], workspace_dir: Optional[str] = None) -> Dict[str, Any]:
    """Routes MCP tool calls to S-Class EOS python APIs."""
    ws = workspace_dir or arguments.get("workspace_dir", os.getcwd())
    workspace_dir = ws

    if tool_name == "sclass_initialize":
        goal = arguments.get("goal", "")
        profile = arguments.get("profile")
        runtime.initialize_state(workspace_dir, goal=goal, profile=profile)
        state = runtime.get_state(workspace_dir)
        return {
            "status": "initialized",
            "state": asdict(state),
            "complexity_tier": getattr(state, "complexityTier", "feature"),
            "complexity_decision": getattr(state, "complexityDecision", "")
        }

    elif tool_name == "sclass_get_state":
        state = runtime.get_state(workspace_dir)
        return {
            "state": asdict(state),
            "complexity_tier": getattr(state, "complexityTier", "feature"),
            "complexity_decision": getattr(state, "complexityDecision", "")
        }

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

    elif tool_name in ["sclass_strategy_planner", "sclass_planner"]:
        goal = arguments.get("goal", "")
        exec_plan = ExecutionPlanner.create_plan(goal, workspace_dir=workspace_dir)
        try:
            plan = MetaPlanner.classify_goal(goal)
        except AttributeError:
            plan = MetaPlanner.select_profile(goal)
        return {
            "profile": plan.profile.value,
            "rationale": plan.rationale,
            "strategy": exec_plan.to_dict()
        }

    elif tool_name == "sclass_spec_synthesis":
        from spec_synthesis import SpecSynthesisEngine
        raw_intent = arguments.get("raw_intent", arguments.get("raw_request", "Fullstack App Build"))
        spec = None
        try:
            engine = SpecSynthesisEngine()
            spec = engine.run_synthesis(raw_request=raw_intent, workspace_dir=workspace_dir)
        except (TypeError, AttributeError):
            try:
                spec = SpecSynthesisEngine.run_synthesis(raw_intent=raw_intent, workspace_dir=workspace_dir)
            except Exception:
                engine = SpecSynthesisEngine()
                spec = engine.run_synthesis(raw_intent=raw_intent, workspace_dir=workspace_dir)
        except Exception:
            try:
                spec = SpecSynthesisEngine.run_synthesis(raw_intent=raw_intent, workspace_dir=workspace_dir)
            except Exception:
                spec = SpecSynthesisEngine.run_synthesis(raw_request=raw_intent, workspace_dir=workspace_dir)
        if hasattr(spec, "to_dict"):
            spec_data = spec.to_dict()
        elif is_dataclass(spec):
            spec_data = asdict(spec)
        elif hasattr(spec, "__dict__"):
            spec_data = spec.__dict__
        else:
            spec_data = str(spec)
        return {"synthesized_spec": spec_data}

    elif tool_name == "sclass_preflight_scan":
        from workspace_preflight_scanner import WorkspacePreflightScanner
        discovery = WorkspacePreflightScanner.full_project_discovery(workspace_dir)
        return {"project_discovery": discovery}

    elif tool_name == "sclass_advance_fsm":
        advance_res = runtime.FSMGoalSequenceRunner.advance_one_state(workspace_dir)
        return {"advance_result": advance_res}

    elif tool_name == "sclass_run_goal_sequence" or tool_name == "sclass_goal":
        from sdk_interface import SClassSDK
        sdk = SClassSDK(workspace_dir=workspace_dir)
        goal = arguments.get("goal", "Autonomous Objective")
        return sdk.execute_goal(goal=goal)

    elif tool_name == "sclass_boost":
        from sdk_interface import SClassSDK
        sdk = SClassSDK(workspace_dir=workspace_dir)
        task = arguments.get("task", arguments.get("goal", "High-Velocity Task"))
        return sdk.execute_boost(goal_or_task=task)

    elif tool_name == "sclass_learn":
        from sdk_interface import SClassSDK
        sdk = SClassSDK(workspace_dir=workspace_dir)
        pattern = arguments.get("pattern")
        fix = arguments.get("fix_description")
        return sdk.execute_learn(pattern=pattern, fix_description=fix)

    else:
        raise ValueError(f"Unknown MCP tool: {tool_name}")


def main():
    """Stdio MCP Server entrypoint using official MCP SDK with fallback."""
    if HAS_OFFICIAL_MCP and not os.environ.get("SCLASS_LEGACY_MCP"):
        server = create_mcp_server()
        if server is not None:
            logger.info("Starting official Model Context Protocol (MCP) SDK Server on stdio...")
            server.run(transport="stdio")
            return

    _legacy_stdio_loop()


def _legacy_stdio_loop():
    """Fallback Stdio JSON-RPC MCP Server listener loop."""
    logger.info("S-Class EOS MCP Server started on stdio (fallback mode).")
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
                            {"name": "sclass_preflight_scan", "description": "Run 100% upfront workspace AST and project discovery"},
                            {"name": "sclass_advance_fsm", "description": "Advance FSM one step forward"},
                            {"name": "sclass_goal", "description": "Execute full autonomous goal sequence (/goal)"},
                            {"name": "sclass_boost", "description": "Execute high-velocity swarm execution (/boost)"},
                            {"name": "sclass_learn", "description": "Capture or inspect learned principles and promote candidates (/learn)"}
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
