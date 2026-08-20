"""
S-Class EOS V11.2 - D5 Main Controller Orchestrator (§8.1, §8.3, CORE-05, CORE-25).
Orchestrates the 5-stage lifecycle:
PRE_VALIDATE -> PRE_AUTHORIZE -> (IMMUTABLE DECISION) -> PRE_EXECUTE -> (ADMISSION & D2 NONCE CONSUMPTION) -> (D6 EXECUTION) -> POST_EXECUTE -> POST_OBSERVE.
"Planner proposes. Controller disposes."
Enforces:
1. Controller holds the ONLY token minting and admission signing paths.
2. PRE_AUTHORIZE failure never mints execution tokens.
3. ExecutionToken admission/consumption occurs BEFORE D6 execution.
4. ExecutionAdmissionResult is deeply immutable, signed by Authority, and binds:
   token_id, execution_nonce, obligation_id, source_sha, policy_version, decision_id, admitted_at.
5. complete_execution() verifies that every binding field matches the supplied ExecutionToken,
   verifies admission signature, and atomically reserves completion nonce in D2 durable store (CORE-25).
6. Admission lifecycle: completed admission cannot be reused. Controller restart preserves state via D2.
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
    ExecutionToken,
    ExecutionAdmissionResult,
    _mint_execution_token,
    _build_admission_payload,
    _compute_admission_canonical_bytes,
    verify_and_consume_execution_token,
    verify_execution_token_signature,
    verify_admission_signature,
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

        # Precondition Evaluation -> Creates IMMUTABLE AuthorizationDecision (evaluating active D3 policy)
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

        # Controller holds the ONLY issuance path, binding decision_id
        token = _mint_execution_token(
            token_id=f"TOK-{uuid.uuid4().hex[:12].upper()}",
            decision_id=decision.decision_id,
            obligation_id=proposal.obligation_id,
            proposal_id=proposal.proposal_id,
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
        current_time_iso: str,
        signer_identity: str = "Gate3AuthoritativeVerifier",
    ) -> ExecutionAdmissionResult:
        """Admits an ExecutionToken BEFORE D6 execution by verifying bindings, time bounds, and reserving nonce in D2 store.
        
        Issues an immutable, Authority-signed ExecutionAdmissionResult bound to all token parameters.
        """
        if not isinstance(token, ExecutionToken):
            return ExecutionAdmissionResult(
                token_id="UNKNOWN",
                execution_nonce="UNKNOWN",
                obligation_id="UNKNOWN",
                source_sha="0" * 40,
                policy_version=1,
                decision_id="UNKNOWN",
                admitted_at=current_time_iso,
                is_admitted=False,
                error_message="Invalid ExecutionToken provided.",
            )

        is_token_valid = verify_and_consume_execution_token(
            token=token,
            expected_obligation_id=expected_obligation_id,
            expected_source_sha=expected_source_sha,
            expected_policy_version=expected_policy_version,
            current_time_iso=current_time_iso,
            authority_signer=self._authority_signer,
            nonce_store=self._nonce_store,
        )

        if not is_token_valid:
            return ExecutionAdmissionResult(
                token_id=token.token_id,
                execution_nonce=token.execution_nonce,
                obligation_id=token.obligation_id,
                source_sha=token.source_sha,
                policy_version=token.policy_version,
                decision_id=token.decision_id,
                admitted_at=current_time_iso,
                is_admitted=False,
                error_message="Execution token verification or single-use nonce reservation failed.",
            )

        # Mint authentic Ed25519-signed ExecutionAdmissionResult via D3 Authority
        admission_payload = _build_admission_payload(
            token_id=token.token_id,
            execution_nonce=token.execution_nonce,
            obligation_id=token.obligation_id,
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
            source_sha=token.source_sha,
            policy_version=token.policy_version,
            decision_id=token.decision_id,
            admitted_at=current_time_iso,
            is_admitted=True,
            signature=authority_sig,
        )

    def complete_execution(
        self,
        token: ExecutionToken,
        admission: ExecutionAdmissionResult,
        execution_result: Optional[Mapping[str, Any]] = None,
    ) -> ExecutionCompletionResult:
        """Processes execution completion AFTER D6 execution through POST_EXECUTE -> POST_OBSERVE hooks.
        
        Strictly verifies:
        1. Valid ExecutionToken and ExecutionAdmissionResult instances.
        2. Admission was granted (is_admitted is True).
        3. ALL binding fields in admission match the supplied token:
           token_id, execution_nonce, obligation_id, source_sha, policy_version, decision_id.
        4. Cryptographic signatures of both token and admission are valid.
        5. Atomic single-use completion reservation in D2 durable store (prevents repeated completion).
        """
        if not token or not isinstance(token, ExecutionToken):
            return ExecutionCompletionResult(
                token_id="UNKNOWN",
                is_valid_execution=False,
                error_message="Invalid ExecutionToken.",
            )

        if not admission or not isinstance(admission, ExecutionAdmissionResult) or not admission.is_admitted:
            return ExecutionCompletionResult(
                token_id=token.token_id,
                is_valid_execution=False,
                error_message="Execution was not admitted prior to completion.",
            )

        # Complete Binding Verification: Every field in admission MUST match token
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

        # Atomic D2 Durable Completion Reservation (Single-Use Lifecycle: prevents repeated/replayed completion)
        try:
            completed_reserved = self._nonce_store.reserve_nonce(f"COMPLETE:{token.execution_nonce}")
            if not completed_reserved:
                return ExecutionCompletionResult(
                    token_id=token.token_id,
                    is_valid_execution=False,
                    error_message="Execution completion already consumed (repeated completion rejected).",
                )
        except Exception:
            return ExecutionCompletionResult(
                token_id=token.token_id,
                is_valid_execution=False,
                error_message="Durable storage failure during completion.",
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
            return ExecutionCompletionResult(
                token_id=token.token_id,
                is_valid_execution=False,
                error_message=post_obs_res.error_message or "POST_OBSERVE hook rejected observation",
            )

        return ExecutionCompletionResult(
            token_id=token.token_id,
            is_valid_execution=True,
            observation_payload=execution_result,
        )
