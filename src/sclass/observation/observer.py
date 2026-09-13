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
from sclass.domain.execution import ExecutionIdentity
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
    "cargo test": "cargo",
    "go test": "go",
}


def detect_execution_kind(command: str) -> Tuple[str, str]:
    """Detects if a command executes an authorized test runner."""
    cmd_lower = (command or "").strip().lower()
    for pattern, verifier_name in KNOWN_TEST_VERIFIERS.items():
        if re.search(r"\b" + re.escape(pattern) + r"\b", cmd_lower):
            return "test_runner", verifier_name
    return "generic_command", ""


def observe_command(
    command: str,
    workspace_dir: str,
    task_id: str = "task_default",
    claim_id: str = "claim_default",
    agent: str = "agent",
    action: str = "run_command",
    timeout: float = 60.0,
    allow_shell: bool = False,
    ledger: Optional[LocalLedger] = None,
    execution_kind: Optional[str] = None,
    verifier: Optional[str] = None,
) -> ObservedReceipt:
    """
    Independently executes and observes a command, recording its execution identity,
    exit code, stdout/stderr hashes, and workspace state fingerprints.
    Anchors an immutable OBSERVATION event in the LocalLedger.
    """
    ws = os.path.abspath(workspace_dir)

    # Sanitize and detect execution kind
    det_kind, det_ver = detect_execution_kind(command)
    kind = execution_kind or det_kind
    ver = verifier or det_ver

    # Capture before fingerprint
    snapshot_before = compute_workspace_snapshot(ws)
    fingerprint_before = compute_workspace_fingerprint(snapshot_before)

    # Split command tokens safely
    try:
        tokens = shlex.split(command)
    except ValueError as ve:
        raise SecurityViolationError(f"Command contains unparseable syntax: {ve}") from ve

    if not tokens:
        raise SecurityViolationError("Empty command string provided for observation.")

    # Disallow shell injection tokens if not explicitly allow_shell
    if not allow_shell:
        for t in tokens:
            if any(c in t for c in (";", "&&", "||", "|", "`", "$(")):
                raise SecurityViolationError(f"Command contains forbidden shell chaining characters: {t}")

    # Capture process execution identity
    exec_id = ExecutionIdentity.capture(tokens, cwd=ws)

    started_at = datetime.now(timezone.utc).isoformat()
    try:
        proc = subprocess.run(
            tokens,
            cwd=ws,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=allow_shell,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as te:
        exit_code = 124
        stdout = te.stdout or "" if isinstance(te.stdout, str) else ""
        stderr = (te.stderr or "") + "\nCommand timed out."
    except FileNotFoundError as fnf:
        exit_code = 127
        stdout = ""
        stderr = f"Executable not found: {fnf}"
    except Exception as exc:
        exit_code = 1
        stdout = ""
        stderr = f"Execution exception: {exc}"

    finished_at = datetime.now(timezone.utc).isoformat()

    # Capture after fingerprint
    snapshot_after = compute_workspace_snapshot(ws)
    fingerprint_after = compute_workspace_fingerprint(snapshot_after)

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
                "timestamp": finished_at,
            },
        )
    except Exception as append_err:
        raise ObservationIntegrityError(
            f"Observation completed but provenance could not be anchored in ledger: {append_err}"
        ) from append_err

    return receipt
