"""
S-Class Integration: Standalone External Codex Agent CLI (RC.1.1).

Runs as an independent OS process (simulating or invoking OpenAI Codex CLI agent):
- Runs in dedicated external process boundary (distinct PID, session, stdout/stderr).
- Can execute in:
    1. --native: Unconstrained execution directly touching filesystem and shell.
    2. --governed: Connects to S-Class control plane / ACP bridge for real-time authorization.
- Tracks real execution telemetry: duration, token count, tool calls, and completion claims.
"""

from __future__ import annotations
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import time
import json
import uuid
import argparse
import subprocess
from typing import Dict, Any, List, Optional


def count_tokens(text: str) -> int:
    """Rough token estimation (4 chars per token) when tiktoken is unavailable."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


class SimulatedAgentProvider:
    """
    Simulated reference agent provider used for testing, benchmarking, and harnesses.
    Explicitly marked as simulated test infrastructure (real_provider = False).
    Commands route through canonical S-Class ExecutionProvider without shell=True.
    """
    provider_kind: str = "simulated"
    real_provider: bool = False

    def __init__(
        self,
        workspace_dir: str,
        session_id: Optional[str] = None,
        mode: str = "native",
        report_file: Optional[str] = None,
    ) -> None:
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.session_id = session_id or f"sim_sess_{uuid.uuid4().hex[:8]}"
        self.mode = mode.lower()
        self.report_file = report_file
        self.pid = os.getpid()

        self.steps_attempted = 0
        self.steps_completed = 0
        self.steps_blocked = 0
        self.unsafe_actions_attempted = 0
        self.unsafe_actions_blocked = 0
        self.tool_calls: List[Dict[str, Any]] = []
        self.total_tokens = 0

        # Lazy load S-Class adapter only in governed mode
        self.governor = None
        if self.mode == "governed":
            from sclass.integrations.codex.adapter import CodexAdapter
            self.governor = CodexAdapter(workspace_dir=self.workspace_dir, mode="enforce")

    def run_task(self, task_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the task steps autonomously."""
        t_start = time.perf_counter()
        steps = task_spec.get("steps", [])
        goal = task_spec.get("goal", "Autonomous task")

        # Initial prompt tokens
        self.total_tokens += count_tokens(json.dumps(task_spec))

        overall_success = True
        last_exit = 0

        for step in steps:
            self.steps_attempted += 1
            stype = step.get("type")
            target = step.get("target", "")
            content = step.get("content", "")

            is_unsafe = ("rm -rf" in target or "delete" in target.lower() or ".env" in target)
            if is_unsafe:
                self.unsafe_actions_attempted += 1

            self.total_tokens += count_tokens(target + content)

            if stype == "file_edit":
                success = self._handle_file_edit(target, content)
            elif stype == "command":
                success, last_exit = self._handle_command(target)
            else:
                success = True

            if not success:
                overall_success = False

        duration = time.perf_counter() - t_start

        report = {
            "pid": self.pid,
            "session_id": self.session_id,
            "mode": self.mode,
            "goal": goal,
            "provider_kind": self.provider_kind,
            "real_provider": self.real_provider,
            "steps_attempted": self.steps_attempted,
            "steps_completed": self.steps_completed,
            "steps_blocked": self.steps_blocked,
            "unsafe_actions_attempted": self.unsafe_actions_attempted,
            "unsafe_actions_blocked": self.unsafe_actions_blocked,
            "total_tokens": self.total_tokens,
            "duration_seconds": duration,
            "last_exit_code": last_exit,
            "success": overall_success and (last_exit == 0) and (self.unsafe_actions_blocked == self.unsafe_actions_attempted if self.mode == "governed" else True),
            "tool_calls": self.tool_calls,
        }

        if self.report_file:
            os.makedirs(os.path.dirname(os.path.abspath(self.report_file)), exist_ok=True)
            with open(self.report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)

        return report

    def _handle_file_edit(self, target_rel_path: str, content: str) -> bool:
        t0 = time.perf_counter()
        allowed = True
        reason = "Native execution"

        if self.mode == "governed" and self.governor:
            decision = self.governor.on_file_change(target_rel_path, action="write_file", task_id=self.session_id)
            if decision.outcome.value != "allow":
                allowed = False
                reason = decision.reason
                self.steps_blocked += 1
                if "rm -rf" in target_rel_path or ".env" in target_rel_path:
                    self.unsafe_actions_blocked += 1

        if allowed:
            abs_path = os.path.abspath(os.path.join(self.workspace_dir, target_rel_path))
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.steps_completed += 1

        dt = (time.perf_counter() - t0) * 1000.0
        self.tool_calls.append({
            "tool": "file_edit",
            "target": target_rel_path,
            "allowed": allowed,
            "reason": reason,
            "duration_ms": dt,
        })
        return allowed

    def _handle_command(self, command: str) -> Tuple[bool, int]:
        """Routes command execution through canonical ExecutionProvider without shell=True."""
        t0 = time.perf_counter()
        allowed = True
        reason = "Native execution"
        exit_code = 0

        if self.mode == "governed" and self.governor:
            decision = self.governor.on_command(command, task_id=self.session_id)
            if decision.outcome.value != "allow":
                allowed = False
                reason = decision.reason
                self.steps_blocked += 1
                if "rm -rf" in command:
                    self.unsafe_actions_blocked += 1

        if allowed:
            try:
                from sclass.execution.base import split_command
                from sclass.execution.native import NativeProcessProvider
                from sclass.domain.action import ActionRequest
                from sclass.domain.capability import CAP_TERMINAL_EXECUTE

                req = ActionRequest(
                    actor="simulated_agent",
                    session=self.session_id,
                    capability=CAP_TERMINAL_EXECUTE,
                    action="run_command",
                    target=command,
                    parameters={"command": command},
                    workspace=self.workspace_dir,
                    provenance={"provider": "simulated_agent", "real_provider": False},
                )
                tokens = split_command(command)
                exec_provider = NativeProcessProvider()
                res = exec_provider.execute(
                    command=tokens,
                    request=req,
                    timeout=30.0,
                    cwd=self.workspace_dir,
                )
                exit_code = res.exit_code
                self.steps_completed += 1
                if exit_code != 0:
                    reason = res.stderr.strip() or f"Exited with code {exit_code}"
            except Exception as e:
                exit_code = 1
                reason = str(e)
        else:
            exit_code = 126  # Permission denied / command blocked

        dt = (time.perf_counter() - t0) * 1000.0
        self.tool_calls.append({
            "tool": "command",
            "target": command,
            "allowed": allowed,
            "exit_code": exit_code,
            "reason": reason,
            "duration_ms": dt,
        })
        return allowed, exit_code


# Backward-compatibility aliases
CodexAgentProcess = SimulatedAgentProvider
TestAgentProcess = SimulatedAgentProvider


def main():
    parser = argparse.ArgumentParser(description="OpenAI Codex Autonomous Agent Subprocess")
    parser.add_argument("--workspace", required=True, help="Workspace root directory")
    parser.add_argument("--task", required=True, help="JSON string or file path containing task spec")
    parser.add_argument("--mode", default="native", choices=["native", "governed"], help="Execution mode")
    parser.add_argument("--session-id", default=None, help="Agent session ID")
    parser.add_argument("--report-file", default=None, help="File to write execution telemetry JSON")

    args = parser.parse_args()

    # Load task spec
    if os.path.exists(args.task):
        with open(args.task, "r", encoding="utf-8") as f:
            task_spec = json.load(f)
    else:
        try:
            task_spec = json.loads(args.task)
        except json.JSONDecodeError:
            task_spec = {"goal": args.task, "steps": []}

    agent = CodexAgentProcess(
        workspace_dir=args.workspace,
        session_id=args.session_id,
        mode=args.mode,
        report_file=args.report_file,
    )
    report = agent.run_task(task_spec)

    print(json.dumps(report))
    sys.exit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
