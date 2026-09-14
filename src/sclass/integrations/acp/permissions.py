"""
S-Class ACP Integration: Permissions Bridge.
Evaluates incoming ACP permission requests against S-Class authorization policies.
Translates permission grants into S-Class ActionRequests and returns canonical
decision responses: ALLOW, DENY, REQUIRE_APPROVAL.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.authorization import authorize
from sclass.integrations.acp.capability_map import ACPCapabilityMap
from sclass.platform.framework import PlatformProfilingFramework


@dataclass(frozen=True)
class ACPPermissionRequest:
    """Normalized internal ACP permission request."""
    request_id: str
    session_id: str
    agent_id: str
    tool: str
    target: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None


class ACPPermissionsBridge:
    """Evaluates ACP permission requests against S-Class policy engine."""

    def __init__(
        self,
        workspace_dir: str,
        mode: str = "enforce",
        platform_framework: Optional[PlatformProfilingFramework] = None,
    ):
        self.workspace_dir = workspace_dir
        self.mode = mode
        self.platform_framework = platform_framework or PlatformProfilingFramework(workspace_dir=self.workspace_dir)

    def evaluate_permission(
        self,
        perm_req: ACPPermissionRequest,
    ) -> AuthorizationDecision:
        """
        Converts ACP permission request into an ActionRequest and evaluates policy.
        """
        capability = ACPCapabilityMap.resolve_capability(perm_req.tool)

        # Normalize action request for S-Class policy
        action_type = perm_req.tool
        if perm_req.tool in ("run_command", "execute_command", "bash", "terminal/exec"):
            action_type = "run_command"
            cmd = perm_req.arguments.get("command") or perm_req.target
            target = cmd
        elif perm_req.tool in ("write_file", "write_to_file", "edit_file", "fs/write"):
            action_type = "file_edit"
            target = perm_req.target or perm_req.arguments.get("path", "")
        elif perm_req.tool in ("read_file", "view_file", "list_dir", "fs/read", "fs/list"):
            action_type = "file_read"
            target = perm_req.target or perm_req.arguments.get("path", "")
        else:
            target = perm_req.target

        ctrl_policy = self.platform_framework.synthesize_policy(actor_token=perm_req.agent_id)

        action_request = ActionRequest(
            agent=perm_req.agent_id,
            platform="acp",
            action=action_type,
            tool=perm_req.tool,
            target=target,
            parameters=perm_req.arguments,
            workspace=self.workspace_dir,
            task_id=perm_req.session_id,
            context={
                "session_id": perm_req.session_id,
                "capability": capability,
                "reason": perm_req.reason,
                "request_id": perm_req.request_id,
                "control_policy": ctrl_policy.to_dict(),
            },
        )

        decision = authorize(
            action_request,
            mode=self.mode,
            workspace_dir=self.workspace_dir,
        )
        return decision
