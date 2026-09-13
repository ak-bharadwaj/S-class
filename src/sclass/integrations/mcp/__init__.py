"""
S-Class MCP Integration: Authoritative Gateway, Interceptor, and Tools.
"""

from sclass.integrations.mcp.tool_policy import MCPToolPolicy
from sclass.integrations.mcp.interceptor import MCPInterceptor
from sclass.integrations.mcp.normalization import MCPToolCall
from sclass.integrations.mcp.auth import MCPAuthorizationContext, MCPAuthenticator
from sclass.integrations.mcp.tools import MCPToolDefinition, MCPToolRegistry
from sclass.integrations.mcp.resources import MCPResource, MCPResourceRegistry
from sclass.integrations.mcp.gateway import MCPGateway
from sclass.integrations.mcp.transport import MCPProtocolTransport, MCPProtocolRequest
from sclass.integrations.mcp.client import MCPClient
from sclass.integrations.mcp.server import MCPServer

__all__ = [
    "MCPToolPolicy",
    "MCPInterceptor",
    "MCPToolCall",
    "MCPAuthorizationContext",
    "MCPAuthenticator",
    "MCPToolDefinition",
    "MCPToolRegistry",
    "MCPResource",
    "MCPResourceRegistry",
    "MCPGateway",
    "MCPProtocolTransport",
    "MCPProtocolRequest",
    "MCPClient",
    "MCPServer",
]
