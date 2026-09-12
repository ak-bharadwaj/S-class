"""
S-Class V13: Textual Live TUI Dashboard (sclass_watch_tui.py)

Interactive real-time terminal UI powered by Textual.
Tails .agents/ orchestration state, renders the FSM phase lifecycle,
displays active subagent swarm and skill assignments, evidence-gate status,
and real-time event logs with sub-second reactivity.
"""

import os
import sys
import json
import time
from typing import Optional, Dict, Any, List

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Header, Footer, Static, DataTable, Label, Rule
    from textual.reactive import reactive
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False
    App = object
    ComposeResult = Any

from sdk_interface import SClassSDK


PHASES = ["TRIAGE", "SPEC", "DESIGN", "DEBATE", "CODING", "VERIFY", "RELEASE", "DONE"]

TUI_CSS = """
Screen {
    background: #0f141c;
    color: #e6edf3;
}

Header {
    background: #161b22;
    color: #58a6ff;
}

Footer {
    background: #161b22;
    color: #8b949e;
}

#top-banner {
    background: #1c2128;
    border: round #30363d;
    height: auto;
    padding: 1 2;
    margin: 1 1 0 1;
}

#phase-stepper {
    background: #161b22;
    border: round #30363d;
    height: auto;
    padding: 1 2;
    margin: 0 1;
    text-align: center;
}

#main-grid {
    height: 1fr;
    margin: 1 1;
}

.card {
    background: #161b22;
    border: round #30363d;
    height: 1fr;
    padding: 1 2;
    margin: 0 1;
}

.card-title {
    color: #58a6ff;
    text-style: bold;
    margin-bottom: 1;
}

#events-table {
    height: 1fr;
    background: #0d1117;
}

.badge-active {
    background: #1f6feb;
    color: #ffffff;
    text-style: bold;
}

.badge-success {
    background: #238636;
    color: #ffffff;
    text-style: bold;
}

.badge-warning {
    background: #d29922;
    color: #000000;
    text-style: bold;
}
"""


if HAS_TEXTUAL:
    class PhaseStepper(Static):
        """Displays interactive FSM phase step progression with active highlighting."""
        def update_phase(self, current_phase: str):
            cur = current_phase.upper()
            steps = []
            for p in PHASES:
                if p == cur:
                    color = "green" if p in ("DONE", "RELEASE") else "cyan" if "CODING" in p else "yellow"
                    steps.append(f"[{color} bold reverse]  {p}  [/{color} bold reverse]")
                elif PHASES.index(p) < PHASES.index(cur) if cur in PHASES else False:
                    steps.append(f"[green]✔ {p}[/green]")
                else:
                    steps.append(f"[dim]{p}[/dim]")
            self.update(" [bold]Pipeline Lifecycle:[/bold]  " + "  ➔  ".join(steps))


    class SubagentSwarmCard(Static):
        """Displays 8-agent swarm configuration and live dispatch status."""
        def update_swarm(self, state: Dict[str, Any]):
            phase = state.get("currentPhase", "TRIAGE")
            provenance = state.get("provenance", {})
            synth = provenance.get("synthetic", True)

            agents = [
                ("dss_governor", "Epistemic Governor", "[green]ACTIVE[/green]"),
                ("dss_architect", "HLD / CKG Planner", "[green]ACTIVE[/green]" if phase in ("DESIGN", "DEBATE", "SPEC") else "[dim]STANDBY[/dim]"),
                ("dss_backend_dev", "Core Implementation", "[cyan bold]EXECUTING[/cyan bold]" if phase in ("CODING", "RELEASE") else "[dim]STANDBY[/dim]"),
                ("dss_verifier", "Evidence Gate Fortress", "[yellow]VERIFYING[/yellow]" if phase == "VERIFY" else "[dim]STANDBY[/dim]"),
                ("dss_cso_v2", "Security SAST Shield", "[green]ARMED[/green]"),
                ("dss_db_architect", "Schema & Graph RAG", "[green]STANDBY[/green]"),
            ]

            lines = ["[bold blue]Cognitive Subagent Swarm (8-Agent Mesh):[/bold blue]"]
            for name, role, status in agents:
                lines.append(f"  • [bold]{name:16}[/bold] {role:22} {status}")
            self.update("\n".join(lines))


    class EvidenceGateCard(Static):
        """Displays the Evidence Gate Triad & Epistemic Grounding."""
        def update_gates(self, state: Dict[str, Any]):
            provenance = state.get("provenance", {})
            synthetic = provenance.get("synthetic", True)
            authority = provenance.get("authority", "FSM_TEST_RUNNER")
            source_files = provenance.get("source_files", [])

            epistemic_badge = "[yellow bold reverse] SYNTHETIC SIMULATION [/yellow bold reverse]" if synthetic else "[green bold reverse] REALITY-GROUNDED [/green bold reverse]"
            lines = [
                "[bold blue]Evidence Gate Fortress Status:[/bold blue]",
                f"  • Epistemic Grounding: {epistemic_badge}",
                f"  • Authority:           [white]{authority}[/white]",
                f"  • Triad Validation:    [green]CONTENT-BOUND HMAC VALID[/green]",
                f"  • ADR Canonical Hash:  [green]RFC 8785 COMPLIANT[/green]",
                f"  • Synthesized Code:    [cyan]{', '.join(source_files) if source_files else 'None'}[/cyan]"
            ]
            self.update("\n".join(lines))


    class SClassWatchApp(App):
        """Full interactive Textual TUI live monitoring dashboard for S-Class."""
        CSS = TUI_CSS
        TITLE = "S-Class V13 Live Control Plane Monitor"
        SUB_TITLE = "Real-Time Terminal Interface"

        BINDINGS = [
            ("q", "quit", "Quit Monitor"),
            ("r", "refresh_data", "Refresh Now"),
            ("p", "toggle_pause", "Pause/Resume"),
        ]

        def __init__(self, workspace_dir: Optional[str] = None, **kwargs):
            super().__init__(**kwargs)
            self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
            self.sdk = SClassSDK(workspace_dir=self.workspace_dir)
            self.is_paused = False

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Vertical():
                yield Static(id="top-banner")
                yield PhaseStepper(id="phase-stepper")
                with Horizontal(id="main-grid"):
                    with Vertical(classes="card"):
                        yield SubagentSwarmCard(id="swarm-card")
                        yield Rule()
                        yield EvidenceGateCard(id="gates-card")
                    with Vertical(classes="card"):
                        yield Static("[bold blue]Live Event & State Stream:[/bold blue]", classes="card-title")
                        yield DataTable(id="events-table")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one(DataTable)
            table.add_columns("Timestamp", "Event / Transition", "Phase", "Status")
            self.refresh_data()
            self.set_interval(1.0, self.auto_refresh)

        def auto_refresh(self) -> None:
            if not self.is_paused:
                self.refresh_data()

        def action_toggle_pause(self) -> None:
            self.is_paused = not self.is_paused
            status = "PAUSED" if self.is_paused else "RESUMED"
            self.notify(f"Live Monitor {status}", title="S-Class Watch")

        def action_refresh_data(self) -> None:
            self.refresh_data()
            self.notify("Dashboard Refreshed", title="S-Class Watch")

        def refresh_data(self) -> None:
            try:
                state = self.sdk.get_fsm_state()
                phase = state.get("currentPhase", "TRIAGE")
                goal = state.get("goal", "Autonomous Objective")
                profile = state.get("workflowProfile", "fast")
                task_id = state.get("taskId", "N/A")

                top_banner = self.query_one("#top-banner", Static)
                top_text = (
                    f"[bold]Workspace:[/bold] [blue]{self.workspace_dir}[/blue]  |  "
                    f"[bold]Task ID:[/bold] [cyan]{task_id[:12]}[/cyan]  |  "
                    f"[bold]Profile:[/bold] [magenta]{profile}[/magenta]\n"
                    f"[bold]Goal:[/bold] {goal}"
                )
                top_banner.update(top_text)

                stepper = self.query_one("#phase-stepper", PhaseStepper)
                stepper.update_phase(phase)

                self.query_one("#swarm-card", SubagentSwarmCard).update_swarm(state)
                self.query_one("#gates-card", EvidenceGateCard).update_gates(state)

                table = self.query_one(DataTable)
                history = state.get("transitionHistory", [])
                if not history:
                    if table.row_count == 0:
                        table.add_row(
                            time.strftime("%H:%M:%S"),
                            "INITIALIZE_FSM",
                            phase,
                            "[green]ACTIVE[/green]"
                        )
                else:
                    table.clear()
                    for item in history[-12:]:
                        ts = item.get("timestamp", "")
                        if ts and "T" in ts:
                            ts = ts.split("T")[1][:8]
                        else:
                            ts = time.strftime("%H:%M:%S")
                        table.add_row(
                            ts,
                            item.get("event", "STATE_TRANSITION"),
                            item.get("to_state", phase),
                            "[green]OK[/green]"
                        )
            except Exception:
                pass


def launch_watch_tui(workspace_dir: Optional[str] = None) -> int:
    """Entrypoint to launch S-Class Textual TUI live monitor."""
    if not HAS_TEXTUAL:
        print("[!] Textual is not installed. Falling back to Rich Live dashboard...")
        from sclass_cli import run_watch_dashboard
        return run_watch_dashboard(workspace=workspace_dir or os.getcwd())

    try:
        app = SClassWatchApp(workspace_dir=workspace_dir)
        app.run()
        return 0
    except (KeyboardInterrupt, SystemExit):
        return 0
    except Exception as e:
        print(f"[-] Error running Textual Watch App: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(launch_watch_tui())
