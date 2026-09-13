"""
S-Class Integration: OpenAI Codex CLI Platform Adapter.
"""

from __future__ import annotations
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize


class CodexAdapter:
    """Adapts OpenAI Codex CLI tool calls and bash commands."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        self.workspace_dir = workspace_dir
        self.mode = mode

    def on_command(self, command: str, task_id: Optional[str] = None) -> AuthorizationDecision:
        req = ActionRequest(
            agent="codex",
            platform="codex",
            action="run_command",
            tool="bash",
            target=command,
            parameters={"command": command},
            workspace=self.workspace_dir,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)
