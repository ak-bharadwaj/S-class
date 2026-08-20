"""
S-Class EOS V11.2 - D7 Capability-Scoped Agent Tool Registry (§8.1, §8.3).
Provides strictly schema-validated inspection and action proposal tools.
"""

from __future__ import annotations
import os
from typing import Dict, Optional, Sequence, Any, Tuple
from agent.models import ToolDefinition, AgentToolCall, AgentToolResult
from execution.workspace import IsolatedWorkspace


class AgentToolRegistry:
    """Registry of capability-scoped tools exposed to AI workers."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register(self, tool: ToolDefinition) -> None:
        if not isinstance(tool, ToolDefinition):
            raise TypeError("tool must be an instance of ToolDefinition.")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> Sequence[ToolDefinition]:
        return tuple(self._tools.values())

    def get_available_tools_for_capabilities(self, granted_capabilities: Sequence[str]) -> Tuple[ToolDefinition, ...]:
        """Returns only tools whose required capabilities are a subset of granted_capabilities."""
        granted_set = set(granted_capabilities)
        available = []
        for tool in self._tools.values():
            if all(cap in granted_set for cap in tool.required_capabilities):
                available.append(tool)
        return tuple(available)

    def validate_tool_call(self, tool_call: AgentToolCall) -> Tuple[bool, Optional[str]]:
        """Validates that a tool call matches a registered tool and required argument types."""
        if not isinstance(tool_call, AgentToolCall):
            return False, "Invalid tool_call object type."
        
        tool_def = self.get_tool(tool_call.tool_name)
        if not tool_def:
            return False, f"Unknown tool '{tool_call.tool_name}'."

        schema = tool_def.parameters_schema
        required_props = schema.get("required", [])
        props = schema.get("properties", {})

        for req in required_props:
            if req not in tool_call.arguments:
                return False, f"Missing required argument '{req}' for tool '{tool_call.tool_name}'."

        for arg_name, arg_val in tool_call.arguments.items():
            if arg_name in props:
                expected_type = props[arg_name].get("type")
                if expected_type == "string" and not isinstance(arg_val, str):
                    return False, f"Argument '{arg_name}' must be a string, got {type(arg_val).__name__}."
                elif expected_type == "integer" and not isinstance(arg_val, int):
                    return False, f"Argument '{arg_name}' must be an integer, got {type(arg_val).__name__}."
                elif expected_type == "number" and not isinstance(arg_val, (int, float)):
                    return False, f"Argument '{arg_name}' must be a number, got {type(arg_val).__name__}."
                elif expected_type == "object" and not isinstance(arg_val, dict):
                    return False, f"Argument '{arg_name}' must be an object/dict, got {type(arg_val).__name__}."

        return True, None

    def _register_default_tools(self) -> None:
        # 1. read_file_chunk
        self.register(
            ToolDefinition(
                name="read_file_chunk",
                description="Reads a slice of lines from a workspace-contained file.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to file inside workspace."},
                        "start_line": {"type": "integer", "description": "1-indexed starting line."},
                        "end_line": {"type": "integer", "description": "1-indexed ending line."},
                    },
                    "required": ["path"],
                },
                required_capabilities=("CAP_READ_CODE",),
                is_proposal_tool=False,
            )
        )

        # 2. search_codebase
        self.register(
            ToolDefinition(
                name="search_codebase",
                description="Performs keyword search across workspace files.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Keyword search query."},
                        "glob_filter": {"type": "string", "description": "Optional file glob filter."},
                    },
                    "required": ["query"],
                },
                required_capabilities=("CAP_READ_CODE",),
                is_proposal_tool=False,
            )
        )

        # 3. propose_code_patch
        self.register(
            ToolDefinition(
                name="propose_code_patch",
                description="Synthesizes and proposes a code patch action to the D5 Controller.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "obligation_id": {"type": "string", "description": "Obligation ID targeted by patch."},
                        "target_file": {"type": "string", "description": "Target file relative path."},
                        "patch_content": {"type": "string", "description": "Unified diff or replacement content."},
                        "purpose": {"type": "string", "description": "Purpose of the patch modification."},
                    },
                    "required": ["obligation_id", "target_file", "patch_content", "purpose"],
                },
                required_capabilities=("CAP_PROPOSE_ACTION",),
                is_proposal_tool=True,
            )
        )

        # 4. propose_test_run
        self.register(
            ToolDefinition(
                name="propose_test_run",
                description="Proposes running a pytest verification suite against target test file.",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "obligation_id": {"type": "string", "description": "Obligation ID targeted by test."},
                        "target_test": {"type": "string", "description": "Target test file relative path."},
                        "purpose": {"type": "string", "description": "Purpose of test execution."},
                        "parameters": {"type": "object", "description": "Optional execution parameters (e.g. quiet, maxfail)."},
                    },
                    "required": ["obligation_id", "target_test", "purpose"],
                },
                required_capabilities=("CAP_PROPOSE_ACTION",),
                is_proposal_tool=True,
            )
        )
