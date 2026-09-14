"""
S-Class Integration: Cursor IDE Platform Adapter.
Hooks into Cursor agent lifecycle:
- before shell execution
- file operations
- agent events
- approval handling
- command failure reporting
- completion claim evaluation
"""

from __future__ import annotations
import os
import shutil
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.domain.capability import CAP_TERMINAL_EXECUTE, CAP_FILESYSTEM_READ, CAP_FILESYSTEM_WRITE
from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult
from sclass.control.authorization import authorize
from sclass.verification.engine import verify_claim
from sclass.integrations.base import AdapterCapabilities, AdapterStatus, BasePlatformAdapter


class CursorAdapter(BasePlatformAdapter):
    """Adapts Cursor IDE hooks and composer tool calls to S-Class governance."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        super().__init__(
            workspace_dir=workspace_dir,
            platform_id="cursor",
            mode=mode,
            capabilities=AdapterCapabilities(
                pre_action_enforcement=True,
                post_action_observation=False,
                approval=True,
                verification=True,
                session_events=True,
                native_protocol="native_hook",
            ),
        )

    def inspect_status(self) -> AdapterStatus:
        cursor_home = os.path.expanduser("~/.cursor")
        if os.path.exists(cursor_home) or shutil.which("cursor"):
            return AdapterStatus.INSTALLED
        return AdapterStatus.SUPPORTED

    @property
    def status(self) -> AdapterStatus:
        return self.inspect_status()

    def before_shell_execution(self, command: str, task_id: Optional[str] = None) -> AuthorizationDecision:
        """Pre-execution hook for Cursor terminal / bash commands."""
        req = ActionRequest(
            actor="cursor",
            session=task_id or "",
            capability=CAP_TERMINAL_EXECUTE,
            action="run_command",
            target=command,
            parameters={"command": command},
            workspace=self.workspace_dir,
            context={"command": command},
            provenance={"platform": "cursor", "agent": "cursor"},
            agent="cursor",
            platform="cursor",
            tool="terminal",
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

    def on_file_operation(self, operation: str, file_path: str, contents: str = "", task_id: Optional[str] = None) -> AuthorizationDecision:
        """Evaluates file read, write, edit, or delete actions."""
        cap = CAP_FILESYSTEM_READ if operation in ("read", "file_read") else CAP_FILESYSTEM_WRITE
        req = ActionRequest(
            actor="cursor",
            session=task_id or "",
            capability=cap,
            action=operation,
            target=file_path,
            parameters={"contents": contents, "file_path": file_path},
            workspace=self.workspace_dir,
            context={"file_path": file_path, "operation": operation},
            provenance={"platform": "cursor", "agent": "cursor"},
            agent="cursor",
            platform="cursor",
            tool="composer",
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

    def on_agent_event(self, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Tracks Cursor composer events without polluting verified state."""
        return {
            "event": f"cursor.{event_name}",
            "payload": payload,
            "status": "observed",
        }

    def on_command_failure(self, command: str, exit_code: int, error_output: str) -> Dict[str, Any]:
        """Captures failure evidence directly from Cursor terminal."""
        return {
            "event": "cursor.command_failure",
            "command": command,
            "exit_code": exit_code,
            "error": error_output,
            "status": "failure_recorded",
        }

    def evaluate_completion_claim(self, claim: Claim, evidence: Any) -> VerificationResult:
        """Evaluates Cursor composer completion claim."""
        return verify_claim(claim, evidence, workspace_dir=self.workspace_dir)
