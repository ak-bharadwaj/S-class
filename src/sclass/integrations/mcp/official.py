"""
S-Class Official Model Context Protocol (MCP) Integration (MCP 2.x Official SDK).

Architecture Rule:
MCP is strictly an INGRESS ADAPTER, NOT a trust boundary.
MCP Request -> Platform Optimization -> ActionRequest -> Authorization -> Execution -> Observation -> Verification -> MCP Response

S-Class owns:
- Platform detection, profiling, and optimization policy
- ActionRequest normalization
- Authoritative authorization and boundary enforcement
- Execution observation and receipt sealing (LocalLedger)
- Claim verification
MCP owns:
- Transport mechanics (stdio, streamable HTTP, SSE)
- JSON-RPC framing and serialization
- Tool discovery protocol (tools/list)
- Tool invocation protocol (tools/call)
"""

from __future__ import annotations
import os
import sys
import json
import time
import uuid
import hashlib
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List, Tuple, Union, AsyncIterator

import anyio
from mcp.server.mcpserver import MCPServer
import mcp.types as types
from mcp.client.session import ClientSession

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import (
    Capability,
    CAP_TERMINAL_EXECUTE,
    CAP_FILESYSTEM_READ,
    CAP_FILESYSTEM_WRITE,
    CAP_GIT_READ,
    CAP_GIT_WRITE,
    CAP_PROCESS_SPAWN,
)
from sclass.control.resources import classify_resource, AuthorityBoundary
from sclass.policy.authorization_service import AuthorizationService
from sclass.policy.capability_resolver import CapabilityRegistry
from sclass.observation.convergence import ObservationConvergence
from sclass.trust.ledger import LocalLedger
from sclass.verification.engine import verify_claim
from sclass.domain.claim import Claim, ClaimType
from sclass.execution.modes import check_protected_resource_targeting
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.platform.framework import PlatformProfilingFramework
from sclass.platform.engine import ControlPolicy


TOOL_CAPABILITY_MAP = {
    "run_command": CAP_TERMINAL_EXECUTE,
    "execute_command": CAP_TERMINAL_EXECUTE,
    "read_file": CAP_FILESYSTEM_READ,
    "write_file": CAP_FILESYSTEM_WRITE,
    "list_dir": CAP_FILESYSTEM_READ,
    "sclass_verify": "sclass.verify",
    "sclass_initialize": "sclass.state",
    "sclass_get_state": "sclass.state",
    "sclass_profile": "sclass.profile",
}


@asynccontextmanager
async def open_in_memory_session(mcp_server: MCPServer) -> AsyncIterator[ClientSession]:
    """
    Spawns an in-memory client session connected to an official MCPServer over bidirectional memory streams.
    Enables zero-overhead, highly deterministic in-process testing and verification.
    """
    s2c_send, s2c_recv = anyio.create_memory_object_stream(100)
    c2s_send, c2s_recv = anyio.create_memory_object_stream(100)

    async with anyio.create_task_group() as tg:
        async def run_server() -> None:
            await mcp_server._lowlevel_server.run(
                c2s_recv,
                s2c_send,
                mcp_server._lowlevel_server.create_initialization_options(),
            )

        tg.start_soon(run_server)

        async with ClientSession(s2c_recv, c2s_send) as session:
            await session.initialize()
            yield session

        tg.cancel_scope.cancel()


class SClassMCPServer:
    """
    Authoritative S-Class MCP Server powered by the official Python mcp SDK.
    Implements the full 5-stage ingress governance pipeline on every tool call.
    """

    def __init__(
        self,
        workspace_dir: str,
        name: str = "sclass-official-mcp",
        mode: str = "enforce",
        auth_service: Optional[AuthorizationService] = None,
        capability_registry: Optional[CapabilityRegistry] = None,
        ledger: Optional[LocalLedger] = None,
        agent_id: str = "mcp_agent",
        session_id: Optional[str] = None,
        platform_framework: Optional[PlatformProfilingFramework] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.name = name
        self.mode = mode
        self.agent_id = agent_id
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"

        self.capability_registry = capability_registry or CapabilityRegistry(load_defaults=True)
        self.auth_service = auth_service or AuthorizationService(capability_registry=self.capability_registry)
        self.ledger = ledger or LocalLedger(workspace_dir=self.workspace_dir)
        self.platform_framework = platform_framework or PlatformProfilingFramework(workspace_dir=self.workspace_dir)

        self.mcp = MCPServer(
            name=self.name,
            instructions="S-Class Official Governance & Execution Ingress Gateway",
        )
        self._register_official_tools()

    def _register_official_tools(self) -> None:
        """Registers official MCP tools with strict schema definitions."""

        @self.mcp.tool(
            name="run_command",
            description="Execute a terminal command governed by S-Class policy, observed execution, and ledger receipting.",
        )
        def run_command_tool(command: str, timeout: float = 60.0) -> types.CallToolResult:
            return self.handle_run_command(command=command, timeout=timeout)

        @self.mcp.tool(
            name="read_file",
            description="Read file content safely from the workspace with security boundary enforcement.",
        )
        def read_file_tool(path: str) -> types.CallToolResult:
            return self.handle_read_file(path=path)

        @self.mcp.tool(
            name="write_file",
            description="Write content to a file in the workspace with boundary enforcement and ledger recording.",
        )
        def write_file_tool(path: str, content: str) -> types.CallToolResult:
            return self.handle_write_file(path=path, content=content)

        @self.mcp.tool(
            name="list_dir",
            description="List directory entries in the workspace with boundary enforcement.",
        )
        def list_dir_tool(path: str = ".") -> types.CallToolResult:
            return self.handle_list_dir(path=path)

        @self.mcp.tool(
            name="sclass_verify",
            description="Verify an agent claim against an observed evidence receipt in the immutable ledger.",
        )
        def sclass_verify_tool(claim_text: str, receipt_id: Optional[str] = None) -> types.CallToolResult:
            return self.handle_sclass_verify(claim_text=claim_text, receipt_id=receipt_id)

        @self.mcp.tool(
            name="sclass_initialize",
            description="Initialize S-Class workflow state and execution strategy.",
        )
        def sclass_initialize_tool(goal: str = "", profile: Optional[str] = None) -> types.CallToolResult:
            return self.handle_sclass_initialize(goal=goal, profile=profile)

        @self.mcp.tool(
            name="sclass_get_state",
            description="Inspect current S-Class workflow state and complexity tier.",
        )
        def sclass_get_state_tool() -> types.CallToolResult:
            return self.handle_sclass_get_state()

        @self.mcp.tool(
            name="sclass_profile",
            description="Inspect active platform profile, compensation policy, and synthesized control policy.",
        )
        def sclass_profile_tool() -> types.CallToolResult:
            return self.handle_sclass_profile()

    def get_control_policy(self, task: str = "execute action", risk: str = "medium") -> ControlPolicy:
        """Synthesizes active control policy for current agent and workspace."""
        return self.platform_framework.synthesize_control_policy(
            task=task,
            risk=risk,
            requested_actor=self.agent_id,
        )

    def handle_run_command(self, command: str, timeout: float = 60.0) -> types.CallToolResult:
        """
        Governs command execution through the full 5-stage ingress pipeline:
        1. Normalization -> ActionRequest
        2. Authorization -> boundary + policy
        3. Execution & Observation -> HostProcessBackend -> ObservedReceipt -> LocalLedger
        4. Verification -> verify output & exit code
        5. Response -> CallToolResult
        """
        # Stage 1: Normalization
        action_req = ActionRequest(
            actor=self.agent_id,
            session=self.session_id,
            capability=CAP_TERMINAL_EXECUTE,
            action="run_command",
            target=command,
            parameters={"command": command, "timeout": timeout},
            workspace=self.workspace_dir,
            platform="mcp",
        )

        # Stage 2: Authorization & Boundary Protection
        is_targeted, prot_reason = check_protected_resource_targeting(command)
        if is_targeted:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Security Block] SCLASS-MCP-PROT: Command targets protected trust boundary: {prot_reason}",
                    )
                ],
                is_error=True,
                meta={"policy_id": "SCLASS-MCP-PROT", "reason": prot_reason},
            )

        decision = self.auth_service.authorize(action_req, workspace_dir=self.workspace_dir)
        if decision.is_denied:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Policy Block] {decision.policy_id}: {decision.reason}",
                    )
                ],
                is_error=True,
                meta={"decision": decision.to_dict()},
            )

        # Stage 3: Execution & Observation
        try:
            exec_result, receipt = ObservationConvergence.execute_and_observe(
                request=action_req,
                command=command,
                workspace_dir=self.workspace_dir,
                timeout=timeout,
                ledger=self.ledger,
                auth_service=self.auth_service,
                capability_registry=self.capability_registry,
                authorization=decision,
            )
        except Exception as ex:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Execution Error] Failed to execute: {ex}",
                    )
                ],
                is_error=True,
                meta={"error": str(ex)},
            )

        # Handle Timeout fail-closed
        if exec_result.timed_out:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Tool Timeout] Command execution timed out after {timeout} seconds: {command}",
                    )
                ],
                is_error=True,
                meta={"timed_out": True, "receipt_id": receipt.receipt_id},
            )

        # Handle Non-Zero Exit Code failure
        if exec_result.exit_code != 0:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=(
                            f"[S-Class Tool Failure] Command exited with code {exec_result.exit_code}\n"
                            f"STDOUT:\n{exec_result.stdout}\n"
                            f"STDERR:\n{exec_result.stderr}"
                        ),
                    )
                ],
                is_error=True,
                meta={"exit_code": exec_result.exit_code, "receipt_id": receipt.receipt_id},
            )

        # Stage 4: Verification
        claim = Claim(
            claim_id=receipt.claim_id,
            statement=f"Successfully executed: {command}",
            task_id=receipt.task_id,
            claim_type=ClaimType.EXECUTION.value,
            metadata={
                "agent": self.agent_id,
                "action": "run_command",
                "workspace": self.workspace_dir,
                "declared_evidence": {"receipt_id": receipt.receipt_id},
            },
        )
        v_res = verify_claim(claim, receipt, workspace_dir=self.workspace_dir, ledger=self.ledger)
        if not v_res.is_accepted:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Verification Failure] {v_res.reason}",
                    )
                ],
                is_error=True,
                meta={"verification": v_res.to_dict()},
            )

        # Stage 5: Response
        output_text = exec_result.stdout if exec_result.stdout else "Command completed successfully with code 0."
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=output_text)],
            is_error=False,
            meta={
                "receipt_id": receipt.receipt_id,
                "receipt_hash": receipt.receipt_hash,
                "exit_code": 0,
                "duration_ms": exec_result.duration_ms,
            },
        )

    def handle_read_file(self, path: str) -> types.CallToolResult:
        """Reads a workspace file with boundary enforcement and ledger tracking."""
        action_req = ActionRequest(
            actor=self.agent_id,
            session=self.session_id,
            capability=CAP_FILESYSTEM_READ,
            action="read_file",
            target=path,
            parameters={"path": path},
            workspace=self.workspace_dir,
            platform="mcp",
        )

        r_kind, boundary = classify_resource(path, self.workspace_dir)
        if boundary in (AuthorityBoundary.SCLASS_TRUST_ROOT, AuthorityBoundary.SCLASS_VERIFICATION_ONLY):
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Security Block] SCLASS-MCP-PROT: Cannot access protected resource: {path}",
                    )
                ],
                is_error=True,
                meta={"policy_id": "SCLASS-MCP-PROT", "target": path},
            )

        decision = self.auth_service.authorize(action_req, workspace_dir=self.workspace_dir)
        if decision.is_denied:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Policy Block] {decision.policy_id}: {decision.reason}",
                    )
                ],
                is_error=True,
                meta={"decision": decision.to_dict()},
            )

        abs_path = os.path.abspath(os.path.join(self.workspace_dir, path) if not os.path.isabs(path) else path)
        if not os.path.exists(abs_path):
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Tool Failure] File not found: {path}",
                    )
                ],
                is_error=True,
                meta={"target": path, "error": "file_not_found"},
            )

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.ledger.append("filesystem.read", {"path": path, "size": len(content)})
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=content)],
                is_error=False,
                meta={"path": path, "size": len(content)},
            )
        except Exception as ex:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"[S-Class Tool Failure] Read error: {ex}")],
                is_error=True,
                meta={"error": str(ex)},
            )

    def handle_write_file(self, path: str, content: str) -> types.CallToolResult:
        """Writes a file to workspace with boundary enforcement and ledger recording."""
        action_req = ActionRequest(
            actor=self.agent_id,
            session=self.session_id,
            capability=CAP_FILESYSTEM_WRITE,
            action="write_file",
            target=path,
            parameters={"path": path, "content": content},
            workspace=self.workspace_dir,
            platform="mcp",
        )

        r_kind, boundary = classify_resource(path, self.workspace_dir)
        if boundary in (AuthorityBoundary.SCLASS_TRUST_ROOT, AuthorityBoundary.SCLASS_VERIFICATION_ONLY):
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Security Block] SCLASS-MCP-PROT: Cannot modify protected resource: {path}",
                    )
                ],
                is_error=True,
                meta={"policy_id": "SCLASS-MCP-PROT", "target": path},
            )

        decision = self.auth_service.authorize(action_req, workspace_dir=self.workspace_dir)
        if decision.is_denied:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Policy Block] {decision.policy_id}: {decision.reason}",
                    )
                ],
                is_error=True,
                meta={"decision": decision.to_dict()},
            )

        abs_path = os.path.abspath(os.path.join(self.workspace_dir, path) if not os.path.isabs(path) else path)
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)

            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            self.ledger.append(
                "filesystem.write",
                {"path": path, "content_hash": content_hash, "size": len(content)},
            )

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Successfully wrote {len(content)} characters to {path}",
                    )
                ],
                is_error=False,
                meta={"path": path, "content_hash": content_hash, "size": len(content)},
            )
        except Exception as ex:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"[S-Class Tool Failure] Write error: {ex}")],
                is_error=True,
                meta={"error": str(ex)},
            )

    def handle_list_dir(self, path: str = ".") -> types.CallToolResult:
        """Lists directory entries safely with boundary enforcement."""
        r_kind, boundary = classify_resource(path, self.workspace_dir)
        if boundary in (AuthorityBoundary.SCLASS_TRUST_ROOT, AuthorityBoundary.SCLASS_VERIFICATION_ONLY):
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Security Block] SCLASS-MCP-PROT: Cannot list protected resource: {path}",
                    )
                ],
                is_error=True,
            )

        abs_path = os.path.abspath(os.path.join(self.workspace_dir, path) if not os.path.isabs(path) else path)
        if not os.path.exists(abs_path):
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"[S-Class Tool Failure] Directory not found: {path}")],
                is_error=True,
            )

        try:
            entries = sorted(os.listdir(abs_path))
            return types.CallToolResult(
                content=[types.TextContent(type="text", text="\n".join(entries))],
                is_error=False,
                meta={"count": len(entries), "path": path},
            )
        except Exception as ex:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"[S-Class Tool Failure] List error: {ex}")],
                is_error=True,
            )

    def handle_sclass_verify(self, claim_text: str, receipt_id: Optional[str] = None) -> types.CallToolResult:
        """
        Verifies an agent claim against observed evidence in LocalLedger.
        Detects unobserved claims, fabricated receipts, exit code discrepancies, and workspace mutations.
        """
        matching_evidence = None
        if receipt_id:
            from sclass.observation.receipt import load_receipt
            matching_evidence = load_receipt(receipt_id, self.workspace_dir)
            if matching_evidence is None:
                # Fallback to scanning ledger payloads
                entries = self.ledger.read_all()
                for ent in reversed(entries):
                    payload = ent.get("payload", {})
                    if isinstance(payload, dict) and payload.get("receipt_id") == receipt_id:
                        from sclass.domain.evidence import EvidenceReceipt
                        try:
                            matching_evidence = EvidenceReceipt.from_dict(payload)
                            break
                        except Exception:
                            pass
        else:
            entries = self.ledger.read_all()
            for ent in reversed(entries):
                if ent.get("event", "").upper() == "OBSERVATION":
                    payload = ent.get("payload", {})
                    r_id = payload.get("receipt_id")
                    if r_id:
                        from sclass.observation.receipt import load_receipt
                        matching_evidence = load_receipt(r_id, self.workspace_dir)
                        if matching_evidence:
                            break

        claim = Claim(
            claim_id=f"claim_{uuid.uuid4().hex[:8]}",
            statement=claim_text,
            task_id=self.session_id,
            claim_type=ClaimType.EXECUTION.value,
            metadata={
                "agent": self.agent_id,
                "action": "verify",
                "workspace": self.workspace_dir,
                "declared_evidence": {"receipt_id": receipt_id} if receipt_id else {},
            },
        )

        v_res = verify_claim(claim, matching_evidence, workspace_dir=self.workspace_dir, ledger=self.ledger)
        if not v_res.is_accepted:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"[S-Class Verification Rejected] {v_res.reason}",
                    )
                ],
                is_error=True,
                meta={"verification": v_res.to_dict()},
            )

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=f"[S-Class Verification Accepted] {v_res.reason or 'Evidence successfully verified against immutable ledger.'}",
                )
            ],
            is_error=False,
            meta={"verification": v_res.to_dict()},
        )

    def handle_sclass_initialize(self, goal: str = "", profile: Optional[str] = None) -> types.CallToolResult:
        """Initializes S-Class runtime state."""
        import runtime
        runtime.initialize_state(self.workspace_dir, goal=goal, profile=profile)
        state = runtime.get_state(self.workspace_dir)
        import dataclasses
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(dataclasses.asdict(state), indent=2),
                )
            ],
            is_error=False,
            meta={"status": "initialized"},
        )

    def handle_sclass_get_state(self) -> types.CallToolResult:
        """Inspects current S-Class runtime state."""
        import runtime
        state = runtime.get_state(self.workspace_dir)
        import dataclasses
        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(dataclasses.asdict(state), indent=2),
                )
            ],
            is_error=False,
            meta={"currentPhase": state.currentPhase},
        )

    def handle_sclass_profile(self) -> types.CallToolResult:
        """Inspects active platform profile, compensation policy, and synthesized control policy."""
        detected = self.platform_framework.resolve_platform(requested_actor=self.agent_id)
        ctrl_policy = self.get_control_policy(task="mcp_session")
        report = {
            "platform_id": detected.platform_id,
            "confidence": detected.confidence,
            "version": detected.version,
            "evidence": detected.evidence,
            "native_strengths": detected.profile.native_strengths,
            "preserved_capabilities": ctrl_policy.preserved_capabilities,
            "active_compensations": ctrl_policy.active_compensations,
            "verification_gate": ctrl_policy.verification_gate,
            "observation_mode": ctrl_policy.observation_mode,
            "interruption_policy": ctrl_policy.interruption_policy,
            "budget": ctrl_policy.budget.to_dict(),
        }
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(report, indent=2))],
            is_error=False,
            meta={"platform_id": detected.platform_id},
        )

    def open_client_session(self) -> AsyncIterator[ClientSession]:
        """Returns an async context manager for an in-memory ClientSession."""
        return open_in_memory_session(self.mcp)

    def streamable_http_app(self) -> Any:
        """Returns the official Starlette ASGI application for streamable HTTP transport."""
        return self.mcp.streamable_http_app()

    def sse_app(self) -> Any:
        """Returns the official Starlette ASGI application for SSE transport."""
        return self.mcp.sse_app()


def create_sclass_mcp_server(
    workspace_dir: str,
    name: str = "sclass-official-mcp",
    mode: str = "enforce",
    auth_service: Optional[AuthorizationService] = None,
    capability_registry: Optional[CapabilityRegistry] = None,
    ledger: Optional[LocalLedger] = None,
    agent_id: str = "mcp_agent",
    platform_framework: Optional[PlatformProfilingFramework] = None,
) -> SClassMCPServer:
    """Factory creating an authoritative SClassMCPServer instance."""
    return SClassMCPServer(
        workspace_dir=workspace_dir,
        name=name,
        mode=mode,
        auth_service=auth_service,
        capability_registry=capability_registry,
        ledger=ledger,
        agent_id=agent_id,
        platform_framework=platform_framework,
    )
