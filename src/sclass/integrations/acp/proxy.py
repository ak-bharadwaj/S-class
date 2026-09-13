"""
S-Class ACP Integration: JSON-RPC Proxy.
Monitors and intercepts Agent Client Protocol traffic between client IDE and agent backend.
"""

from __future__ import annotations
import json
import sys
import logging
from typing import Dict, Any, Optional, Tuple, Callable

from sclass.integrations.acp.decision_bridge import ACPDecisionBridge

logger = logging.getLogger("sclass.integrations.acp.proxy")


class ACPProxy:
    """Synchronous JSON-RPC message filter and authorization interceptor."""

    def __init__(self, workspace_dir: str, mode: str = "enforce", agent_name: str = "acp_agent"):
        self.bridge = ACPDecisionBridge(workspace_dir=workspace_dir, mode=mode, agent_name=agent_name)

    def process_incoming_message(self, raw_message: str) -> Tuple[bool, Optional[str]]:
        """
        Processes a single JSON-RPC line.
        Returns (is_intercepted, response_string).
        If intercepted is True, caller must return response_string to the sender and NOT forward.
        If intercepted is False, caller forwards raw_message as-is.
        """
        raw_clean = raw_message.strip()
        if not raw_clean:
            return False, None

        try:
            msg = json.loads(raw_clean)
        except Exception:
            return False, None

        method = msg.get("method")
        msg_id = msg.get("id")

        if method in ("tool/call", "tool_call", "action/execute"):
            params = msg.get("params", {})
            tool_name = params.get("tool") or params.get("name") or "unknown_tool"
            arguments = params.get("arguments") or params.get("parameters") or {}
            task_id = params.get("task_id")

            decision, error_resp = self.bridge.handle_tool_call(
                tool_call_id=str(msg_id),
                tool_name=tool_name,
                arguments=arguments,
                task_id=task_id,
            )

            if decision.is_denied and error_resp:
                return True, json.dumps(error_resp)

        return False, None
