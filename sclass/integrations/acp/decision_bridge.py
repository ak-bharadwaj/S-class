"""
S-Class ACP Integration: Decision Bridge.
Translates Agent Client Protocol messages into S-Class authorization requests and state events.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Tuple

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize


class ACPDecisionBridge:
    """Translates ACP JSON-RPC payloads into S-Class control plane decisions."""

    def __init__(self, workspace_dir: str, mode: str = "enforce", agent_name: str = "acp_agent"):
        self.workspace_dir = workspace_dir
        self.mode = mode
        self.agent_name = agent_name

    def handle_tool_call(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> Tuple[AuthorizationDecision, Optional[Dict[str, Any]]]:
        """Evaluates an ACP tool execution request."""
        # Determine target from args
        target = (
            arguments.get("path")
            or arguments.get("file")
            or arguments.get("TargetFile")
            or arguments.get("command")
            or arguments.get("CommandLine")
            or tool_name
        )

        # Map to action type
        if tool_name in ("run_command", "bash", "terminal", "exec"):
            action_type = "run_command"
        elif tool_name in ("edit", "write_file", "replace_content", "save_file"):
            action_type = "file_edit"
        elif tool_name in ("read_file", "view_file"):
            action_type = "file_read"
        else:
            action_type = "tool_call"

        req = ActionRequest(
            agent=self.agent_name,
            platform="acp",
            action=action_type,
            tool=tool_name,
            target=str(target),
            parameters=arguments,
            workspace=self.workspace_dir,
            task_id=task_id,
        )

        decision = authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

        if decision.is_denied:
            error_response = {
                "jsonrpc": "2.0",
                "id": tool_call_id,
                "error": {
                    "code": -32001,
                    "message": f"[S-Class Policy Block] {decision.policy_id}: {decision.reason}",
                    "data": {
                        "remediation": decision.remediation,
                        "risk_level": decision.risk_level,
                    },
                },
            }
            return decision, error_response

        return decision, None
