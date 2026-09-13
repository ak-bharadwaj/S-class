"""
S-Class ACP Integration: Agent Capability Mapping.
Maps external ACP agent capabilities and tools into authoritative S-Class capabilities.
"""

from __future__ import annotations
from typing import Dict, Any, List, Set, Optional
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ACPCapabilitySpec:
    """Declared capabilities of an agent or client under ACP v1."""
    tools: tuple[str, ...] = field(default_factory=tuple)
    prompts: tuple[str, ...] = field(default_factory=tuple)
    streaming: bool = True
    cancellation: bool = True
    authorization: bool = True
    fs_gateway: bool = True
    terminal_gateway: bool = True


# Mapping of ACP tool names to canonical S-Class capability tokens
ACP_TOOL_TO_SCLASS_CAPABILITY: Dict[str, str] = {
    "run_command": "terminal.execute",
    "execute_command": "terminal.execute",
    "bash": "terminal.execute",
    "terminal/exec": "terminal.execute",
    "fs/read": "filesystem.read",
    "fs/write": "filesystem.write",
    "fs/list": "filesystem.read",
    "read_file": "filesystem.read",
    "view_file": "filesystem.read",
    "list_dir": "filesystem.read",
    "write_file": "filesystem.write",
    "write_to_file": "filesystem.write",
    "replace_file_content": "filesystem.write",
    "edit_file": "filesystem.write",
    "git": "git.execute",
}


class ACPCapabilityMap:
    """Translates ACP capability requests into S-Class authorization capability tokens."""

    @classmethod
    def resolve_capability(cls, tool_name: str) -> str:
        """Resolves ACP tool name to canonical S-Class capability string."""
        return ACP_TOOL_TO_SCLASS_CAPABILITY.get(tool_name, f"custom.{tool_name}")

    @classmethod
    def validate_capability_access(
        cls, declared_spec: ACPCapabilitySpec, requested_tool: str
    ) -> bool:
        """Verifies if an agent declared access to a requested tool or capability."""
        if not declared_spec.tools:
            return True  # If not restricted, allow policy engine to evaluate
        return requested_tool in declared_spec.tools
