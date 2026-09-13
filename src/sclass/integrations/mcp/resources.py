"""
S-Class MCP Integration: Protected Resources and Content Boundaries.
Registers and guards MCP resources (files, URIs, templates) against unauthorized reads
and exfiltration according to S-Class security policies.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from sclass.control.resources import classify_resource, AuthorityBoundary


@dataclass(frozen=True)
class MCPResource:
    """Registered MCP resource metadata."""
    uri: str
    name: str
    description: str = ""
    mime_type: Optional[str] = None
    boundary: str = AuthorityBoundary.AGENT_WRITABLE.value
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mime_type": self.mime_type,
            "boundary": self.boundary,
            "metadata": self.metadata,
        }


class MCPResourceRegistry:
    """Registry coordinating MCP resources and boundary enforcement."""

    def __init__(self, workspace_dir: str = ""):
        self.workspace_dir = workspace_dir
        self._resources: Dict[str, MCPResource] = {}

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str = "",
        mime_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MCPResource:
        boundary = classify_resource(uri, self.workspace_dir)
        res = MCPResource(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
            boundary=boundary.value,
            metadata=metadata or {},
        )
        self._resources[uri] = res
        return res

    def get_resource(self, uri: str) -> Optional[MCPResource]:
        return self._resources.get(uri)

    def list_resources(self) -> List[MCPResource]:
        return list(self._resources.values())
