"""
S-Class EOS V11.2 - D7 Action Proposal Synthesizer & Output Normalizer (§8.1, §8.3).
Normalizes agent tool calls into canonical D0 ActionProposal objects for D5 Controller submission.
Enforces zero ambient authority: proposals must pass full D5 authorization gates.
"""

from __future__ import annotations
import os
import uuid
from typing import Tuple, Optional, Any, Mapping
from controller.authorization import ActionProposal
from controller.token import ExecutionContext
from agent.models import AgentToolCall


class ActionProposalSynthesizer:
    """Validates proposal tool calls and normalizes them into schema-compliant ActionProposal instances."""

    @staticmethod
    def synthesize_proposal(
        tool_call: AgentToolCall,
        provider_id: str = "pytest_runner_engine",
        sandbox_profile_id: str = "sbx_std",
        resource_profile_id: str = "res_std",
        granted_capabilities: Tuple[str, ...] = ("CAP_EXEC_TEST",),
        workspace_id: Optional[str] = None,
        estimated_cost_usd: float = 0.05,
    ) -> Tuple[Optional[ActionProposal], Optional[str]]:
        """Transforms a proposal tool call (e.g. propose_code_patch, propose_test_run) into an ActionProposal."""
        if not isinstance(tool_call, AgentToolCall):
            return None, "tool_call must be an instance of AgentToolCall."

        args = tool_call.arguments
        ws_id = workspace_id or f"ws_{uuid.uuid4().hex[:8]}"

        context = ExecutionContext(
            provider_id=provider_id,
            sandbox_profile_id=sandbox_profile_id,
            workspace_id=ws_id,
            resource_profile_id=resource_profile_id,
            capability_set=granted_capabilities,
        )

        proposal_id = f"PROP-{uuid.uuid4().hex[:8].upper()}"

        if tool_call.tool_name == "propose_test_run":
            obl_id = args.get("obligation_id")
            target_test = args.get("target_test")
            purpose = args.get("purpose", "Run test verification")
            params = args.get("parameters", {})

            if not obl_id or not isinstance(obl_id, str):
                return None, "Missing or invalid 'obligation_id' in propose_test_run."
            if not target_test or not isinstance(target_test, str):
                return None, "Missing or invalid 'target_test' in propose_test_run."

            proposal = ActionProposal(
                proposal_id=proposal_id,
                obligation_id=obl_id,
                action_type="EXECUTE_TEST",
                target=target_test,
                purpose=purpose,
                execution_context=context,
                estimated_cost_usd=estimated_cost_usd,
                parameters=params,
            )
            return proposal, None

        elif tool_call.tool_name == "propose_code_patch":
            obl_id = args.get("obligation_id")
            target_file = args.get("target_file")
            patch_content = args.get("patch_content")
            purpose = args.get("purpose", "Apply code patch")

            if not obl_id or not isinstance(obl_id, str):
                return None, "Missing or invalid 'obligation_id' in propose_code_patch."
            if not target_file or not isinstance(target_file, str):
                return None, "Missing or invalid 'target_file' in propose_code_patch."
            if not patch_content or not isinstance(patch_content, str):
                return None, "Missing or invalid 'patch_content' in propose_code_patch."

            proposal = ActionProposal(
                proposal_id=proposal_id,
                obligation_id=obl_id,
                action_type="APPLY_PATCH",
                target=target_file,
                purpose=purpose,
                execution_context=context,
                estimated_cost_usd=estimated_cost_usd,
                parameters={"patch_content": patch_content},
            )
            return proposal, None

        return None, f"Tool '{tool_call.tool_name}' is not a recognized proposal tool."
