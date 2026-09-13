"""
S-Class Observation: Evidence Receipt Management.
Provides secure receipt serialization, canonical path containment, and authentic observation creation.
"""

from __future__ import annotations
import os
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sclass.domain.evidence import EvidenceReceipt, ObservedReceipt, _OBSERVATION_TOKEN
from sclass.storage.paths import WorkspacePaths
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint


def save_receipt(receipt: EvidenceReceipt, workspace_dir: str) -> str:
    """Saves evidence receipt JSON to .sclass/evidence/receipts/ and .agents/receipts/."""
    paths = WorkspacePaths(workspace_dir)
    paths.ensure_directories()
    raw = json.dumps(receipt.to_dict(), indent=2, ensure_ascii=False)

    target_sclass = os.path.join(paths.receipts_dir, f"{receipt.receipt_id}.json")
    with open(target_sclass, "w", encoding="utf-8") as f:
        f.write(raw)

    target_legacy = os.path.join(paths.legacy_receipts_dir, f"{receipt.receipt_id}.json")
    with open(target_legacy, "w", encoding="utf-8") as f:
        f.write(raw)

    return target_sclass


def load_receipt(receipt_id: str, workspace_dir: str) -> Optional[EvidenceReceipt]:
    """
    Loads and validates a receipt from receipts directory.
    Strictly forbids absolute paths and directory traversal.
    Returns None if missing, forged, or path traversal attempted.
    """
    if not receipt_id or not isinstance(receipt_id, str):
        return None
    if ".." in receipt_id or "/" in receipt_id or "\\" in receipt_id or os.path.isabs(receipt_id):
        return None

    clean_id = receipt_id[:-5] if receipt_id.endswith(".json") else receipt_id
    paths = WorkspacePaths(workspace_dir)

    # Search in .sclass/ first, fallback to .agents/
    candidates = [
        os.path.abspath(os.path.join(paths.receipts_dir, f"{clean_id}.json")),
        os.path.abspath(os.path.join(paths.legacy_receipts_dir, f"{clean_id}.json")),
    ]

    target = None
    for cand in candidates:
        # Canonical containment check
        base = paths.receipts_dir if cand.startswith(paths.receipts_dir) else paths.legacy_receipts_dir
        try:
            if os.path.commonpath([base, cand]) == base and os.path.isfile(cand):
                target = cand
                break
        except (ValueError, OSError):
            continue

    if not target:
        return None

    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)

        recorded_hash = data.get("receipt_hash")
        if not recorded_hash:
            return None

        receipt = EvidenceReceipt.from_dict(data)
        if receipt.compute_hash() != recorded_hash:
            return None

        return receipt
    except Exception:
        return None


def create_observed_receipt(
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
    base_commit: str = "",
    result_commit: str = "",
    files_changed: Optional[List[str]] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
    execution_kind: str = "generic_command",
    verifier: str = "",
    workspace_snapshot: Optional[Dict[str, Any]] = None,
    workspace_fingerprint: Optional[str] = None,
    workspace_fingerprint_before: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ObservedReceipt:
    """Creates an authentic ObservedReceipt with private capability token."""
    ws = os.path.abspath(workspace)
    stdout_hash = hashlib.sha256(stdout_content.encode("utf-8")).hexdigest()
    stderr_hash = hashlib.sha256(stderr_content.encode("utf-8")).hexdigest()

    if workspace_snapshot is None:
        workspace_snapshot = compute_workspace_snapshot(ws)
    if workspace_fingerprint is None:
        workspace_fingerprint = compute_workspace_fingerprint(workspace_snapshot)
    if workspace_fingerprint_before is None:
        workspace_fingerprint_before = workspace_fingerprint

    meta = dict(metadata or {})
    meta["workspace_snapshot"] = workspace_snapshot
    meta["workspace_fingerprint"] = workspace_fingerprint
    meta["workspace_fingerprint_before"] = workspace_fingerprint_before

    receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
    receipt = ObservedReceipt(
        receipt_id=receipt_id,
        task_id=task_id,
        claim_id=claim_id,
        agent=agent,
        action=action,
        workspace=ws,
        base_commit=base_commit,
        result_commit=result_commit,
        command=command,
        exit_code=exit_code,
        started_at=started_at,
        finished_at=finished_at,
        stdout_hash=stdout_hash,
        stderr_hash=stderr_hash,
        files_changed=files_changed or [],
        evidence=evidence or [],
        metadata=meta,
        execution_kind=execution_kind,
        verifier=verifier,
        workspace_fingerprint=workspace_fingerprint,
        verified=False,
    )
    receipt.receipt_hash = receipt.compute_hash()
    save_receipt(receipt, ws)
    return receipt
