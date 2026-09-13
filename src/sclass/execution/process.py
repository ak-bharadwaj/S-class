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

from sclass.domain.execution import ExecutionIdentity
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
        allow_shell: bool = False,
    ) -> ProcessExecutionResult:
        """Executes a command safely, capturing execution identity and resource metrics."""
        ws = os.path.abspath(cwd)

        if isinstance(command, str):
            try:
                tokens = shlex.split(command)
            except ValueError as ve:
                raise SecurityViolationError(f"Unparseable command string: {ve}") from ve
        else:
            tokens = list(command)

        if not tokens:
            raise SecurityViolationError("Empty command tokens provided.")

        # Capture process identity before launching
        identity = ExecutionIdentity.capture(tokens, cwd=ws, env=env)

        # Apply sandbox wrapper
        wrapped_tokens = self.sandbox.wrap_command(tokens, cwd=ws)

        started_dt = datetime.now(timezone.utc)
        start_mono = time.monotonic()
        timed_out = False

        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        try:
            proc = subprocess.run(
                wrapped_tokens,
                cwd=ws,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=allow_shell,
                env=run_env,
            )
            exit_code = proc.returncode
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
        except subprocess.TimeoutExpired as te:
            exit_code = 124
            timed_out = True
            stdout = te.stdout or "" if isinstance(te.stdout, str) else ""
            stderr = (te.stderr or "") + f"\nProcess execution timed out after {timeout} seconds."
        except FileNotFoundError as fnf:
            exit_code = 127
            stdout = ""
            stderr = f"Executable not found: {fnf}"
        except Exception as exc:
            exit_code = 1
            stdout = ""
            stderr = f"Execution exception: {exc}"

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
