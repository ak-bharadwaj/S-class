"""
S-Class ACP Integration: Terminal Gateway.
Implements the official ACP terminal execution operations (`terminal/exec`, `terminal/kill`).
Strictly routes execution through S-Class process execution, computing `ExecutionIdentity`,
verifying trust allowlists, capturing OS-level observations, and recording immutable receipts.
"""

from __future__ import annotations
import os
from typing import Dict, Any, Optional

from sclass.integrations.acp.schema import (
    ACPTerminalExecParams,
    ACPTerminalExecResult,
)
from sclass.control.authorization import authorize
from sclass.domain.action import ActionRequest
from sclass.observation.observer import observe_command
from sclass.trust.ledger import LocalLedger


class ACPTerminalGateway:
    """Terminal gateway executing commands under S-Class process observation."""

    def __init__(self, workspace_dir: str, mode: str = "enforce", ledger: Optional[LocalLedger] = None):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.mode = mode
        self.ledger = ledger or LocalLedger(self.workspace_dir)

    def execute_terminal_command(
        self,
        params: ACPTerminalExecParams,
        agent_id: str = "acp_agent",
    ) -> ACPTerminalExecResult:
        """
        Authorizes and executes a terminal command under full S-Class observation.
        """
        # 1. Authorize via S-Class policy
        action_req = ActionRequest(
            agent=agent_id,
            platform="acp",
            action="run_command",
            tool="terminal/exec",
            target=params.command,
            parameters={"command": params.command, "cwd": params.cwd or self.workspace_dir},
            workspace=self.workspace_dir,
            task_id=params.session_id,
            context={"session_id": params.session_id},
        )

        decision = authorize(action_req, mode=self.mode, workspace_dir=self.workspace_dir)
        if decision.is_denied:
            raise PermissionError(f"Command execution denied by S-Class policy: {decision.reason}")

        # 2. Execute process with observation
        receipt = observe_command(
            command=params.command,
            workspace_dir=self.workspace_dir,
            task_id=f"acp_{params.session_id}",
            claim_id=f"acp_claim_{params.session_id}",
            ledger=self.ledger,
        )

        return ACPTerminalExecResult(
            command=params.command,
            exit_code=receipt.exit_code,
            stdout=receipt.stdout_hash,
            stderr=receipt.stderr_hash,
            execution_receipt_id=receipt.receipt_id,
        )
