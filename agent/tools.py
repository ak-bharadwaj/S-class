"""
S-Class EOS V11.2 - D7 Capability-Scoped Agent Tool Registry (§8.1, §8.3).
Provides strictly schema-validated inspection and action proposal tools using jsonschema Draft 2020-12.
Enforces capability verification at tool execution / validation time: tools cannot be invoked
without the required capabilities in the granted session capability set.
"""

from __future__ import annotations
import jsonschema
from typing import Dict, Optional, Sequence, Any, Tuple
from agent.models import ToolDefinition, AgentToolCall, AgentToolResult


class AgentToolRegistry:
    """Registry of capability-scoped tools exposed to AI workers with Draft 2020-12 schema validation."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._validators: Dict[str, jsonschema.Draft202012Validator] = {}
        self._register_default_tools()

    def register(self, tool: ToolDefinition) -> None:
        if not isinstance(tool, ToolDefinition):
            raise TypeError("tool must be an instance of ToolDefinition.")
        self._tools[tool.name] = tool
        # Compile full Draft 2020-12 JSON Schema validator
        validator = jsonschema.Draft202012Validator(dict(tool.parameters_schema))
        self._validators[tool.name] = validator

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

    def validate_tool_call(
        self,
        tool_call: AgentToolCall,
        granted_capabilities: Sequence[str],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates tool call against:
        1. Tool existence in registry.
        2. Session capability enforcement: every tool.required_capability must be in granted_capabilities.
        3. Full standard JSON Schema validation (Draft 2020-12).
        """
        if not isinstance(tool_call, AgentToolCall):
            return False, "Invalid tool_call object type."
        
        tool_def = self.get_tool(tool_call.tool_name)
        if not tool_def:
            return False, f"Unknown tool '{tool_call.tool_name}'."

        # 1. Enforce capability authorization at validation time
        granted_set = set(granted_capabilities)
        for req_cap in tool_def.required_capabilities:
            if req_cap not in granted_set:
                return False, f"Missing required capability '{req_cap}' for tool '{tool_call.tool_name}'."

        # 2. Full JSON Schema validation against registered parameters_schema
        validator = self._validators.get(tool_call.tool_name)
        if validator is None:
            validator = jsonschema.Draft202012Validator(dict(tool_def.parameters_schema))
            self._validators[tool_call.tool_name] = validator

        args_dict = dict(tool_call.arguments)
        errors = list(validator.iter_errors(args_dict))
        if errors:
            first_err = errors[0]
            field_name = ".".join(str(p) for p in first_err.path) or "arguments"
            return False, f"Schema validation error on {field_name}: {first_err.message}"

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
                        "path": {"type": "string", "minLength": 1, "description": "Relative path to file inside workspace."},
                        "start_line": {"type": "integer", "minimum": 1, "description": "1-indexed starting line."},
                        "end_line": {"type": "integer", "minimum": 1, "description": "1-indexed ending line."},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
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
                        "query": {"type": "string", "minLength": 1, "description": "Keyword search query."},
                        "glob_filter": {"type": "string", "description": "Optional file glob filter."},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
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
                        "obligation_id": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$", "description": "Obligation ID."},
                        "target_file": {"type": "string", "minLength": 1, "description": "Target file relative path."},
                        "patch_content": {"type": "string", "minLength": 1, "description": "Unified diff or replacement content."},
                        "purpose": {"type": "string", "minLength": 1, "description": "Purpose of the patch modification."},
                    },
                    "required": ["obligation_id", "target_file", "patch_content", "purpose"],
                    "additionalProperties": False,
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
                        "obligation_id": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$", "description": "Obligation ID."},
                        "target_test": {"type": "string", "minLength": 1, "description": "Target test file relative path."},
                        "purpose": {"type": "string", "minLength": 1, "description": "Purpose of test execution."},
                        "parameters": {"type": "object", "description": "Optional execution parameters."},
                    },
                    "required": ["obligation_id", "target_test", "purpose"],
                    "additionalProperties": False,
                },
                required_capabilities=("CAP_PROPOSE_ACTION",),
                is_proposal_tool=True,
            )
        )
