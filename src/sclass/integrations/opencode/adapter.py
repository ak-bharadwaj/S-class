"""
S-Class Integration: OpenCode / CodeSandbox Platform Adapter.
"""

from __future__ import annotations
import shutil
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize
from sclass.integrations.base import AdapterCapabilities, AdapterStatus


class OpenCodeAdapter:
    """Adapts OpenCode actions into S-Class governance."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        self.workspace_dir = workspace_dir
        self.mode = mode
        self.capabilities = AdapterCapabilities(
            pre_action_enforcement=True,
            post_action_observation=True,
            approval=True,
            verification=True,
            session_events=True,
            native_protocol="acp",
        )

    def inspect_status(self) -> AdapterStatus:
        if shutil.which("opencode"):
            return AdapterStatus.INSTALLED
        return AdapterStatus.SUPPORTED

    @property
    def status(self) -> AdapterStatus:
        return self.inspect_status()

    def on_action(self, action_name: str, target: str, parameters: Dict[str, Any], task_id: Optional[str] = None) -> AuthorizationDecision:
        req = ActionRequest(
            agent="opencode",
            platform="opencode",
            action=action_name,
            tool=action_name,
            target=target,
            parameters=parameters,
            workspace=self.workspace_dir,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)
