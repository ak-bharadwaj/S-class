"""
S-Class V13: Dedicated CLI & Slash Command Dispatcher (sclass_cli.py)

Exposes command-line and interactive interfaces for S-Class slash commands:
- /goal [objective]   : Autonomous Goal Execution across the FSM
- /boost [task]       : High-velocity swarm execution with CKG pre-indexing and parallel agents
- /learn [pattern]    : Automated learning capture, memory inspection, and KB promotion
- /status             : Current FSM state and task pipeline summary
- /advance            : Steps the FSM forward one state
- /grill [spec]       : Red-teaming plan stress test across 5 threat vectors
- /doubt [question]   : Non-interrupting read-only architectural inquiry
- /inquire [query]    : Read-only symbol and dependency query

External Workspace Options (can be placed before or after command):
- -w, --workspace <path> : Target external workspace directory
- --target <path>        : Target external workspace directory
- --dir <path>           : Target external workspace directory
- -C <path>              : Target external workspace directory
Environment variable fallback: SCLASS_WORKSPACE or WORKSPACE_DIR
"""

import sys
import os
import json
from typing import Optional, List, Dict, Any, Tuple

from sdk_interface import SClassSDK


def extract_workspace_arg(argv: List[str]) -> Tuple[Optional[str], List[str]]:
    """
    Extracts --workspace/-w/--target/--dir/-C from argv without interfering with slash commands.
    Returns (workspace_dir, remaining_argv).
    """
    workspace_dir = None
    remaining = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--workspace", "-w", "--target", "--dir", "-C"):
            if i + 1 < len(argv):
                workspace_dir = argv[i + 1]
                i += 2
                continue
            else:
                # Flag with no value
                i += 1
                continue
        elif any(arg.startswith(prefix) for prefix in ("--workspace=", "-w=", "--target=", "--dir=", "-C=")):
            workspace_dir = arg.split("=", 1)[1]
            i += 1
            continue
        else:
            remaining.append(arg)
            i += 1
    return workspace_dir, remaining


def print_result_with_epistemic_provenance(res: Dict[str, Any]) -> None:
    """Prints result JSON and highlights epistemic provenance warning if synthetic."""
    print(json.dumps(res, indent=2))
    provenance = res.get("provenance", {})
    if provenance.get("synthetic"):
        print("\n" + "=" * 70)
        print(" [!] S-CLASS EPISTEMIC NOTICE: SYNTHETIC SIMULATION RUN")
        print(f"     Authority: {provenance.get('authority', 'UNKNOWN')}")
        print(f"     Mode:      {provenance.get('execution_mode', 'TEST')}")
        if provenance.get("epistemic_warning"):
            print(f"     Warning:   {provenance.get('epistemic_warning')}")
        if provenance.get("source_files"):
            print(f"     Synthesized Starter Code: {', '.join(provenance.get('source_files', []))}")
        else:
            print("     Source Code: None generated (pipeline simulation only)")
        print("=" * 70 + "\n")


def print_help() -> None:
    print("S-Class V13 Control Plane CLI")
    print("Supported slash commands: /goal, /boost, /learn, /status, /advance, /grill, /doubt, /inquire")
    print("\nUsage:")
    print("  python sclass_cli.py [-w <workspace>] </command> [arguments...]")
    print("  python sclass_cli.py </command> [arguments...] [-w <workspace>]")
    print("\nWorkspace Options:")
    print("  -w, --workspace <path>    Target external project workspace directory")
    print("  --target <path>           Alias for --workspace")
    print("  --dir <path>              Alias for --workspace")
    print("  -C <path>                 Git-style directory switch")
    print("  Environment variable:     SCLASS_WORKSPACE or WORKSPACE_DIR")
    print("\nExamples:")
    print("  python sclass_cli.py -w /path/to/my-project /status")
    print("  python sclass_cli.py /goal \"implement rate limiter\" --workspace /path/to/my-project")
    print("  python sclass_cli.py -w ./backend /boost \"optimize database pool\"")


def run_cli(argv: Optional[List[str]] = None) -> int:
    raw_args = argv if argv is not None else sys.argv[1:]

    # Extract workspace flag if present
    parsed_ws, remaining = extract_workspace_arg(raw_args)

    if not remaining:
        print_help()
        return 0

    command_raw = remaining[0]
    if command_raw in ("-h", "--help", "help"):
        print_help()
        return 0

    # Resolve target workspace
    resolved_ws = (
        parsed_ws
        or os.environ.get("SCLASS_WORKSPACE")
        or os.environ.get("WORKSPACE_DIR")
        or os.getcwd()
    )
    target_workspace = os.path.abspath(resolved_ws)
    os.makedirs(target_workspace, exist_ok=True)
    os.environ["SCLASS_WORKSPACE"] = target_workspace

    # Normalize command: accept either '/goal' or 'goal'
    cmd = command_raw if command_raw.startswith("/") else f"/{command_raw}"
    rest = " ".join(remaining[1:]) if len(remaining) > 1 else ""

    sdk = SClassSDK(workspace_dir=target_workspace)

    if cmd == "/goal":
        goal_text = rest or "Autonomous Objective"
        print(f"[*] Executing S-Class /goal in workspace: {sdk.workspace_dir}")
        res = sdk.execute_goal(goal=goal_text)
        print_result_with_epistemic_provenance(res)
        return 0

    elif cmd == "/boost":
        boost_task = rest or "High-Velocity Task"
        print(f"[*] Executing S-Class /boost in workspace: {sdk.workspace_dir}")
        res = sdk.execute_boost(goal_or_task=boost_task)
        print_result_with_epistemic_provenance(res)
        return 0

    elif cmd == "/learn":
        pattern = remaining[1] if len(remaining) > 1 else None
        fix = remaining[2] if len(remaining) > 2 else "Learned engineering principle"
        print(f"[*] Executing S-Class /learn in workspace: {sdk.workspace_dir} (pattern: {pattern or 'all'})")
        res = sdk.execute_learn(pattern=pattern, fix_description=fix if pattern else None)
        print(json.dumps(res, indent=2))
        return 0

    elif cmd == "/status":
        state = sdk.get_fsm_state()
        print(json.dumps(state, indent=2))
        return 0

    elif cmd == "/advance":
        print(f"[*] S-Class Advancing phase in workspace: {sdk.workspace_dir}")
        res = sdk.advance_phase()
        print(json.dumps(res, indent=2))
        return 0

    elif cmd == "/grill":
        from sclass_grill import SpecGrillerEngine
        print(f"[*] S-Class Red-Teaming Plan (SpecGriller) in workspace: {sdk.workspace_dir}")
        report = SpecGrillerEngine.grill_specification(workspace_dir=sdk.workspace_dir)
        print(json.dumps({
            "workspace": sdk.workspace_dir,
            "overall_passed": report.overall_passed,
            "critical_defects": report.critical_defects_found,
            "vectors_tested": report.total_vectors_tested,
        }, indent=2))
        return 0 if report.overall_passed else 1

    elif cmd in ("/doubt", "/inquire"):
        query = rest or ""
        print(f"[*] S-Class Inquiry in workspace: {sdk.workspace_dir} (query: {query})")
        nodes = sdk.query_graph(pattern=query)
        print(json.dumps({
            "workspace": sdk.workspace_dir,
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
