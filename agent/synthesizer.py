"""
S-Class EOS V11.2 - D7 Action Proposal Synthesizer & Cryptographic Authority Verification (§8.1, §8.3).
Normalizes agent tool calls into canonical D0 ActionProposal objects for D5 Controller submission.
Verifies cryptographically signed AuthorizedSessionExecutionBinding against authority signer,
active session, repository, commit SHA, task, context digest, and capability set.
D7 receives and verifies authority credentials; D7 never manufactures or self-attests authority.
"""

from __future__ import annotations
import uuid
from typing import Tuple, Optional, Any, Mapping, Sequence
from controller.authorization import ActionProposal
from controller.token import (
    ExecutionContext,
    AuthorizedSessionExecutionBinding,
    verify_authorized_session_binding,
)
from policy.models import AuthoritySignerProtocol
from agent.models import AgentToolCall


class ActionProposalSynthesizer:
    """Validates proposal tool calls and normalizes them into schema-compliant ActionProposal instances."""

    @staticmethod
    def synthesize_proposal(
        tool_call: AgentToolCall,
        session_execution_context: ExecutionContext,
        session_binding: AuthorizedSessionExecutionBinding,
        authority_signer: AuthoritySignerProtocol,
        active_session_id: str,
        authoritative_repo_id: str,
        authoritative_source_sha: str,
        active_task_id: str,
        estimated_cost_usd: float = 0.05,
    ) -> Tuple[Optional[ActionProposal], Optional[str]]:
        """
        Transforms a proposal tool call into an ActionProposal after cryptographically verifying
        authority provenance against the immutable, signed AuthorizedSessionExecutionBinding.
        """
        # 1. Type and instance integrity checks
        if not isinstance(tool_call, AgentToolCall):
            return None, "tool_call must be an instance of AgentToolCall."

        if not isinstance(session_execution_context, ExecutionContext):
            return None, "session_execution_context must be an authoritative ExecutionContext instance."

        if not isinstance(session_binding, AuthorizedSessionExecutionBinding):
            return None, "session_binding must be an authoritative AuthorizedSessionExecutionBinding instance."

        if not isinstance(authority_signer, AuthoritySignerProtocol):
            return None, "authority_signer must implement AuthoritySignerProtocol."

        # 2. Cryptographic Authority Signature Verification (Ed25519)
        if not verify_authorized_session_binding(session_binding, authority_signer):
            return None, "AUTHORITY_SIGNATURE_INVALID: AuthorizedSessionExecutionBinding cryptographic signature is invalid or untrusted."

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

        if not sorted_caps:
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
