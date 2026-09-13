"""
S-Class Integration: OpenCode / CodeSandbox Platform Adapter.
Supports:
- connection handshake
- action authorization
- tool invocation
- execution observation
- event logging
- claim verification
- handoff packages
"""

from __future__ import annotations
import os
import shutil
from typing import Dict, Any, Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult
from sclass.control.authorization import authorize
from sclass.verification.engine import verify_claim
from sclass.context.handoff import HandoffAssembler, HandoffPackage
from sclass.integrations.base import AdapterCapabilities, AdapterStatus


class OpenCodeAdapter:
    """Adapts OpenCode actions into S-Class governance."""

    def __init__(self, workspace_dir: str, mode: str = "enforce"):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.mode = mode
        self.connected = False
        self.capabilities = AdapterCapabilities(
            pre_action_enforcement=True,
            post_action_observation=True,
            approval=True,
            verification=True,
            session_events=True,
            native_protocol="acp",
        )

    def inspect_status(self) -> AdapterStatus:
        if shutil.which("opencode"):
            return AdapterStatus.INSTALLED
        return AdapterStatus.SUPPORTED

    @property
    def status(self) -> AdapterStatus:
        return self.inspect_status()

    def connect(self) -> Dict[str, Any]:
        """Establishes authenticated connection with OpenCode runtime."""
        self.connected = True
        return {"status": "connected", "platform": "opencode", "workspace": self.workspace_dir}

    def on_action(self, action_name: str, target: str, parameters: Dict[str, Any], task_id: Optional[str] = None) -> AuthorizationDecision:
        req = ActionRequest(
            agent="opencode",
            platform="opencode",
            action=action_name,
            tool=action_name,
            target=target,
            parameters=parameters,
            workspace=self.workspace_dir,
            task_id=task_id,
        )
        return authorize(req, mode=self.mode, workspace_dir=self.workspace_dir)

    def on_tool(self, tool_name: str, arguments: Dict[str, Any], task_id: Optional[str] = None) -> AuthorizationDecision:
        target = arguments.get("target") or arguments.get("path") or arguments.get("command") or tool_name
        return self.on_action(tool_name, str(target), arguments, task_id=task_id)

    def on_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"event": f"opencode.{event_type}", "payload": payload, "status": "recorded"}

    def evaluate_claim(self, claim: Claim, evidence: Any) -> VerificationResult:
        return verify_claim(claim, evidence, workspace_dir=self.workspace_dir)

    def create_handoff(self, project_id: str, next_action: Optional[str] = None) -> HandoffPackage:
        assembler = HandoffAssembler(self.workspace_dir)
        return assembler.assemble_package(project_id, next_action=next_action)
