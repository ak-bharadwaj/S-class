"""
S-Class Integration: Generic POSIX / Shell Process Adapter.
"""

from __future__ import annotations
import os
import sys
from typing import Optional, List

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize


class GenericProcessAdapter:
    """Generic CLI execution authorization bridge for external agent runners."""

    def __init__(self, workspace_dir: str, mode: str = "enforce", agent_name: str = "generic_agent"):
        self.workspace_dir = workspace_dir
        self.mode = mode
        self.agent_name = agent_name

    def authorize_command(self, command: str, task_id: Optional[str] = None) -> AuthorizationDecision:
        req = ActionRequest(
            agent=self.agent_name,
            platform="generic",
            action="run_command",
            tool="cli",
            target=command,
            parameters={"command": command},
            workspace=self.workspace_dir,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)
