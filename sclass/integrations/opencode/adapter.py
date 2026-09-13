"""
S-Class Integration: OpenCode / OpenHands Platform Adapter.
"""

from __future__ import annotations
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize


class OpenCodeAdapter:
    """Adapts OpenCode / OpenHands events into S-Class ActionRequests."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        self.workspace_dir = workspace_dir
        self.mode = mode

    def on_event(self, event_type: str, payload: Dict[str, Any], task_id: Optional[str] = None) -> AuthorizationDecision:
        action = payload.get("action", "tool_call")
        target = payload.get("path") or payload.get("command") or event_type

        req = ActionRequest(
            agent="opencode",
            platform="opencode",
            action=action,
            tool=payload.get("tool", event_type),
            target=str(target),
            parameters=payload,
            workspace=self.workspace_dir,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)
