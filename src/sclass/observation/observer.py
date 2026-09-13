"""
S-Class Observation: Independent Command Observer.
Executes processes under observation, captures execution identity,
and anchors provenance into LocalLedger via ObservationFactory.
Eliminates caller-chosen verifiers and execution kinds (Invariant 3).
"""

from __future__ import annotations
import os
import sys
import shlex
from typing import Optional, Any, Dict, List, Tuple

from sclass.domain.evidence import ObservedReceipt
from sclass.execution.modes import (
    ExecutionMode,
    ExecutionPolicy,
    check_protected_resource_targeting,
)
from sclass.execution.process import ProcessRunner, ProcessExecutionResult
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.observation.factory import ObservationFactory
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
    requested_verifier: Optional[str] = None,
) -> ObservedReceipt:
    """
    Independently executes and observes a command, recording child execution identity,
    exit code, stdout/stderr hashes, and workspace state fingerprints.
    Eliminates caller-supplied verifier authority (Invariant 3).
    Atomically commits an immutable OBSERVATION event in the LocalLedger.
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

    # 1. Protected resource analysis (Part V, #12)
    is_targeted, reason = check_protected_resource_targeting(command)
    if is_targeted:
        raise SecurityViolationError(f"Security policy violation: {reason}")

    is_shell = (mode == ExecutionMode.HOST_SHELL)

    # Disallow shell injection tokens if not explicitly HOST_SHELL
    if not is_shell:
        for t in tokens:
            if t in (";", "&&", "||", "|") or any(c in t for c in ("&&", "||", "`", "$(")):
                raise SecurityViolationError(f"Command contains forbidden shell chaining characters: {t}")

    # Capture before fingerprint
    snapshot_before = compute_workspace_snapshot(ws)
    fingerprint_before = compute_workspace_fingerprint(snapshot_before)

    # Initialize ledger early if needed
    if ledger is None:
        try:
            ledger = LocalLedger(workspace_dir=ws)
        except Exception as l_err:
            raise ObservationIntegrityError(
                f"Local ledger could not be initialized for observation: {l_err}"
            ) from l_err

    # 2. Execute process using ProcessRunner
    runner = ProcessRunner()
    result = runner.run(
        command=tokens,
        cwd=ws,
        timeout=timeout,
        mode=mode,
        task_id=task_id,
    )

    # 3. Caller-supplied verifier is treated strictly as an untrusted request (Invariant 3)
    req_v = requested_verifier or verifier

    # 4. Use ObservationFactory to derive authoritative verifier and atomically anchor receipt
    receipt = ObservationFactory.create_observation(
        execution_result=result,
        workspace_dir=ws,
        task_id=task_id,
        claim_id=claim_id,
        agent=agent,
        action=action,
        fingerprint_before=fingerprint_before,
        snapshot_before=snapshot_before,
        ledger=ledger,
        requested_verifier=req_v,
    )

    return receipt
