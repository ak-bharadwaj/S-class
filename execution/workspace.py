"""
S-Class EOS V11.2 - D6 Isolated Execution Workspace Management.
Provides isolated directory management with path traversal / symlink escape prevention.
"""

from __future__ import annotations
import os
import shutil
import uuid
from typing import Optional


class IsolatedWorkspace:
    """Manages an isolated directory environment for a single execution."""

    def __init__(self, workspace_id: str, base_dir: Optional[str] = None):
        if not workspace_id or not isinstance(workspace_id, str):
            raise ValueError("workspace_id must be a non-empty string.")

        self.workspace_id = workspace_id
        self._base_dir = os.path.abspath(base_dir or os.path.join(os.getcwd(), ".sclass_workspaces"))
        self._unique_id = uuid.uuid4().hex[:12]
        self._workspace_path = os.path.join(self._base_dir, f"{self.workspace_id}_{self._unique_id}")
        self._is_active = False

    @property
    def path(self) -> str:
        return self._workspace_path

    @property
    def is_active(self) -> bool:
        return self._is_active

    def setup(self) -> str:
        """Initializes the isolated directory ensuring no path traversal."""
        real_ws = os.path.realpath(self._workspace_path)
        real_base = os.path.realpath(self._base_dir)
        if not (real_ws == real_base or real_ws.startswith(real_base + os.sep)):
            raise ValueError(f"Path escape detected: '{real_ws}' is outside base directory '{real_base}'")

        os.makedirs(self._workspace_path, exist_ok=True)
        self._is_active = True
        return self._workspace_path

    def resolve_safe_path(self, relative_path: str) -> str:
        """Resolves a path within the workspace, preventing directory traversal, absolute paths, and symlink escapes."""
        if not relative_path:
            return self._workspace_path
        
        if not isinstance(relative_path, str):
            raise TypeError(f"relative_path must be a string, got {type(relative_path)}")

        # 1. Disallow absolute paths, UNC network shares, or Windows drive letters
        if os.path.isabs(relative_path) or (len(relative_path) > 1 and relative_path[1] == ":") or relative_path.startswith("\\\\"):
            raise ValueError(f"Path traversal rejected: absolute or drive paths not allowed '{relative_path}'")

        # 2. Prevent explicit '..' traversal
        normalized = os.path.normpath(relative_path)
        parts = normalized.replace("\\", "/").split("/")
        if ".." in parts:
            raise ValueError(f"Path traversal rejected: parent directory references '..' not allowed in '{relative_path}'")

        # 3. Canonicalize symlinks and check containment
        combined = os.path.join(self._workspace_path, relative_path)
        real_target = os.path.realpath(combined)
        real_ws = os.path.realpath(self._workspace_path)

        if not (real_target == real_ws or real_target.startswith(real_ws + os.sep)):
            raise ValueError(f"Path escape detected: '{relative_path}' resolves to '{real_target}' outside workspace '{real_ws}'")
        return real_target

    def cleanup(self) -> None:
        """Cleans up the temporary workspace directory."""
        if os.path.exists(self._workspace_path):
            try:
                shutil.rmtree(self._workspace_path, ignore_errors=True)
            except Exception:
                pass
        self._is_active = False

    def __enter__(self) -> IsolatedWorkspace:
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()
