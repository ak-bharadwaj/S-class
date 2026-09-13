"""
S-Class Integration: Claude Code Platform Adapter.
Thin translation layer mapping Claude Code tool use and session hooks into S-Class ActionRequests.
"""

from __future__ import annotations
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize


class ClaudeCodeAdapter:
    """Adapts Claude Code hooks and tool invocations to S-Class governance."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        self.workspace_dir = workspace_dir
        self.mode = mode

    def on_pre_tool_use(self, tool_name: str, tool_input: Dict[str, Any], task_id: Optional[str] = None) -> AuthorizationDecision:
        """Translates Claude Code PreToolUse into an ActionRequest and evaluates policy."""
        target = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("command") or tool_name

        if tool_name in ("Bash", "terminal"):
            action = "run_command"
        elif tool_name in ("Edit", "Write", "MultiEdit"):
            action = "file_edit"
        elif tool_name in ("View", "Read"):
            action = "file_read"
        else:
            action = "tool_call"

        req = ActionRequest(
            agent="claude",
            platform="claude_code",
            action=action,
            tool=tool_name,
            target=str(target),
            parameters=tool_input,
            workspace=self.workspace_dir,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)
