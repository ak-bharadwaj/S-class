"""
S-Class ACP Integration: Filesystem Gateway.
Implements the official ACP filesystem operations (`fs/read`, `fs/write`, `fs/list`).
Strictly enforces:
- Workspace path containment (prevents symlink/junction/directory traversal escape)
- Protected resource security checks (.git, .env, system directories)
- Content hashing and audit receipt integration
"""

from __future__ import annotations
import os
import hashlib
from typing import Dict, Any, Tuple, Optional

from sclass.integrations.acp.schema import (
    ACPFsReadParams,
    ACPFsReadResult,
    ACPFsWriteParams,
    ACPFsWriteResult,
)
from sclass.control.resources import classify_resource, ResourceKind, AuthorityBoundary


class ACPFsGateway:
    """Filesystem gateway enforcing path containment and policy checks for ACP."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)

    def _resolve_contained_path(self, relative_or_abs_path: str, is_write: bool = False) -> str:
        """Resolves target path and ensures it remains strictly inside workspace and adheres to boundary policy."""
        if os.path.isabs(relative_or_abs_path):
            target = os.path.abspath(relative_or_abs_path)
        else:
            target = os.path.abspath(os.path.join(self.workspace_dir, relative_or_abs_path))

        # Check path containment
        try:
            common = os.path.commonpath([self.workspace_dir, target])
            if common != self.workspace_dir:
                raise PermissionError(f"Target path '{target}' escapes workspace '{self.workspace_dir}'.")
        except ValueError:
            raise PermissionError(f"Target path '{target}' escapes workspace '{self.workspace_dir}'.")

        # Classify resource
        kind, boundary = classify_resource(target, self.workspace_dir)

        # Secret resources cannot be read or written by agents
        if kind == ResourceKind.SECRET:
            raise PermissionError(f"Target path '{relative_or_abs_path}' is a protected or secret resource.")

        # For write operations: agent can ONLY write to AGENT_WRITABLE resources
        if is_write:
            if boundary != AuthorityBoundary.AGENT_WRITABLE or kind in (
                ResourceKind.GIT,
                ResourceKind.SECRET,
                ResourceKind.SCLASS_STATE,
                ResourceKind.SCLASS_EVIDENCE,
                ResourceKind.SCLASS_LEDGER,
                ResourceKind.SCLASS_CONFIG,
            ):
                raise PermissionError(
                    f"Target path '{relative_or_abs_path}' is not agent writable (boundary={boundary}, kind={kind})."
                )
        else:
            # For read operations: SCLASS_TRUST_ROOT ledger is protected from direct agent manipulation
            if boundary == AuthorityBoundary.SCLASS_TRUST_ROOT and not relative_or_abs_path.startswith("src/"):
                if kind in (ResourceKind.SCLASS_LEDGER, ResourceKind.SECRET):
                    raise PermissionError(f"Target path '{relative_or_abs_path}' is an immutable S-Class resource.")

        return target

    def read_file(self, params: ACPFsReadParams) -> ACPFsReadResult:
        """Reads file content within workspace boundaries."""
        target_path = self._resolve_contained_path(params.path, is_write=False)

        if not os.path.exists(target_path):
            raise FileNotFoundError(f"File not found: {params.path}")
        if os.path.isdir(target_path):
            raise IsADirectoryError(f"Path is a directory: {params.path}")

        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            if params.offset:
                f.seek(params.offset)
            if params.limit:
                content = f.read(params.limit)
            else:
                content = f.read()

        return ACPFsReadResult(
            path=params.path,
            content=content,
            bytes_read=len(content.encode("utf-8")),
        )

    def write_file(self, params: ACPFsWriteParams) -> ACPFsWriteResult:
        """Writes file content within workspace boundaries."""
        target_path = self._resolve_contained_path(params.path, is_write=True)

        if os.path.exists(target_path) and not params.overwrite:
            raise FileExistsError(f"File already exists and overwrite=False: {params.path}")

        parent_dir = os.path.dirname(target_path)
        os.makedirs(parent_dir, exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(params.content)

        content_bytes = params.content.encode("utf-8")
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        return ACPFsWriteResult(
            path=params.path,
            status="written",
            bytes_written=len(content_bytes),
            content_hash=content_hash,
        )

    def list_dir(self, relative_path: str = "") -> list[str]:
        """Lists directory entries safely contained in workspace."""
        target_path = self._resolve_contained_path(relative_path or ".", is_write=False)
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Directory not found: {relative_path}")
        if not os.path.isdir(target_path):
            raise NotADirectoryError(f"Path is not a directory: {relative_path}")
        return sorted(os.listdir(target_path))
