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
    AuthorizedWorkRequest,
    FrozenMap,
    ObligationStatus,
    VerificationStatus,
    WorkerClaimStatus,
    WorkerContract,
    WorkProposal,
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
    """

    def __init__(
        self,
        store: Any,
        verification_provider: Optional[ReferenceVerificationProvider] = None,
        max_iterations: int = 10,
    ):
        self.store = store
        self.verification_provider = verification_provider or ReferenceVerificationProvider()
        self.max_iterations = max_iterations

    def run_cycle(
        self,
        workspace_id: str,
        actor: ActorIdentity,
        worker: Optional[WorkerContract] = None,
        observation_provider: Optional[Any] = None,
        authorized_request: Optional[AuthorizedWorkRequest] = None,
        authorized_requests: Optional[Any] = None,
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
