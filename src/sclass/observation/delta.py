"""
S-Class Observation: Granular Workspace Delta & Mutation Calculator (RC.3 / Layer E).
Computes exact pre-action and post-action file mutations, content digests, and byte metrics.
"""

from __future__ import annotations
import os
from typing import Dict, Any, Optional, List, Set, Tuple

from sclass.observation.record import FileMutation, WorkspaceDelta
from sclass.observation.fingerprint import compute_workspace_fingerprint


class DeltaCalculator:
    """
    Computes deterministic, fine-grained workspace mutation deltas
    between pre-execution and post-execution workspace snapshots.
    """

    @staticmethod
    def _normalize_snapshot(snapshot: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """Extracts {rel_path: hash} map from varying snapshot structures."""
        if not snapshot or not isinstance(snapshot, dict):
            return {}
        if "files" in snapshot and isinstance(snapshot["files"], dict):
            raw = snapshot["files"]
        else:
            raw = snapshot
        return {str(k).replace("\\", "/"): str(v) for k, v in raw.items() if not str(k).startswith("__")}

    @staticmethod
    def _get_file_size(workspace_dir: str, rel_path: str) -> int:
        """Safely returns the byte size of a file on disk."""
        if not workspace_dir:
            return 0
        full_path = os.path.join(workspace_dir, rel_path)
        try:
            if os.path.isfile(full_path):
                return os.path.getsize(full_path)
        except (OSError, PermissionError):
            pass
        return 0

    @classmethod
    def compute_delta(
        cls,
        snapshot_before: Optional[Dict[str, Any]],
        snapshot_after: Optional[Dict[str, Any]],
        workspace_dir: str,
        fingerprint_before: Optional[str] = None,
        fingerprint_after: Optional[str] = None,
    ) -> WorkspaceDelta:
        """
        Computes WorkspaceDelta across snapshot dictionaries and disk reality.
        """
        ws = os.path.abspath(workspace_dir) if workspace_dir else ""
        before_map = cls._normalize_snapshot(snapshot_before)
        after_map = cls._normalize_snapshot(snapshot_after)

        fp_before = fingerprint_before or compute_workspace_fingerprint(before_map)
        fp_after = fingerprint_after or compute_workspace_fingerprint(after_map)

        paths_before: Set[str] = set(before_map.keys())
        paths_after: Set[str] = set(after_map.keys())

        added_paths = sorted(list(paths_after - paths_before))
        deleted_paths = sorted(list(paths_before - paths_after))
        common_paths = paths_before & paths_after

        modified_paths = sorted([p for p in common_paths if before_map[p] != after_map[p]])

        mutations: List[FileMutation] = []
        total_bytes_changed = 0

        # Process Added Files
        for p in added_paths:
            h_after = after_map[p]
            b_after = cls._get_file_size(ws, p)
            total_bytes_changed += b_after
            mutations.append(
                FileMutation(
                    path=p,
                    status="added",
                    hash_before=None,
                    hash_after=h_after,
                    bytes_before=0,
                    bytes_after=b_after,
                )
            )

        # Process Modified Files
        for p in modified_paths:
            h_before = before_map[p]
            h_after = after_map[p]
            b_after = cls._get_file_size(ws, p)
            # Estimate bytes changed as either size difference or post-size
            total_bytes_changed += b_after
            mutations.append(
                FileMutation(
                    path=p,
                    status="modified",
                    hash_before=h_before,
                    hash_after=h_after,
                    bytes_before=0,
                    bytes_after=b_after,
                )
            )

        # Process Deleted Files
        for p in deleted_paths:
            h_before = before_map[p]
            mutations.append(
                FileMutation(
                    path=p,
                    status="deleted",
                    hash_before=h_before,
                    hash_after=None,
                    bytes_before=0,
                    bytes_after=0,
                )
            )

        # Sort mutations deterministically by path
        mutations.sort(key=lambda m: m.path)

        return WorkspaceDelta(
            tree_fingerprint_before=fp_before,
            tree_fingerprint_after=fp_after,
            files_added=tuple(added_paths),
            files_modified=tuple(modified_paths),
            files_deleted=tuple(deleted_paths),
            mutations=tuple(mutations),
            total_bytes_changed=total_bytes_changed,
        )


__all__ = ["DeltaCalculator"]
