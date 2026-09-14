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

    # Phase 4: Comprehensive Workspace Snapshot & Fingerprint Verification
    if receipt.workspace_fingerprint:
        current_snapshot = ev_mod.compute_workspace_snapshot(workspace_dir)
        current_fingerprint = ev_mod.compute_workspace_fingerprint(current_snapshot)
        if current_fingerprint != receipt.workspace_fingerprint:
            rec_snap = receipt.metadata.get("workspace_snapshot") if isinstance(receipt.metadata, dict) else None
            rec_files_map = {f["path"]: f for f in rec_snap.get("files", [])} if rec_snap and isinstance(rec_snap.get("files"), list) else {}
            curr_files_map = {f["path"]: f for f in current_snapshot.get("files", [])}

            # Check type changes, link targets, and content hash modifications:
            for p, curr_f in sorted(curr_files_map.items()):
                if p in rec_files_map:
                    old_f = rec_files_map[p]
                    if old_f.get("type") != curr_f.get("type"):
                        return (False, f"File type altered after verification: {p} changed from {old_f.get('type')} to {curr_f.get('type')}")
                    if old_f.get("type") == "symlink" and old_f.get("link_target") != curr_f.get("link_target"):
                        return (False, f"Symlink target modified after verification: {p} changed from {old_f.get('link_target')} to {curr_f.get('link_target')}")
                    if old_f.get("type") == "file" and old_f.get("content_hash") != curr_f.get("content_hash"):
                        return (False, f"Recorded file content changed after verification: {p} (expected hash {str(old_f.get('content_hash'))[:8]}, got {str(curr_f.get('content_hash'))[:8]})")
                else:
                    # New untracked or uncommitted file added after verification
                    return (False, f"File type altered or uncommitted changes introduced after verification: {p}")

            # Check deletions:
            for p, f_info in sorted(rec_files_map.items()):
                if p not in curr_files_map:
                    return (False, f"File type altered or recorded file deleted after verification: {p}")

            # Check Git status discrepancies:
            rec_git = rec_snap.get("git_state", {}) if rec_snap and isinstance(rec_snap.get("git_state"), dict) else {}
            curr_git = current_snapshot.get("git_state", {})
            if curr_git.get("untracked_files") != rec_git.get("untracked_files"):
                diff_untracked = set(curr_git.get("untracked_files", [])) - set(rec_git.get("untracked_files", []))
                if diff_untracked:
                    return (False, f"Repository contains uncommitted file changes introduced after verification: {sorted(list(diff_untracked))[0]}")
            if curr_git.get("renamed_files") != rec_git.get("renamed_files"):
                diff_renamed = set(curr_git.get("renamed_files", [])) - set(rec_git.get("renamed_files", []))
                if diff_renamed:
                    return (False, f"File rename detected after verification: {sorted(list(diff_renamed))[0]}")
            if curr_git.get("deleted_files") != rec_git.get("deleted_files"):
                diff_deleted = set(curr_git.get("deleted_files", [])) - set(rec_git.get("deleted_files", []))
                if diff_deleted:
                    return (False, f"Recorded file was deleted after verification: {sorted(list(diff_deleted))[0]}")

            return (False, f"Workspace fingerprint mismatch: expected {receipt.workspace_fingerprint[:8]}, got {current_fingerprint[:8]}")

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
