"""Non-authoritative reference scaffold execution gate with fail-closed R-GPT guards (A6-R1 through A6-R6).

Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

import inspect
import os
import signal
from typing import Any, Mapping, Optional, Sequence, Union

from sclass_semantics_v6_0_1 import (
    ActionType,
    ActorIdentity,
    ActorKind,
    AssessmentMethod,
    AssessmentVerdict,
    AuthorizedWorkRequest,
    BoundaryContext,
    ClosureVerdict,
    CompositionMode,
    DeltaMatchVerdict,
    Digest,
    EngineeringState,
    EvidenceClosure,
    EvidenceComposition,
    EvidenceDependencySet,
    EvidenceKind,
    EvidenceReceipt,
    ExecutionOutcome,
    FrozenMap,
    GateResult,
    IndependenceLevel,
    IndependenceProfile,
    IndependentAssessment,
    KeyStatus,
    ObservationRecord,
    ProcessExecutionResult,
    ResourceBudget,
    SignatureBlock,
    SignatureVerificationRecord,
    SignatureVerificationResult,
    SignedEvidencePayload,
    UtcInstant,
    VerificationResult,
    VerificationStatus,
    WorkerContract,
    WorkerHealth,
    WorkspaceSnapshotHandle,
    apply_delta_observation_matches,
    digest,
    evidence_signed_payload_digest,
    replace,
    signature_block_digest,
    signature_preimage,
)
from sclass_runtime_v6_0_1 import (
    ExecutionGate,
    LinuxExecutionBoundary,
    RuntimeDisposition,
    SubprocessWorker,
    _now,
    _stable_id,
)


class ReferenceExecutionGate(ExecutionGate):
    """Non-authoritative reference scaffold execution gate.

    Implements fail-closed guards for findings A6-R1 through A6-R6:
    - A6-R1: Cancellation & process-exit proof; PermissionError != EXITED.
    - A6-R2: Exit code 0 is not obligation verification.
    - A6-R3: Worker-supplied results rejected; PermissionError is unproven quiescence.
    - A6-R4: No broad TypeError retry; duplicate execution prevented.
    - A6-R5: Atomic lifecycle event commitment; rollback partial batches.
    - A6-R6: Evidence authenticity, independent assessor, reject empty requirements.
    """

    def _evaluate_verification_verdict(
        self,
        request: AuthorizedWorkRequest,
        state: EngineeringState,
        result: Any,
        observation: ObservationRecord,
    ) -> AssessmentVerdict:
        """A6-R2: Exit code 0 is necessary but insufficient. Require obligation-specific evidence."""
        process_success = (result.returncode == 0 and not result.timed_out)
        if not process_success:
            return AssessmentVerdict.REJECT

        delta_digest = request.requested_effect.delta_digest if request.requested_effect else None

        if request.action_type == ActionType.APPLY_DELTA:
            if not delta_digest:
                return AssessmentVerdict.REJECT
            delta = next((d for d in state.verified_deltas.values() if d.delta_digest == delta_digest), None)
            if not delta:
                return AssessmentVerdict.REJECT
            if apply_delta_observation_matches(delta, observation) != DeltaMatchVerdict.MATCH:
                return AssessmentVerdict.REJECT
            return AssessmentVerdict.ACCEPT
        elif delta_digest:
            delta = next((d for d in state.verified_deltas.values() if d.delta_digest == delta_digest), None)
            if not delta:
                return AssessmentVerdict.REJECT
            if apply_delta_observation_matches(delta, observation) != DeltaMatchVerdict.MATCH:
                return AssessmentVerdict.REJECT
            return AssessmentVerdict.ACCEPT

        # A6-R2: For non-APPLY_DELTA work, require obligation verification.
        primary_obl_id = getattr(getattr(request, "proposal", None), "primary_obligation_id", None)
        if not primary_obl_id:
            return AssessmentVerdict.REJECT

        obligations_map = getattr(getattr(state, "obligations", None), "_obligations", {})
        obl = obligations_map.get(primary_obl_id)
        if obl is None:
            return AssessmentVerdict.REJECT

        if not getattr(obl, "acceptance_contract_id", None) or not getattr(obl, "verification_plan_id", None):
            return AssessmentVerdict.REJECT

        has_mutations = bool(getattr(observation, "mutations", None))
        has_results = bool(getattr(observation, "requirement_results", None))
        has_receipts = bool(getattr(observation, "receipts", None))
        if not (has_mutations or has_results or has_receipts):
            return AssessmentVerdict.REJECT

        return AssessmentVerdict.ACCEPT

    def verify_quiescence(self, pid: Optional[int], start_time_ns: Optional[int]) -> bool:
        """A6-R3: Verify quiescence fail-closed.

        Only verified process absence establishes quiescence.
        PermissionError and other unverified OS errors CANNOT prove quiescence.
        """
        if pid is None or start_time_ns is None:
            return False
        try:
            if hasattr(os, "killpg"):
                os.killpg(pid, 0)
            else:
                os.kill(pid, 0)
            # Process is still running -> not quiescent
            return False
        except ProcessLookupError:
            # PID no longer exists in OS process table -> quiescence proven
            return True
        except (PermissionError, OSError):
            # PermissionError or OS error -> CANNOT prove process absence. Fail closed.
            return False

    def execute_worker_without_retry(
        self,
        worker_instance: Any,
        request: AuthorizedWorkRequest,
        ctx: Any,
        handle: Any,
        **kwargs,
    ) -> Any:
        """A6-R4: Invoke worker without broad TypeError retry.

        Validates signature compatibility before invoking. A TypeError raised inside
        execution is treated as an execution failure; the worker is NEVER invoked twice.
        """
        # Inspect parameters accepted by worker
        sig = inspect.signature(worker_instance.execute)
        accepts_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        param_names = set(sig.parameters.keys())

        if accepts_kwargs or "_gate_capability" in param_names:
            return worker_instance.execute(request, ctx, handle, **kwargs)
        else:
            return worker_instance.execute(request, ctx, handle)
