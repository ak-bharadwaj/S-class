"""
S-Class Integration: Claude Code Platform Adapter.
Thin translation layer mapping Claude Code tool use and session hooks into S-Class ActionRequests.
Supports complete workflow:
Claude -> ACP -> S-Class -> workspace:
- prompt
- file read
- file write
- shell
- test run
- permission
- claim
- rejection
- handoff
- resume
"""

from __future__ import annotations
import os
import shutil
from typing import Dict, Any, Optional, Tuple, List

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult
from sclass.control.authorization import authorize
from sclass.verification.engine import verify_claim
from sclass.context.handoff import HandoffPackage, HandoffAssembler
from sclass.integrations.base import AdapterCapabilities, AdapterStatus, BasePlatformAdapter
from sclass.integrations.acp.adapter import ACPAdapter


class ClaudeCodeAdapter(BasePlatformAdapter):
    """Adapts Claude Code hooks, ACP sessions, and tool invocations to S-Class governance."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        super().__init__(
            workspace_dir=workspace_dir,
            platform_id="claude_code",
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
        self.acp = ACPAdapter(workspace_dir=self.workspace_dir, agent_id="claude", mode=mode)
        self.active_session_id: Optional[str] = None

    def inspect_status(self) -> AdapterStatus:
        """Determines honest installation status of Claude Code."""
        if shutil.which("claude"):
            return AdapterStatus.INSTALLED
        return AdapterStatus.SUPPORTED

    @property
    def status(self) -> AdapterStatus:
        return self.inspect_status()

    def start_session(self) -> str:
        """Initializes an ACP session for Claude Code."""
        res = self.acp.process_acp_message({
            "jsonrpc": "2.0",
            "id": "claude-init",
            "method": "initialize",
            "params": {"capabilities": {"tools": ["Bash", "Edit", "View", "Read", "Write"]}},
        })
        self.active_session_id = res["result"]["sessionId"]
        return self.active_session_id

    def on_prompt(self, prompt_text: str) -> Dict[str, Any]:
        """Handles user prompt delivery into Claude session."""
        return self.acp.process_acp_message({
            "jsonrpc": "2.0",
            "id": "claude-prompt",
            "method": "prompt",
            "params": {"session_id": self.active_session_id or "default", "prompt": prompt_text},
        })

    def on_pre_tool_use(self, tool_name: str, tool_input: Dict[str, Any], task_id: Optional[str] = None) -> AuthorizationDecision:
        """Translates Claude Code PreToolUse into an ActionRequest and evaluates policy."""
        target = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("command") or tool_name

        if tool_name in ("Bash", "terminal"):
            action = "run_command"
        elif tool_name in ("Edit", "Write", "MultiEdit"):
            action = "file_edit"
        elif tool_name in ("View", "Read"):
            action = "file_read"
        else:
            action = "tool_call"

        req = ActionRequest(
            actor="claude",
            session=task_id or "",
            capability=tool_name,
            action=action,
            target=str(target),
            parameters=tool_input,
            workspace=self.workspace_dir,
            context={"tool_name": tool_name},
            provenance={"platform": "claude_code", "agent": "claude"},
            agent="claude",
            platform="claude_code",
            tool=tool_name,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

    def on_file_read(self, file_path: str, task_id: Optional[str] = None) -> AuthorizationDecision:
        return self.on_pre_tool_use("View", {"file_path": file_path}, task_id=task_id)

    def on_file_write(self, file_path: str, content: str = "", task_id: Optional[str] = None) -> AuthorizationDecision:
        return self.on_pre_tool_use("Edit", {"file_path": file_path, "content": content}, task_id=task_id)

    def on_shell_command(self, command: str, task_id: Optional[str] = None) -> AuthorizationDecision:
        return self.on_pre_tool_use("Bash", {"command": command}, task_id=task_id)

    def on_permission_request(self, tool_name: str, arguments: Dict[str, Any], task_id: Optional[str] = None) -> Dict[str, Any]:
        """Bridges Claude permission request through ACP protocol bridge."""
        return self.acp.process_acp_message({
            "jsonrpc": "2.0",
            "id": "claude-perm",
            "method": "permission",
            "params": {
                "session_id": self.active_session_id or "default",
                "tool": tool_name,
                "arguments": arguments,
                "task_id": task_id,
            },
        })

    def evaluate_claim(self, claim: Claim, evidence: Any) -> VerificationResult:
        """Authoritatively evaluates Claude's completion claim against observed evidence."""
        return verify_claim(claim, evidence, workspace_dir=self.workspace_dir)

    def create_handoff_package(self, project_id: str, next_action: Optional[str] = None) -> HandoffPackage:
        """Assembles authoritative handoff package when session/credits end."""
        assembler = HandoffAssembler(self.workspace_dir)
        return assembler.assemble_package(project_id, next_action=next_action)

    def resume_session(self, session_id: str) -> Dict[str, Any]:
        """Resumes active Claude session."""
        res = self.acp.process_acp_message({
            "jsonrpc": "2.0",
            "id": "claude-resume",
            "method": "session/resume",
            "params": {"session_id": session_id},
        })
        if "result" in res:
            self.active_session_id = session_id
        return res


# Backward-compatible alias
ClaudeAdapter = ClaudeCodeAdapter
