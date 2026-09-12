"""
S-Class V12: Dedicated CLI & Slash Command Dispatcher (sclass_cli.py)

Exposes command-line and interactive interfaces for S-Class slash commands:
- /goal [objective]   : Autonomous Goal Execution across the 11-state FSM
- /boost [task]       : High-velocity swarm execution with CKG pre-indexing and parallel agents
- /learn [pattern]    : Automated learning capture, memory inspection, and KB promotion
- /status             : Current FSM state and task pipeline summary
- /advance            : Steps the FSM forward one state
- /grill [spec]       : Red-teaming plan stress test across 5 threat vectors
- /doubt [question]   : Non-interrupting read-only architectural inquiry
- /inquire [query]    : Read-only symbol and dependency query
"""

import sys
import os
import json
import argparse
from typing import Optional, List, Dict, Any

from sdk_interface import SClassSDK


def run_cli(argv: Optional[List[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("S-Class V12 Control Plane CLI")
        print("Supported slash commands: /goal, /boost, /learn, /status, /advance, /grill, /doubt, /inquire")
        print("Usage: python sclass_cli.py </command> [arguments...]")
        return 0

    command_raw = args[0]
    if command_raw in ("-h", "--help", "help"):
        print("S-Class V12 Control Plane CLI")
        print("Supported slash commands: /goal, /boost, /learn, /status, /advance, /grill, /doubt, /inquire")
        print("Usage: python sclass_cli.py </command> [arguments...]")
        return 0

    # Normalize command: accept either '/goal' or 'goal'
    cmd = command_raw if command_raw.startswith("/") else f"/{command_raw}"
    rest = " ".join(args[1:]) if len(args) > 1 else ""

    sdk = SClassSDK()

    if cmd == "/goal":
        goal_text = rest or "Autonomous Objective"
        print(f"[*] Executing S-Class /goal: {goal_text}")
        res = sdk.execute_goal(goal=goal_text)
        print(json.dumps(res, indent=2))
        return 0

    elif cmd == "/boost":
        boost_task = rest or "High-Velocity Task"
        print(f"[*] Executing S-Class /boost: {boost_task}")
        res = sdk.execute_boost(goal_or_task=boost_task)
        print(json.dumps(res, indent=2))
        return 0

    elif cmd == "/learn":
        pattern = args[1] if len(args) > 1 else None
        fix = args[2] if len(args) > 2 else "Learned engineering principle"
        print(f"[*] Executing S-Class /learn (pattern: {pattern or 'all'})")
        res = sdk.execute_learn(pattern=pattern, fix_description=fix if pattern else None)
        print(json.dumps(res, indent=2))
        return 0

    elif cmd == "/status":
        state = sdk.get_fsm_state()
        print(json.dumps(state, indent=2))
        return 0

    elif cmd == "/advance":
        res = sdk.advance_phase()
        print(json.dumps(res, indent=2))
        return 0

    elif cmd == "/grill":
        from sclass_grill import SpecGrillerEngine
        report = SpecGrillerEngine.grill_specification(workspace_dir=sdk.workspace_dir)
        print(json.dumps({
            "overall_passed": report.overall_passed,
            "critical_defects": report.critical_defects_found,
            "vectors_tested": report.total_vectors_tested,
        }, indent=2))
        return 0 if report.overall_passed else 1

    elif cmd in ("/doubt", "/inquire"):
        query = rest or ""
        print(f"[*] S-Class Read-Only Inquiry: {query}")
        nodes = sdk.query_graph(pattern=query)
        print(json.dumps({
            "query": query,
            "matching_symbols_count": len(nodes),
            "symbols": nodes[:10],
        }, indent=2))
        return 0

    else:
        print(f"[-] Unknown command: {command_raw}")
        print("Supported commands: /goal, /boost, /learn, /status, /advance, /grill, /doubt, /inquire")
        return 1


if __name__ == "__main__":
    sys.exit(run_cli())
