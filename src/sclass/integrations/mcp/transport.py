"""
S-Class Integration: Official MCP Protocol Transport Layer.
Implements the clean architectural boundary:
    MCPProtocolTransport
            ↓
    MCPNormalizer
            ↓
    S-Class Authorization
            ↓
    MCP Execution / Result

Leverages official mcp.types (where available) while providing robust
fallback schemas for JSON-RPC 2.0 protocol envelopes, July 2026 stateless
routing, and explicit tool execution results.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict

try:
    import mcp.types as mcp_types
    HAS_MCP_SDK = True
except ImportError:
    mcp_types = None
    HAS_MCP_SDK = False

from sclass.domain.action import AuthorizationDecision


class MCPProtocolRequest(BaseModel):
    """Normalized inbound MCP JSON-RPC 2.0 request envelope."""
    model_config = ConfigDict(extra="allow")
    jsonrpc: str = Field(default="2.0")
    id: Union[str, int]
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class MCPProtocolTransport:
    """
    Authoritative transport layer for MCP JSON-RPC 2.0 requests.
    Validates protocol format, extracts request-level routing and Task metadata,
    and constructs schema-compliant MCP responses and errors.
    """

    @classmethod
    def parse_request(cls, raw_rpc: Dict[str, Any]) -> MCPProtocolRequest:
        """Parses and validates raw dictionary as MCP JSON-RPC 2.0 request."""
        if not isinstance(raw_rpc, dict):
            raise ValueError("Malformed MCP message: payload must be a JSON object.")
        if raw_rpc.get("jsonrpc") != "2.0":
            raise ValueError("Malformed MCP message: 'jsonrpc' must be '2.0'.")
        if "id" not in raw_rpc:
            raise ValueError("Malformed MCP message: missing request 'id'.")
        if not raw_rpc.get("method"):
            raise ValueError("Malformed MCP message: missing request 'method'.")
        return MCPProtocolRequest.model_validate(raw_rpc)

    @classmethod
    def build_tool_result(
        cls,
        call_id: Union[str, int],
        content: Any,
        status: str = "success",
        mcp_identity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Constructs an official MCP CallToolResult response."""
        # Convert content to standard MCP content items
        if isinstance(content, list):
            formatted_content = content
        elif isinstance(content, dict):
            formatted_content = [{"type": "text", "text": str(content)}]
        elif isinstance(content, str):
            formatted_content = [{"type": "text", "text": content}]
        else:
            formatted_content = [{"type": "text", "text": "Execution authorized by S-Class"}]

        result_payload: Dict[str, Any] = {
            "status": status,
            "content": formatted_content,
        }
        if mcp_identity:
            result_payload["mcp_identity"] = mcp_identity

        return {
            "jsonrpc": "2.0",
            "id": call_id,
            "result": result_payload,
        }

    @classmethod
    def build_authorization_denied(
        cls,
        call_id: Union[str, int],
        decision: AuthorizationDecision,
        mcp_identity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Constructs standard MCP -32003 authorization rejection error."""
        error_data = {
            "policy_id": decision.policy_id,
            "reason": decision.reason,
            "risk_level": decision.risk_level,
        }
        if mcp_identity:
            error_data["mcp_identity"] = mcp_identity

        return {
            "jsonrpc": "2.0",
            "id": call_id,
            "error": {
                "code": -32003,
                "message": f"Authorization DENIED by S-Class policy [{decision.policy_id}]: {decision.reason}",
                "data": error_data,
            },
        }

    @classmethod
    def build_error(
        cls,
        call_id: Union[str, int, None],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Constructs standard MCP JSON-RPC error."""
        err_obj: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err_obj["data"] = data
        return {
            "jsonrpc": "2.0",
            "id": call_id,
            "error": err_obj,
        }
