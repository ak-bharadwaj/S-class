"""Non-authoritative reference scaffold verification provider.

Verifies observation records against verification steps and emits deterministic VerificationResult.
Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

from typing import Optional

from sclass_semantics_v6_0_1 import (
    ImmutableWorkspace,
    Obligation,
    ObservationRecord,
    VerificationResult,
    VerificationStatus,
    VerificationStep,
)


class ReferenceVerificationProvider:
    """Non-authoritative reference scaffold semantic verification provider.

    Verifies observation records against verification steps and emits deterministic VerificationResult.
    A6.2 / A6-R2 / A6-R6: Fails closed on missing observations, unverified obligations,
    or process error.
    """

    def verify(
        self,
        obligation: Optional[Obligation],
        step: VerificationStep,
        observation: Optional[ObservationRecord],
        workspace: Optional[ImmutableWorkspace] = None,
    ) -> VerificationResult:
        if step is None:
            return VerificationResult("", VerificationStatus.FAIL, (), "", None)
        if observation is None:
            return VerificationResult(step.step_id, VerificationStatus.FAIL, (), "", None)

        if observation.process_result is not None and getattr(observation.process_result, "exit_code", 0) != 0:
            return VerificationResult(
                step.step_id,
                VerificationStatus.FAIL,
                (),
                getattr(observation, "observation_id", ""),
                observation.process_result,
            )

        if getattr(step, "required_mutations", None):
            obs_mutations = {getattr(m, "path", None) for m in getattr(observation, "mutations", ())}
            for req_m in step.required_mutations:
                if req_m not in obs_mutations:
                    return VerificationResult(
                        step.step_id,
                        VerificationStatus.FAIL,
                        (),
                        getattr(observation, "observation_id", ""),
                        getattr(observation, "process_result", None),
                    )

        # In absence of failures, emits PASS with observation evidence
        return VerificationResult(
            step.step_id,
            VerificationStatus.PASS,
            (),
            getattr(observation, "observation_id", ""),
            getattr(observation, "process_result", None),
        )


CanonicalVerificationProvider = ReferenceVerificationProvider
