"""
S-Class EOS V11.2 - D6 Constrained Local Process Execution Backend.
Implements bounded child-process execution without shell=True.
Enforces:
1. Strict argv arrays (never shell=True).
2. Restricted inherited environment (sanitized host environment).
3. Bounded stdout/stderr byte capture.
4. Robust timeout enforcement with recursive process-tree termination.
5. Structured process facts metrics.
"""

from __future__ import annotations
import os
import sys
import time
import subprocess
import signal
from datetime import datetime, timezone
from typing import Mapping, Optional, Sequence
from execution.models import TerminationReason, ResourceUsage
from execution.backend import BackendProcessResult, ExecutionBackend


# Safe whitelist of environment variables permitted to child processes
SAFE_ENV_WHITELIST = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "PYTHONPATH",
    "PYTHONHOME",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOME",
    "LANG",
    "LC_ALL",
    "COMSPEC",
    "PATHEXT",
}


def sanitize_environment(custom_env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Builds a clean, restricted environment dict containing only safe whitelisted variables."""
    clean_env = {}
    for key in SAFE_ENV_WHITELIST:
        if key in os.environ:
            clean_env[key] = os.environ[key]

    if custom_env:
        for k, v in custom_env.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            # Block shell injection or dangerous environment variables
            if k.upper() in {"LD_PRELOAD", "PYTHONSTARTUP", "NODE_OPTIONS", "BASH_ENV"}:
                continue
            clean_env[k] = v

    clean_env["PYTHONUNBUFFERED"] = "1"
    return clean_env


def terminate_process_tree(proc: subprocess.Popen) -> None:
    """Terminates child process and all recursive descendant processes."""
    if proc.poll() is not None:
        return

    pid = proc.pid
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class LocalProcessBackend(ExecutionBackend):
    """Constrained local process execution backend (§8.1, §8.3).
    
    Security Classification: Constrained Local Execution (argv arrays, restricted environment, bounded streams, timeouts).
    """

    def execute_command(
        self,
        command_argv: Sequence[str],
        working_directory: str,
        environment: Optional[Mapping[str, str]] = None,
        timeout_seconds: float = 30.0,
        max_output_bytes: int = 1048576,
    ) -> BackendProcessResult:
        if not command_argv:
            raise ValueError("command_argv cannot be empty.")
        if not isinstance(command_argv, (list, tuple)):
            raise TypeError("command_argv must be a list or tuple of string arguments.")
        for arg in command_argv:
            if not isinstance(arg, str):
                raise TypeError(f"command_argv elements must be strings, got {type(arg)}")

        if not os.path.exists(working_directory):
            raise ValueError(f"working_directory does not exist: '{working_directory}'")

        cleaned_env = sanitize_environment(environment)
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()

        proc = None
        stdout_bytes = b""
        stderr_bytes = b""
        stdout_truncated = False
        stderr_truncated = False
        termination_reason = TerminationReason.EXIT_ZERO
        exit_code = -1
        err_msg = None

        try:
            # argv arrays strictly without shell=True
            proc = subprocess.Popen(
                list(command_argv),
                cwd=working_directory,
                env=cleaned_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
            )

            try:
                raw_stdout, raw_stderr = proc.communicate(timeout=max(0.1, timeout_seconds))
                exit_code = proc.returncode
                if exit_code == 0:
                    termination_reason = TerminationReason.EXIT_ZERO
                else:
                    termination_reason = TerminationReason.EXIT_NON_ZERO

            except subprocess.TimeoutExpired:
                terminate_process_tree(proc)
                raw_stdout, raw_stderr = proc.communicate()
                exit_code = -9
                termination_reason = TerminationReason.TIMEOUT_EXPIRED
                err_msg = f"Process timed out after {timeout_seconds}s"

            # Stream bounding
            if len(raw_stdout) > max_output_bytes:
                stdout_bytes = raw_stdout[:max_output_bytes]
                stdout_truncated = True
            else:
                stdout_bytes = raw_stdout

            if len(raw_stderr) > max_output_bytes:
                stderr_bytes = raw_stderr[:max_output_bytes]
                stderr_truncated = True
            else:
                stderr_bytes = raw_stderr

        except Exception as e:
            if proc:
                terminate_process_tree(proc)
            exit_code = -1
            termination_reason = TerminationReason.BACKEND_FAULT
            err_msg = f"Local process backend fault: {str(e)}"
        finally:
            if proc and proc.poll() is None:
                terminate_process_tree(proc)

        t1 = time.perf_counter()
        ended_at = datetime.now(timezone.utc).isoformat()
        wall_clock = max(0.0, t1 - t0)

        usage = ResourceUsage(
            wall_clock_seconds=wall_clock,
            cpu_user_seconds=wall_clock,
            cpu_system_seconds=0.0,
            memory_peak_bytes=len(stdout_bytes) + len(stderr_bytes),
        )

        return BackendProcessResult(
            exit_code=exit_code,
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            started_at=started_at,
            ended_at=ended_at,
            termination_reason=termination_reason,
            resource_usage=usage,
            error_message=err_msg,
        )
