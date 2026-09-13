"""
S-Class Integration: Authoritative ACP (Agent Client Protocol) Adapter.
Normalizes external ACP protocol messages into S-Class AgentEvent, ActionRequest,
AgentSession, and AgentCapability models without becoming a trust authority (Invariant 5).
"""

from __future__ import annotations
import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.authorization import authorize


@dataclass(frozen=True)
class AgentCapability:
    """Declared capabilities of an agent or client under ACP."""
    tools: tuple[str, ...] = field(default_factory=tuple)
    prompts: tuple[str, ...] = field(default_factory=tuple)
    streaming: bool = True
    cancellation: bool = True


@dataclass
class AgentSession:
    """Lifecycle tracking for an active ACP agent session."""
    session_id: str
    agent_id: str
    workspace_dir: str
    capabilities: AgentCapability
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = True


@dataclass(frozen=True)
class AgentEvent:
    """Normalized internal event model for ACP lifecycle and message events."""
    event_type: str  # "initialize", "session.create", "session.close", "prompt", "tool.request", "cancel"
    session_id: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ACPAdapter:
    """
    Standard ACP adapter translating external ACP protocol events into S-Class
    ActionRequests and AgentEvents. Invariant 5: This adapter NEVER directly produces
    ObservedReceipt or VerificationEvent objects.
    """

    def __init__(self, workspace_dir: str, agent_id: str = "acp_agent", mode: str = "enforce"):
        self.workspace_dir = workspace_dir
        self.agent_id = agent_id
        self.mode = mode
        self.sessions: Dict[str, AgentSession] = {}

    def normalize_message(self, raw_message: Dict[str, Any]) -> Tuple[Optional[AgentEvent], Optional[ActionRequest]]:
        """Normalizes an incoming ACP JSON-RPC message into AgentEvent and optional ActionRequest."""
        method = raw_message.get("method", "")
        params = raw_message.get("params", {})
        msg_id = raw_message.get("id")

        if method in ("initialize", "init"):
            session_id = str(uuid.uuid4())
            caps = AgentCapability(
                tools=tuple(params.get("capabilities", {}).get("tools", [])),
                prompts=tuple(params.get("capabilities", {}).get("prompts", [])),
            )
            session = AgentSession(
                session_id=session_id,
                agent_id=self.agent_id,
                workspace_dir=self.workspace_dir,
                capabilities=caps,
            )
            self.sessions[session_id] = session
            return AgentEvent("initialize", session_id, params), None

        elif method in ("session/close", "session.close"):
            sid = params.get("session_id", "default")
            if sid in self.sessions:
                self.sessions[sid].active = False
            return AgentEvent("session.close", sid, params), None

        elif method in ("prompt", "message"):
            sid = params.get("session_id", "default")
            return AgentEvent("prompt", sid, params), None

        elif method in ("cancel", "cancellation"):
            sid = params.get("session_id", "default")
            return AgentEvent("cancel", sid, params), None

        elif method in ("tool/call", "tool_call", "action/execute"):
            sid = params.get("session_id", "default")
            tool_name = params.get("tool") or params.get("name") or "unknown_tool"
            args = params.get("arguments") or params.get("parameters") or {}
            target = args.get("target") or args.get("path") or args.get("command") or ""

            # Normalize to ActionRequest
            req = ActionRequest(
                agent=self.agent_id,
                platform="acp",
                action=tool_name,
                tool=tool_name,
                target=target,
                parameters=args,
                workspace=self.workspace_dir,
                task_id=params.get("task_id"),
                context={"acp_message_id": msg_id, "session_id": sid},
            )
            return AgentEvent("tool.request", sid, params), req

        return None, None

    def process_acp_message(self, raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an ACP request, performing authorization if an ActionRequest is produced.
        Returns a conformant ACP JSON-RPC response.
        """
        msg_id = raw_message.get("id")
        method = raw_message.get("method")
        event, action_req = self.normalize_message(raw_message)

        if method in ("initialize", "init"):
            session_id = event.session_id if event else str(uuid.uuid4())
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2026-07-28",
                    "sessionId": session_id,
                    "capabilities": {
                        "tools": True,
                        "prompts": True,
                        "authorization": True,
                    },
                },
            }

        if action_req:
            decision = authorize(action_req, mode=self.mode, workspace_dir=self.workspace_dir)
            if decision.is_denied:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32003,
                        "message": f"Authorization DENIED by S-Class policy [{decision.policy_id}]: {decision.reason}",
                        "data": decision.to_dict(),
                    },
                }

        # Successful passthrough acknowledgement
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"status": "authorized_passthrough"},
        }
