"""
S-Class MCP Integration: MCP Server Endpoint.
Exposes MCP endpoints protected by S-Class policy gateway.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Callable

from sclass.integrations.mcp.gateway import MCPGateway


class MCPServer:
    """Standard MCP server endpoint delegating requests to MCPGateway."""

    def __init__(self, gateway: MCPGateway, executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None):
        self.gateway = gateway
        self.executor = executor

    def handle_request(self, raw_rpc: Dict[str, Any]) -> Dict[str, Any]:
        """Handles an incoming JSON-RPC request."""
        return self.gateway.process_message(raw_rpc, executor=self.executor)
