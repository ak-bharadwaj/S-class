"""
S-Class Control: Path Authority and Resource Boundary Model.
Enforces SCLASS_ONLY, AGENT_WRITABLE, and USER_WRITABLE protection domains.
"""

from __future__ import annotations
import os
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from sclass.storage.paths import WorkspacePaths
from sclass.core.errors import SecurityViolationError


class PathAuthorityLevel(str, Enum):
    AGENT_WRITABLE = "agent_writable"
    USER_WRITABLE = "user_writable"
    SCLASS_ONLY = "sclass_only"


@dataclass(frozen=True)
class ResourceRef:
    """Canonical target resource representation across all interfaces."""
    workspace_id: str
    canonical_path: str
    resource_type: str  # "file", "directory", "process", "tool", "config"
    authority: PathAuthorityLevel

    @classmethod
    def from_path(cls, path: str, workspace_dir: str, workspace_id: str = "default") -> ResourceRef:
        authority = get_path_authority(path, workspace_dir)
        canon = os.path.abspath(path)
        rtype = "directory" if os.path.isdir(canon) else "file"
        return cls(
            workspace_id=workspace_id,
            canonical_path=canon,
            resource_type=rtype,
            authority=authority,
        )


def get_path_authority(target_path: str, workspace_dir: str) -> PathAuthorityLevel:
    """
    Authoritatively determines access level for a target path.
    Strictly forbids escaping the workspace boundary or tampering with SCLASS_ONLY assets.
    """
    paths = WorkspacePaths(workspace_dir)
    abs_target = os.path.abspath(os.path.join(workspace_dir, target_path) if not os.path.isabs(target_path) else target_path)

    # Check workspace escape
    if not paths.is_contained(abs_target):
        return PathAuthorityLevel.SCLASS_ONLY  # Block external modifications by default

    # Check S-Class protected areas
    if paths.is_sclass_protected(abs_target):
        return PathAuthorityLevel.SCLASS_ONLY

    # Git internal directory (.git/) is S-Class / VCS only
    git_dir = os.path.join(paths.root, ".git")
    if paths.is_contained(abs_target, git_dir):
        return PathAuthorityLevel.SCLASS_ONLY

    return PathAuthorityLevel.AGENT_WRITABLE


class PathAuthority:
    """Evaluates filesystem access requests against S-Class authority boundaries."""

    def __init__(self, workspace_dir: str):
        self.paths = WorkspacePaths(workspace_dir)

    def check_write_access(self, target_path: str, agent: str = "") -> None:
        """Raises SecurityViolationError if agent attempts to write to SCLASS_ONLY resource."""
        authority = get_path_authority(target_path, self.paths.root)
        if authority == PathAuthorityLevel.SCLASS_ONLY:
            raise SecurityViolationError(
                f"Security violation: Target path '{target_path}' is protected under SCLASS_ONLY authority. "
                f"Agent '{agent}' cannot modify S-Class control plane state or evidence."
            )
