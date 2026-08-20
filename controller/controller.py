"""
S-Class EOS V11.2 - D5 Main Controller Orchestrator (§8.1, §8.3, CORE-05, CORE-25).
Orchestrates the 5-stage lifecycle:
PRE_VALIDATE -> PRE_AUTHORIZE -> (IMMUTABLE DECISION) -> PRE_EXECUTE -> (ADMISSION & D2 NONCE CONSUMPTION -> ENVELOPE) -> (D6 EXECUTION) -> POST_EXECUTE -> POST_OBSERVE -> COMPLETION_FINALIZED.
"Planner proposes. Controller disposes."
Enforces:
1. Mandatory ExecutionEnvelope delivery to D6 containing (Token, Admission, ActionBinding, ExecutionContext).
2. Exact Action & Context Binding (token.action_digest == admission.action_digest == action_binding.action_digest).
3. Controller holds the ONLY token minting and admission signing paths.
4. Transactional Admission: generates and verifies signed admission artifact before atomic reservation.
5. Explicit Durable Completion Lifecycle in D2:
   COMPLETION_STARTED -> POST_EXECUTE -> POST_OBSERVE -> COMPLETION_FINALIZED (or COMPLETION_FAILED).
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Optional, Sequence, Any
from domain.models import Obligation, Policy
from events.store import D2NonceStore
from policy.models import AuthoritySignerProtocol
from controller.authorization import ActionProposal, AuthorizationDecision, AuthorizationStatus, AuthorizationEngine
from controller.hooks import LifecycleStage, HookContext, HookResult, LifecyclePipeline
from controller.token import (
    ActionBinding,
    ExecutionContext,
    ExecutionToken,
    ExecutionAdmissionResult,
    ExecutionEnvelope,
    _mint_execution_token,
    _build_admission_payload,
    _compute_admission_canonical_bytes,
    verify_and_consume_execution_token,
    verify_execution_token_signature,
    verify_admission_signature,
    verify_execution_envelope,
)


@dataclass(frozen=True)
class ControllerDispatchResult:
    """Result of submitting an ActionProposal to the Controller."""
    proposal_id: str
    decision: AuthorizationDecision
    execution_token: Optional[ExecutionToken] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ExecutionCompletionResult:
    """Result of completing an authorized action execution."""
    token_id: str
    is_valid_execution: bool
    error_message: Optional[str] = None
    observation_payload: Optional[Mapping[str, Any]] = None


class SClassController:
    """Authoritative D5 Controller governing action proposal lifecycle & execution authorization."""

    def __init__(
        self,
        authority_signer: AuthoritySignerProtocol,
        pipeline: Optional[LifecyclePipeline] = None,
        nonce_store: Optional[D2NonceStore] = None,
    ):
        if not isinstance(authority_signer, AuthoritySignerProtocol):
            raise TypeError("authority_signer must implement AuthoritySignerProtocol.")
        self._authority_signer = authority_signer
        self._pipeline = pipeline or LifecyclePipeline()
        self._nonce_store = nonce_store or D2NonceStore()

    def submit_proposal(
        self,
        proposal: ActionProposal,
        obligations: Mapping[str, Obligation],
        policies: Mapping[str, Policy],
        source_sha: str,
        policy_version: int,
        evaluated_at: str,
        expires_at: str,
        budget_remaining: float = 100.0,
        allowed_action_types: Optional[Sequence[str]] = None,
    ) -> ControllerDispatchResult:
        """Processes an ActionProposal through PRE_VALIDATE -> PRE_AUTHORIZE -> PRE_EXECUTE."""
        if not isinstance(proposal, ActionProposal):
            raise TypeError("proposal must be an ActionProposal instance.")
        if not evaluated_at or not expires_at:
            raise ValueError("evaluated_at and expires_at timestamps are required.")

        # Stage 1: PRE_VALIDATE Hook
        pre_val_ctx = HookContext(
            stage=LifecycleStage.PRE_VALIDATE,
            proposal_id=proposal.proposal_id,
            obligation_id=proposal.obligation_id,
            action_type=proposal.action_type,
            target=proposal.target,
            source_sha=source_sha,
        )
        pre_val_res = self._pipeline.run_stage(LifecycleStage.PRE_VALIDATE, pre_val_ctx)
        if not pre_val_res.proceed:
            decision = AuthorizationDecision(
                decision_id=f"DEC-{uuid.uuid4().hex[:8]}",
                proposal_id=proposal.proposal_id,
                obligation_id=proposal.obligation_id,
                action_digest=proposal.action_digest,
                context_digest=proposal.context_digest,
                status=AuthorizationStatus.REJECTED,
                rejection_reasons=(pre_val_res.error_message or "PRE_VALIDATE hook failed closed",),
                evaluated_at=evaluated_at,
                source_sha=source_sha,
                policy_version=policy_version,
            )
            return ControllerDispatchResult(
                proposal_id=proposal.proposal_id,
                decision=decision,
                error_message=pre_val_res.error_message,
            )

        # Stage 2: PRE_AUTHORIZE Hook & Precondition Evaluation
        pre_auth_ctx = HookContext(
            stage=LifecycleStage.PRE_AUTHORIZE,
            proposal_id=proposal.proposal_id,
            obligation_id=proposal.obligation_id,
            action_type=proposal.action_type,
            target=proposal.target,
            source_sha=source_sha,
        )
        pre_auth_res = self._pipeline.run_stage(LifecycleStage.PRE_AUTHORIZE, pre_auth_ctx)
        if not pre_auth_res.proceed:
            decision = AuthorizationDecision(
                decision_id=f"DEC-{uuid.uuid4().hex[:8]}",
                proposal_id=proposal.proposal_id,
                obligation_id=proposal.obligation_id,
                action_digest=proposal.action_digest,
                context_digest=proposal.context_digest,
                status=AuthorizationStatus.REJECTED,
                rejection_reasons=(pre_auth_res.error_message or "PRE_AUTHORIZE hook failed closed",),
                evaluated_at=evaluated_at,
                source_sha=source_sha,
                policy_version=policy_version,
            )
            return ControllerDispatchResult(
                proposal_id=proposal.proposal_id,
                decision=decision,
                error_message=pre_auth_res.error_message,
            )

        # Precondition Evaluation -> Creates IMMUTABLE AuthorizationDecision
        decision = AuthorizationEngine.evaluate_proposal(
            proposal=proposal,
            obligations=obligations,
            policies=policies,
            source_sha=source_sha,
            policy_version=policy_version,
            evaluated_at=evaluated_at,
            budget_remaining=budget_remaining,
            allowed_action_types=allowed_action_types,
        )

        # If not authorized, halt immediately: no token minted
        if decision.status != AuthorizationStatus.AUTHORIZED:
            return ControllerDispatchResult(
                proposal_id=proposal.proposal_id,
                decision=decision,
            )

        # Stage 3: PRE_EXECUTE Hook & Token Issuance
        pre_exec_ctx = HookContext(
            stage=LifecycleStage.PRE_EXECUTE,
            proposal_id=proposal.proposal_id,
            obligation_id=proposal.obligation_id,
            action_type=proposal.action_type,
            target=proposal.target,
            source_sha=source_sha,
            authorization_decision=decision,
        )
        pre_exec_res = self._pipeline.run_stage(LifecycleStage.PRE_EXECUTE, pre_exec_ctx)
        if not pre_exec_res.proceed:
            return ControllerDispatchResult(
                proposal_id=proposal.proposal_id,
                decision=decision,
                error_message=pre_exec_res.error_message or "PRE_EXECUTE hook aborted execution",
            )

        # Controller holds the ONLY issuance path, strictly binding decision_id, action_digest, context_digest
        token = _mint_execution_token(
            token_id=f"TOK-{uuid.uuid4().hex[:12].upper()}",
            decision_id=decision.decision_id,
            obligation_id=proposal.obligation_id,
            proposal_id=proposal.proposal_id,
            action_digest=decision.action_digest,
            context_digest=decision.context_digest,
            source_sha=source_sha,
            policy_version=policy_version,
            issued_at=evaluated_at,
            expires_at=expires_at,
            authority_signer=self._authority_signer,
        )

        return ControllerDispatchResult(
            proposal_id=proposal.proposal_id,
            decision=decision,
            execution_token=token,
        )

    def admit_execution(
        self,
        token: ExecutionToken,
        expected_obligation_id: str,
        expected_source_sha: str,
        expected_policy_version: int,
        expected_action_binding: ActionBinding,
        expected_execution_context: ExecutionContext,
        current_time_iso: str,
        signer_identity: str = "Gate3AuthoritativeVerifier",
    ) -> ExecutionAdmissionResult:
        """Admits an ExecutionToken BEFORE D6 execution and returns signed ExecutionAdmissionResult."""
        if not isinstance(token, ExecutionToken):
            return ExecutionAdmissionResult(
                token_id="UNKNOWN",
                execution_nonce="UNKNOWN",
                obligation_id="UNKNOWN",
                action_digest="0" * 64,
                context_digest="0" * 64,
                source_sha="0" * 40,
                policy_version=1,
                decision_id="UNKNOWN",
                admitted_at=current_time_iso,
                is_admitted=False,
                error_message="Invalid ExecutionToken provided.",
            )

        if not isinstance(expected_action_binding, ActionBinding):
            return ExecutionAdmissionResult(
                token_id=token.token_id,
                execution_nonce=token.execution_nonce,
                obligation_id=token.obligation_id,
                action_digest=token.action_digest,
                context_digest=token.context_digest,
                source_sha=token.source_sha,
                policy_version=token.policy_version,
                decision_id=token.decision_id,
                admitted_at=current_time_iso,
                is_admitted=False,
                error_message="Invalid expected_action_binding provided.",
            )

        if not isinstance(expected_execution_context, ExecutionContext):
            return ExecutionAdmissionResult(
                token_id=token.token_id,
                execution_nonce=token.execution_nonce,
                obligation_id=token.obligation_id,
                action_digest=token.action_digest,
                context_digest=token.context_digest,
                source_sha=token.source_sha,
                policy_version=token.policy_version,
                decision_id=token.decision_id,
                admitted_at=current_time_iso,
                is_admitted=False,
                error_message="Invalid expected_execution_context provided.",
            )

        # 1. Verify token bindings and signature
        is_token_valid = verify_and_consume_execution_token(
            token=token,
            expected_obligation_id=expected_obligation_id,
            expected_source_sha=expected_source_sha,
            expected_policy_version=expected_policy_version,
            expected_action_digest=expected_action_binding.action_digest,
            expected_context_digest=expected_execution_context.context_digest,
            current_time_iso=current_time_iso,
            authority_signer=self._authority_signer,
            nonce_store=self._nonce_store,
        )

        if not is_token_valid:
            return ExecutionAdmissionResult(
                token_id=token.token_id,
                execution_nonce=token.execution_nonce,
                obligation_id=token.obligation_id,
                action_digest=token.action_digest,
                context_digest=token.context_digest,
                source_sha=token.source_sha,
                policy_version=token.policy_version,
                decision_id=token.decision_id,
                admitted_at=current_time_iso,
                is_admitted=False,
                error_message="Execution token verification or single-use nonce reservation failed.",
            )

        # 2. Transactional Admission: Mint authentic Ed25519-signed ExecutionAdmissionResult via D3 Authority
        admission_payload = _build_admission_payload(
            token_id=token.token_id,
            execution_nonce=token.execution_nonce,
            obligation_id=token.obligation_id,
            action_digest=token.action_digest,
            context_digest=token.context_digest,
            source_sha=token.source_sha,
            policy_version=token.policy_version,
            decision_id=token.decision_id,
            admitted_at=current_time_iso,
        )
        canonical_bytes = _compute_admission_canonical_bytes(admission_payload)
        authority_sig = self._authority_signer.sign_payload(
            canonical_bytes=canonical_bytes,
            verifier_identity=signer_identity,
            timestamp_iso=current_time_iso,
        )

        return ExecutionAdmissionResult(
            token_id=token.token_id,
            execution_nonce=token.execution_nonce,
            obligation_id=token.obligation_id,
            action_digest=token.action_digest,
            context_digest=token.context_digest,
            source_sha=token.source_sha,
            policy_version=token.policy_version,
            decision_id=token.decision_id,
            admitted_at=current_time_iso,
            is_admitted=True,
            signature=authority_sig,
        )

    def create_execution_envelope(
        self,
        token: ExecutionToken,
        admission: ExecutionAdmissionResult,
        action_binding: ActionBinding,
        execution_context: ExecutionContext,
    ) -> ExecutionEnvelope:
        """Constructs the mandatory ExecutionEnvelope delivered to D6 executor."""
        return ExecutionEnvelope(
            token=token,
            admission=admission,
            action_binding=action_binding,
            execution_context=execution_context,
        )

    def complete_execution(
        self,
        envelope: ExecutionEnvelope,
        execution_result: Optional[Mapping[str, Any]] = None,
    ) -> ExecutionCompletionResult:
        """Processes execution completion AFTER D6 execution consuming mandatory ExecutionEnvelope.
        
        Explicit D2 durable lifecycle:
        COMPLETION_STARTED -> POST_EXECUTE -> POST_OBSERVE -> COMPLETION_FINALIZED (or COMPLETION_FAILED).
        """
        if not isinstance(envelope, ExecutionEnvelope):
            return ExecutionCompletionResult(
                token_id="UNKNOWN",
                is_valid_execution=False,
                error_message="Invalid ExecutionEnvelope supplied to complete_execution.",
            )

        token = envelope.token
        admission = envelope.admission
        action_binding = envelope.action_binding
        ctx = envelope.execution_context

        if not admission.is_admitted:
            return ExecutionCompletionResult(
                token_id=token.token_id,
                is_valid_execution=False,
                error_message="Execution was not admitted prior to completion.",
            )

        # Complete Binding Verification: Every field in admission MUST match token and action_binding/context
        if not (token.action_digest == admission.action_digest == action_binding.action_digest):
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="action_digest mismatch")
        if not (token.context_digest == admission.context_digest == ctx.context_digest):
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="context_digest mismatch")
        if admission.token_id != token.token_id:
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="token_id mismatch")
        if admission.execution_nonce != token.execution_nonce:
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="execution_nonce mismatch")
        if admission.obligation_id != token.obligation_id:
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="obligation_id mismatch")
        if admission.source_sha != token.source_sha:
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="source_sha mismatch")
        if admission.policy_version != token.policy_version:
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="policy_version mismatch")
        if admission.decision_id != token.decision_id:
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="decision_id mismatch")

        # Cryptographic verification of both Token and Admission signatures
        if not verify_execution_token_signature(token, self._authority_signer):
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="Token signature invalid.")
        if not verify_admission_signature(admission, self._authority_signer):
            return ExecutionCompletionResult(token_id=token.token_id, is_valid_execution=False, error_message="Admission signature invalid.")

        # Stage A: Durable Lifecycle - COMPLETION_STARTED reservation
        try:
            started_reserved = self._nonce_store.reserve_nonce(f"COMPLETION_STARTED:{token.execution_nonce}")
            if not started_reserved:
                return ExecutionCompletionResult(
                    token_id=token.token_id,
                    is_valid_execution=False,
                    error_message="Execution completion already started or consumed (repeated completion rejected).",
                )
        except Exception:
            return ExecutionCompletionResult(
                token_id=token.token_id,
                is_valid_execution=False,
                error_message="Durable storage failure during completion start.",
            )

        # Stage 4: POST_EXECUTE Hook
        post_exec_ctx = HookContext(
            stage=LifecycleStage.POST_EXECUTE,
            proposal_id=token.proposal_id,
            obligation_id=token.obligation_id,
            action_type="EXECUTE",
            target="child_worker",
            source_sha=token.source_sha,
            execution_token=token,
            execution_result=execution_result,
        )
        post_exec_res = self._pipeline.run_stage(LifecycleStage.POST_EXECUTE, post_exec_ctx)
        if not post_exec_res.proceed:
            self._nonce_store.reserve_nonce(f"COMPLETION_FAILED:{token.execution_nonce}")
            return ExecutionCompletionResult(
                token_id=token.token_id,
                is_valid_execution=False,
                error_message=post_exec_res.error_message or "POST_EXECUTE hook rejected execution",
            )

        # Stage 5: POST_OBSERVE Hook
        post_obs_ctx = HookContext(
            stage=LifecycleStage.POST_OBSERVE,
            proposal_id=token.proposal_id,
            obligation_id=token.obligation_id,
            action_type="EXECUTE",
            target="observation_gateway",
            source_sha=token.source_sha,
            execution_token=token,
            execution_result=execution_result,
        )
        post_obs_res = self._pipeline.run_stage(LifecycleStage.POST_OBSERVE, post_obs_ctx)
        if not post_obs_res.proceed:
            self._nonce_store.reserve_nonce(f"COMPLETION_FAILED:{token.execution_nonce}")
            return ExecutionCompletionResult(
                token_id=token.token_id,
                is_valid_execution=False,
                error_message=post_obs_res.error_message or "POST_OBSERVE hook rejected observation",
            )

        # Stage B: Durable Lifecycle - COMPLETION_FINALIZED reservation
        self._nonce_store.reserve_nonce(f"COMPLETION_FINALIZED:{token.execution_nonce}")

        return ExecutionCompletionResult(
            token_id=token.token_id,
            is_valid_execution=True,
            observation_payload=execution_result,
        )
