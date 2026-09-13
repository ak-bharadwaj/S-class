"""
S-Class MCP Integration: Tool Registry, Schema Hashing, and Trust Invalidation.
Tracks tool definitions and schemas across MCP servers.
Enforces Invariant: If a tool definition or schema changes, its trust cache
is immediately invalidated to prevent tool mutation attacks.
"""

from __future__ import annotations
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List, Set


def compute_schema_hash(schema: Dict[str, Any]) -> str:
    """Computes authoritative SHA256 digest of an MCP tool input schema."""
    canonical = json.dumps(schema or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MCPToolDefinition:
    """Registered MCP tool schema and metadata."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    schema_hash: str
    server_id: str
    version: str = "1.0.0"
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "schema_hash": self.schema_hash,
            "server_id": self.server_id,
            "version": self.version,
            "registered_at": self.registered_at,
        }


class MCPToolRegistry:
    """
    Registry of validated MCP tools per server.
    Detects dynamic tool tampering and invalidates trust when definitions change.
    """

    def __init__(self):
        # Key: (server_id, tool_name) -> MCPToolDefinition
        self._tools: Dict[Tuple[str, str], MCPToolDefinition] = {}
        self._invalidated_tools: Set[Tuple[str, str]] = set()

    def register_tool(
        self,
        server_id: str,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        version: str = "1.0.0",
    ) -> Tuple[MCPToolDefinition, bool]:
        """
        Registers or updates an MCP tool definition.
        Returns (definition, was_invalidated).
        If the schema hash has changed since prior registration, trust is invalidated!
        """
        new_hash = compute_schema_hash(input_schema)
        key = (server_id, name)
        existing = self._tools.get(key)

        was_invalidated = False
        if existing and existing.schema_hash != new_hash:
            # Tool definition changed -> trust/cache invalidation!
            was_invalidated = True
            self._invalidated_tools.add(key)

        defn = MCPToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            schema_hash=new_hash,
            server_id=server_id,
            version=version,
        )
        self._tools[key] = defn
        return defn, was_invalidated

    def get_tool(self, server_id: str, name: str) -> Optional[MCPToolDefinition]:
        return self._tools.get((server_id, name))

    def is_invalidated(self, server_id: str, name: str) -> bool:
        return (server_id, name) in self._invalidated_tools

    def list_tools(self, server_id: Optional[str] = None) -> List[MCPToolDefinition]:
        if server_id:
            return [t for (s, _), t in self._tools.items() if s == server_id]
        return list(self._tools.values())
