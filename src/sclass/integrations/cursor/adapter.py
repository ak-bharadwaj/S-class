"""
S-Class Integration: Cursor IDE Platform Adapter.
"""

from __future__ import annotations
import os
import shutil
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize
from sclass.integrations.base import AdapterCapabilities, AdapterStatus


class CursorAdapter:
    """Adapts Cursor IDE hooks and composer tool calls to S-Class governance."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        self.workspace_dir = workspace_dir
        self.mode = mode
        self.capabilities = AdapterCapabilities(
            pre_action_enforcement=True,
            post_action_observation=False,
            approval=True,
            verification=False,
            session_events=True,
            native_protocol="native_hook",
        )

    def inspect_status(self) -> AdapterStatus:
        cursor_home = os.path.expanduser("~/.cursor")
        if os.path.exists(cursor_home) or shutil.which("cursor"):
            return AdapterStatus.INSTALLED
        return AdapterStatus.SUPPORTED

    @property
    def status(self) -> AdapterStatus:
        return self.inspect_status()

    def on_composer_action(self, action_type: str, file_path: str, contents: str = "", task_id: Optional[str] = None) -> AuthorizationDecision:
        req = ActionRequest(
            agent="cursor",
            platform="cursor",
            action=action_type,
            tool="composer",
            target=file_path,
            parameters={"contents": contents},
            workspace=self.workspace_dir,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)
