"""
S-Class Domain: Capability Security Model.
Defines multidimensional capabilities governing agent and tool operations.
"""

from __future__ import annotations
import fnmatch
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Union

# Canonical capability operation tokens
CAP_TERMINAL_EXECUTE = "terminal.execute"
CAP_FILESYSTEM_READ = "filesystem.read"
CAP_FILESYSTEM_WRITE = "filesystem.write"
CAP_GIT_READ = "git.read"
CAP_GIT_WRITE = "git.write"
CAP_NETWORK_REQUEST = "network.request"
CAP_SECRET_READ = "secret.read"
CAP_PROCESS_SPAWN = "process.spawn"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NetworkAccessLevel(str, Enum):
    NONE = "none"
    LOCAL = "local"
    EGRESS = "egress"
    FULL = "full"


class FilesystemAccessLevel(str, Enum):
    NONE = "none"
    READ = "read"
    READ_WRITE = "read_write"
    ISOLATED = "isolated"


@dataclass(frozen=True)
class Capability:
    """
    Multidimensional capability specification defining explicit permissions
    for an actor executing operations within an S-Class workspace.
    """
    operation: str
    actor: str = "*"
    resource: str = "*"
    scope: str = "workspace"
    workspace: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    risk: str = "medium"
    duration: Optional[float] = None
    network: Union[bool, str] = False
    filesystem: str = "read_write"
    credentials: List[str] = field(default_factory=list)
    approval: Union[bool, str] = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def allows_operation(self, requested_op: str) -> bool:
        """Evaluates whether this capability permits the requested operation."""
        if self.operation in ("*", requested_op):
            return True
        if self.operation.endswith(".*"):
            prefix = self.operation[:-2]
            return requested_op.startswith(prefix + ".")
        return False

    def allows_actor(self, requested_actor: str) -> bool:
        """Evaluates whether this capability applies to the requested actor."""
        if self.actor in ("*", requested_actor):
            return True
        return fnmatch.fnmatch(requested_actor, self.actor)

    def allows_resource(self, requested_resource: str, workspace_dir: str = "") -> bool:
        """Evaluates whether the resource target matches allowed resource patterns."""
        if self.resource == "*":
            return True
        if not requested_resource:
            return True

        norm_req = requested_resource.replace("\\", "/")
        norm_res = self.resource.replace("\\", "/")

        if fnmatch.fnmatch(norm_req, norm_res):
            return True

        # Check path prefix containment if both are absolute or relative
        if self.scope == "workspace" and workspace_dir:
            ws_norm = os.path.abspath(workspace_dir).replace("\\", "/").rstrip("/")
            req_abs = os.path.abspath(os.path.join(workspace_dir, requested_resource)).replace("\\", "/")
            if req_abs.startswith(ws_norm):
                return True

        return False

    def allows_request(self, request: Any, workspace_dir: str = "") -> bool:
        """
        Evaluates whether an ActionRequest is fully permitted by this capability.
        """
        req_actor = getattr(request, "actor", None) or getattr(request, "agent", "unknown")
        req_op = getattr(request, "capability", None) or getattr(request, "action", "")
        req_target = getattr(request, "target", "")
        ws = workspace_dir or getattr(request, "workspace", "")

        if not self.allows_actor(req_actor):
            return False
        if not self.allows_operation(req_op):
            return False
        if not self.allows_resource(req_target, ws):
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "actor": self.actor,
            "resource": self.resource,
            "scope": self.scope,
            "workspace": self.workspace,
            "arguments": dict(self.arguments),
            "risk": self.risk,
            "duration": self.duration,
            "network": self.network,
            "filesystem": self.filesystem,
            "credentials": list(self.credentials),
            "approval": self.approval,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Capability:
        return cls(
            operation=data.get("operation", "*"),
            actor=data.get("actor", "*"),
            resource=data.get("resource", "*"),
            scope=data.get("scope", "workspace"),
            workspace=data.get("workspace", ""),
            arguments=dict(data.get("arguments", {})),
            risk=data.get("risk", "medium"),
            duration=data.get("duration"),
            network=data.get("network", False),
            filesystem=data.get("filesystem", "read_write"),
            credentials=list(data.get("credentials", [])),
            approval=data.get("approval", False),
            metadata=dict(data.get("metadata", {})),
        )
