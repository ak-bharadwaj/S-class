"""
S-Class Integration: OpenAI Codex Platform Adapter.
Handles Codex events:
- shell commands
- file changes
- permission requests
- MCP tool calls
- subagent delegation
- plan / review activity
- handoff package generation
"""

from __future__ import annotations
import os
import shutil
from typing import Dict, Any, Optional, List

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.domain.capability import CAP_TERMINAL_EXECUTE, CAP_FILESYSTEM_WRITE, CAP_PROCESS_SPAWN
from sclass.control.authorization import authorize
from sclass.integrations.base import AdapterCapabilities, AdapterStatus, BasePlatformAdapter
from sclass.integrations.acp.adapter import ACPAdapter
from sclass.integrations.mcp.gateway import MCPGateway
from sclass.context.handoff import HandoffAssembler, HandoffPackage


class CodexAdapter(BasePlatformAdapter):
    """Adapts OpenAI Codex CLI and ACP events to S-Class control plane."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        super().__init__(
            workspace_dir=workspace_dir,
            platform_id="codex",
            mode=mode,
            capabilities=AdapterCapabilities(
                pre_action_enforcement=True,
                post_action_observation=True,
                approval=True,
                verification=True,
                session_events=True,
                native_protocol="acp",
            ),
        )
        self.acp = ACPAdapter(workspace_dir=self.workspace_dir, agent_id="codex", mode=mode)
        self.mcp_gateway = MCPGateway(workspace_dir=self.workspace_dir, server_id="codex_mcp", mode=mode)

    def inspect_status(self) -> AdapterStatus:
        if shutil.which("codex"):
            return AdapterStatus.INSTALLED
        return AdapterStatus.SUPPORTED

    @property
    def status(self) -> AdapterStatus:
        return self.inspect_status()

    def on_command(self, command: str, task_id: Optional[str] = None) -> AuthorizationDecision:
        """Evaluates shell commands executed by Codex."""
        req = ActionRequest(
            actor="codex",
            session=task_id or "",
            capability=CAP_TERMINAL_EXECUTE,
            action="run_command",
            target=command,
            parameters={"command": command},
            workspace=self.workspace_dir,
            context={"command": command},
            provenance={"platform": "codex", "agent": "codex"},
            agent="codex",
            platform="codex",
            tool="bash",
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

    def on_file_change(self, file_path: str, action: str = "write_file", task_id: Optional[str] = None) -> AuthorizationDecision:
        """Evaluates file creations or modifications by Codex."""
        req = ActionRequest(
            actor="codex",
            session=task_id or "",
            capability=CAP_FILESYSTEM_WRITE,
            action=action,
            target=file_path,
            parameters={"file_path": file_path},
            workspace=self.workspace_dir,
            context={"file_path": file_path},
            provenance={"platform": "codex", "agent": "codex"},
            agent="codex",
            platform="codex",
            tool="file_editor",
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

    def on_permission(self, tool_name: str, arguments: Dict[str, Any], task_id: Optional[str] = None) -> Dict[str, Any]:
        """Evaluates permission request through ACP bridge."""
        return self.acp.process_acp_message({
            "jsonrpc": "2.0",
            "id": "codex-perm",
            "method": "permission",
            "params": {"tool": tool_name, "arguments": arguments, "task_id": task_id},
        })

    def on_mcp_call(self, tool_name: str, arguments: Dict[str, Any], task_id: Optional[str] = None) -> Dict[str, Any]:
        """Routes Codex MCP tool invocations through the S-Class MCP gateway."""
        return self.mcp_gateway.handle_call_tool(
            tool_name=tool_name,
            arguments=arguments,
            agent_id="codex",
            task_id=task_id,
        )

    def on_subagent_dispatch(self, subagent_name: str, goal: str, task_id: Optional[str] = None) -> AuthorizationDecision:
        """Evaluates whether Codex is authorized to spawn a subagent."""
        req = ActionRequest(
            actor="codex",
            session=task_id or "",
            capability=CAP_PROCESS_SPAWN,
            action="spawn_subagent",
            target=subagent_name,
            parameters={"subagent": subagent_name, "goal": goal},
            workspace=self.workspace_dir,
            context={"goal": goal},
            provenance={"platform": "codex", "agent": "codex"},
            agent="codex",
            platform="codex",
            tool="subagent_dispatcher",
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

    def on_review_event(self, review_notes: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Records plan / review event into journal without modifying authoritative state."""
        return {
            "event": "codex.review",
            "notes": review_notes,
            "task_id": task_id,
            "status": "acknowledged",
        }

    def create_handoff(self, project_id: str, next_action: Optional[str] = None) -> HandoffPackage:
        assembler = HandoffAssembler(self.workspace_dir)
        return assembler.assemble_package(project_id, next_action=next_action)
