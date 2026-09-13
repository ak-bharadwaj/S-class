"""
S-Class Integration: Authoritative MCP (Model Context Protocol) Adapter.
Captures cryptographic tool identity, schema digests, and normalizes MCP methods
(tools/call, tools/list, resources/*, prompts/*) into S-Class authorization requests.
Enforces Invariant 5 (adapters cannot create authoritative receipts or events directly).
"""

from __future__ import annotations
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize
from sclass.control.resources import classify_resource, AuthorityBoundary


@dataclass(frozen=True)
class MCPToolIdentity:
    """Authoritative provenance and schema binding of an MCP tool invocation."""
    server_identity: str
    tool_identity: str
    tool_version: str
    request_id: str
    arguments_hash: str
    authorization_decision: str
    execution_result_hash: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def compute_identity_hash(self) -> str:
        payload = (
            f"{self.server_identity}|{self.tool_identity}|{self.tool_version}|"
            f"{self.request_id}|{self.arguments_hash}|{self.authorization_decision}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "server_identity": self.server_identity,
            "tool_identity": self.tool_identity,
            "tool_version": self.tool_version,
            "request_id": self.request_id,
            "arguments_hash": self.arguments_hash,
            "authorization_decision": self.authorization_decision,
            "execution_result_hash": self.execution_result_hash,
            "timestamp": self.timestamp,
            "identity_hash": self.compute_identity_hash(),
        }


class MCPAdapter:
    """
    Standard MCP adapter validating tool identities, normalizing requests,
    and enforcing security boundaries against protected resources.
    """

    def __init__(
        self,
        workspace_dir: str,
        server_id: str = "mcp_server",
        agent_id: str = "mcp_agent",
        mode: str = "enforce",
    ):
        self.workspace_dir = workspace_dir
        self.server_id = server_id
        self.agent_id = agent_id
        self.mode = mode

    def compute_arguments_hash(self, arguments: Dict[str, Any]) -> str:
        canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def normalize_request(
        self,
        method: str,
        params: Dict[str, Any],
        request_id: str = "",
    ) -> Tuple[ActionRequest, Optional[MCPToolIdentity]]:
        """Translates MCP method call into typed ActionRequest and MCPToolIdentity."""
        args = params.get("arguments") or params.get("parameters") or {}
        tool_name = params.get("name") or params.get("tool") or method
        target = args.get("path") or args.get("target") or args.get("file_path") or args.get("command") or ""

        action_req = ActionRequest(
            agent=self.agent_id,
            platform="mcp",
            action=tool_name,
            tool=f"{self.server_id}/{tool_name}",
            target=target,
            parameters=args,
            workspace=self.workspace_dir,
            task_id=params.get("task_id"),
            context={"mcp_method": method, "request_id": request_id},
        )

        tool_id = MCPToolIdentity(
            server_identity=self.server_id,
            tool_identity=tool_name,
            tool_version=params.get("version", "1.0"),
            request_id=request_id or "req_default",
            arguments_hash=self.compute_arguments_hash(args),
            authorization_decision="PENDING",
        )

        return action_req, tool_id

    def handle_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        request_id: str = "",
    ) -> Tuple[AuthorizationDecision, Optional[MCPToolIdentity], Optional[Dict[str, Any]]]:
        """
        Intercepts and evaluates an MCP tools/call request.
        Blocks write attempts to protected resources even if tool name is deceptively safe.
        """
        action_req, tool_identity = self.normalize_request(
            method="tools/call",
            params={"name": tool_name, "arguments": arguments},
            request_id=request_id,
        )

        # Check target against protected resources
        if action_req.target:
            r_kind, boundary = classify_resource(action_req.target, self.workspace_dir)
            if boundary in (AuthorityBoundary.SCLASS_TRUST_ROOT, AuthorityBoundary.SCLASS_VERIFICATION_ONLY):
                decision = AuthorizationDecision(
                    outcome="deny",
                    policy_id="SCLASS-MCP-PROT",
                    risk_level="CRITICAL",
                    reason=f"MCP tool '{tool_name}' attempted to access protected resource: {action_req.target}",
                    remediation="Protected S-Class state and evidence cannot be accessed via MCP tools.",
                )
                error_response = {
                    "isError": True,
                    "content": [{"type": "text", "text": f"[S-Class Security Block] {decision.reason}"}],
                }
                return decision, tool_identity, error_response

        decision = authorize(action_req, mode=self.mode, workspace_dir=self.workspace_dir)

        # Update identity with final authorization verdict
        resolved_identity = MCPToolIdentity(
            server_identity=tool_identity.server_identity,
            tool_identity=tool_identity.tool_identity,
            tool_version=tool_identity.tool_version,
            request_id=tool_identity.request_id,
            arguments_hash=tool_identity.arguments_hash,
            authorization_decision=decision.outcome.value if hasattr(decision.outcome, "value") else str(decision.outcome),
        )

        if decision.is_denied:
            error_response = {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": f"[S-Class Policy Block] {decision.policy_id}: {decision.reason}",
                    }
                ],
                "_sclass_decision": decision.to_dict(),
            }
            return decision, resolved_identity, error_response

        return decision, resolved_identity, None
