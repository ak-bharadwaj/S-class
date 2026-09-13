"""
S-Class Observation: Independent Command Observer.
Executes processes under observation, captures execution identity, and anchors provenance into LocalLedger.
"""

from __future__ import annotations
import os
import sys
import shlex
import subprocess
import re
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List, Tuple

from sclass.domain.evidence import ObservedReceipt
from sclass.domain.execution import ExecutionIdentity, ExecutionMode
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.observation.receipt import create_observed_receipt
from sclass.trust.ledger import LocalLedger
from sclass.core.errors import ObservationIntegrityError, SecurityViolationError


KNOWN_TEST_VERIFIERS: Dict[str, str] = {
    "pytest": "pytest",
    "unittest": "unittest",
    "jest": "jest",
    "vitest": "vitest",
    "mocha": "mocha",
    "playwright": "playwright",
    "cargo": "cargo",
    "go": "go",
}


def detect_execution_kind(command_or_argv: str | List[str], resolved_executable: str = "") -> Tuple[str, str]:
    """
    Detects if a command executes an authorized test runner based on structured argv tokens.
    Eliminates substring regex matching to prevent command injection and spoofing.
    """
    if isinstance(command_or_argv, str):
        try:
            tokens = shlex.split(command_or_argv)
        except Exception:
            return "generic_command", ""
    else:
        tokens = list(command_or_argv)

    if not tokens:
        return "generic_command", ""

    raw_exe = resolved_executable or tokens[0]
    exe_name = os.path.basename(raw_exe).lower()
    if exe_name.endswith(".exe"):
        exe_name = exe_name[:-4]

    # Check for python invocations: python -m pytest ...
    if exe_name in ("python", "python3", "py"):
        args = tokens[1:]
        # If -c is present anywhere before -m, it is arbitrary code execution, never a test runner!
        if "-c" in args:
            return "generic_command", ""

        # Check for -m <module>
        for i, arg in enumerate(args):
            if arg == "-m" and i + 1 < len(args):
                module = args[i + 1].lower()
                if module == "pytest":
                    return "test_runner", "pytest"
                if module == "unittest":
                    return "test_runner", "unittest"
            elif arg.startswith("-m") and len(arg) > 2:
                module = arg[2:].lower()
                if module == "pytest":
                    return "test_runner", "pytest"
                if module == "unittest":
                    return "test_runner", "unittest"
        return "generic_command", ""

    # Direct test runner binaries
    if exe_name in ("pytest", "py.test"):
        return "test_runner", "pytest"
    if exe_name in ("jest", "vitest", "mocha"):
        return "test_runner", exe_name
    if exe_name == "playwright" and len(tokens) > 1 and tokens[1].lower() == "test":
        return "test_runner", "playwright"
    if exe_name in ("cargo", "go") and len(tokens) > 1 and tokens[1].lower() == "test":
        return "test_runner", exe_name
    if exe_name in ("npm", "pnpm", "yarn", "bun") and len(tokens) > 1:
        sub = tokens[1].lower()
        if sub == "test" or (len(tokens) > 2 and sub == "run" and tokens[2].lower() == "test"):
            return "test_runner", exe_name

    return "generic_command", ""


def observe_command(
    command: str,
    workspace_dir: str,
    task_id: str = "task_default",
    claim_id: str = "claim_default",
    agent: str = "agent",
    action: str = "run_command",
    timeout: float = 60.0,
    mode: ExecutionMode = ExecutionMode.HOST_ARGV,
    allow_shell: Optional[bool] = None,
    ledger: Optional[LocalLedger] = None,
    execution_kind: Optional[str] = None,
    verifier: Optional[str] = None,
) -> ObservedReceipt:
    """
    Independently executes and observes a command, recording its child execution identity,
    exit code, stdout/stderr hashes, and workspace state fingerprints.
    Anchors an immutable OBSERVATION event in the LocalLedger.
    """
    ws = os.path.abspath(workspace_dir)

    if allow_shell is not None:
        mode = ExecutionMode.HOST_SHELL if allow_shell else ExecutionMode.HOST_ARGV

    # Split command tokens safely
    try:
        tokens = shlex.split(command)
    except ValueError as ve:
        raise SecurityViolationError(f"Command contains unparseable syntax: {ve}") from ve

    if not tokens:
        raise SecurityViolationError("Empty command string provided for observation.")

    is_shell = (mode == ExecutionMode.HOST_SHELL)

    # Disallow shell injection tokens if not explicitly HOST_SHELL
    if not is_shell:
        for t in tokens:
            if any(c in t for c in (";", "&&", "||", "|", "`", "$(")):
                raise SecurityViolationError(f"Command contains forbidden shell chaining characters: {t}")

    # Structured detection of execution kind from parsed tokens
    det_kind, det_ver = detect_execution_kind(tokens)
    kind = execution_kind or det_kind
    ver = verifier or det_ver

    # Capture before fingerprint
    snapshot_before = compute_workspace_snapshot(ws)
    fingerprint_before = compute_workspace_fingerprint(snapshot_before)

    started_at = datetime.now(timezone.utc).isoformat()
    proc = None
    try:
        cmd_args = tokens if not is_shell else command
        proc = subprocess.Popen(
            cmd_args,
            cwd=ws,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            shell=is_shell,
        )
        child_pid = proc.pid
        parent_pid = os.getpid()
        exec_id = ExecutionIdentity.capture(
            tokens,
            cwd=ws,
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
        if proc:
            try:
                proc.kill()
                out, err = proc.communicate()
                stdout = out or ""
                stderr = (err or "") + "\nCommand timed out."
            except Exception:
                stdout = ""
                stderr = "\nCommand timed out."
        else:
            stdout = ""
            stderr = "\nCommand timed out."
        if "exec_id" not in locals():
            exec_id = ExecutionIdentity.capture(
                tokens,
                cwd=ws,
                pid=proc.pid if proc else None,
                parent_pid=os.getpid(),
                mode=mode,
            )
    except FileNotFoundError as fnf:
        exit_code = 127
        stdout = ""
        stderr = f"Executable not found: {fnf}"
        exec_id = ExecutionIdentity.capture(
            tokens,
            cwd=ws,
            pid=None,
            parent_pid=os.getpid(),
            mode=mode,
        )
    except Exception as exc:
        exit_code = 1
        stdout = ""
        stderr = f"Execution exception: {exc}"
        if "exec_id" not in locals():
            exec_id = ExecutionIdentity.capture(
                tokens,
                cwd=ws,
                pid=None,
                parent_pid=os.getpid(),
                mode=mode,
            )

    finished_at = datetime.now(timezone.utc).isoformat()

    # Capture after fingerprint
    snapshot_after = compute_workspace_snapshot(ws)
    fingerprint_after = compute_workspace_fingerprint(snapshot_after)

    meta = {
        "execution_identity": exec_id.to_dict(),
    }

    receipt = create_observed_receipt(
        task_id=task_id,
        claim_id=claim_id,
        agent=agent,
        action=action,
        workspace=ws,
        command=command,
        exit_code=exit_code,
        started_at=started_at,
        finished_at=finished_at,
        stdout_content=stdout,
        stderr_content=stderr,
        execution_kind=kind,
        verifier=ver,
        workspace_snapshot=snapshot_after,
        workspace_fingerprint=fingerprint_after,
        workspace_fingerprint_before=fingerprint_before,
        metadata=meta,
    )

    # Fail closed: anchor in LocalLedger
    if ledger is None:
        try:
            ledger = LocalLedger(workspace_dir=ws)
        except Exception as l_err:
            raise ObservationIntegrityError(
                f"Observation completed but local ledger could not be initialized: {l_err}"
            ) from l_err

    try:
        ledger.append(
            "OBSERVATION",
            {
                "receipt_id": receipt.receipt_id,
                "receipt_hash": receipt.receipt_hash,
                "fingerprint_before": fingerprint_before,
                "fingerprint_after": fingerprint_after,
                "command": command,
                "exit_code": exit_code,
                "execution_kind": receipt.execution_kind,
                "verifier": receipt.verifier,
                "execution_identity": exec_id.to_dict(),
                "timestamp": finished_at,
            },
        )
    except Exception as append_err:
        raise ObservationIntegrityError(
            f"Observation completed but provenance could not be anchored in ledger: {append_err}"
        ) from append_err

    return receipt
