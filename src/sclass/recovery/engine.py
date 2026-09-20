"""
S-Class Recovery: Evidence-Driven Bounded Convergence Kernel.
Implements the D9 recovery lifecycle:
FAILED / DRIFTED -> DIAGNOSE -> CREATE REPAIR OBLIGATION -> BOUNDED ATTEMPT -> REVERIFY -> CONVERGED / EXHAUSTED

Enforces:
1. Recovery is evidence-driven (cannot begin from textual claim).
2. Repair obligations are deterministic and distinguishable from original obligations.
3. Explicit recovery state machine with illegal transitions rejected.
4. Bounded retries: monotonic attempt count, durable across process restarts, exhaustion fails closed.
5. Convergence is verification, not optimism.
6. Regression protection: preserves previously accepted unaffected obligations.
7. Durable, fail-closed recovery persistence.
8. Idempotency against replayed transitions.
"""

from __future__ import annotations
import os
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Union

from sclass.recovery.models import (
    RecoveryState,
    RepairObligation,
    RecoveryAttempt,
    RecoveryRecord,
    RecoveryResult,
)
from sclass.recovery.state_machine import RecoveryStateMachine
from sclass.recovery.persistence import RecoveryPersistence
from sclass.core.errors import (
    RecoveryError,
    RecoveryStateTransitionError,
    RecoveryExhaustedError,
    RecoveryPersistenceError,
)


class RecoveryEngine:
    """Authoritative D9 recovery controller managing evidence-driven convergence cycles."""

    def __init__(
        self,
        workspace_dir: str,
        default_max_attempts: int = 3,
        persistence: Optional[RecoveryPersistence] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.default_max_attempts = max(1, int(default_max_attempts))
        self.persistence = persistence or RecoveryPersistence(self.workspace_dir)

    def get_recovery(self, recovery_id: str) -> Optional[RecoveryRecord]:
        """Loads authoritative RecoveryRecord by ID from persistent storage."""
        return self.persistence.load_recovery(recovery_id)

    def diagnose_failure(
        self,
        task_id: str,
        obligation_id: str,
        failure_evidence: Any,
        failure_classification: str = "EXECUTION_FAILURE",
        reason: str = "",
        staleness_cause: Optional[str] = None,
        max_attempts: Optional[int] = None,
        project_state_ref: str = "",
    ) -> RecoveryRecord:
        """
        Initiates an evidence-driven recovery cycle from an authoritative failure or drift condition.
        Enforces:
        - Must be evidence-driven: textual claims ("fix complete") cannot establish failure or recovery.
        - Fails closed if failure_evidence lacks authentic failure provenance.
        """
        if not task_id or not obligation_id:
            raise RecoveryError("Recovery requires non-empty task_id and obligation_id.")

        # Invariant 1: Recovery is evidence-driven
        if failure_evidence is None or isinstance(failure_evidence, str):
            raise RecoveryError(
                "Recovery is evidence-driven: cannot initiate recovery from textual statement or missing evidence. "
                "Authoritative failure evidence (VerificationResult, ObservedReceipt, or failure record) is required."
            )

        # Inspect failure evidence for authentic failure condition
        is_failure = False
        aff_claim_id = None
        aff_evidence_id = None
        ev_reason = reason

        if hasattr(failure_evidence, "is_verified"):
            if not failure_evidence.is_verified:
                is_failure = True
                ev_reason = ev_reason or getattr(failure_evidence, "reason", "")
                aff_claim_id = getattr(failure_evidence, "claim_id", None)
                aff_evidence_id = getattr(failure_evidence, "receipt_id", None)
        elif hasattr(failure_evidence, "exit_code"):
            if failure_evidence.exit_code != 0:
                is_failure = True
                aff_evidence_id = getattr(failure_evidence, "receipt_id", None)
        elif isinstance(failure_evidence, dict):
            status = str(failure_evidence.get("status", "")).upper()
            exit_code = failure_evidence.get("exit_code")
            if status in ("REJECT", "INVALID", "FAILED", "ERROR") or (exit_code is not None and exit_code != 0):
                is_failure = True
                ev_reason = ev_reason or failure_evidence.get("reason", "")
                aff_claim_id = failure_evidence.get("claim_id")
                aff_evidence_id = failure_evidence.get("receipt_id")

        if not is_failure:
            raise RecoveryError(
                "Recovery is evidence-driven: provided evidence does not represent an authoritative failure or drift condition."
            )

        recovery_id = f"recov_{task_id}_{obligation_id}"
        existing = self.persistence.load_recovery(recovery_id)
        if existing:
            # Idempotency: return existing in-progress recovery if not terminal
            if not existing.current_state.is_terminal:
                return existing

        now_iso = datetime.now(timezone.utc).isoformat()
        bound_max = max(1, int(max_attempts or self.default_max_attempts))

        record = RecoveryRecord(
            recovery_id=recovery_id,
            task_id=task_id,
            affected_obligation_id=obligation_id,
            current_state=RecoveryState.FAILED,
            attempt_number=0,
            max_attempts=bound_max,
            created_at=now_iso,
            updated_at=now_iso,
            failure_classification=failure_classification,
            reason=ev_reason,
            affected_claim_id=aff_claim_id,
            affected_evidence_id=aff_evidence_id,
            project_state_ref=project_state_ref,
            history=[{
                "event": "failure_diagnosed",
                "from_state": None,
                "to_state": RecoveryState.FAILED.value,
                "timestamp": now_iso,
                "reason": ev_reason,
            }],
        )

        # Transition FAILED -> DIAGNOSING
        RecoveryStateMachine.validate_transition(RecoveryState.FAILED, RecoveryState.DIAGNOSING)
        record.current_state = RecoveryState.DIAGNOSING
        record.history.append({
            "event": "diagnosing_started",
            "from_state": RecoveryState.FAILED.value,
            "to_state": RecoveryState.DIAGNOSING.value,
            "timestamp": now_iso,
        })

        self.persistence.save_recovery(record)
        return record

    def create_repair_obligation(
        self,
        recovery_id: str,
        target: str = "",
        reason_override: Optional[str] = None,
    ) -> RepairObligation:
        """
        Creates a deterministic repair obligation and advances the recovery state to REPAIR_REQUIRED.
        Enforces:
        - Monotonic attempt numbering.
        - Strict retry bound: exceeding max_attempts transitions to RECOVERY_EXHAUSTED and fails closed.
        - Idempotency: duplicate calls within the same attempt return the existing repair obligation.
        """
        record = self.persistence.load_recovery(recovery_id)
        if not record:
            raise RecoveryError(f"Recovery record '{recovery_id}' not found.")

        # Fail closed immediately if already exhausted
        if record.current_state == RecoveryState.RECOVERY_EXHAUSTED:
            raise RecoveryExhaustedError(
                f"Recovery attempt budget exhausted: recovery '{recovery_id}' is in terminal RECOVERY_EXHAUSTED state. Fail-closed enforced."
            )

        now_iso = datetime.now(timezone.utc).isoformat()

        # Idempotency check: if already in REPAIR_REQUIRED for this attempt
        if record.current_state == RecoveryState.REPAIR_REQUIRED and record.current_repair_obligation:
            return record.current_repair_obligation

        # Determine next attempt number
        if record.current_state == RecoveryState.DIAGNOSING:
            next_attempt = 1
        elif record.current_state in (RecoveryState.REPAIR_REQUIRED, RecoveryState.REVERIFY_REQUIRED):
            next_attempt = record.attempt_number + 1
        else:
            # Validate state transition
            RecoveryStateMachine.validate_transition(record.current_state, RecoveryState.REPAIR_REQUIRED)
            next_attempt = record.attempt_number + 1

        # Enforce attempt bound (Requirement 4)
        if next_attempt > record.max_attempts:
            # Transition to RECOVERY_EXHAUSTED
            prev_state = record.current_state
            RecoveryStateMachine.validate_transition(prev_state, RecoveryState.RECOVERY_EXHAUSTED)
            record.current_state = RecoveryState.RECOVERY_EXHAUSTED
            record.history.append({
                "event": "recovery_exhausted",
                "from_state": prev_state.value,
                "to_state": RecoveryState.RECOVERY_EXHAUSTED.value,
                "timestamp": now_iso,
                "reason": f"Maximum recovery attempts ({record.max_attempts}) exhausted.",
            })
            self.persistence.save_recovery(record)
            raise RecoveryExhaustedError(
                f"Recovery attempt budget exhausted: attempt {next_attempt} exceeds maximum {record.max_attempts}. "
                f"Recovery '{recovery_id}' is now RECOVERY_EXHAUSTED. Fail-closed enforced."
            )

        # Validate transition to REPAIR_REQUIRED
        RecoveryStateMachine.validate_transition(record.current_state, RecoveryState.REPAIR_REQUIRED)

        # Construct deterministic repair obligation distinguishable from original
        repair_ob_id = f"ob_repair_{record.affected_obligation_id}_attempt_{next_attempt}"
        repair_target = target or (record.current_repair_obligation.target if record.current_repair_obligation else "")

        repair_ob = RepairObligation(
            obligation_id=repair_ob_id,
            task_id=record.task_id,
            affected_obligation_id=record.affected_obligation_id,
            affected_claim_id=record.affected_claim_id,
            affected_evidence_id=record.affected_evidence_id,
            failure_classification=record.failure_classification,
            reason=reason_override or record.reason,
            attempt_number=next_attempt,
            project_state_ref=record.project_state_ref,
            target=repair_target,
            created_at=now_iso,
        )

        prev_state = record.current_state
        record.attempt_number = next_attempt
        record.current_state = RecoveryState.REPAIR_REQUIRED
        record.current_repair_obligation = repair_ob
        record.history.append({
            "event": "repair_obligation_created",
            "from_state": prev_state.value,
            "to_state": RecoveryState.REPAIR_REQUIRED.value,
            "repair_obligation_id": repair_ob_id,
            "attempt_number": next_attempt,
            "timestamp": now_iso,
        })

        self.persistence.save_recovery(record)
        return repair_ob

    def start_repair(self, recovery_id: str) -> RepairObligation:
        """
        Transitions recovery state from REPAIR_REQUIRED to REPAIR_IN_PROGRESS.
        Rejects illegal state transitions.
        """
        record = self.persistence.load_recovery(recovery_id)
        if not record:
            raise RecoveryError(f"Recovery record '{recovery_id}' not found.")

        # Idempotency
        if record.current_state == RecoveryState.REPAIR_IN_PROGRESS:
            return record.current_repair_obligation

        RecoveryStateMachine.validate_transition(record.current_state, RecoveryState.REPAIR_IN_PROGRESS)

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_state = record.current_state
        record.current_state = RecoveryState.REPAIR_IN_PROGRESS
        record.history.append({
            "event": "repair_in_progress",
            "from_state": prev_state.value,
            "to_state": RecoveryState.REPAIR_IN_PROGRESS.value,
            "timestamp": now_iso,
        })

        self.persistence.save_recovery(record)
        return record.current_repair_obligation

    def submit_for_reverification(self, recovery_id: str) -> None:
        """
        Transitions recovery state from REPAIR_IN_PROGRESS to REVERIFY_REQUIRED.
        Rejects illegal state transitions.
        """
        record = self.persistence.load_recovery(recovery_id)
        if not record:
            raise RecoveryError(f"Recovery record '{recovery_id}' not found.")

        # Idempotency
        if record.current_state == RecoveryState.REVERIFY_REQUIRED:
            return

        RecoveryStateMachine.validate_transition(record.current_state, RecoveryState.REVERIFY_REQUIRED)

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_state = record.current_state
        record.current_state = RecoveryState.REVERIFY_REQUIRED
        record.history.append({
            "event": "reverify_required",
            "from_state": prev_state.value,
            "to_state": RecoveryState.REVERIFY_REQUIRED.value,
            "timestamp": now_iso,
        })

        self.persistence.save_recovery(record)

    def evaluate_convergence(
        self,
        recovery_id: str,
        verification_result: Any,
        evidence: Optional[Any] = None,
        known_accepted_obligations: Optional[List[str]] = None,
        invalidated_obligations: Optional[List[str]] = None,
    ) -> RecoveryResult:
        """
        Evaluates re-verification evidence against the recovery state machine.
        Enforces:
        - Convergence is verification, not optimism: requires authentic positive verification verdict.
        - Stale or failed verification returns to REPAIR_REQUIRED (or RECOVERY_EXHAUSTED if attempt limit reached).
        - Regression protection: preserves previously accepted unaffected obligations.
        """
        record = self.persistence.load_recovery(recovery_id)
        if not record:
            raise RecoveryError(f"Recovery record '{recovery_id}' not found.")

        now_iso = datetime.now(timezone.utc).isoformat()

        # Idempotency: if already CONVERGED
        if record.current_state == RecoveryState.CONVERGED:
            return RecoveryResult(
                recovery_id=record.recovery_id,
                status=record.current_state.value,
                is_converged=True,
                repaired_obligation_id=record.affected_obligation_id,
                preserved_obligation_ids=tuple(known_accepted_obligations or []),
                invalidated_obligation_ids=tuple(invalidated_obligations or []),
                attempts_used=record.attempt_number,
                max_attempts=record.max_attempts,
                final_evidence_id=record.affected_evidence_id,
                reason="Recovery already converged.",
            )

        # Must be in REVERIFY_REQUIRED to evaluate convergence
        if record.current_state != RecoveryState.REVERIFY_REQUIRED:
            RecoveryStateMachine.validate_transition(record.current_state, RecoveryState.CONVERGED)

        # Requirement 5: Convergence is verification, not optimism
        if verification_result is None or isinstance(verification_result, str):
            raise RecoveryError(
                "Convergence is verification, not optimism: cannot establish convergence from textual statement or missing verification."
            )

        is_verified = False
        verif_reason = ""
        evidence_id = getattr(evidence, "receipt_id", None) if evidence else None

        if hasattr(verification_result, "is_verified"):
            is_verified = bool(verification_result.is_verified)
            verif_reason = getattr(verification_result, "reason", "")
            evidence_id = evidence_id or getattr(verification_result, "receipt_id", None)
        elif hasattr(verification_result, "status"):
            is_verified = (str(verification_result.status).upper() in ("ACCEPT", "PASS"))
            verif_reason = getattr(verification_result, "reason", "")
        elif isinstance(verification_result, dict):
            status = str(verification_result.get("status", "")).upper()
            is_verified = (status in ("ACCEPT", "PASS"))
            verif_reason = verification_result.get("reason", "")
            evidence_id = evidence_id or verification_result.get("receipt_id")

        # Check evidence staleness
        if hasattr(verification_result, "invalidation_reason") and verification_result.invalidation_reason:
            is_verified = False
            verif_reason = f"Evidence invalidated: {verification_result.invalidation_reason}"

        if hasattr(evidence, "is_stale") and evidence.is_stale:
            is_verified = False
            verif_reason = "Evidence is stale: subsequent workspace modifications detected."

        prev_state = record.current_state

        if is_verified:
            # Transition REVERIFY_REQUIRED -> CONVERGED
            RecoveryStateMachine.validate_transition(prev_state, RecoveryState.CONVERGED)
            record.current_state = RecoveryState.CONVERGED
            record.affected_evidence_id = evidence_id
            record.resulting_verification = {
                "verified_at": now_iso,
                "evidence_id": evidence_id,
                "reason": verif_reason,
            }
            record.history.append({
                "event": "convergence_established",
                "from_state": prev_state.value,
                "to_state": RecoveryState.CONVERGED.value,
                "evidence_id": evidence_id,
                "timestamp": now_iso,
            })
            self.persistence.save_recovery(record)

            # Regression protection: distinguish repaired, preserved, and invalidated
            known = list(known_accepted_obligations or [])
            inval = list(invalidated_obligations or [])
            # Invariant: unaffected accepted obligations remain preserved
            preserved = [ob for ob in known if ob not in inval and ob != record.affected_obligation_id]

            return RecoveryResult(
                recovery_id=record.recovery_id,
                status=RecoveryState.CONVERGED.value,
                is_converged=True,
                repaired_obligation_id=record.affected_obligation_id,
                preserved_obligation_ids=tuple(preserved),
                invalidated_obligation_ids=tuple(inval),
                attempts_used=record.attempt_number,
                max_attempts=record.max_attempts,
                final_evidence_id=evidence_id,
                reason=verif_reason or "Obligation independently reverified and converged.",
            )
        else:
            # Re-verification failed or is stale
            # Check attempt bound to transition to REPAIR_REQUIRED or RECOVERY_EXHAUSTED
            if record.attempt_number >= record.max_attempts:
                # Exhausted
                RecoveryStateMachine.validate_transition(prev_state, RecoveryState.RECOVERY_EXHAUSTED)
                record.current_state = RecoveryState.RECOVERY_EXHAUSTED
                record.history.append({
                    "event": "reverification_failed_exhausted",
                    "from_state": prev_state.value,
                    "to_state": RecoveryState.RECOVERY_EXHAUSTED.value,
                    "reason": verif_reason or "Re-verification failed and attempt limit reached.",
                    "timestamp": now_iso,
                })
                self.persistence.save_recovery(record)

                return RecoveryResult(
                    recovery_id=record.recovery_id,
                    status=RecoveryState.RECOVERY_EXHAUSTED.value,
                    is_converged=False,
                    repaired_obligation_id=record.affected_obligation_id,
                    preserved_obligation_ids=tuple(known_accepted_obligations or []),
                    invalidated_obligation_ids=tuple(invalidated_obligations or []),
                    attempts_used=record.attempt_number,
                    max_attempts=record.max_attempts,
                    final_evidence_id=evidence_id,
                    reason=f"Recovery exhausted after {record.attempt_number} attempts: {verif_reason}",
                )
            else:
                # Return to REPAIR_REQUIRED
                RecoveryStateMachine.validate_transition(prev_state, RecoveryState.REPAIR_REQUIRED)
                record.current_state = RecoveryState.REPAIR_REQUIRED
                record.current_repair_obligation = None
                record.history.append({
                    "event": "reverification_failed_retry",
                    "from_state": prev_state.value,
                    "to_state": RecoveryState.REPAIR_REQUIRED.value,
                    "reason": verif_reason or "Re-verification failed, retry required.",
                    "timestamp": now_iso,
                })
                self.persistence.save_recovery(record)

                return RecoveryResult(
                    recovery_id=record.recovery_id,
                    status=RecoveryState.REPAIR_REQUIRED.value,
                    is_converged=False,
                    repaired_obligation_id=record.affected_obligation_id,
                    preserved_obligation_ids=tuple(known_accepted_obligations or []),
                    invalidated_obligation_ids=tuple(invalidated_obligations or []),
                    attempts_used=record.attempt_number,
                    max_attempts=record.max_attempts,
                    final_evidence_id=evidence_id,
                    reason=f"Re-verification failed: {verif_reason}. Fresh repair attempt required.",
                )
