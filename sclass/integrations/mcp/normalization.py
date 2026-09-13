"""
S-Class MCP Integration: Request Normalization and Tool Identity.
Binds complete provenance for every MCP tool call:
- server_id
- server_version
- tool_name
- tool_schema_hash
- arguments_hash
- authorization_context
- task_id
- agent_id
"""

from __future__ import annotations
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from sclass.domain.action import ActionRequest


def compute_hash(data: Any) -> str:
    """Computes deterministic SHA256 of arbitrary serializable payload."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MCPToolCall:
    """Authoritative normalized MCP tool call identity."""
    server_id: str
    server_version: str
    tool_name: str
    tool_schema_hash: str
    arguments_hash: str
    authorization_context: Dict[str, Any]
    task_id: Optional[str]
    agent_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    call_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def compute_identity_digest(self) -> str:
        payload = (
            f"{self.server_id}:{self.server_version}:{self.tool_name}:"
            f"{self.tool_schema_hash}:{self.arguments_hash}:{self.task_id}:{self.agent_id}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_action_request(self, workspace_dir: str) -> ActionRequest:
        target = (
            self.parameters.get("target")
            or self.parameters.get("path")
            or self.parameters.get("command")
            or self.parameters.get("file_path")
            or ""
        )
        return ActionRequest(
            agent=self.agent_id,
            platform="mcp",
            action=self.tool_name,
            tool=f"{self.server_id}/{self.tool_name}",
            target=str(target),
            parameters=self.parameters,
            workspace=workspace_dir,
            task_id=self.task_id,
            context={
                "server_id": self.server_id,
                "server_version": self.server_version,
                "tool_schema_hash": self.tool_schema_hash,
                "arguments_hash": self.arguments_hash,
                "authorization_context": self.authorization_context,
                "call_id": self.call_id,
                "identity_digest": self.compute_identity_digest(),
            },
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server_id": self.server_id,
            "server_version": self.server_version,
            "tool_name": self.tool_name,
            "tool_schema_hash": self.tool_schema_hash,
            "arguments_hash": self.arguments_hash,
            "authorization_context": self.authorization_context,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "parameters": self.parameters,
            "call_id": self.call_id,
            "timestamp": self.timestamp,
            "identity_digest": self.compute_identity_digest(),
        }
