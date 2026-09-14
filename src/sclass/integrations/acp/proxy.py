"""
S-Class ACP Integration: JSON-RPC Proxy & Protocol Interceptor (RC.7).
Monitors, intercepts, and gates Agent Client Protocol traffic between client IDE and agent backend.
Evaluates authorization policies before forwarding tool actions and emits canonical ProtocolEvents.
"""

from __future__ import annotations
import json
import logging
from typing import Dict, Any, Optional, Tuple, Union

from sclass.integrations.acp.decision_bridge import ACPDecisionBridge
from sclass.integrations.protocol_gateway import ProtocolEventGateway, get_protocol_gateway

logger = logging.getLogger("sclass.integrations.acp.proxy")


class ACPProxy:
    """
    Authoritative ACP protocol interceptor and conductor.
    Filters JSON-RPC messages, enforces S-Class authorization, and streams canonical events.
    """

    def __init__(
        self,
        workspace_dir: str,
        mode: str = "enforce",
        agent_name: str = "acp_agent",
        gateway: Optional[ProtocolEventGateway] = None,
    ):
        self.workspace_dir = workspace_dir
        self.mode = mode
        self.agent_name = agent_name
        self.bridge = ACPDecisionBridge(workspace_dir=workspace_dir, mode=mode, agent_name=agent_name)
        self.gateway = gateway or get_protocol_gateway()

    def intercept_message(self, msg: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Processes a structured ACP JSON-RPC message dictionary.
        Returns (is_intercepted, response_dict).
        If is_intercepted is True, caller MUST return response_dict to sender and abort forwarding.
        If is_intercepted is False, caller forwards the message.
        """
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})
        session_id = params.get("session_id", "default_session")

        # 1. Emit lifecycle / prompt / cancel events
        if method in ("initialize", "init"):
            self.gateway.emit_acp(
                event_type="acp.initialize",
                session_id=session_id,
                agent_id=self.agent_name,
                payload=params,
            )
            return False, None

        elif method in ("session/new", "session.new"):
            self.gateway.emit_acp(
                event_type="acp.session_new",
                session_id=session_id,
                agent_id=self.agent_name,
                payload=params,
            )
            return False, None

        elif method in ("cancel", "cancellation"):
            self.gateway.emit_acp(
                event_type="acp.cancellation",
                session_id=session_id,
                agent_id=self.agent_name,
                payload=params,
            )
            return False, None

        elif method in ("shutdown", "session/close"):
            self.gateway.emit_acp(
                event_type="acp.shutdown",
                session_id=session_id,
                agent_id=self.agent_name,
                payload=params,
            )
            return False, None

        # 2. Intercept and gate tool execution requests
        elif method in ("tool/call", "tool_call", "action/execute", "tool/action"):
            tool_name = params.get("tool") or params.get("name") or "unknown_tool"
            arguments = params.get("arguments") or params.get("parameters") or {}
            task_id = params.get("task_id")

            # Emit tool call request event
            self.gateway.emit_acp(
                event_type="acp.tool_call",
                session_id=session_id,
                agent_id=self.agent_name,
                payload={"tool": tool_name, "arguments": arguments, "task_id": task_id, "id": msg_id},
            )

            decision, error_resp = self.bridge.handle_tool_call(
                tool_call_id=str(msg_id) if msg_id is not None else "",
                tool_name=tool_name,
                arguments=arguments,
                task_id=task_id,
            )

            if decision.is_denied:
                self.gateway.emit_acp(
                    event_type="acp.action_denied",
                    session_id=session_id,
                    agent_id=self.agent_name,
                    payload={"decision": decision.to_dict(), "tool": tool_name, "arguments": arguments},
                )
                return True, error_resp

            # Authorized passthrough
            self.gateway.emit_acp(
                event_type="acp.action_authorized",
                session_id=session_id,
                agent_id=self.agent_name,
                payload={"decision": decision.to_dict(), "tool": tool_name},
            )
            return False, None

        # 3. Handle explicit permission requests
        elif method in ("permission", "permission/request"):
            self.gateway.emit_acp(
                event_type="acp.permission_request",
                session_id=session_id,
                agent_id=self.agent_name,
                payload=params,
            )
            return False, None

        return False, None

    def process_incoming_message(self, raw_message: str) -> Tuple[bool, Optional[str]]:
        """
        Processes a single raw JSON-RPC string line.
        Returns (is_intercepted, response_string).
        """
        raw_clean = raw_message.strip()
        if not raw_clean:
            return False, None

        try:
            msg = json.loads(raw_clean)
        except Exception:
            return False, None

        intercepted, resp_dict = self.intercept_message(msg)
        if intercepted and resp_dict:
            return True, json.dumps(resp_dict)
        return False, None
