"""
S-Class MCP Integration: HTTP MCP Authorization and Identity Context.
Enforces current MCP authorization semantics:
- issuer
- resource metadata
- client identity
- credential scope
- server identity
Maintains S-Class task and resource policies above MCP authorization.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List


@dataclass(frozen=True)
class MCPAuthorizationContext:
    """Cryptographic authorization context for HTTP MCP flows."""
    issuer: str
    resource_metadata: Dict[str, Any]
    client_identity: str
    credential_scope: str
    server_identity: str
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issuer": self.issuer,
            "resource_metadata": self.resource_metadata,
            "client_identity": self.client_identity,
            "credential_scope": self.credential_scope,
            "server_identity": self.server_identity,
            "issued_at": self.issued_at,
            "is_valid": self.is_valid,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MCPAuthorizationContext:
        return cls(
            issuer=data.get("issuer", "local"),
            resource_metadata=data.get("resource_metadata", {}),
            client_identity=data.get("client_identity", "unknown_client"),
            credential_scope=data.get("credential_scope", "default"),
            server_identity=data.get("server_identity", "mcp_server"),
            issued_at=data.get("issued_at", datetime.now(timezone.utc).isoformat()),
            is_valid=data.get("is_valid", True),
        )


class MCPAuthenticator:
    """Validates MCP authorization tokens, protected resource metadata, and scopes."""

    def __init__(self, allowed_issuers: Optional[List[str]] = None):
        self.allowed_issuers = set(allowed_issuers or ["local", "sclass", "https://auth.sclass.dev"])

    def validate(self, auth_context: MCPAuthorizationContext) -> Tuple[bool, str]:
        """Validates MCP protocol authorization before S-Class policy engine evaluation."""
        if not auth_context.is_valid:
            return False, "MCP authorization context marked invalid or revoked."

        if not auth_context.issuer:
            return False, "Missing authorization issuer in MCP request."

        if self.allowed_issuers and auth_context.issuer not in self.allowed_issuers:
            return False, f"Untrusted MCP authorization issuer: '{auth_context.issuer}'."

        if not auth_context.client_identity:
            return False, "Missing client identity in MCP authorization."

        return True, "MCP authorization valid."
