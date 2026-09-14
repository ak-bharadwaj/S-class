"""
S-Class Integration: OpenAI Codex Execution Harness (RC.1).

Connects S-Class observation and control policies to real Codex executions:
- Evaluates actions against synthesized Codex ControlPolicy (non-interfering during long-horizon coding).
- Authorizes commands and file changes with fail-closed security.
- Executes real host operations (file I/O, subprocess execution) safely within workspace boundaries.
- Performs final cryptographic boundary verification against OS reality.
"""

from __future__ import annotations
import os
import sys
import time
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

from sclass.integrations.codex.adapter import CodexAdapter
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.project import VerifiedProjectState
from sclass.platform.archetypes.codex import get_codex_profile, get_codex_compensation_policy
from sclass.platform.engine import PlatformOptimizationEngine
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.storage.paths import WorkspacePaths


@dataclass
class StepResult:
    """Telemetry and outcome from a single execution step."""
    action: str
    target: str
    decision: AuthorizationDecision
    executed: bool
    exit_code: Optional[int] = None
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0


@dataclass
class HarnessRunResult:
    """Summary metrics of a task execution run under the Codex harness."""
    task_id: str
    steps_executed: int
    steps_blocked: int
    interventions: int
    wall_clock_sec: float
    verified: bool
    step_results: List[StepResult] = field(default_factory=list)
    state: Optional[VerifiedProjectState] = None
    telemetry: Dict[str, Any] = field(default_factory=dict)


class CodexExecutionHarness:
    """
    Authoritative execution harness for OpenAI Codex.
    Preserves Codex long-horizon autonomy while guaranteeing fail-closed boundary verification.
    """

    def __init__(
        self,
        workspace_dir: str,
        mode: str = "enforce",
        codex_bin: Optional[str] = None,
    ) -> None:
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.mode = mode
        self.codex_bin = codex_bin or shutil.which("codex")
        self.adapter = CodexAdapter(workspace_dir=self.workspace_dir, mode=mode)
        self.paths = WorkspacePaths(self.workspace_dir)
        self.paths.ensure_directories()

        # Synthesize tailored Control Policy
        self.profile = get_codex_profile()
        self.compensation_policy = get_codex_compensation_policy()
        self.control_policy = PlatformOptimizationEngine.reconcile(
            profile=self.profile,
            compensation_policy=self.compensation_policy,
            task={"type": "autonomous_coding"},
            risk="normal",
        )

    def execute_file_edit(
        self,
        file_rel_path: str,
        content: str,
        task_id: Optional[str] = None,
    ) -> StepResult:
        """
        Authorizes and applies a file creation or modification.
        Enforces path containment and protection boundaries.
        """
        t0 = time.perf_counter()
        decision = self.adapter.on_file_change(file_rel_path, action="write_file", task_id=task_id)

        if decision.outcome != DecisionOutcome.ALLOW:
            dt = (time.perf_counter() - t0) * 1000.0
            return StepResult(
                action="write_file",
                target=file_rel_path,
                decision=decision,
                executed=False,
                error=decision.reason,
                duration_ms=dt,
            )

        # Apply file mutation within workspace
        abs_target = os.path.abspath(os.path.join(self.workspace_dir, file_rel_path))
        os.makedirs(os.path.dirname(abs_target), exist_ok=True)
        with open(abs_target, "w", encoding="utf-8") as f:
            f.write(content)

        dt = (time.perf_counter() - t0) * 1000.0
        return StepResult(
            action="write_file",
            target=file_rel_path,
            decision=decision,
            executed=True,
            duration_ms=dt,
        )

    def execute_command(
        self,
        command: str,
        task_id: Optional[str] = None,
        timeout_sec: float = 30.0,
    ) -> StepResult:
        """
        Authorizes and executes a shell command in the workspace.
        Blocks destructive commands (e.g. rm -rf) via S-Class policy.
        """
        t0 = time.perf_counter()
        decision = self.adapter.on_command(command, task_id=task_id)

        if decision.outcome != DecisionOutcome.ALLOW:
            dt = (time.perf_counter() - t0) * 1000.0
            return StepResult(
                action="run_command",
                target=command,
                decision=decision,
                executed=False,
                error=decision.reason,
                duration_ms=dt,
            )

        # Real command execution on host OS
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            dt = (time.perf_counter() - t0) * 1000.0
            return StepResult(
                action="run_command",
                target=command,
                decision=decision,
                executed=True,
                exit_code=proc.returncode,
                output=proc.stdout,
                error=proc.stderr,
                duration_ms=dt,
            )
        except Exception as e:
            dt = (time.perf_counter() - t0) * 1000.0
            return StepResult(
                action="run_command",
                target=command,
                decision=decision,
                executed=False,
                exit_code=1,
                error=str(e),
                duration_ms=dt,
            )

    def run_task(
        self,
        task_id: str,
        steps: List[Dict[str, Any]],
        claim_statement: str = "",
    ) -> HarnessRunResult:
        """
        Executes a sequence of autonomous Codex task steps.
        Preserves long-horizon autonomy by suppressing unnecessary micro-interruptions.
        """
        t_start = time.perf_counter()
        step_results: List[StepResult] = []
        steps_executed = 0
        steps_blocked = 0
        interventions = 0

        for step in steps:
            stype = step.get("type")
            target = step.get("target", "")

            if stype == "file_edit":
                res = self.execute_file_edit(target, step.get("content", ""), task_id=task_id)
            elif stype == "command":
                res = self.execute_command(target, task_id=task_id)
            else:
                continue

            step_results.append(res)
            if res.executed:
                steps_executed += 1
            else:
                steps_blocked += 1
                interventions += 1

        # Task boundary cryptographic verification
        wall_clock = time.perf_counter() - t_start
        snap = compute_workspace_snapshot(self.workspace_dir)
        fp = compute_workspace_fingerprint(snap)

        state = VerifiedProjectState(
            repository="codex-project",
            workspace=self.workspace_dir,
            current_revision=fp,
        )

        # Verification boundary check
        last_exit = 0
        for sr in reversed(step_results):
            if sr.action == "run_command" and sr.exit_code is not None:
                last_exit = sr.exit_code
                break

        verified = (steps_blocked == 0) and (last_exit == 0)

        if verified:
            state.record_verified_claim(
                claim={"claim_id": f"c_{task_id}", "statement": claim_statement or f"Task {task_id} completed successfully"},
                receipt={"receipt_id": f"rcpt_{task_id}", "base_commit": fp, "exit_code": 0},
            )
        else:
            state.record_invalidated_claim(
                claim_or_id=f"c_{task_id}",
                reason=f"Task boundary verification failed: steps_blocked={steps_blocked}, last_exit={last_exit}",
            )

        return HarnessRunResult(
            task_id=task_id,
            steps_executed=steps_executed,
            steps_blocked=steps_blocked,
            interventions=interventions,
            wall_clock_sec=wall_clock,
            verified=verified,
            step_results=step_results,
            state=state,
            telemetry={
                "fingerprint": fp,
                "control_policy": {
                    "interruption_policy": self.control_policy.interruption_policy,
                    "suppressed_interventions": self.control_policy.suppressed_interventions,
                },
            },
        )
