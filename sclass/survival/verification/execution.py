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
from sclass.survival.evidence import create_receipt, _get_git_commit_hash, _get_git_changed_files


def execute_and_record(
    command: str,
    workspace_dir: str,
    task_id: str = "task_default",
    claim_id: str = "claim_default",
    agent: str = "agent",
    action: str = "run_command",
    timeout: float = 60.0,
) -> EvidenceReceipt:
    """
    Independently executes a command, captures exit code, hashes stdout/stderr,
    and records repository state changes into an authoritative EvidenceReceipt.
    """
    ws = os.path.abspath(workspace_dir)
    started_at = datetime.now(timezone.utc).isoformat()
    base_commit = _get_git_commit_hash(ws)

    try:
        proc = subprocess.run(
            command,
            cwd=ws,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as te:
        exit_code = 124
        stdout = te.stdout or "" if isinstance(te.stdout, str) else ""
        stderr = (te.stderr or "") + "\nCommand timed out after timeout limit"
    except Exception as e:
        exit_code = 1
        stdout = ""
        stderr = f"Execution exception: {str(e)}"

    finished_at = datetime.now(timezone.utc).isoformat()
    result_commit = _get_git_commit_hash(ws)
    files_changed = _get_git_changed_files(ws, base_commit)

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
    )
