"""
S-Class Integration: Official ACP (Agent Client Protocol) Protocol Specification & Schema.
Provides strict Pydantic models for JSON-RPC 2.0 ACP protocol envelopes:
- initialize, session/new, prompt, session/update, permission, tool/action,
  cancellation, session/resume, session/fork, shutdown.

Enforces protocol boundaries: S-Class delegates protocol correctness to this schema layer,
normalizing validated ACP messages into S-Class domain ActionRequests and PermissionRequests.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


# Standard ACP Protocol Release Identifiers
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-01-01", "2026-07-28")
DEFAULT_PROTOCOL_VERSION = "2026-07-28"


class ACPErrorData(BaseModel):
    """Standard JSON-RPC 2.0 Error Object."""
    model_config = ConfigDict(extra="allow")
    code: int
    message: str
    data: Optional[Any] = None


class ACPMessage(BaseModel):
    """Base JSON-RPC 2.0 envelope."""
    model_config = ConfigDict(extra="allow")
    jsonrpc: str = Field(default="2.0")


class ACPRequest(ACPMessage):
    """Incoming ACP JSON-RPC 2.0 Request."""
    id: Union[str, int]
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class ACPNotification(ACPMessage):
    """Incoming or outgoing ACP JSON-RPC 2.0 Notification (no id)."""
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class ACPResponse(ACPMessage):
    """Outgoing ACP JSON-RPC 2.0 Response."""
    id: Optional[Union[str, int]]
    result: Optional[Any] = None
    error: Optional[ACPErrorData] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            out["error"] = self.error.model_dump()
        else:
            out["result"] = self.result if not isinstance(self.result, BaseModel) else self.result.model_dump()
        return out


# Typed Parameter & Result Schemas for ACP Lifecycle Methods

class ACPInitializeParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    clientInfo: Optional[Dict[str, Any]] = None
    protocolVersion: Optional[str] = None


class ACPInitializeResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    protocolVersion: str = Field(default=DEFAULT_PROTOCOL_VERSION)
    sessionId: str
    capabilities: Dict[str, Any]
    serverInfo: Optional[Dict[str, Any]] = None


class ACPSessionNewParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    cwd: Optional[str] = None
    agentId: Optional[str] = None
    env: Optional[Dict[str, str]] = None


class ACPSessionNewResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    sessionId: str
    status: str = "active"


class ACPPromptParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    sessionId: str
    prompt: str
    context: Optional[Dict[str, Any]] = None


class ACPPromptResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    message: Optional[str] = None


class ACPPermissionParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    requestId: str
    sessionId: str
    tool: str
    target: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None


class ACPPermissionResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    authorized: bool
    policyId: Optional[str] = None
    reason: Optional[str] = None


class ACPToolCallParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    tool: Optional[str] = None
    name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    sessionId: Optional[str] = None
    taskId: Optional[str] = None

    @property
    def tool_name(self) -> str:
        return self.tool or self.name or "unknown_tool"

    @property
    def tool_args(self) -> Dict[str, Any]:
        return self.arguments or self.parameters or {}


class ACPToolCallResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    data: Any = None
    metadata: Optional[Dict[str, Any]] = None


class ACPSessionForkParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    sessionId: str


class ACPSessionForkResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    sessionId: str
    forkedFrom: str


class ACPShutdownParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    sessionId: Optional[str] = None


class ACPShutdownResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str = "closed"


class ACPProtocolTransport:
    """
    Authoritative ACP Protocol Transport.
    Validates inbound messages against official JSON-RPC 2.0 ACP schemas
    and packages conformant outgoing responses.
    """

    @classmethod
    def validate_request(cls, raw_message: Dict[str, Any]) -> ACPRequest:
        """Strictly validates an incoming dictionary against JSON-RPC 2.0 ACPRequest."""
        if not isinstance(raw_message, dict):
            raise ValueError("Malformed ACP message: payload must be a JSON object.")
        if raw_message.get("jsonrpc") != "2.0":
            raise ValueError("Malformed ACP message: 'jsonrpc' must be '2.0'.")
        if "id" not in raw_message:
            raise ValueError("Malformed ACP message: missing request 'id'.")
        if not raw_message.get("method"):
            raise ValueError("Malformed ACP message: missing request 'method'.")
        return ACPRequest.model_validate(raw_message)

    @classmethod
    def create_response(cls, request_id: Union[str, int, None], result: Union[BaseModel, Dict[str, Any]]) -> Dict[str, Any]:
        """Creates a schema-compliant ACP JSON-RPC 2.0 response."""
        res_data = result.model_dump() if isinstance(result, BaseModel) else result
        resp = ACPResponse(id=request_id, result=res_data)
        return resp.to_dict()

    @classmethod
    def create_error(cls, request_id: Union[str, int, None], code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
        """Creates a schema-compliant ACP JSON-RPC 2.0 error response."""
        err = ACPErrorData(code=code, message=message, data=data)
        resp = ACPResponse(id=request_id, error=err)
        return resp.to_dict()
