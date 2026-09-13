"""
S-Class Storage: Content-Addressed Evidence Store.
"""

from __future__ import annotations
import os
import json
import hashlib
from typing import Optional, Dict, Any

from sclass.storage.paths import WorkspacePaths


class EvidenceStore:
    """Content-addressed store for receipts, reports, snapshots, and execution evidence."""

    def __init__(self, workspace_dir: str):
        self.paths = WorkspacePaths(workspace_dir)
        self.base_dir = self.paths.evidence_dir
        self.paths.ensure_directories()

    def put_bytes(self, data: bytes, suffix: str = ".bin") -> str:
        """Stores bytes under their SHA-256 hash address."""
        digest = hashlib.sha256(data).hexdigest()
        shard = digest[:2]
        shard_dir = os.path.join(self.base_dir, shard)
        os.makedirs(shard_dir, exist_ok=True)
        target = os.path.join(shard_dir, f"{digest}{suffix}")
        if not os.path.exists(target):
            tmp_target = f"{target}.tmp"
            with open(tmp_target, "wb") as f:
                f.write(data)
            os.replace(tmp_target, target)
        return digest

    def get_bytes(self, digest: str, suffix: str = ".bin") -> Optional[bytes]:
        """Retrieves bytes by SHA-256 hash digest."""
        if not digest or len(digest) < 2:
            return None
        shard = digest[:2]
        target = os.path.join(self.base_dir, shard, f"{digest}{suffix}")
        if not os.path.exists(target):
            return None
        with open(target, "rb") as f:
            return f.read()

    def put_json(self, data: Dict[str, Any]) -> str:
        """Stores JSON object under its canonical RFC 8785 / sorted-key SHA-256 digest."""
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return self.put_bytes(raw, suffix=".json")

    def get_json(self, digest: str) -> Optional[Dict[str, Any]]:
        """Retrieves and parses JSON object by digest."""
        raw = self.get_bytes(digest, suffix=".json")
        if raw is None:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None
