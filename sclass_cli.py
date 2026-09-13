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

try:
    import typer
    HAS_TYPER = True
except ImportError:
    typer = None
    HAS_TYPER = False

cli_app = typer.Typer(
    name="sclass",
    help="S-Class: Authoritative AI Coding Control Plane & Execution Microkernel",
    add_completion=False,
    no_args_is_help=False
) if HAS_TYPER else None


def _resolve_workspace(workspace: Optional[str] = None) -> str:
    """Authoritatively resolves target workspace directory and sets SCLASS_WORKSPACE env var."""
    resolved = (
        workspace
        or os.environ.get("SCLASS_WORKSPACE")
        or os.environ.get("WORKSPACE_DIR")
        or os.getcwd()
    )
    target = os.path.abspath(resolved)
    os.makedirs(target, exist_ok=True)
    os.environ["SCLASS_WORKSPACE"] = target
    return target


if cli_app is not None:
    @cli_app.command(name="goal", help="Autonomous Goal Execution across the FSM (/goal)")
    def _typer_goal(
        objective: str = typer.Argument("Autonomous Objective", help="Objective description to execute"),
        workspace: Optional[str] = typer.Option(None, "--workspace", "-w", "--dir", "-C", help="Target external workspace directory")
    ):
        ws = _resolve_workspace(workspace)
        sdk = SClassSDK(workspace_dir=ws)
        print(f"[*] Executing S-Class /goal in workspace: {sdk.workspace_dir}")
        res = sdk.execute_goal(goal=objective)
        print_result_with_epistemic_provenance(res)

    @cli_app.command(name="boost", help="High-velocity swarm execution with CKG pre-indexing (/boost)")
    def _typer_boost(
        task: str = typer.Argument("High-Velocity Task", help="Task description to execute"),
        workspace: Optional[str] = typer.Option(None, "--workspace", "-w", "--dir", "-C", help="Target external workspace directory")
    ):
        ws = _resolve_workspace(workspace)
        sdk = SClassSDK(workspace_dir=ws)
        print(f"[*] Executing S-Class /boost in workspace: {sdk.workspace_dir}")
        res = sdk.execute_boost(goal_or_task=task)
        print_result_with_epistemic_provenance(res)

    @cli_app.command(name="learn", help="Automated learning capture and memory promotion (/learn)")
    def _typer_learn(
        pattern: Optional[str] = typer.Argument(None, help="Failure pattern to capture"),
        fix: str = typer.Argument("Learned engineering principle", help="Fix description"),
        workspace: Optional[str] = typer.Option(None, "--workspace", "-w", "--dir", "-C", help="Target external workspace directory")
    ):
        ws = _resolve_workspace(workspace)
        sdk = SClassSDK(workspace_dir=ws)
        print(f"[*] Executing S-Class /learn in workspace: {sdk.workspace_dir} (pattern: {pattern or 'all'})")
        res = sdk.execute_learn(pattern=pattern, fix_description=fix if pattern else None)
        print(json.dumps(res, indent=2))

    @cli_app.command(name="status", help="Current FSM state and task pipeline summary (/status)")
    def _typer_status(
        json_output: bool = typer.Option(False, "--json", help="Output raw JSON state only"),
        workspace: Optional[str] = typer.Option(None, "--workspace", "-w", "--dir", "-C", help="Target external workspace directory")
    ):
        ws = _resolve_workspace(workspace)
        sdk = SClassSDK(workspace_dir=ws)
        state = sdk.get_fsm_state()
        if not json_output:
            render_rich_status(state, sdk.workspace_dir)
        print(json.dumps(state, indent=2))

    @cli_app.command(name="watch", help="Real-time FSM watch monitor & terminal dashboard (/watch)")
    def _typer_watch(
        workspace: Optional[str] = typer.Option(None, "--workspace", "-w", "--dir", "-C", help="Target external workspace directory")
    ):
        ws = _resolve_workspace(workspace)
        sdk = SClassSDK(workspace_dir=ws)
        try:
            import sclass_watch_tui
            if sclass_watch_tui.HAS_TEXTUAL and sys.stdout.isatty():
                return sclass_watch_tui.launch_watch_tui(workspace_dir=sdk.workspace_dir)
        except Exception:
            pass
        return run_watch_dashboard(workspace=sdk.workspace_dir)

    @cli_app.command(name="advance", help="Step FSM forward one state (/advance)")
    def _typer_advance(
        workspace: Optional[str] = typer.Option(None, "--workspace", "-w", "--dir", "-C", help="Target external workspace directory")
    ):
        ws = _resolve_workspace(workspace)
        sdk = SClassSDK(workspace_dir=ws)
        print(f"[*] S-Class Advancing phase in workspace: {sdk.workspace_dir}")
        res = sdk.advance_phase()
        print(json.dumps(res, indent=2))


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


def render_rich_status(state: Dict[str, Any], workspace: str) -> None:
    """Renders formatted Rich terminal panels for FSM state and execution pipeline."""
    try:
        from rich.console import Console, Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        console = Console()
        phase = state.get("currentPhase", "TRIAGE")
        status = state.get("status", "INITIALIZED")
        phase_color = "green" if phase in ("DONE", "RELEASE") else "cyan" if "CODING" in phase else "yellow"

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_row("[bold]Workspace:[/bold]", f"[blue]{workspace}[/blue]")
        table.add_row("[bold]Current Phase:[/bold]", f"[{phase_color} bold]{phase}[/{phase_color} bold]")
        table.add_row("[bold]FSM Status:[/bold]", f"[bold]{status}[/bold]")
        table.add_row("[bold]Goal:[/bold]", f"[white]{state.get('goal', 'None')}[/white]")

        phases = ["TRIAGE", "SPEC", "DESIGN", "DEBATE", "CODING", "VERIFY", "RELEASE"]
        pipeline_strs = []
        for p in phases:
            if p == phase:
                pipeline_strs.append(f"[bold reverse {phase_color}] {p} [/bold reverse {phase_color}]")
            else:
                pipeline_strs.append(f"[dim]{p}[/dim]")
        pipeline_view = " ➔ ".join(pipeline_strs)

        content = Group(
            table,
            Text(""),
            Text.from_markup(f"[bold]Pipeline Lifecycle:[/bold] {pipeline_view}")
        )

        panel = Panel(
            content,
            title="[bold blue]S-Class V13 Governance Kernel[/bold blue]",
            subtitle="Deterministic Control Plane",
            border_style="blue"
        )
        console.print(panel)
    except Exception:
        pass


def run_watch_dashboard(workspace: str, poll_interval: float = 1.0, max_iterations: Optional[int] = None) -> int:
    """
    Live real-time monitoring dashboard for S-Class FSM, task lifecycle, and active subagents.
    """
    try:
        import time
        from rich.console import Console
        from rich.live import Live
        from rich.panel import Panel
        from rich.table import Table

        console = Console()
        sdk = SClassSDK(workspace_dir=workspace)
        console.print(f"[bold cyan][*] S-Class Live Watch Monitor Active for:[/bold cyan] {workspace}")

        iterations = 0
        with Live(console=console, refresh_per_second=2) as live:
            while True:
                state = sdk.get_fsm_state()
                phase = state.get("currentPhase", "TRIAGE")
                status = state.get("status", "ACTIVE")
                phase_color = "green" if phase == "DONE" else "cyan" if "CODING" in phase else "yellow"

                table = Table(title=f"S-Class Live Monitor - {os.path.basename(workspace)}", expand=True)
                table.add_column("Property", style="bold cyan")
                table.add_column("Value", style="bold white")

                table.add_row("Phase", f"[{phase_color} bold]{phase}[/{phase_color} bold]")
                table.add_row("Status", status)
                table.add_row("Workspace", workspace)
                prov = state.get("provenance", {})
                synth = prov.get("synthetic", True)
                table.add_row("Epistemic Grounding", "[yellow]SYNTHETIC (Simulated)[/yellow]" if synth else "[green]REALITY GROUNDED[/green]")

                panel = Panel(table, title="[bold green]Live FSM Dashboard[/bold green]", border_style="green")
                live.update(panel)

                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break
                time.sleep(poll_interval)
        return 0
    except (KeyboardInterrupt, SystemExit):
        return 0
    except Exception as e:
        print(f"[-] Error running watch monitor: {e}")
        return 1


def print_help() -> None:
    print("S-Class V13 Control Plane CLI")
    print("Supported slash commands: /goal, /boost, /learn, /status, /watch, /advance, /grill, /doubt, /inquire")
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
        if "--json" not in remaining:
            render_rich_status(state, sdk.workspace_dir)
        print(json.dumps(state, indent=2))
        return 0

    elif cmd in ("/watch", "watch"):
        try:
            import sclass_watch_tui
            if sclass_watch_tui.HAS_TEXTUAL and sys.stdout.isatty():
                return sclass_watch_tui.launch_watch_tui(workspace_dir=sdk.workspace_dir)
        except Exception:
            pass
        return run_watch_dashboard(workspace=sdk.workspace_dir)

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
