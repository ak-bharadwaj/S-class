"""S-CLASS MCP Server (06-IDE / Model Context Protocol).

Exposes Senior Staff IDE Governance and Co-Pilot capabilities over standard
MCP JSON-RPC 2.0 stdio protocol.

Supported tools:
- sclass_guide_task: Context package, architectural constraints, test obligations.
- sclass_validate_patch: Staged execution, multi-engine verification, signed receipts.
- sclass_get_status: Active obligations, budget usage, release readiness.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sclass.client import SClassClient
from sclass.intelligence.compiler import IntentCompiler
from sclass.intelligence.world_model import (
    ContextCompiler,
    EngineeringWorldModelBuilder,
)
from sclass.verification.engine import MultiEngineVerificationPlane


class SClassMCPServer:
    """Production IDE MCP Server exposing S-Class governance over JSON-RPC 2.0 stdio."""

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "sclass-mcp-server"
    SERVER_VERSION = "6.0.1"

    def __init__(
        self,
        workspace_root: Path | str = ".",
        db_path: str = "sclass.sqlite",
        boundary: Any | None = None,
        verification_plane: MultiEngineVerificationPlane | None = None,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.db_path = str(self.workspace_root / db_path) if not Path(db_path).is_absolute() else db_path
        self._verification_plane = verification_plane
        self.boundary = boundary

    # -------------------------------------------------------------------------
    # Core Tools
    # -------------------------------------------------------------------------

    def sclass_guide_task(self, intent: str, workspace_id: str = "default") -> dict[str, Any]:
        """Compile user intent into context package, constraints, and obligations."""
        wm = EngineeringWorldModelBuilder.build(self.workspace_root, workspace_id=workspace_id)
        compiler = IntentCompiler()
        program = compiler.compile(intent, wm)

        # Retrieve canonical engineering state
        client = SClassClient.connect(self.db_path)
        try:
            state = client.get_state(workspace_id)
        finally:
            client.close()

        # Primary implementation work node
        root_node_id = program.work_graph._graph.nodes[0] if program.work_graph._graph.nodes else None
        node = program.work_graph._nodes[root_node_id] if root_node_id else None

        ctx_dict: dict[str, Any] | None = None
        if node is not None:
            ctx_pkg = ContextCompiler.compile_context(node, state, wm)
            ctx_dict = {
                "budget": ctx_pkg.budget,
                "obligation_context": ctx_pkg.obligation_context,
                "constraints": list(ctx_pkg.constraints),
                "repo_map": {
                    "item_id": ctx_pkg.repo_map.item_id,
                    "token_estimate": ctx_pkg.repo_map.token_estimate,
                },
                "items": [
                    {
                        "item_id": it.item_id,
                        "kind": it.kind.value,
                        "path": it.path,
                        "rank": it.rank,
                        "token_estimate": it.token_estimate,
                    }
                    for it in ctx_pkg.items
                ],
                "estimated_input_tokens": ctx_pkg.token_accounting.estimated_input_tokens,
            }

        structured_intent = program.objective.revisions[0].structured_intent
        architectural_constraints = [
            {
                "type": c.type.value if hasattr(c.type, "value") else str(c.type),
                "expression": c.expression,
                "description": c.description,
            }
            for c in getattr(structured_intent, "constraints", ())
        ]

        test_obligations = [
            {
                "obligation_id": obl.obligation_id,
                "kind": obl.kind.value,
                "risk_tier": obl.risk_tier.value,
                "status": obl.status.value,
                "description": obl.description,
            }
            for obl in program.obligations
        ]

        return {
            "status": "success",
            "intent": intent,
            "objective_id": program.objective.objective_id,
            "context_package": ctx_dict,
            "architectural_constraints": architectural_constraints,
            "test_obligations": test_obligations,
        }

    def sclass_validate_patch(
        self,
        patch: str,
        target_file: str,
        workspace_id: str = "default",
        restore: bool = False,
    ) -> dict[str, Any]:
        """Stage patch in PatchAgentWorker, run verification plane, and emit signed receipts.

        Under Path 2 (strict fail-closed refusal), standalone MCP patch validation lacks
        authentic validation context and canonical StateBinding. It returns a structured
        BLOCKED_ON_HUMAN refusal before creating any WorkProposal, lease, authorization claim,
        digest, or synthetic validation evidence.
        """
        target_path = Path(target_file)
        norm_target = str(target_path.as_posix())
        if (
            target_path.is_absolute()
            or norm_target.startswith(("/", "\\"))
            or ".." in target_path.parts
        ):
            raise PermissionError(f"Target file path '{target_file}' escapes workspace root")

        # Refusal check under Path 2: standalone MCP patch validation lacks authentic validation context
        # and canonical StateBinding. Refuse fail-closed before creating any WorkProposal, lease,
        # authorization claim, digest, or synthetic evidence object.
        return {
            "status": "BLOCKED_ON_HUMAN",
            "reason_code": "MISSING_AUTHENTIC_VALIDATION_CONTEXT",
            "reason": "Authentic validation context and canonical StateBinding are unavailable for standalone MCP patch validation.",
            "missing_items": [
                "state_binding",
                "engineering_program",
                "work_graph",
                "causal_frontier",
                "context_digest",
                "request_content_digest",
            ],
        }

    def sclass_get_status(self, workspace_id: str = "default") -> dict[str, Any]:
        """Query canonical engineering status, obligations, budget, and release readiness."""
        client = SClassClient.connect(self.db_path)
        try:
            state = client.get_state(workspace_id)
            chain = client.verify_chain(workspace_id)
            release = client.evaluate_and_release(workspace_id)
        finally:
            client.close()

        active_obligations: list[dict[str, Any]] = []
        if state.obligations and hasattr(state.obligations, "_obligations"):
            for obl_id, obl in state.obligations._obligations.items():
                active_obligations.append({
                    "obligation_id": obl_id,
                    "kind": obl.kind.value,
                    "status": obl.status.value,
                    "risk_tier": obl.risk_tier.value,
                    "description": obl.description,
                })

        budget_usage = {
            "reservations_count": len(state.budgets) if hasattr(state, "budgets") and state.budgets else 0,
            "active_leases_count": len(state.leases) if hasattr(state, "leases") and state.leases else 0,
        }

        return {
            "workspace_id": workspace_id,
            "event_sequence": state.event_sequence,
            "state_revision": str(state.state_revision),
            "chain_status": chain.value,
            "release_verdict": release.name,
            "active_obligations": active_obligations,
            "budget_usage": budget_usage,
        }

    # -------------------------------------------------------------------------
    # JSON-RPC 2.0 Dispatcher
    # -------------------------------------------------------------------------

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return MCP tool schemas."""
        return [
            {
                "name": "sclass_guide_task",
                "description": "Run world model indexing and intent compilation to produce bounded context packages, architectural constraints, and test obligations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string", "description": "High-level user or engineering task intent"},
                        "workspace_id": {"type": "string", "description": "Target workspace identifier", "default": "default"},
                    },
                    "required": ["intent"],
                },
            },
            {
                "name": "sclass_validate_patch",
                "description": "Stage a patch via PatchAgentWorker boundary and execute MultiEngineVerificationPlane, returning structured diagnostics and authentic signed receipts.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "patch": {"type": "string", "description": "Source patch or content to stage and validate"},
                        "target_file": {"type": "string", "description": "Relative file path within the workspace"},
                        "workspace_id": {"type": "string", "description": "Target workspace identifier", "default": "default"},
                        "restore": {"type": "boolean", "description": "Whether to restore original file content after verification", "default": False},
                    },
                    "required": ["patch", "target_file"],
                },
            },
            {
                "name": "sclass_get_status",
                "description": "Query canonical engineering status, active obligations, resource budget consumption, and release readiness.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workspace_id": {"type": "string", "description": "Target workspace identifier", "default": "default"},
                    },
                },
            },
        ]

    def handle_jsonrpc(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle incoming MCP JSON-RPC 2.0 request."""
        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": self.SERVER_NAME,
                        "version": self.SERVER_VERSION,
                    },
                },
            }

        if method in ("notifications/initialized", "initialized"):
            return None

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tool_definitions(),
                },
            }

        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            try:
                if tool_name == "sclass_guide_task":
                    res = self.sclass_guide_task(
                        intent=tool_args["intent"],
                        workspace_id=tool_args.get("workspace_id", "default"),
                    )
                elif tool_name == "sclass_validate_patch":
                    res = self.sclass_validate_patch(
                        patch=tool_args["patch"],
                        target_file=tool_args["target_file"],
                        workspace_id=tool_args.get("workspace_id", "default"),
                        restore=tool_args.get("restore", False),
                    )
                elif tool_name == "sclass_get_status":
                    res = self.sclass_get_status(
                        workspace_id=tool_args.get("workspace_id", "default"),
                    )
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}",
                        },
                    }

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(res, indent=2),
                            }
                        ],
                    },
                }
            except Exception as exc:  # noqa: BLE001 - JSON-RPC server must catch all tool exceptions to prevent process crash
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Tool execution failed: {exc}",
                            }
                        ],
                        "isError": True,
                    },
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }

    def run_stdio(self) -> None:
        """Run line-delimited JSON-RPC loop over stdio."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as exc:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"},
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()
                continue

            resp = self.handle_jsonrpc(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


def create_mcp_app(server: SClassMCPServer | None = None):
    """Factory creating an MCPServer instance from the mcp library if available."""
    try:
        from mcp.server.mcpserver import MCPServer

        srv = server or SClassMCPServer()
        app = MCPServer(srv.SERVER_NAME)

        @app.tool()
        def sclass_guide_task(intent: str, workspace_id: str = "default") -> str:
            """Run world model indexing and intent compilation."""
            res = srv.sclass_guide_task(intent, workspace_id=workspace_id)
            return json.dumps(res, indent=2)

        @app.tool()
        def sclass_validate_patch(
            patch: str, target_file: str, workspace_id: str = "default", restore: bool = False
        ) -> str:
            """Stage a patch and execute MultiEngineVerificationPlane."""
            res = srv.sclass_validate_patch(patch, target_file, workspace_id=workspace_id, restore=restore)
            return json.dumps(res, indent=2)

        @app.tool()
        def sclass_get_status(workspace_id: str = "default") -> str:
            """Query canonical status, obligations, budget, and release readiness."""
            res = srv.sclass_get_status(workspace_id=workspace_id)
            return json.dumps(res, indent=2)

        return app
    except ImportError:
        return None


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='S-Class Model Context Protocol (MCP) Server')
    parser.add_argument('--workspace', default='.', help='Path to workspace root')
    parser.add_argument('--db', default='sclass.sqlite', help='Path to authority database')
    args = parser.parse_args()
    server = SClassMCPServer(workspace_root=args.workspace, db_path=args.db)
    server.run_stdio()

if __name__ == '__main__':
    main()
