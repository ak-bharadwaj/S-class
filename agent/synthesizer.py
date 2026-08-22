"""
S-Class EOS V11.2 - D7 Action Proposal Synthesizer & Cryptographic Authority Verification (§8.1, §8.3).
Normalizes agent tool calls into canonical D0 ActionProposal objects for D5 Controller submission.
Verifies cryptographically signed AuthorizedSessionExecutionBinding against controller trust root,
active session, repository, commit SHA, task, context digest, and capability set.
D7 receives and verifies authority credentials; D7 never manufactures or self-attests authority.
"""

from __future__ import annotations
import uuid
from typing import Tuple, Optional, Any, Mapping, Sequence
from controller.authorization import ActionProposal
from controller.token import ExecutionContext, AuthorizedSessionExecutionBinding
from controller.controller import SClassController
from controller.authority import ProposalAuthorityContext
from agent.models import AgentToolCall


class ActionProposalSynthesizer:
    """Validates proposal tool calls and normalizes them into schema-compliant ActionProposal instances."""

    @staticmethod
    def synthesize_proposal(
        tool_call: AgentToolCall,
        session_execution_context: ExecutionContext,
        session_binding: AuthorizedSessionExecutionBinding,
        controller: SClassController,
        active_session_id: str,
        authoritative_repo_id: str,
        authoritative_source_sha: str,
        active_task_id: str,
        estimated_cost_usd: float = 0.05,
    ) -> Tuple[Optional[ActionProposal], Optional[str]]:
        """
        Transforms a proposal tool call into an ActionProposal after cryptographically verifying
        authority provenance against the Controller's immutable authority trust root.
        """
        # 1. Type and instance integrity checks
        if not isinstance(tool_call, AgentToolCall):
            return None, "tool_call must be an instance of AgentToolCall."

        if not isinstance(session_execution_context, ExecutionContext):
            return None, "session_execution_context must be an authoritative ExecutionContext instance."

        if not isinstance(session_binding, AuthorizedSessionExecutionBinding):
            return None, "session_binding must be an authoritative AuthorizedSessionExecutionBinding instance."

        if not isinstance(controller, SClassController):
            return None, "controller must be an authoritative SClassController instance."

        # 2. Cryptographic Authority Signature Verification against Controller Trust Root
        if not controller.verify_session_binding(session_binding):
            return None, "AUTHORITY_SIGNATURE_INVALID: AuthorizedSessionExecutionBinding cryptographic signature is invalid or not signed by Controller trust root."

        # 3. Exact Authority Field Bindings
        if session_binding.session_id != active_session_id:
            return None, (
                f"BINDING_MISMATCH: session_id mismatch: binding has '{session_binding.session_id}', "
                f"active session is '{active_session_id}'."
            )

        if session_binding.repository_id != authoritative_repo_id:
            return None, (
                f"BINDING_MISMATCH: repository_id mismatch: binding has '{session_binding.repository_id}', "
                f"authoritative repo is '{authoritative_repo_id}'."
            )

        if session_binding.source_sha != authoritative_source_sha:
            return None, (
                f"BINDING_MISMATCH: source_sha mismatch: binding has '{session_binding.source_sha}', "
                f"authoritative SHA is '{authoritative_source_sha}'."
            )

        if session_binding.task_id != active_task_id:
            return None, (
                f"BINDING_MISMATCH: task_id mismatch: binding has '{session_binding.task_id}', "
                f"active task is '{active_task_id}'."
            )

        if session_binding.execution_context_digest != session_execution_context.context_digest:
            return None, (
                f"BINDING_MISMATCH: context_digest mismatch: binding expected '{session_binding.execution_context_digest}', "
                f"context has '{session_execution_context.context_digest}'."
            )

        # 4. Single-Source Capability Authority (The signed binding is the authoritative capability source)
        sorted_caps = tuple(sorted(set(session_execution_context.capability_set)))
        if session_binding.granted_capabilities != sorted_caps:
            return None, (
                f"CAPABILITY_AUTHORITY_MISMATCH: signed binding granted capabilities {session_binding.granted_capabilities} "
                f"do not match execution context capability set {sorted_caps}."
            )

        # 5. Authoritatively resolve ProposalAuthorityContext from Controller boundary (Strict Fail-Closed)
        try:
            auth_ctx = controller.resolve_proposal_authority_context(active_task_id)
        except Exception as e:
            return None, f"AUTHORITY_RESOLUTION_FAILED: Failed to resolve authoritative coordinates from Controller: {e}"

        if not isinstance(auth_ctx, ProposalAuthorityContext):
            return None, "AUTHORITY_RESOLUTION_FAILED: Controller returned an invalid ProposalAuthorityContext instance."

        owner_id = auth_ctx.owner_id
        fencing_token = auth_ctx.fencing_token
        lease_epoch = auth_ctx.lease_epoch
        state_version = auth_ctx.state_version
        state_digest = auth_ctx.state_digest

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
                owner_id=owner_id,
                fencing_token=fencing_token,
                lease_epoch=lease_epoch,
                state_version=state_version,
                state_digest=state_digest,
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
                owner_id=owner_id,
                fencing_token=fencing_token,
                lease_epoch=lease_epoch,
                state_version=state_version,
                state_digest=state_digest,
            )
            return proposal, None

        return None, f"Tool '{tool_call.tool_name}' is not a recognized proposal tool."
