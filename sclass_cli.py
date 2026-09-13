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
from datetime import datetime, timezone
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



    @cli_app.command(name="init", help="Detects platforms and installs IDE hooks with optional rule projection")
    def _typer_init(
        no_rules: bool = typer.Option(False, "--no-rules", help="Install hooks only; skip rule projection"),
        workspace: Optional[str] = typer.Option(None, "--workspace", "-w", "--dir", "-C", help="Target external workspace directory")
    ):
        ws = _resolve_workspace(workspace)
        res = execute_init_command(workspace_dir=ws, no_rules=no_rules)
        print(json.dumps(res, indent=2))

    @cli_app.command(name="strict", help="Upgrades an adapter from warn mode to blocking enforcement")
    def _typer_strict(
        platform: str = typer.Option(..., "--platform", "-p", help="Target platform name (claude_code, cursor, codex, antigravity, copilot, windsurf)"),
        workspace: Optional[str] = typer.Option(None, "--workspace", "-w", "--dir", "-C", help="Target external workspace directory")
    ):
        ws = _resolve_workspace(workspace)
        res = execute_strict_command(workspace_dir=ws, platform=platform)
        print(json.dumps(res, indent=2))

    @cli_app.command(name="hooks", help="Inspects platform hook installation and verification status")
    def _typer_hooks(
        subcommand: str = typer.Argument("status", help="Subcommand (status)"),
        workspace: Optional[str] = typer.Option(None, "--workspace", "-w", "--dir", "-C", help="Target external workspace directory")
    ):
        ws = _resolve_workspace(workspace)
        if subcommand == "status":
            res = execute_hooks_status_command(workspace_dir=ws)
            print(json.dumps(res, indent=2))
        else:
            print(f"[-] Unknown hooks subcommand: {subcommand}. Expected 'status'.")



def execute_init_command(workspace_dir: str, no_rules: bool = False) -> Dict[str, Any]:
    """Detects platforms, initializes .agents/sclass_hooks.json, installs hook configs, and projects rules."""
    from adapters import detect_platforms
    from adapters.claude_code import ClaudeCodeAdapter
    from adapters.cursor import CursorAdapter
    from adapters.codex_cli import CodexCliAdapter
    from adapters.antigravity import AntigravityAdapter
    from adapters.copilot import CopilotAdapter
    from adapters.windsurf import WindsurfAdapter
    from rule_generator import PlatformRuleGenerator

    state_dir = os.path.join(workspace_dir, ".agents")
    os.makedirs(state_dir, exist_ok=True)
    detected = detect_platforms(workspace_dir)

    hooks_cfg_path = os.path.join(state_dir, "sclass_hooks.json")
    installed_at = datetime.now(timezone.utc).isoformat()
    existing_enforcement = {}
    existing_verified = {}

    if os.path.exists(hooks_cfg_path):
        try:
            with open(hooks_cfg_path, "r", encoding="utf-8") as f:
                old = json.load(f)
            installed_at = old.get("installed_at", installed_at)
            existing_enforcement = old.get("enforcement_mode", {})
            existing_verified = old.get("last_verified", {})
        except Exception:
            pass

    installed_adapters = {}
    for plat in detected.keys():
        mode = existing_enforcement.get(plat, "warn")
        strict_mode = mode == "block"
        if plat == "claude_code":
            installed_adapters[plat] = ClaudeCodeAdapter(workspace_dir=workspace_dir).install_hooks(strict=strict_mode)
        elif plat == "cursor":
            installed_adapters[plat] = CursorAdapter(workspace_dir=workspace_dir).install_hooks(strict=strict_mode)
        elif plat == "codex":
            installed_adapters[plat] = CodexCliAdapter(workspace_dir=workspace_dir).install_hooks(strict=strict_mode)
        elif plat == "antigravity":
            installed_adapters[plat] = AntigravityAdapter(workspace_dir=workspace_dir).install_hooks(strict=strict_mode)
        elif plat == "copilot":
            installed_adapters[plat] = CopilotAdapter(workspace_dir=workspace_dir).install_hooks(strict=strict_mode)
        elif plat == "windsurf":
            installed_adapters[plat] = WindsurfAdapter(workspace_dir=workspace_dir).install_hooks(strict=strict_mode)

    cfg = {
        "version": 1,
        "installed_at": installed_at,
        "platforms_detected": list(detected.keys()),
        "enforcement_mode": {p: existing_enforcement.get(p, "warn") for p in detected.keys()},
        "last_verified": {p: existing_verified.get(p, None) for p in detected.keys()},
    }
    with open(hooks_cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    rule_projections = {}
    if not no_rules:
        rg = PlatformRuleGenerator(workspace_dir=workspace_dir)
        rule_projections = rg.generate_all_projections(platforms=list(detected.keys()), no_rules=False)

    return {
        "workspace": workspace_dir,
        "status": "SUCCESS",
        "platforms_detected": list(detected.keys()),
        "installed_adapters": installed_adapters,
        "rules_projected": list(rule_projections.keys()) if not no_rules else "SKIPPED (--no-rules)",
        "enforcement_mode": cfg["enforcement_mode"],
        "initial_status": "UNVERIFIED (awaiting first real event)",
    }


def execute_strict_command(workspace_dir: str, platform: str) -> Dict[str, Any]:
    """Upgrades platform enforcement mode from warn to block."""
    from adapters import detect_platforms
    state_dir = os.path.join(workspace_dir, ".agents")
    hooks_cfg_path = os.path.join(state_dir, "sclass_hooks.json")
    if not os.path.exists(hooks_cfg_path):
        return {"error": "Hooks not initialized. Run sclass init first."}

    with open(hooks_cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    norm_plat = platform.lower().strip()
    if norm_plat not in cfg.get("enforcement_mode", {}):
        return {"error": f"Platform '{platform}' not configured in {hooks_cfg_path}"}

    cfg["enforcement_mode"][norm_plat] = "block"
    with open(hooks_cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    # Re-apply adapter with strict=True
    execute_init_command(workspace_dir=workspace_dir, no_rules=True)

    return {
        "workspace": workspace_dir,
        "platform": norm_plat,
        "mode": "block",
        "message": f"Upgraded {norm_plat} to blocking enforcement mode.",
    }


def execute_hooks_status_command(workspace_dir: str) -> Dict[str, Any]:
    """Inspects platform hook status, separating static capabilities from dynamic verified state."""
    from adapters import detect_platforms
    detections = detect_platforms(workspace_dir)
    return {
        "workspace": workspace_dir,
        "platforms": {p: info.to_dict() for p, info in detections.items()},
        "active_enforcement_targets": len(detections),
    }


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

    elif cmd in ("init", "/init"):
        no_rules = "--no-rules" in remaining
        res = execute_init_command(workspace_dir=sdk.workspace_dir, no_rules=no_rules)
        print(json.dumps(res, indent=2))
        return 0

    elif cmd in ("strict", "/strict"):
        plat = None
        for i, a in enumerate(remaining):
            if a in ("--platform", "-p") and i + 1 < len(remaining):
                plat = remaining[i + 1]
            elif a.startswith("--platform="):
                plat = a.split("=", 1)[1]
        if not plat and len(remaining) > 1 and not remaining[1].startswith("-"):
            plat = remaining[1]
        if not plat:
            print("[-] Error: --platform/-p argument is required for strict command.")
            return 1
        res = execute_strict_command(workspace_dir=sdk.workspace_dir, platform=plat)
        print(json.dumps(res, indent=2))
        return 0

    elif cmd in ("hooks", "/hooks"):
        sub = "status"
        if len(remaining) > 1 and not remaining[1].startswith("-"):
            sub = remaining[1]
        if sub == "status":
            res = execute_hooks_status_command(workspace_dir=sdk.workspace_dir)
            print(json.dumps(res, indent=2))
            return 0
        else:
            print(f"[-] Unknown hooks subcommand: {sub}. Expected 'status'.")
            return 1

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
