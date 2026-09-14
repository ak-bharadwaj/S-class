"""
S-Class Integration: Authoritative ACP (Agent Client Protocol) Transport & Adapter.
Normalizes external ACP protocol messages into S-Class models:
- AgentSession
- AgentEvent
- ActionRequest
- PermissionRequest
- AgentResult
- AgentError

Implements complete ACP session lifecycle:
initialize, session/new, prompt, session/update, permission, tool/action,
cancellation, session/resume, session/fork, shutdown.

Enforces Invariant 5: Adapters never directly produce ObservedReceipt or VerificationEvent objects.
"""

from __future__ import annotations
import os
import uuid
import json
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.authorization import authorize
from sclass.integrations.acp.protocol import (
    ACPProtocolTransport,
    ACPInitializeResult,
    ACPSessionNewResult,
    ACPPermissionResult,
    ACPToolCallResult,
    ACPSessionForkResult,
    ACPShutdownResult,
    DEFAULT_PROTOCOL_VERSION,
)
from sclass.integrations.acp.fs_gateway import ACPFsGateway
from sclass.integrations.acp.terminal_gateway import ACPTerminalGateway
from sclass.integrations.acp.schema import (
    ACPFsReadParams,
    ACPFsWriteParams,
    ACPTerminalExecParams,
)
from sclass.integrations.protocol_gateway import ProtocolEventGateway, get_protocol_gateway
from sclass.platform.framework import PlatformProfilingFramework
from sclass.platform.engine import ControlPolicy


@dataclass(frozen=True)
class AgentCapability:
    """Declared capabilities of an agent or client under ACP."""
    tools: tuple[str, ...] = field(default_factory=tuple)
    prompts: tuple[str, ...] = field(default_factory=tuple)
    streaming: bool = True
    cancellation: bool = True
    authorization: bool = True


@dataclass
class AgentSession:
    """Lifecycle tracking for an active ACP agent session."""
    session_id: str
    agent_id: str
    workspace_dir: str
    capabilities: AgentCapability
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = True
    forked_from: Optional[str] = None
    state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "workspace_dir": self.workspace_dir,
            "started_at": self.started_at,
            "active": self.active,
            "forked_from": self.forked_from,
            "state": dict(self.state),
        }


@dataclass(frozen=True)
class AgentEvent:
    """Normalized internal event model for ACP lifecycle and message events."""
    event_type: str
    session_id: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "session_id": self.session_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class PermissionRequest:
    """Explicit ACP permission grant request from client/agent."""
    request_id: str
    session_id: str
    agent_id: str
    tool: str
    target: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None

    def to_action_request(self, workspace_dir: str, task_id: Optional[str] = None) -> ActionRequest:
        return ActionRequest(
            agent=self.agent_id,
            platform="acp",
            action=self.tool,
            tool=self.tool,
            target=self.target,
            parameters=self.parameters,
            workspace=workspace_dir,
            task_id=task_id,
            context={"acp_permission_request_id": self.request_id, "session_id": self.session_id},
        )


@dataclass(frozen=True)
class AgentResult:
    """Normalized response from ACP session or tool invocation."""
    session_id: str
    result_id: str
    status: str
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "result_id": self.result_id,
            "status": self.status,
            "data": self.data,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class AgentError:
    """Standardized ACP protocol error."""
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            res["data"] = self.data
        return res


class ACPAdapter:
    """
    Production ACP transport adapter normalizing agent interactions into S-Class
    ActionRequests, PermissionRequests, and session lifecycle state machines.
    """

    def __init__(
        self,
        workspace_dir: str,
        agent_id: str = "acp_agent",
        mode: str = "enforce",
        platform_framework: Optional[PlatformProfilingFramework] = None,
        gateway: Optional[ProtocolEventGateway] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.agent_id = agent_id
        self.mode = mode
        self.sessions: Dict[str, AgentSession] = {}
        self.fs_gateway = ACPFsGateway(self.workspace_dir)
        self.terminal_gateway = ACPTerminalGateway(self.workspace_dir, mode=self.mode)
        self.platform_framework = platform_framework or PlatformProfilingFramework(workspace_dir=self.workspace_dir)
        self.gateway = gateway or get_protocol_gateway()

    def get_control_policy(self, task: Optional[Any] = None) -> ControlPolicy:
        """Synthesizes active control policy for this ACP session."""
        return self.platform_framework.synthesize_policy(actor_token=self.agent_id, task=task)

    def normalize_message(self, raw_message: Dict[str, Any]) -> Tuple[Optional[AgentEvent], Optional[ActionRequest]]:
        """Backwards-compatible helper extracting event and action request."""
        method = raw_message.get("method", "")
        raw_params = raw_message.get("params")
        params: Dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
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

        elif method in ("session/close", "session.close", "shutdown"):
            sid = params.get("session_id", "default")
            if sid in self.sessions:
                self.sessions[sid].active = False
            return AgentEvent("shutdown", sid, params), None

        elif method in ("prompt", "message"):
            sid = params.get("session_id", "default")
            return AgentEvent("prompt", sid, params), None

        elif method in ("cancel", "cancellation"):
            sid = params.get("session_id", "default")
            return AgentEvent("cancellation", sid, params), None

        elif method in ("tool/call", "tool_call", "action/execute", "tool/action"):
            sid = params.get("session_id", "default")
            tool_name = params.get("tool") or params.get("name") or "unknown_tool"
            args = params.get("arguments") or params.get("parameters") or {}
            target = args.get("target") or args.get("path") or args.get("command") or ""

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

    def handle_message(self, message: Union[str, Dict[str, Any]]) -> str:
        """
        Convenience method accepting JSON string or dictionary and returning serialized JSON response.
        """
        if isinstance(message, str):
            raw_msg = json.loads(message)
        else:
            raw_msg = message
        resp = self.process_acp_message(raw_msg)
        return json.dumps(resp)

    def process_acp_message(self, raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authoritatively handles incoming ACP requests according to specification lifecycle:
        initialize, session/new, prompt, session/update, permission, tool/action,
        cancellation, session/resume, session/fork, shutdown.
        """
        msg_id = raw_message.get("id")
        method = raw_message.get("method", "")
        params = raw_message.get("params", {})

        session_id_hint = str(params.get("session_id") or msg_id or "default")
        norm_method = method.replace("/", "_").replace(".", "_")
        self.gateway.emit_acp(
            event_type=f"acp.{norm_method}",
            session_id=session_id_hint,
            agent_id=self.agent_id,
            payload=params,
        )

        # 1. initialize
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
            return ACPProtocolTransport.create_response(
                msg_id,
                ACPInitializeResult(
                    protocolVersion=DEFAULT_PROTOCOL_VERSION,
                    sessionId=session_id,
                    capabilities={
                        "tools": True,
                        "prompts": True,
                        "authorization": True,
                        "cancellation": True,
                        "fork": True,
                    },
                ),
            )

        # 2. session/new
        elif method in ("session/new", "session.new"):
            sid = str(uuid.uuid4())
            session = AgentSession(
                session_id=sid,
                agent_id=params.get("agent_id", self.agent_id),
                workspace_dir=self.workspace_dir,
                capabilities=AgentCapability(),
            )
            self.sessions[sid] = session
            return ACPProtocolTransport.create_response(
                msg_id,
                ACPSessionNewResult(sessionId=sid, status="active"),
            )

        # 3. prompt
        elif method in ("prompt", "message"):
            sid = params.get("session_id", "default")
            return ACPProtocolTransport.create_response(
                msg_id,
                {"status": "prompt_received", "session_id": sid},
            )

        # 4. session/update
        elif method in ("session/update", "session.update"):
            sid = params.get("session_id", "default")
            if sid in self.sessions:
                self.sessions[sid].state.update(params.get("state", {}))
            return ACPProtocolTransport.create_response(
                msg_id,
                {"status": "updated", "session_id": sid},
            )

        # 5. permission (The Permission Bridge)
        elif method in ("permission", "permission/request"):
            sid = params.get("session_id", "default")
            tool_name = params.get("tool") or params.get("name") or "unknown_tool"
            args = params.get("arguments") or params.get("parameters") or {}
            target = args.get("target") or args.get("path") or args.get("command") or ""

            perm_req = PermissionRequest(
                request_id=str(msg_id or uuid.uuid4()),
                session_id=sid,
                agent_id=self.agent_id,
                tool=tool_name,
                target=target,
                parameters=args,
                reason=params.get("reason"),
            )
            act_req = perm_req.to_action_request(self.workspace_dir, task_id=params.get("task_id"))
            decision = authorize(act_req, mode=self.mode, workspace_dir=self.workspace_dir)

            if decision.is_denied:
                self.gateway.emit_acp(
                    event_type="acp.action_denied",
                    session_id=sid,
                    agent_id=self.agent_id,
                    payload={"decision": decision.to_dict(), "tool": tool_name},
                )
                return ACPProtocolTransport.create_response(
                    msg_id,
                    {
                        "outcome": "DENY",
                        "policy_id": decision.policy_id,
                        "reason": decision.reason,
                        "risk_level": decision.risk_level,
                    },
                )
            elif decision.requires_approval or decision.outcome == DecisionOutcome.REQUIRE_APPROVAL:
                self.gateway.emit_acp(
                    event_type="acp.action_require_approval",
                    session_id=sid,
                    agent_id=self.agent_id,
                    payload={"decision": decision.to_dict(), "tool": tool_name},
                )
                return ACPProtocolTransport.create_response(
                    msg_id,
                    {
                        "outcome": "APPROVAL",
                        "policy_id": decision.policy_id,
                        "reason": decision.reason,
                    },
                )
            self.gateway.emit_acp(
                event_type="acp.action_authorized",
                session_id=sid,
                agent_id=self.agent_id,
                payload={"decision": decision.to_dict(), "tool": tool_name},
            )
            return ACPProtocolTransport.create_response(
                msg_id,
                {"outcome": "ALLOW", "policy_id": decision.policy_id},
            )

        # 6. tool/action
        elif method in ("tool/action", "tool/call", "tool_call", "action/execute"):
            sid = params.get("session_id", "default")
            tool_name = params.get("tool") or params.get("name") or "unknown_tool"
            args = params.get("arguments") or params.get("parameters") or {}
            target = args.get("target") or args.get("path") or args.get("command") or ""

            act_req = ActionRequest(
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
            decision = authorize(act_req, mode=self.mode, workspace_dir=self.workspace_dir)
            if decision.is_denied:
                self.gateway.emit_acp(
                    event_type="acp.action_denied",
                    session_id=sid,
                    agent_id=self.agent_id,
                    payload={"decision": decision.to_dict(), "tool": tool_name},
                )
                return ACPProtocolTransport.create_error(
                    msg_id,
                    code=-32003,
                    message=f"Authorization DENIED by S-Class policy [{decision.policy_id}]: {decision.reason}",
                    data=decision.to_dict(),
                )

            self.gateway.emit_acp(
                event_type="acp.action_authorized",
                session_id=sid,
                agent_id=self.agent_id,
                payload={"decision": decision.to_dict(), "tool": tool_name},
            )
            return ACPProtocolTransport.create_response(
                msg_id,
                {"status": "authorized_passthrough", "policy_id": decision.policy_id},
            )

        # 7. cancellation
        elif method in ("cancel", "cancellation"):
            sid = params.get("session_id", "default")
            return ACPProtocolTransport.create_response(
                msg_id,
                {"status": "cancelled", "session_id": sid},
            )

        # 8. session/resume
        elif method in ("session/resume", "session.resume"):
            sid = params.get("session_id")
            if sid and sid in self.sessions:
                self.sessions[sid].active = True
                return ACPProtocolTransport.create_response(
                    msg_id,
                    {"sessionId": sid, "status": "resumed"},
                )
            return ACPProtocolTransport.create_error(
                msg_id,
                code=-32004,
                message=f"Session '{sid}' not found for resume.",
            )

        # 9. session/fork
        elif method in ("session/fork", "session.fork"):
            parent_sid = params.get("parent_session_id") or params.get("session_id")
            new_sid = str(uuid.uuid4())
            parent_sess = self.sessions.get(parent_sid) if parent_sid else None
            new_sess = AgentSession(
                session_id=new_sid,
                agent_id=self.agent_id,
                workspace_dir=self.workspace_dir,
                capabilities=parent_sess.capabilities if parent_sess else AgentCapability(),
                forked_from=parent_sid,
                state=dict(parent_sess.state) if parent_sess else {},
            )
            self.sessions[new_sid] = new_sess
            return ACPProtocolTransport.create_response(
                msg_id,
                ACPSessionForkResult(sessionId=new_sid, forkedFrom=str(parent_sid)),
            )

        # 10. shutdown
        elif method in ("shutdown", "session/close", "session.close"):
            sid = params.get("session_id", "default")
            if sid in self.sessions:
                self.sessions[sid].active = False
            return ACPProtocolTransport.create_response(
                msg_id,
                {"status": "shutdown_complete", "session_id": sid},
            )

        # 11. fs/read
        elif method in ("fs/read", "fs.read"):
            path = params.get("path", "")
            offset = params.get("offset", 0)
            limit = params.get("limit")
            read_params = ACPFsReadParams(
                session_id=params.get("session_id", "default"),
                path=path,
                offset=offset,
                limit=limit,
            )
            try:
                result = self.fs_gateway.read_file(read_params)
                return ACPProtocolTransport.create_response(msg_id, result.model_dump())
            except PermissionError as pe:
                return ACPProtocolTransport.create_error(msg_id, code=-32003, message=f"Permission denied: {pe}")
            except FileNotFoundError as fe:
                return ACPProtocolTransport.create_error(msg_id, code=-32004, message=f"File not found: {fe}")
            except Exception as e:
                return ACPProtocolTransport.create_error(msg_id, code=-32603, message=f"Filesystem read error: {e}")

        # 12. fs/write
        elif method in ("fs/write", "fs.write"):
            path = params.get("path", "")
            content = params.get("content", "")
            overwrite = params.get("overwrite", True)
            write_params = ACPFsWriteParams(
                session_id=params.get("session_id", "default"),
                path=path,
                content=content,
                overwrite=overwrite,
            )
            try:
                result = self.fs_gateway.write_file(write_params)
                return ACPProtocolTransport.create_response(msg_id, result.model_dump())
            except PermissionError as pe:
                return ACPProtocolTransport.create_error(msg_id, code=-32003, message=f"Permission denied: {pe}")
            except FileExistsError as fe:
                return ACPProtocolTransport.create_error(msg_id, code=-32005, message=f"File already exists: {fe}")
            except Exception as e:
                return ACPProtocolTransport.create_error(msg_id, code=-32603, message=f"Filesystem write error: {e}")

        # 13. fs/list
        elif method in ("fs/list", "fs.list"):
            path = params.get("path", "")
            try:
                entries = self.fs_gateway.list_dir(path)
                return ACPProtocolTransport.create_response(msg_id, {"path": path, "entries": entries})
            except PermissionError as pe:
                return ACPProtocolTransport.create_error(msg_id, code=-32003, message=f"Permission denied: {pe}")
            except (FileNotFoundError, NotADirectoryError) as fe:
                return ACPProtocolTransport.create_error(msg_id, code=-32004, message=str(fe))
            except Exception as e:
                return ACPProtocolTransport.create_error(msg_id, code=-32603, message=f"Filesystem list error: {e}")

        # 14. terminal/exec
        elif method in ("terminal/exec", "terminal.exec"):
            cmd = params.get("command", "")
            cwd = params.get("cwd")
            sid = params.get("session_id", "default")
            exec_params = ACPTerminalExecParams(session_id=sid, command=cmd, cwd=cwd)
            try:
                result = self.terminal_gateway.execute_terminal_command(exec_params, agent_id=self.agent_id)
                return ACPProtocolTransport.create_response(msg_id, result.model_dump())
            except PermissionError as pe:
                return ACPProtocolTransport.create_error(msg_id, code=-32003, message=f"Permission denied: {pe}")
            except Exception as e:
                return ACPProtocolTransport.create_error(msg_id, code=-32603, message=f"Terminal execution error: {e}")

        # 15. sclass/profile & sclass/control_policy (B.6 Platform Optimization)
        elif method in ("sclass/profile", "sclass.profile", "sclass/control_policy"):
            det = self.platform_framework.detect(actor_token=self.agent_id)
            prof = self.platform_framework.get_profile(det.platform_id)
            ctrl = self.platform_framework.synthesize_policy(actor_token=self.agent_id)
            return ACPProtocolTransport.create_response(
                msg_id,
                {
                    "platform_id": prof.platform_id,
                    "confidence": det.confidence,
                    "execution_style": prof.execution_style,
                    "native_strengths": prof.native_strengths,
                    "preserved_capabilities": list(ctrl.preserved_capabilities),
                    "active_compensations": list(ctrl.active_compensations),
                    "observation_mode": ctrl.observation_mode,
                    "verification_gate": ctrl.verification_gate,
                    "interruption_policy": ctrl.interruption_policy,
                },
            )

        # Fallback for unknown methods
        return ACPProtocolTransport.create_error(
            msg_id,
            code=-32601,
            message=f"Method '{method}' not found",
        )
