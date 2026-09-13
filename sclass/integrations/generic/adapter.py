"""
S-Class Integration: Generic POSIX / Shell Process Adapter.
First-class integration interface for arbitrary or unknown agent runners.
"""

from __future__ import annotations
import os
import sys
from typing import Optional, List, Dict, Any

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize
from sclass.integrations.base import AdapterCapabilities, AdapterStatus


class GenericProcessAdapter:
    """Generic CLI execution authorization bridge for external agent runners."""

    def __init__(self, workspace_dir: str, mode: str = "enforce", agent_name: str = "generic_agent"):
        self.workspace_dir = workspace_dir
        self.mode = mode
        self.agent_name = agent_name
        self.capabilities = AdapterCapabilities(
            pre_action_enforcement=True,
            post_action_observation=True,
            approval=True,
            verification=True,
            session_events=True,
            native_protocol="cli",
        )

    def inspect_status(self) -> AdapterStatus:
        # Generic adapter is always installed and ready on any supported system
        return AdapterStatus.INSTALLED

    @property
    def status(self) -> AdapterStatus:
        return self.inspect_status()

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
