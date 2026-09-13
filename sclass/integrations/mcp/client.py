"""
S-Class MCP Integration: MCP Client Transport.
Provides client connectivity to upstream MCP servers while passing calls through MCPGateway.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, Optional

from sclass.integrations.mcp.gateway import MCPGateway


class MCPClient:
    """Standard client invoking tools on an MCP server through the S-Class gateway."""

    def __init__(self, gateway: MCPGateway, client_id: str = "sclass_mcp_client"):
        self.gateway = gateway
        self.client_id = client_id

    def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calls a tool through the MCPGateway."""
        return self.gateway.handle_call_tool(
            tool_name=tool_name,
            arguments=arguments,
            agent_id=self.client_id,
            task_id=task_id,
        )

    def list_tools(self) -> Dict[str, Any]:
        """Lists available tools from the gateway."""
        return self.gateway.process_message({"method": "tools/list", "id": str(uuid.uuid4())})
