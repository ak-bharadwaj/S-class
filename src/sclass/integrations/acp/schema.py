"""
S-Class Integration: Official ACP (Agent Client Protocol) v1 Schemas.
Provides strict Pydantic models for JSON-RPC 2.0 ACP v1 protocol messages,
parameters, and result objects across complete agent lifecycle:
- initialize, session/new, prompt, session/update, permission, tool/call,
  cancellation, session/resume, session/fork, shutdown, fs/*, and terminal/*.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


# Standard ACP Protocol Release Identifiers
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-01-01", "2026-07-28", "v1")
DEFAULT_PROTOCOL_VERSION = "v1"


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
    sessionId: str
    status: str = "completed"
    output: Optional[str] = None


class ACPSessionUpdateParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    state: Dict[str, Any] = Field(default_factory=dict)


class ACPSessionUpdateResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    status: str = "updated"


class ACPPermissionParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    tool: str
    target: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    reason: Optional[str] = None


class ACPPermissionResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    decision_id: str
    outcome: str  # ALLOW, DENY, REQUIRE_APPROVAL
    policy_id: str
    reason: Optional[str] = None


class ACPToolCallParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ACPToolCallResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    call_id: str
    status: str  # authorized_passthrough, executed, denied
    result: Optional[Any] = None


class ACPCancelParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    reason: Optional[str] = None


class ACPCancelResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    status: str = "cancelled"


class ACPSessionResumeParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    checkpoint_id: Optional[str] = None


class ACPSessionResumeResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    status: str = "resumed"
    resumed_from: Optional[str] = None


class ACPSessionForkParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str


class ACPSessionForkResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    sessionId: str
    forkedFrom: str
    status: str = "forked"


class ACPShutdownParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: Optional[str] = None


class ACPShutdownResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str = "shutdown_complete"


# Gateway Schemas (Filesystem & Terminal)

class ACPFsReadParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    path: str
    offset: Optional[int] = 0
    limit: Optional[int] = None


class ACPFsReadResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    path: str
    content: str
    bytes_read: int


class ACPFsWriteParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    path: str
    content: str
    overwrite: bool = True


class ACPFsWriteResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    path: str
    status: str = "written"
    bytes_written: int
    content_hash: str


class ACPTerminalExecParams(BaseModel):
    model_config = ConfigDict(extra="allow")
    session_id: str
    command: str
    cwd: Optional[str] = None
    timeout: Optional[int] = 60


class ACPTerminalExecResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    command: str
    exit_code: int
    stdout: str
    stderr: str
    execution_receipt_id: Optional[str] = None
