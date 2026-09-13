"""
S-Class Survival v0: Verifier Evidence Module (sclass/survival/verification/evidence.py)

Implements Phase 9:
✓ evidence receipt validation
✓ repository state verification
✓ staleness and invalidation checking
"""

from __future__ import annotations
import os
from typing import Optional, Tuple, List

from sclass.survival.models import EvidenceReceipt
import sclass.survival.evidence as ev_mod


def check_verification_staleness(receipt: EvidenceReceipt, workspace_dir: str) -> Tuple[bool, Optional[str]]:
    """
    Checks if repository state has changed since the evidence was produced.
    Returns (True, None) if fresh, or (False, reason) if invalidated.
    """
    # Use dynamically dispatched commit hash lookup to support mock / monkeypatching
    try:
        import sclass.survival.verification as v_pkg
        get_commit_fn = getattr(v_pkg, "_get_git_commit_hash", ev_mod._get_git_commit_hash)
        get_changed_fn = getattr(v_pkg, "_get_git_changed_files", ev_mod._get_git_changed_files)
    except Exception:
        get_commit_fn = ev_mod._get_git_commit_hash
        get_changed_fn = ev_mod._get_git_changed_files

    current_head = get_commit_fn(workspace_dir)
    if receipt.result_commit and current_head and receipt.result_commit != "0" * 40 and current_head != "0" * 40:
        if receipt.result_commit != current_head:
            return (False, f"Repository HEAD advanced from {receipt.result_commit[:8]} to {current_head[:8]}")

    # Check for uncommitted changes introduced after execution
    changed = get_changed_fn(workspace_dir, receipt.result_commit)
    # Filter out .agents directory changes
    code_changes = [f.replace("\\", "/") for f in changed if not f.replace("\\", "/").startswith(".agents")]
    if code_changes:
        receipt_files = [f.replace("\\", "/") for f in receipt.files_changed]
        unrecorded = [f for f in code_changes if f not in receipt_files]
        if unrecorded:
            return (False, f"Repository contains {len(unrecorded)} uncommitted file changes introduced after verification: {', '.join(unrecorded[:3])}")

    return (True, None)
