"""
S-Class Survival v0: Verifier Execution Module (sclass/survival/verification/execution.py)

Implements Phase 9:
✓ command execution
✓ exit code
✓ test result
✓ repository state
✓ errors
"""

from __future__ import annotations
import os
import subprocess
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sclass.survival.models import EvidenceReceipt, ObservedReceipt
from sclass.survival.evidence import (
    _create_observed_receipt,
    create_receipt,
    _get_git_commit_hash,
    _get_git_changed_files,
    compute_file_hashes,
    compute_workspace_snapshot,
    compute_workspace_fingerprint,
    sanitize_verification_command,
    resolve_executable_tokens,
)


def execute_and_record(
    command: str,
    workspace_dir: str,
    task_id: str = "task_default",
    claim_id: str = "claim_default",
    agent: str = "agent",
    action: str = "run_command",
    timeout: float = 60.0,
    allow_shell: bool = False,
) -> ObservedReceipt:
    """
    Independently executes a command, captures exit code, hashes stdout/stderr,
    and records repository state changes and file fingerprints into an authoritative ObservedReceipt.
    Prevents shell injection vulnerabilities by using tokenized execution and policy gating.
    """
    ws = os.path.abspath(workspace_dir)
    started_at = datetime.now(timezone.utc).isoformat()
    base_commit = _get_git_commit_hash(ws)

    try:
        if allow_shell:
            # Policy authorization decision for shell execution
            from sclass.survival.authority import authorize
            from sclass.survival.models import AuthorizationRequest
            auth_req = AuthorizationRequest(
                agent=agent,
                platform="sclass",
                action="execute",
                target=command,
                parameters={"execution_mode": "shell", "command": command},
                workspace=ws,
                task_id=task_id,
            )
            decision = authorize(auth_req, mode="enforce", workspace_dir=ws)
            if not decision.is_allowed:
                raise ValueError(f"Shell execution rejected by S-Class security policy: {decision.reason}")

            proc = subprocess.run(
                command,
                cwd=ws,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        else:
            cmd_tokens = sanitize_verification_command(command)
            resolved_tokens = resolve_executable_tokens(cmd_tokens)
            proc = subprocess.run(
                resolved_tokens,
                cwd=ws,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except ValueError as ve:
        exit_code = 126
        stdout = ""
        stderr = f"Command execution rejected by S-Class security policy: {str(ve)}"
    except subprocess.TimeoutExpired as te:
        exit_code = 124
        stdout = te.stdout or "" if isinstance(te.stdout, str) else ""
        stderr = (te.stderr or "") + "\nCommand timed out after timeout limit"
    except FileNotFoundError as fnf:
        exit_code = 127
        stdout = ""
        stderr = f"Command executable not found: {str(fnf)}"
    except Exception as e:
        exit_code = 1
        stdout = ""
        stderr = f"Execution exception: {str(e)}"

    finished_at = datetime.now(timezone.utc).isoformat()
    result_commit = _get_git_commit_hash(ws)
    files_changed = _get_git_changed_files(ws, base_commit)
    file_hashes = compute_file_hashes(ws, files_changed)

    snapshot_after = compute_workspace_snapshot(ws)
    fingerprint_after = compute_workspace_fingerprint(snapshot_after)

    return _create_observed_receipt(
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
        base_commit=base_commit,
        result_commit=result_commit,
        files_changed=files_changed,
        file_hashes=file_hashes,
        workspace_snapshot=snapshot_after,
        workspace_fingerprint=fingerprint_after,
    )
