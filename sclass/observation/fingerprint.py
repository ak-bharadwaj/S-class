"""
S-Class Observation: Comprehensive Workspace Fingerprinting.
Captures full directory state, symlink targets, and content hashes to prevent TOCTOU and post-verification tampering.
"""

from __future__ import annotations
import os
import hashlib
from typing import Dict, Any, Tuple, Optional


def compute_file_hash(file_path: str) -> Optional[str]:
    """Computes SHA-256 hash of a single file."""
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return None
    try:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None


def compute_workspace_snapshot(workspace_dir: str, max_files: int = 5000) -> Dict[str, Any]:
    """
    Computes a deterministic snapshot of workspace files, content hashes, and symlinks.
    Excludes .git, .sclass, .agents, and vendor directories.
    """
    ws = os.path.abspath(workspace_dir)
    snapshot: Dict[str, Any] = {}
    count = 0

    excluded_dirs = {".git", ".sclass", ".agents", "node_modules", ".venv", "__pycache__", ".pytest_cache"}

    for root, dirs, files in os.walk(ws):
        # Filter excluded directories in-place
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        for f in files:
            if count >= max_files:
                break
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, ws).replace("\\", "/")

            if os.path.islink(full_path):
                try:
                    target = os.readlink(full_path)
                    snapshot[rel_path] = f"symlink:{target}"
                except OSError:
                    snapshot[rel_path] = "symlink:unreadable"
            elif os.path.isfile(full_path):
                f_hash = compute_file_hash(full_path)
                if f_hash:
                    snapshot[rel_path] = f_hash
            count += 1

    return snapshot


def compute_workspace_fingerprint(snapshot: Dict[str, Any]) -> str:
    """Computes a single deterministic SHA-256 fingerprint for a workspace snapshot."""
    sorted_items = sorted(snapshot.items())
    payload = "".join(f"{path}:{digest};" for path, digest in sorted_items)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
