"""Non-authoritative reference scaffold operating and proposal loop.

Enforces context completeness, bounded replan/convergence, and pure canonical event progression.
Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

from typing import Any, Optional

from sclass_semantics_v6_0_1 import (
    ActorIdentity,
    Digest,
    FrozenMap,
    ObligationStatus,
    RequestedEffect,
    ResourceBudget,
    UtcInstant,
    WorkerContract,
    WorkProposal,
    canonical_current_state_binding,
    digest,
)
from sclass.reference_impl.verification import ReferenceVerificationProvider


def fmap(items=()):
    return FrozenMap.from_items(items)


class ReferenceOperatingLoop:
    """Non-authoritative reference scaffold D8 operating and proposal loop.

    Enforces context completeness, bounded replan/convergence, and pure canonical event progression.
    A6.2: Removes fabricated observations, synthetic successful process results, and default-pass behavior.
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
            proposals.append(prop_id)

            # A6.2 fail-closed: If no real worker or verification capability is provided,
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

            binding = canonical_current_state_binding(state, 1, "lineage-default")
            req_budget = ResourceBudget(1, 1, 0, 100, 0, 1, 1, 0, 0, 10, 1)
            effect = RequestedEffect(
                filesystem=(),
                network=(),
                subprocess=(),
                environment=fmap(),
                modifications=(),
                claims=(),
                requested_budget=req_budget,
            )
            req_content = (
                current_obl.obligation_id,
                getattr(current_obl, "requirement_id", "req-1"),
            )
            req_content_digest = digest("sclass/request-content/v1", req_content)
            ctx_digest = digest(
                "sclass/context/v1",
                (state.workspace_id, binding.objective_revision, current_obl.obligation_id),
            )

            proposal = WorkProposal(
                proposal_id=prop_id,
                node_id=current_obl.obligation_id,
                request_content_digest=req_content_digest,
                state_binding=binding,
                context_digest=ctx_digest,
                requested_effect=effect,
            )

            obs = observation_provider(proposal)
            if obs is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_missing",
                }

            step = getattr(current_obl, "verification_step", None)
            v_res = self.verification_provider.verify(current_obl, step, obs)
            from sclass_semantics_v6_0_1 import VerificationStatus
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


CanonicalOperatingLoop = ReferenceOperatingLoop
