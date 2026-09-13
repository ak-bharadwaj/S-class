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

    ws = os.path.abspath(workspace_dir)

    # Finding #3: Content hash fingerprint check for recorded files (same-file staleness hole defense)
    all_files_to_check = set((receipt.file_hashes or {}).keys()) | set(receipt.files_changed or [])
    for rel_path in sorted(all_files_to_check):
        clean_rel = rel_path.replace("\\", "/").strip()
        if not clean_rel or clean_rel.startswith(".agents"):
            continue
        full_path = os.path.join(ws, clean_rel)
        recorded_hash = (receipt.file_hashes or {}).get(clean_rel)
        current_hash = ev_mod.compute_file_hash(full_path)
        if recorded_hash is not None:
            if current_hash is None:
                return (False, f"Recorded file was deleted after verification: {clean_rel}")
            if current_hash != recorded_hash:
                return (False, f"Recorded file content changed after verification: {clean_rel} (expected hash {recorded_hash[:8]}, got {current_hash[:8]})")
            else:
                pass
        else:
            # File was in files_changed but had no recorded hash in receipt
            if current_hash is not None:
                return (False, f"Unfingerprinted file modification detected after verification: {clean_rel}")

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
