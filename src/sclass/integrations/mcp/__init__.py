"""
S-Class MCP Integration: Authoritative Gateway, Interceptor, and Tools (MCP 2026-07-28).
"""

from sclass.integrations.mcp.tool_policy import MCPToolPolicy
from sclass.integrations.mcp.interceptor import MCPInterceptor
from sclass.integrations.mcp.normalization import MCPToolCall
from sclass.integrations.mcp.auth import MCPAuthorizationContext, MCPAuthenticator
from sclass.integrations.mcp.tools import MCPToolDefinition, MCPToolRegistry
from sclass.integrations.mcp.resources import MCPResource, MCPResourceRegistry
from sclass.integrations.mcp.gateway import MCPGateway
from sclass.integrations.mcp.transport import (
    MCPProtocolTransport,
    MCPProtocolRequest,
    MCPHeaderPolicy,
    StatelessSelfDescribingRequest,
    SUPPORTED_MCP_VERSIONS,
    DEFAULT_MCP_VERSION,
)
from sclass.integrations.mcp.tasks import (
    MCPTaskManager,
    MCPTaskOperation,
    MCPTaskStatus,
)
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
    "MCPHeaderPolicy",
    "StatelessSelfDescribingRequest",
    "SUPPORTED_MCP_VERSIONS",
    "DEFAULT_MCP_VERSION",
    "MCPTaskManager",
    "MCPTaskOperation",
    "MCPTaskStatus",
    "MCPClient",
    "MCPServer",
]
