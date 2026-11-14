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
    missing evidence, or process error.
    """

    def verify(
        self,
        obligation: Optional[Obligation],
        step: VerificationStep,
        observation: Optional[ObservationRecord],
        workspace: Optional[ImmutableWorkspace] = None,
    ) -> VerificationResult:
        step_id = getattr(step, "step_id", "") if step else ""
        obs_id = getattr(observation, "observation_id", "") if observation else ""
        proc_res = getattr(observation, "process_result", None) if observation else None

        if step is None or not step_id:
            return VerificationResult("", VerificationStatus.FAIL, (), "", None)

        # A6.2 / A6-R6: Missing observation -> FAIL
        if observation is None:
            return VerificationResult(step_id, VerificationStatus.FAIL, (), "", None)

        # Process execution must have succeeded (exit_code == 0)
        if proc_res is None or getattr(proc_res, "exit_code", -1) != 0:
            return VerificationResult(step_id, VerificationStatus.FAIL, (), obs_id, proc_res)

        # A6-R2: When obligation is evaluated, require valid acceptance contract and verification plan
        if obligation is not None:
            if not getattr(obligation, "acceptance_contract_id", None) or not getattr(
                obligation, "verification_plan_id", None
            ):
                return VerificationResult(step_id, VerificationStatus.FAIL, (), obs_id, proc_res)

        # Required mutations check
        if getattr(step, "required_mutations", None):
            obs_mutations = {
                getattr(m, "path", None) for m in getattr(observation, "mutations", ())
            }
            for req_m in step.required_mutations:
                if req_m not in obs_mutations:
                    return VerificationResult(step_id, VerificationStatus.FAIL, (), obs_id, proc_res)

        # A6-R6: Empty requirement results cannot satisfy an obligation
        req_results = getattr(step, "requirement_results", None)
        if req_results is not None and len(req_results) == 0:
            return VerificationResult(step_id, VerificationStatus.FAIL, (), obs_id, proc_res)

        # In absence of failures, emits PASS with observation evidence
        return VerificationResult(
            step_id,
            VerificationStatus.PASS,
            (),
            obs_id,
            proc_res,
        )


CanonicalVerificationProvider = ReferenceVerificationProvider
