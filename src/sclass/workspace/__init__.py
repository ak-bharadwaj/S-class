"""S-Class Workspace and Project Management.

Provides preflight environment scanning, repository metadata discovery,
and isolated Git worktree management for subagent execution without
compromising canonical authority.
"""

from sclass.workspace.preflight import WorkspacePreflightScanner
from sclass.workspace.worktrees import WorktreeManager

__all__ = [
    "WorkspacePreflightScanner",
    "WorktreeManager",
]
