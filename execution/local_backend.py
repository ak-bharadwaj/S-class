"""
S-Class EOS V11.2 - D6 Constrained Local Process Execution Backend.
Implements bounded child-process execution without shell=True.
Enforces:
1. Strict argv arrays (never shell=True).
2. Restricted inherited environment (sanitized host environment).
3. Bounded stdout/stderr byte capture.
4. Robust timeout enforcement with POSIX process group isolation and recursive process-tree termination.
5. Structured process facts metrics with explicit MeasurementStatus.
"""

from __future__ import annotations
import os
import sys
import time
import subprocess
import signal
import re
from datetime import datetime, timezone
from typing import Mapping, Optional, Sequence
from execution.models import TerminationReason, ResourceUsage, MeasurementStatus
from execution.backend import BackendProcessResult, ExecutionBackend


# Safe whitelist of standard system environment variables inherited from host
SAFE_SYSTEM_VARS = {
    "SYSTEMROOT",
    "WINDIR",
    "LANG",
    "LC_ALL",
    "TZ",
    "PATHEXT",
    "COMSPEC",
}

# Sensitive variables that caller custom environment is strictly forbidden to override
BLOCKED_ENV_PREFIXES = (
    "LD_",
    "DYLD_",
    "PYTHON",
    "NODE_",
    "BASH_",
    "PERL",
    "RUBY",
    "SHELL",
    "IFS",
    "ENV",
    "PS1",
    "SHLVL",
    "PROMPT_COMMAND",
    "TEMP",
    "TMP",
)

BLOCKED_ENV_EXACT = {
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOME",
    "LD_PRELOAD",
    "NODE_OPTIONS",
    "BASH_ENV",
    "PYTHONSTARTUP",
}

VAR_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def sanitize_environment(custom_env: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Constructs child environment strictly from an explicit approved policy."""
    clean_env = {}

    # 1. Inherit safe system runtime variables from host
    for key in SAFE_SYSTEM_VARS:
        if key in os.environ:
            clean_env[key] = os.environ[key]

    # 2. Inherit system PATH and standard temp directories from host (caller cannot override)
    for key in ("PATH", "TEMP", "TMP", "USERPROFILE", "HOME"):
        if key in os.environ:
            clean_env[key] = os.environ[key]

    # 3. Apply validated custom variables from caller (subject to strict policy filtering)
    if custom_env:
        for k, v in custom_env.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            if not VAR_NAME_RE.match(k):
                continue
            k_upper = k.upper()
            if k_upper in BLOCKED_ENV_EXACT or any(k_upper.startswith(p) for p in BLOCKED_ENV_PREFIXES):
                continue
            clean_env[k] = v

    # 4. Enforce strict deterministic Python execution flags
    clean_env["PYTHONUNBUFFERED"] = "1"
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    return clean_env


def terminate_process_tree(proc: subprocess.Popen) -> None:
    """Terminates child process and its dedicated process session/tree."""
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
        # On POSIX, child was spawned with start_new_session=True, so pgid == proc.pid
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                proc.kill()
            except Exception:
                pass
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class LocalProcessBackend(ExecutionBackend):
    """Constrained local process execution backend (§8.1, §8.3).
    
    Security Classification: Constrained Local Execution (argv arrays, restricted environment, bounded streams, timeouts, process group isolation).
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

        popen_kwargs = {
            "cwd": working_directory,
            "env": cleaned_env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "shell": False,
        }

        # POSIX Process-Group / Session Isolation
        if sys.platform != "win32":
            popen_kwargs["start_new_session"] = True
        else:
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            proc = subprocess.Popen(list(command_argv), **popen_kwargs)

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
            wall_clock_status=MeasurementStatus.OBSERVED,
            output_bytes_status=MeasurementStatus.ENFORCED,
            process_tree_termination_status=MeasurementStatus.ENFORCED,
            cpu_user_seconds=None,
            cpu_system_seconds=None,
            cpu_status=MeasurementStatus.UNSUPPORTED,
            memory_peak_bytes=None,
            memory_status=MeasurementStatus.UNSUPPORTED,
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
