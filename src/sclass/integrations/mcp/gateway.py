"""
S-Class MCP Integration: Policy Gateway and Security Interceptor.
S-Class operates as a policy gateway/interceptor, not as an alternative MCP implementation.
Guarantees that every MCP invocation is authoritatively checked against S-Class
task and resource policy before forwarding to underlying tools or servers.
"""

from __future__ import annotations
import uuid
from typing import Dict, Any, Optional, Tuple, Callable

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize
from sclass.integrations.mcp.normalization import MCPToolCall, compute_hash
from sclass.integrations.mcp.auth import MCPAuthorizationContext, MCPAuthenticator
from sclass.integrations.mcp.tools import MCPToolRegistry, MCPToolDefinition
from sclass.integrations.mcp.resources import MCPResourceRegistry


class MCPGateway:
    """
    Authoritative policy gateway intercepting all MCP JSON-RPC protocol requests.
    Prevents unauthorized tool execution, secret exfiltration, and tampered tool calls.
    """

    def __init__(
        self,
        workspace_dir: str,
        server_id: str = "mcp_server",
        server_version: str = "1.0.0",
        mode: str = "enforce",
        tool_registry: Optional[MCPToolRegistry] = None,
        resource_registry: Optional[MCPResourceRegistry] = None,
        authenticator: Optional[MCPAuthenticator] = None,
    ):
        self.workspace_dir = workspace_dir
        self.server_id = server_id
        self.server_version = server_version
        self.mode = mode
        self.tool_registry = tool_registry or MCPToolRegistry()
        self.resource_registry = resource_registry or MCPResourceRegistry(workspace_dir)
        self.authenticator = authenticator or MCPAuthenticator()

    def handle_call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        agent_id: str = "mcp_agent",
        task_id: Optional[str] = None,
        auth_context: Optional[MCPAuthorizationContext] = None,
        call_id: Optional[str] = None,
        executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> Dict[str, Any]:
        """
        Intercepts and evaluates an MCP tools/call request.
        Returns conformant JSON-RPC result or error.
        """
        cid = call_id or str(uuid.uuid4())

        # 1. Check if tool is invalidated due to schema mutation
        if self.tool_registry.is_invalidated(self.server_id, tool_name):
            return {
                "jsonrpc": "2.0",
                "id": cid,
                "error": {
                    "code": -32005,
                    "message": f"MCP tool '{tool_name}' trust cache was invalidated due to schema change.",
                },
            }

        # 2. Validate MCP authorization if context provided
        if auth_context:
            is_valid_auth, auth_err = self.authenticator.validate(auth_context)
            if not is_valid_auth:
                return {
                    "jsonrpc": "2.0",
                    "id": cid,
                    "error": {
                        "code": -32002,
                        "message": f"MCP Authorization failure: {auth_err}",
                    },
                }

        # 3. Lookup tool schema and compute schema hash
        tool_def = self.tool_registry.get_tool(self.server_id, tool_name)
        schema_hash = tool_def.schema_hash if tool_def else "unknown_schema"
        args_hash = compute_hash(arguments)

        # 4. Construct authoritative MCPToolCall identity
        mcp_call = MCPToolCall(
            server_id=self.server_id,
            server_version=self.server_version,
            tool_name=tool_name,
            tool_schema_hash=schema_hash,
            arguments_hash=args_hash,
            authorization_context=auth_context.to_dict() if auth_context else {},
            task_id=task_id,
            agent_id=agent_id,
            parameters=arguments,
            call_id=cid,
        )

        # 5. Evaluate S-Class policy
        action_req = mcp_call.to_action_request(self.workspace_dir)
        decision = authorize(action_req, mode=self.mode, workspace_dir=self.workspace_dir)

        if decision.is_denied:
            return {
                "jsonrpc": "2.0",
                "id": cid,
                "error": {
                    "code": -32003,
                    "message": f"Authorization DENIED by S-Class policy [{decision.policy_id}]: {decision.reason}",
                    "data": {
                        "policy_id": decision.policy_id,
                        "reason": decision.reason,
                        "risk_level": decision.risk_level,
                        "mcp_identity": mcp_call.to_dict(),
                    },
                },
            }

        # 6. Execute through executor if provided
        exec_output = None
        if executor:
            try:
                exec_output = executor(tool_name, arguments)
            except Exception as ex:
                return {
                    "jsonrpc": "2.0",
                    "id": cid,
                    "error": {
                        "code": -32603,
                        "message": f"Tool execution failed: {ex}",
                    },
                }

        return {
            "jsonrpc": "2.0",
            "id": cid,
            "result": {
                "status": "success",
                "content": exec_output or [{"type": "text", "text": "Execution authorized by S-Class"}],
                "mcp_identity": mcp_call.to_dict(),
            },
        }

    def process_message(self, raw_rpc: Dict[str, Any], executor: Optional[Callable] = None) -> Dict[str, Any]:
        """Dispatches arbitrary incoming MCP JSON-RPC message."""
        method = raw_rpc.get("method", "")
        params = raw_rpc.get("params", {})
        rpc_id = raw_rpc.get("id")

        if method in ("tools/call", "tool_call"):
            t_name = params.get("name") or params.get("tool") or ""
            t_args = params.get("arguments") or params.get("parameters") or {}
            auth_data = params.get("authorization_context")
            auth_ctx = MCPAuthorizationContext.from_dict(auth_data) if auth_data else None
            return self.handle_call_tool(
                tool_name=t_name,
                arguments=t_args,
                task_id=params.get("task_id"),
                auth_context=auth_ctx,
                call_id=str(rpc_id),
                executor=executor,
            )

        elif method in ("tools/list", "tools_list"):
            tools = [t.to_dict() for t in self.tool_registry.list_tools(self.server_id)]
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"tools": tools},
            }

        elif method in ("resources/list", "resources_list"):
            resources = [r.to_dict() for r in self.resource_registry.list_resources()]
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"resources": resources},
            }

        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": -32601, "message": f"Method '{method}' not implemented in MCP Gateway."},
        }
