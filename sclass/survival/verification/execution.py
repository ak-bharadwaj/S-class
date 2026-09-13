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

from sclass.survival.models import EvidenceReceipt
from sclass.survival.evidence import (
    create_receipt,
    _get_git_commit_hash,
    _get_git_changed_files,
    compute_file_hashes,
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
) -> EvidenceReceipt:
    """
    Independently executes a command, captures exit code, hashes stdout/stderr,
    and records repository state changes and file fingerprints into an authoritative EvidenceReceipt.
    Prevents shell injection vulnerabilities by using tokenized execution.
    """
    ws = os.path.abspath(workspace_dir)
    started_at = datetime.now(timezone.utc).isoformat()
    base_commit = _get_git_commit_hash(ws)

    try:
        if allow_shell:
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

    return create_receipt(
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
        is_observed=True,
    )
