"""
S-Class Execution: Managed Subprocess Execution.
Executes processes with captured ExecutionIdentity, timeouts, sandboxing, and output streaming.
"""

from __future__ import annotations
import os
import sys
import time
import shlex
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from sclass.domain.execution import ExecutionIdentity, ExecutionMode
from sclass.execution.sandbox import SandboxBackend, HostSandbox, get_sandbox_backend
from sclass.core.errors import SecurityViolationError


@dataclass(frozen=True)
class ProcessExecutionResult:
    """Immutable record of an executed process."""
    exit_code: int
    stdout: str
    stderr: str
    identity: ExecutionIdentity
    duration_ms: float
    started_at: str
    finished_at: str
    timed_out: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "identity": self.identity.to_dict(),
            "duration_ms": round(self.duration_ms, 2),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "timed_out": self.timed_out,
        }


class ProcessRunner:
    """Manages secure process invocations."""

    def __init__(self, sandbox: Optional[SandboxBackend] = None):
        self.sandbox = sandbox or HostSandbox()

    def run(
        self,
        command: str | List[str],
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
        mode: ExecutionMode = ExecutionMode.HOST_ARGV,
        allow_shell: Optional[bool] = None,
    ) -> ProcessExecutionResult:
        """Executes a command safely, capturing child execution identity and resource metrics."""
        ws = os.path.abspath(cwd)

        if allow_shell is not None:
            mode = ExecutionMode.HOST_SHELL if allow_shell else ExecutionMode.HOST_ARGV

        if isinstance(command, str):
            try:
                tokens = shlex.split(command)
            except ValueError as ve:
                raise SecurityViolationError(f"Unparseable command string: {ve}") from ve
        else:
            tokens = list(command)

        if not tokens:
            raise SecurityViolationError("Empty command tokens provided.")

        is_shell = (mode == ExecutionMode.HOST_SHELL)

        # Apply sandbox wrapper
        wrapped_tokens = self.sandbox.wrap_command(tokens, cwd=ws)

        started_dt = datetime.now(timezone.utc)
        start_mono = time.monotonic()
        timed_out = False

        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        proc = None
        try:
            cmd_args = wrapped_tokens if not is_shell else (
                subprocess.list2cmdline(wrapped_tokens) if isinstance(wrapped_tokens, list) else str(wrapped_tokens)
            )
            proc = subprocess.Popen(
                cmd_args,
                cwd=ws,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                shell=is_shell,
                env=run_env,
            )
            child_pid = proc.pid
            parent_pid = os.getpid()

            identity = ExecutionIdentity.capture(
                tokens,
                cwd=ws,
                env=env,
                pid=child_pid,
                parent_pid=parent_pid,
                mode=mode,
            )

            stdout_val, stderr_val = proc.communicate(timeout=timeout)
            exit_code = proc.returncode
            stdout = stdout_val or ""
            stderr = stderr_val or ""
        except subprocess.TimeoutExpired:
            exit_code = 124
            timed_out = True
            if proc:
                try:
                    proc.kill()
                    out, err = proc.communicate()
                    stdout = out or ""
                    stderr = (err or "") + f"\nProcess execution timed out after {timeout} seconds."
                except Exception:
                    stdout = ""
                    stderr = f"\nProcess execution timed out after {timeout} seconds."
            else:
                stdout = ""
                stderr = f"\nProcess execution timed out after {timeout} seconds."
            if "identity" not in locals():
                identity = ExecutionIdentity.capture(
                    tokens,
                    cwd=ws,
                    env=env,
                    pid=proc.pid if proc else None,
                    parent_pid=os.getpid(),
                    mode=mode,
                )
        except FileNotFoundError as fnf:
            exit_code = 127
            stdout = ""
            stderr = f"Executable not found: {fnf}"
            identity = ExecutionIdentity.capture(
                tokens,
                cwd=ws,
                env=env,
                pid=None,
                parent_pid=os.getpid(),
                mode=mode,
            )
        except Exception as exc:
            exit_code = 1
            stdout = ""
            stderr = f"Execution exception: {exc}"
            if "identity" not in locals():
                identity = ExecutionIdentity.capture(
                    tokens,
                    cwd=ws,
                    env=env,
                    pid=None,
                    parent_pid=os.getpid(),
                    mode=mode,
                )

        duration_ms = (time.monotonic() - start_mono) * 1000.0
        finished_dt = datetime.now(timezone.utc)

        return ProcessExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            identity=identity,
            duration_ms=duration_ms,
            started_at=started_dt.isoformat(),
            finished_at=finished_dt.isoformat(),
            timed_out=timed_out,
        )
