"""
S-Class EOS V11.2 - D7 Action Proposal Synthesizer & Output Normalizer (§8.1, §8.3).
Normalizes agent tool calls into canonical D0 ActionProposal objects for D5 Controller submission.
Propagates authoritative session execution context unchanged; never manufactures or defaults topology.
"""

from __future__ import annotations
import uuid
from typing import Tuple, Optional, Any, Mapping, Sequence
from controller.authorization import ActionProposal
from controller.token import ExecutionContext
from agent.models import AgentToolCall


class ActionProposalSynthesizer:
    """Validates proposal tool calls and normalizes them into schema-compliant ActionProposal instances."""

    @staticmethod
    def synthesize_proposal(
        tool_call: AgentToolCall,
        session_execution_context: ExecutionContext,
        estimated_cost_usd: float = 0.05,
    ) -> Tuple[Optional[ActionProposal], Optional[str]]:
        """
        Transforms a proposal tool call into an ActionProposal with strictly propagated session execution context.
        Zero manufacture of provider_id, sandbox_profile_id, resource_profile_id, or random workspace_ids.
        """
        if not isinstance(tool_call, AgentToolCall):
            return None, "tool_call must be an instance of AgentToolCall."

        if not isinstance(session_execution_context, ExecutionContext):
            return None, "session_execution_context must be an authoritative ExecutionContext instance."

        if not session_execution_context.capability_set:
            return None, "Cannot synthesize proposal with empty capability set in execution context."

        args = tool_call.arguments
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
                execution_context=session_execution_context,
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
                execution_context=session_execution_context,
                estimated_cost_usd=estimated_cost_usd,
                parameters={"patch_content": patch_content},
            )
            return proposal, None

        return None, f"Tool '{tool_call.tool_name}' is not a recognized proposal tool."
