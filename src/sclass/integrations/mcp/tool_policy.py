"""
S-Class MCP Integration: Tool Policy Registry.
Maps Model Context Protocol tool calls into canonical ActionRequests and risk levels.
"""

from __future__ import annotations
from typing import Dict, Any, Tuple, Optional

from sclass.domain.action import ActionRequest


TOOL_ACTION_MAP: Dict[str, Tuple[str, str]] = {
    # Tool Name -> (Action Type, Target Key)
    "read_file": ("file_read", "path"),
    "view_file": ("file_read", "AbsolutePath"),
    "list_dir": ("dir_read", "DirectoryPath"),
    "find_by_name": ("dir_read", "SearchDirectory"),
    "grep_search": ("code_search", "SearchPath"),
    "write_file": ("file_edit", "path"),
    "write_to_file": ("file_edit", "TargetFile"),
    "replace_file_content": ("file_edit", "TargetFile"),
    "edit_file": ("file_edit", "path"),
    "run_command": ("run_command", "CommandLine"),
    "execute_command": ("run_command", "command"),
    "bash": ("run_command", "command"),
}


class MCPToolPolicy:
    """Translates incoming MCP call_tool parameters into an ActionRequest."""

    @staticmethod
    def map_call_to_request(
        tool_name: str,
        arguments: Dict[str, Any],
        workspace_dir: str,
        agent: str = "mcp_agent",
        task_id: Optional[str] = None,
    ) -> ActionRequest:
        mapping = TOOL_ACTION_MAP.get(tool_name)
        if mapping:
            action_type, target_key = mapping
            target = str(arguments.get(target_key, ""))
        else:
            action_type = "tool_invocation"
            target = tool_name

        return ActionRequest(
            agent=agent,
            platform="mcp",
            action=action_type,
            tool=tool_name,
            target=target,
            parameters=arguments,
            workspace=workspace_dir,
            task_id=task_id,
        )
