"""Non-authoritative reference scaffold operating and proposal loop.

Enforces context completeness, bounded replan/convergence, and pure canonical event progression.
Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

import types
from typing import Any, Mapping, Optional

from sclass_semantics_v6_0_1 import (
    ActorIdentity,
    AuthorizationDecision,
    AuthorizationLease,
    AuthorizationLeaseClaims,
    AuthorizationState,
    AuthorizedWorkRequest,
    FrozenMap,
    ObligationStatus,
    SignatureBlock,
    UtcInstant,
    VerificationStatus,
    WorkerClaimStatus,
    WorkerContract,
    WorkProposal,
)
from sclass_runtime_v6_0_1 import (
    KeyStatus,
    SignatureVerificationResult,
    SQLiteKeyDirectory,
    _now,
    authorization_binding_digest,
    authorization_lease_signature_message,
)
from sclass.reference_impl.verification import ReferenceVerificationProvider
from sclass.reference_impl.worker import is_work_result_admissible


def fmap(items=()):
    return FrozenMap.from_items(items)


class ReferenceOperatingLoop:
    """Non-authoritative reference scaffold D8 operating and proposal loop.

    Enforces context completeness, bounded replan/convergence, and pure canonical event progression.
    A6.2 / R1-F5:
      - Does NOT manufacture AuthorizationLeaseClaims, AuthorizationLease, ExecutionLease, or SignatureBlock.
      - Requires genuine caller-supplied AuthorizedWorkRequest; fails closed when omitted or invalid.
      - Enforces WorkResult admissibility at the boundary before accepting CLAIMED_COMPLETE.
      - Disallows 1-argument observation-provider path; observation provider must receive (proposal, worker_result).
      - Enforces mandatory observation binding across request_id, execution_attempt_id, execution_generation,
        worker_identity, and worker_result_digest / output_digest (missing fields fail closed).
      - Enforces genuine Ed25519 authorization lease verification against SQLiteKeyDirectory, active key status,
        validity window, canonical authorization decisions in state, and authorization binding digests.
    """

    def __init__(
        self,
        store: Any,
        verification_provider: Optional[ReferenceVerificationProvider] = None,
        max_iterations: int = 10,
        key_directory: Optional[Any] = None,
    ):
        self.store = store
        self.verification_provider = verification_provider or ReferenceVerificationProvider()
        self.max_iterations = max_iterations
        self.key_directory = key_directory

    def run_cycle(
        self,
        workspace_id: str,
        actor: ActorIdentity,
        worker: Optional[WorkerContract] = None,
        observation_provider: Optional[Any] = None,
        authorized_request: Optional[AuthorizedWorkRequest] = None,
        authorized_requests: Optional[Any] = None,
        key_directory: Optional[Any] = None,
        now: Optional[UtcInstant] = None,
    ) -> dict:
        iterations = 0
        proposals = []
        satisfied = []

        if self.max_iterations <= 0:
            return {
                "status": "BOUND_EXCEEDED",
                "iterations": 0,
                "proposals": (),
                "satisfied": (),
                "error": "max_iterations_exceeded",
            }

        while iterations < self.max_iterations:
            iterations += 1
            state = self.store._load_canonical_state(workspace_id)

            if not state.obligations or not getattr(state.obligations, "_obligations", None):
                return {
                    "status": "CONVERGED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": None,
                }

            unsatisfied = [
                obl
                for obl in state.obligations._obligations.values()
                if obl.status is not ObligationStatus.SATISFIED
            ]
            if not unsatisfied:
                return {
                    "status": "CONVERGED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": None,
                }

            current_obl = unsatisfied[0]
            prop_id = f"prop-{current_obl.obligation_id}-{iterations}"

            # A6.2 fail-closed: If no real worker capability is provided,
            # never fabricate synthetic observations or claim convergence.
            if worker is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_worker_capability",
                }

            # A6.2 fail-closed: Missing observation capture capability produces IN_DOUBT.
            # Never fabricate synthetic ObservationRecord with default pass results.
            if observation_provider is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_observation_capture_capability",
                }

            # R1-F5 fail-closed: Loop must NOT manufacture authorization (AuthorizationLeaseClaims,
            # AuthorizationLease, ExecutionLease, SignatureBlock). Accept only genuine caller-supplied
            # AuthorizedWorkRequest or authority material produced by real authorization path.
            req = None
            if authorized_request is not None:
                if not isinstance(authorized_request, AuthorizedWorkRequest):
                    return {
                        "status": "ESCALATED",
                        "iterations": iterations,
                        "proposals": tuple(proposals),
                        "satisfied": tuple(satisfied),
                        "error": "invalid_authorized_work_request_type",
                    }
                req = authorized_request
            elif authorized_requests is not None:
                if callable(authorized_requests):
                    try:
                        req = authorized_requests(current_obl)
                    except Exception as e:
                        return {
                            "status": "ESCALATED",
                            "iterations": iterations,
                            "proposals": tuple(proposals),
                            "satisfied": tuple(satisfied),
                            "error": f"authorized_requests_error: {e}",
                        }
                elif isinstance(authorized_requests, Mapping):
                    req = authorized_requests.get(current_obl.obligation_id)
                if req is not None and not isinstance(req, AuthorizedWorkRequest):
                    return {
                        "status": "ESCALATED",
                        "iterations": iterations,
                        "proposals": tuple(proposals),
                        "satisfied": tuple(satisfied),
                        "error": "invalid_authorized_work_request_type",
                    }

            if req is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_authorized_work_request",
                }

            # Check that caller-supplied request corresponds to current obligation
            if req.primary_obligation_id != current_obl.obligation_id and current_obl.obligation_id not in req.satisfies_obligation_ids:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"authorized_work_request_obligation_mismatch: {req.primary_obligation_id} != {current_obl.obligation_id}",
                }

            # R1-F5 Authority Authenticity Verification
            auth_lease = getattr(req, "authorization_lease", None)
            if auth_lease is None or not isinstance(auth_lease, AuthorizationLease):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_or_invalid_authorization_lease",
                }

            claims = getattr(auth_lease, "claims", None)
            sig = getattr(auth_lease, "signature", None)
            if claims is None or not isinstance(claims, AuthorizationLeaseClaims) or sig is None or not isinstance(sig, SignatureBlock):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "invalid_authorization_lease_structure",
                }

            # 1. Validity window check
            current_time = now if now is not None else _now()
            if not (claims.issued_at.epoch_ns <= current_time.epoch_ns < claims.expires_at.epoch_ns):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "expired_authorization_lease",
                }

            # 2. Key directory resolution and trusted key verification
            kd = (
                key_directory
                or self.key_directory
                or getattr(self.store, "key_directory", None)
                or getattr(getattr(self.store, "control_plane", None), "keys", None)
            )
            if kd is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_key_directory_for_signature_verification",
                }

            key_status = kd.status(sig.key_id, sig.trust_root, current_time)
            if key_status is KeyStatus.UNKNOWN:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"unknown_authorization_key: {sig.key_id}",
                }
            if key_status is KeyStatus.REVOKED:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"revoked_authorization_key: {sig.key_id}",
                }
            if key_status is not KeyStatus.ACTIVE:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"inactive_authorization_key_{key_status.value}: {sig.key_id}",
                }

            if claims.issuer_identity != sig.key_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "authorization_key_issuer_mismatch",
                }

            # 3. Authentic Ed25519 signature verification over canonical lease message
            lease_msg = authorization_lease_signature_message(claims)
            v_sig = kd.verify_current(sig, lease_msg, current_time)
            if v_sig is not SignatureVerificationResult.VALID:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"invalid_authorization_lease_signature: {v_sig.value}",
                }

            # 4. Canonical authorization decision in state
            auth_decisions = getattr(state, "authorization_decisions", None)
            decision = None
            if isinstance(auth_decisions, Mapping) or hasattr(auth_decisions, "get"):
                decision = auth_decisions.get(claims.decision_id)

            if decision is None or not isinstance(decision, AuthorizationDecision):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"missing_or_invalid_authorization_decision: {claims.decision_id}",
                }

            if decision.decision is not AuthorizationState.ALLOW:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"authorization_decision_not_allow: {decision.decision.value}",
                }

            proposal = getattr(req, "proposal", None)
            if proposal is not None and hasattr(proposal, "proposal_id"):
                if decision.proposal_id != proposal.proposal_id:
                    return {
                        "status": "ESCALATED",
                        "iterations": iterations,
                        "proposals": tuple(proposals),
                        "satisfied": tuple(satisfied),
                        "error": "authorization_decision_proposal_mismatch",
                    }

            ex_lease = getattr(req, "execution_lease", None)
            if ex_lease is not None and hasattr(ex_lease, "worker_identity"):
                if decision.worker_identity != ex_lease.worker_identity:
                    return {
                        "status": "ESCALATED",
                        "iterations": iterations,
                        "proposals": tuple(proposals),
                        "satisfied": tuple(satisfied),
                        "error": "authorization_worker_identity_mismatch",
                    }

            # 5. Canonical authorization binding digests
            if claims.state_binding_digest != req.state_binding_digest:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "authorization_binding_mismatch: state_binding_digest",
                }

            expected_auth_binding = authorization_binding_digest(decision, auth_lease)
            if req.authorization_binding_digest != expected_auth_binding:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "authorization_binding_mismatch: authorization_binding_digest",
                }

            proposal = getattr(req, "proposal", None)
            if proposal is not None and hasattr(proposal, "proposal_id"):
                if proposal.proposal_id not in proposals:
                    proposals.append(proposal.proposal_id)
            else:
                proposals.append(prop_id)

            # Execute worker with authentic AuthorizedWorkRequest
            try:
                worker_result = worker.execute(req)
            except Exception as e:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"worker_execution_error: {e}",
                }

            if worker_result is None or getattr(worker_result, "claim_status", None) is not WorkerClaimStatus.CLAIMED_COMPLETE:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "worker_execution_failed",
                }

            # R1-F1: Before accepting CLAIMED_COMPLETE, require the returned WorkResult
            # to pass the defined admissibility check. A result with absent measurements (None)
            # must NOT progress to observation or verification.
            if not is_work_result_admissible(worker_result):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "inadmissible_work_result_missing_metrics",
                }

            # R1-F5: Observation provider must receive proposal and genuine worker_result.
            # Do NOT allow 1-argument fallback for an execution requiring provenance binding.
            try:
                obs = observation_provider(proposal, worker_result)
            except Exception as e:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_provider_error: {e}",
                }

            if obs is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_missing",
                }

            # R1-F5: Mandatory observation provenance binding.
            # Observation must contain and match request ID, attempt ID, generation,
            # worker identity, and worker-result output digest. Missing fields fail closed.
            obs_req_id = getattr(obs, "request_id", None)
            if obs_req_id is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: request_id",
                }
            if obs_req_id != req.request_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: request_id mismatch ({obs_req_id} != {req.request_id})",
                }

            obs_attempt = getattr(obs, "execution_attempt_id", None)
            if obs_attempt is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: execution_attempt_id",
                }
            if obs_attempt != req.execution_attempt_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: execution_attempt_id mismatch ({obs_attempt} != {req.execution_attempt_id})",
                }

            obs_gen = getattr(obs, "execution_generation", None)
            if obs_gen is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: execution_generation",
                }
            if obs_gen != req.execution_generation:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: execution_generation mismatch ({obs_gen} != {req.execution_generation})",
                }

            obs_worker = getattr(obs, "worker_identity", None)
            w_identity = getattr(worker_result, "worker_identity", None)
            if obs_worker is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: worker_identity",
                }
            if not w_identity or obs_worker != w_identity:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: worker_identity mismatch ({obs_worker} != {w_identity})",
                }

            obs_result_dig = getattr(obs, "worker_result_digest", None) or getattr(obs, "output_digest", None)
            w_out_dig = getattr(worker_result, "output_digest", None)
            if obs_result_dig is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: worker_result_digest",
                }
            if not w_out_dig or obs_result_dig != w_out_dig:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: worker_result_digest mismatch ({obs_result_dig} != {w_out_dig})",
                }

            step = getattr(current_obl, "verification_step", None)
            v_res = self.verification_provider.verify(current_obl, step, obs)
            if v_res.status is not VerificationStatus.PASS:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "verification_failed",
                }

            satisfied.append(current_obl.obligation_id)
            return {
                "status": "PROGRESSING",
                "iterations": iterations,
                "proposals": tuple(proposals),
                "satisfied": tuple(satisfied),
                "error": None,
            }

        return {
            "status": "BOUND_EXCEEDED",
            "iterations": iterations,
            "proposals": tuple(proposals),
            "satisfied": tuple(satisfied),
            "error": "max_iterations_exceeded",
        }
