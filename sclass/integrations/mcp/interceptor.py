"""
S-Class MCP Integration: Tool Interceptor.
Enforces S-Class authorization boundaries across Model Context Protocol tool execution.
"""

from __future__ import annotations
from typing import Dict, Any, Tuple, Optional

from sclass.control.authorization import authorize
from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.integrations.mcp.tool_policy import MCPToolPolicy


class MCPInterceptor:
    """Intercepts and governs incoming MCP tool calls before execution."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        self.workspace_dir = workspace_dir
        self.mode = mode

    def intercept(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        agent: str = "mcp_agent",
        task_id: Optional[str] = None,
    ) -> Tuple[AuthorizationDecision, Optional[Dict[str, Any]]]:
        """
        Intercepts tool call. Returns (decision, None) if allowed,
        or (decision, error_payload) if blocked by policy.
        """
        req = MCPToolPolicy.map_call_to_request(
            tool_name=tool_name,
            arguments=arguments,
            workspace_dir=self.workspace_dir,
            agent=agent,
            task_id=task_id,
        )

        decision = authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

        if decision.is_denied:
            error_payload = {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"[S-Class Policy Block] {decision.policy_id}: {decision.reason}\n"
                            f"Remediation: {decision.remediation or 'Check workspace permissions.'}"
                        ),
                    }
                ],
                "_sclass_decision": decision.to_dict(),
            }
            return decision, error_payload

        return decision, None
