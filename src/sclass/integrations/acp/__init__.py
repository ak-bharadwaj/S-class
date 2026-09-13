"""
S-Class Integration: Official ACP (Agent Client Protocol) v1 Boundary.
Provides complete protocol support:
- schema: Pydantic models for ACP v1 JSON-RPC envelopes & params
- transport: JSON-RPC 2.0 message framing and parsing
- session: ACPSessionManager tracking agent session lifecycles
- permissions: ACPPermissionsBridge evaluating policy requests
- event_bridge: ACPEventBridge translating event streams
- capability_map: ACPCapabilityMap translating tool & capability scopes
- compatibility: ACPCompatibility negotiating protocol wire versions
- fs_gateway: ACPFsGateway workspace-contained filesystem operations
- terminal_gateway: ACPTerminalGateway observed process execution
- adapter: ACPAdapter normalizing protocol messages to S-Class control plane
"""

from sclass.integrations.acp.decision_bridge import ACPDecisionBridge
from sclass.integrations.acp.proxy import ACPProxy
from sclass.integrations.acp.schema import (
    ACPMessage,
    ACPRequest,
    ACPResponse,
    ACPNotification,
    ACPErrorData,
    ACPInitializeParams,
    ACPInitializeResult,
    ACPSessionNewParams,
    ACPSessionNewResult,
    ACPPermissionParams,
    ACPPermissionResult,
    ACPToolCallParams,
    ACPToolCallResult,
    ACPSessionForkResult,
    ACPShutdownResult,
    DEFAULT_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
)
from sclass.integrations.acp.transport import ACPTransport
from sclass.integrations.acp.session import ACPSessionManager, ACPAgentSession
from sclass.integrations.acp.permissions import ACPPermissionsBridge, ACPPermissionRequest
from sclass.integrations.acp.event_bridge import ACPEventBridge, ACPInternalEvent
from sclass.integrations.acp.capability_map import ACPCapabilityMap, ACPCapabilitySpec
from sclass.integrations.acp.compatibility import ACPCompatibility
from sclass.integrations.acp.fs_gateway import ACPFsGateway
from sclass.integrations.acp.terminal_gateway import ACPTerminalGateway
from sclass.integrations.acp.adapter import ACPAdapter

__all__ = [
    "ACPDecisionBridge",
    "ACPProxy",
    "ACPAdapter",
    "ACPTransport",
    "ACPSessionManager",
    "ACPAgentSession",
    "ACPPermissionsBridge",
    "ACPPermissionRequest",
    "ACPEventBridge",
    "ACPInternalEvent",
    "ACPCapabilityMap",
    "ACPCapabilitySpec",
    "ACPCompatibility",
    "ACPFsGateway",
    "ACPTerminalGateway",
    "ACPMessage",
    "ACPRequest",
    "ACPResponse",
    "ACPNotification",
    "ACPErrorData",
    "DEFAULT_PROTOCOL_VERSION",
    "SUPPORTED_PROTOCOL_VERSIONS",
]
