"""
S-Class Integration: Official MCP Protocol Transport Layer (MCP 2026-07-28).
Implements the clean architectural boundary:
    MCPProtocolTransport (Headers, Stateless Routing, Framing)
            ↓
    MCPNormalizer (Tool Identity, Provenance)
            ↓
    S-Class Authorization (Policy Enforcement)
            ↓
    MCP Execution / Result / Evidence

Leverages official mcp.types (where available) while providing robust
schemas for JSON-RPC 2.0 protocol envelopes, July 2026 stateless self-describing
routing, header-based policy validation, and explicit tool execution results.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, Optional, List, Union, Tuple
from pydantic import BaseModel, Field, ConfigDict

try:
    import mcp.types as mcp_types
    HAS_MCP_SDK = True
except ImportError:
    mcp_types = None
    HAS_MCP_SDK = False

from sclass.domain.action import AuthorizationDecision


SUPPORTED_MCP_VERSIONS = ("2024-11-05", "2025-01-01", "2026-07-28", "v1")
DEFAULT_MCP_VERSION = "2026-07-28"


class MCPHeaderPolicy:
    """
    Validates and enforces header-based routing and policy checks under MCP 2026-07-28:
    - MCP-Protocol-Version (must match supported protocol versions)
    - Mcp-Method / MCP-Method (must match requested JSON-RPC method)
    - Mcp-Name / MCP-Name (must match tool or resource name)
    """

    @classmethod
    def get_header(cls, headers: Dict[str, str], header_name: str) -> Optional[str]:
        """Case-insensitive header lookup."""
        if not headers:
            return None
        target = header_name.lower()
        for k, v in headers.items():
            if k.lower() == target:
                return str(v)
        return None

    @classmethod
    def validate_headers(
        cls,
        headers: Dict[str, str],
        expected_method: Optional[str] = None,
        expected_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates MCP headers against expected method and supported protocol version.
        Returns (is_valid, error_reason).
        """
        if not headers:
            return True, None

        # 1. Validate MCP-Protocol-Version if present
        proto_ver = cls.get_header(headers, "MCP-Protocol-Version") or cls.get_header(headers, "Mcp-Protocol-Version")
        if proto_ver:
            if proto_ver not in SUPPORTED_MCP_VERSIONS:
                return False, f"Unsupported MCP-Protocol-Version '{proto_ver}'. Supported: {list(SUPPORTED_MCP_VERSIONS)}"

        # 2. Validate Mcp-Method if present
        mcp_method = cls.get_header(headers, "Mcp-Method") or cls.get_header(headers, "MCP-Method")
        if mcp_method and expected_method:
            if mcp_method.lower() != expected_method.lower():
                return False, f"Header Mcp-Method '{mcp_method}' does not match request method '{expected_method}'"

        # 3. Validate Mcp-Name if present
        mcp_name = cls.get_header(headers, "Mcp-Name") or cls.get_header(headers, "MCP-Name")
        if mcp_name and expected_name:
            if mcp_name != expected_name:
                return False, f"Header Mcp-Name '{mcp_name}' does not match target name '{expected_name}'"

        return True, None


class MCPProtocolRequest(BaseModel):
    """Normalized inbound MCP JSON-RPC 2.0 request envelope."""
    model_config = ConfigDict(extra="allow")
    jsonrpc: str = Field(default="2.0")
    id: Union[str, int]
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class StatelessSelfDescribingRequest(BaseModel):
    """Stateless self-describing request under MCP 2026-07-28."""
    model_config = ConfigDict(extra="allow")
    rpc_request: MCPProtocolRequest
    headers: Dict[str, str] = Field(default_factory=dict)
    protocol_version: str = Field(default=DEFAULT_MCP_VERSION)
    routing_key: Optional[str] = None


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
    def parse_stateless_request(
        cls,
        raw_rpc: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> StatelessSelfDescribingRequest:
        """Parses a self-describing stateless MCP request with protocol headers."""
        req = cls.parse_request(raw_rpc)
        hdrs = dict(headers or {})
        # If headers were embedded in params (e.g. meta or headers key)
        if "headers" in raw_rpc and isinstance(raw_rpc["headers"], dict):
            hdrs.update(raw_rpc["headers"])
        if "_meta" in req.params and isinstance(req.params["_meta"], dict):
            meta_headers = req.params["_meta"].get("headers")
            if isinstance(meta_headers, dict):
                hdrs.update(meta_headers)

        proto_ver = (
            MCPHeaderPolicy.get_header(hdrs, "MCP-Protocol-Version")
            or raw_rpc.get("protocol_version")
            or DEFAULT_MCP_VERSION
        )

        return StatelessSelfDescribingRequest(
            rpc_request=req,
            headers=hdrs,
            protocol_version=proto_ver,
            routing_key=MCPHeaderPolicy.get_header(hdrs, "Mcp-Routing-Key"),
        )

    @classmethod
    def build_tool_result(
        cls,
        call_id: Union[str, int],
        content: Any,
        status: str = "success",
        mcp_identity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Constructs an official MCP CallToolResult response."""
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
