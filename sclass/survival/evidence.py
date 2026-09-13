"""
S-Class Survival v0: Canonical Evidence Receipt Generation (sclass/survival/evidence.py)

Implements Phase 4:
Receipts capture independently observed execution and repository state.
The agent is NEVER authoritative for:
- exit_code
- files_changed
- test result
- verification status
"""

from __future__ import annotations
import os
import json
import uuid
import hashlib
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from sclass.survival.models import EvidenceReceipt


def _get_git_commit_hash(workspace_dir: str) -> str:
    """Resolves current HEAD commit hash via git."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass
    return "0" * 40


def _get_git_changed_files(workspace_dir: str, base_commit: str) -> List[str]:
    """Resolves modified and untracked files relative to base_commit."""
    changed = set()
    try:
        if base_commit and base_commit != "0" * 40:
            proc_diff = subprocess.run(
                ["git", "diff", "--name-only", base_commit],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc_diff.returncode == 0:
                for line in proc_diff.stdout.splitlines():
                    if line.strip():
                        changed.add(line.strip().replace("\\", "/"))

        proc_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc_status.returncode == 0:
            for line in proc_status.stdout.splitlines():
                if len(line) > 3:
                    file_part = line[3:].strip().replace("\\", "/")
                    if file_part:
                        changed.add(file_part)
    except Exception:
        pass
    return sorted(list(changed))


def create_receipt(
    task_id: str,
    claim_id: str,
    agent: str,
    action: str,
    workspace: str,
    command: str,
    exit_code: int,
    started_at: str,
    finished_at: str,
    stdout_content: str,
    stderr_content: str,
    base_commit: Optional[str] = None,
    result_commit: Optional[str] = None,
    files_changed: Optional[List[str]] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
    verified: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> EvidenceReceipt:
    """
    Creates a canonical EvidenceReceipt with cryptographic hashes of stdout/stderr.
    """
    ws = os.path.abspath(workspace)
    b_commit = base_commit or _get_git_commit_hash(ws)
    r_commit = result_commit or _get_git_commit_hash(ws)
    f_changed = files_changed if files_changed is not None else _get_git_changed_files(ws, b_commit)

    stdout_hash = hashlib.sha256(stdout_content.encode("utf-8")).hexdigest()
    stderr_hash = hashlib.sha256(stderr_content.encode("utf-8")).hexdigest()

    receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"

    receipt = EvidenceReceipt(
        receipt_id=receipt_id,
        task_id=task_id,
        claim_id=claim_id,
        agent=agent,
        action=action,
        workspace=ws,
        base_commit=b_commit,
        result_commit=r_commit,
        command=command,
        exit_code=exit_code,
        started_at=started_at,
        finished_at=finished_at,
        stdout_hash=stdout_hash,
        stderr_hash=stderr_hash,
        files_changed=f_changed,
        evidence=evidence or [],
        verified=verified,
        metadata=metadata or {},
    )

    # Save receipt to S-Class protected receipts directory
    save_receipt(receipt, ws)
    return receipt


def save_receipt(receipt: EvidenceReceipt, workspace_dir: str) -> str:
    """Saves receipt to .agents/receipts/{receipt_id}.json (SCLASS_ONLY)."""
    receipts_dir = os.path.join(workspace_dir, ".agents", "receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    target = os.path.join(receipts_dir, f"{receipt.receipt_id}.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(receipt.to_dict(), f, indent=2)
    return target


def load_receipt(receipt_id: str, workspace_dir: str) -> Optional[EvidenceReceipt]:
    """Loads and validates a receipt from disk."""
    target = os.path.join(workspace_dir, ".agents", "receipts", f"{receipt_id}.json")
    if not os.path.exists(target):
        return None
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        receipt = EvidenceReceipt.from_dict(data)
        # Validate integrity hash
        recorded_hash = data.get("receipt_hash")
        if recorded_hash and receipt.compute_hash() != recorded_hash:
            return None
        return receipt
    except Exception:
        return None


def observe_command(
    command: str,
    workspace_dir: str,
    task_id: str = "task_default",
    claim_id: str = "claim_default",
    agent: str = "agent",
    action: str = "run_command",
    timeout: float = 60.0,
) -> EvidenceReceipt:
    """
    Independently executes and observes a command, recording its true exit code,
    runtime, stdout/stderr hashes, and repository changes.
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

