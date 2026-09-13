"""
S-Class Integration: Cursor Platform Adapter.
Translates Cursor hook events (beforeShellExecution, beforeReadFile, etc.) into S-Class ActionRequests.
"""

from __future__ import annotations
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize


class CursorAdapter:
    """Adapts Cursor hooks into S-Class control plane decisions."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        self.workspace_dir = workspace_dir
        self.mode = mode

    def on_before_shell_execution(self, command: str, task_id: Optional[str] = None) -> AuthorizationDecision:
        req = ActionRequest(
            agent="cursor",
            platform="cursor",
            action="run_command",
            tool="terminal",
            target=command,
            parameters={"command": command},
            workspace=self.workspace_dir,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

    def on_file_edit(self, file_path: str, content: Optional[str] = None, task_id: Optional[str] = None) -> AuthorizationDecision:
        req = ActionRequest(
            agent="cursor",
            platform="cursor",
            action="file_edit",
            tool="editor",
            target=file_path,
            parameters={"content": content} if content else {},
            workspace=self.workspace_dir,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)
