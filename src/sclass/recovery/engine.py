"""
S-Class Recovery: Evidence-Driven Bounded Convergence Kernel.
Implements the D9 recovery lifecycle:
FAILED / DRIFTED -> DIAGNOSE -> CREATE REPAIR OBLIGATION -> BOUNDED ATTEMPT -> REVERIFY -> CONVERGED / EXHAUSTED

Enforces:
1. Canonical evidence binding: accepts only established S-Class verification/evidence authority.
2. Canonical recovery state authority: integrates with authoritative SQLite state store.
3. Durable recovery-cycle identity tied to originating failure/event.
4. Provenance preservation: parent_event_id, staleness cause, claim/evidence identity, project-state ref.
5. Strict retry bound and fail-closed exhaustion.
6. Convergence is verification, not optimism.
7. Regression protection: preserves previously accepted unaffected obligations.
8. Idempotency against duplicate transitions.
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
    RegressionAssessment,
)
from sclass.recovery.state_machine import RecoveryStateMachine
from sclass.recovery.persistence import RecoveryPersistence
from sclass.core.errors import (
    RecoveryError,
    RecoveryStateTransitionError,
    RecoveryExhaustedError,
    RecoveryPersistenceError,
)
from sclass.domain.verification import VerificationResult as DomainVerificationResult
from sclass.domain.claim import Claim
from sclass.domain.evidence import (
    EvidenceReceipt as DomainEvidenceReceipt,
    ObservedReceipt as DomainObservedReceipt,
)
from sclass.survival.models import (
    VerificationResult as SurvivalVerificationResult,
    ObservedReceipt,
    EvidenceReceipt,
    _OBSERVATION_TOKEN,
)

from sclass.state.tasks import StateRepository
from sclass.trust.ledger import LocalLedger

AUTH_VERIFICATION_CLASSES = (DomainVerificationResult, SurvivalVerificationResult)
AUTH_RECEIPT_CLASSES = (DomainObservedReceipt, DomainEvidenceReceipt, ObservedReceipt, EvidenceReceipt)


def _paths_overlap(claim_targets: set, repair_files: set) -> bool:
    """Returns True if there is any definite target overlap between claim targets and repair files."""
    if not claim_targets or not repair_files:
        return False
    if claim_targets & repair_files:
        return True
    for t in claim_targets:
        t_clean = t.replace("\\", "/").strip("/")
        for r in repair_files:
            r_clean = r.replace("\\", "/").strip("/")
            if t_clean == r_clean:
                return True
            if t_clean.endswith("/" + r_clean) or r_clean.endswith("/" + t_clean):
                return True
    return False


def _parse_iso_timestamp(ts: Any) -> Optional[datetime]:
    """Parses an ISO 8601 timestamp string into a timezone-aware UTC datetime."""
    if not ts or not isinstance(ts, str):
        return None
    s = ts.strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


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

    def _validate_ledger(self) -> LocalLedger:
        """Validates cryptographic integrity of LocalLedger. Fails closed if corrupted."""
        ledger = LocalLedger(workspace_dir=self.workspace_dir)
        is_valid, err = ledger.verify_integrity()
        if not is_valid:
            raise RecoveryError(f"Ledger integrity compromised: {err}")
        return ledger

    def _validate_canonical_receipt_provenance(
        self,
        receipt_id: str,
        expected_claim_id: Optional[str] = None,
        expected_task_id: Optional[str] = None,
        ledger: Optional[LocalLedger] = None,
        receipt_obj: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Validates that receipt is authentically committed to canonical LocalLedger OBSERVATION records.
        Binds task_id, claim_id, workspace, and receipt_hash.
        """
        if not receipt_id:
            raise RecoveryError("Missing receipt/verification provenance: receipt_id is required.")

        norm_engine_ws = os.path.normcase(os.path.abspath(self.workspace_dir))

        # Check receipt_obj workspace immediately (fail closed on workspace mismatch)
        if receipt_obj is not None:
            obj_ws = getattr(receipt_obj, "workspace", None)
            if not obj_ws:
                raise RecoveryError(
                    f"Missing workspace binding: receipt object '{receipt_id}' lacks workspace."
                )
            norm_obj_ws = os.path.normcase(os.path.abspath(str(obj_ws)))
            if norm_obj_ws != norm_engine_ws:
                raise RecoveryError(
                    f"Workspace/project mismatch: receipt workspace '{obj_ws}' does not match engine workspace '{self.workspace_dir}'."
                )

        l = ledger or self._validate_ledger()
        entries = l.read_all_entries()

        matching_entry = None
        for entry in entries:
            if entry.get("event") == "OBSERVATION":
                payload = entry.get("payload", {})
                if payload.get("receipt_id") == receipt_id:
                    matching_entry = entry
                    break

        if not matching_entry:
            raise RecoveryError(
                f"Missing authoritative receipt: receipt '{receipt_id}' not found in canonical ledger OBSERVATION records."
            )

        obs_payload = matching_entry.get("payload", {})

        # 1. Receipt Hash: mandatory in both ledger observation and receipt object
        ledger_hash = obs_payload.get("receipt_hash")
        if not ledger_hash:
            raise RecoveryError(
                f"Missing authoritative receipt hash: ledger observation for receipt '{receipt_id}' lacks receipt_hash."
            )

        if receipt_obj is not None:
            rec_hash = getattr(receipt_obj, "receipt_hash", None)
            if not rec_hash:
                raise RecoveryError(
                    f"Missing authoritative receipt hash: receipt object '{receipt_id}' lacks receipt_hash."
                )
            if rec_hash != ledger_hash:
                raise RecoveryError(
                    f"Receipt hash mismatch: object receipt_hash '{rec_hash}' does not match ledger receipt_hash '{ledger_hash}'."
                )

        # 2. Workspace Binding in ledger: fail-closed, no swallowing RecoveryError, platform-safe normalization
        obs_ws = obs_payload.get("workspace")
        if not obs_ws:
            raise RecoveryError(
                f"Missing workspace binding: ledger observation for receipt '{receipt_id}' lacks workspace."
            )
        norm_obs_ws = os.path.normcase(os.path.abspath(str(obs_ws)))
        if norm_obs_ws != norm_engine_ws:
            raise RecoveryError(
                f"Workspace/project mismatch: ledger receipt workspace '{obs_ws}' does not match engine workspace '{self.workspace_dir}'."
            )

        # 3. Task Binding: required in ledger observation and receipt object; must match expected_task_id if provided
        rec_task = obs_payload.get("task_id")
        if not rec_task:
            raise RecoveryError(
                f"Missing task binding: ledger receipt '{receipt_id}' lacks required task_id."
            )
        if expected_task_id and rec_task != expected_task_id:
            raise RecoveryError(
                f"Task mismatch: ledger receipt task_id '{rec_task}' does not match expected '{expected_task_id}'."
            )
        if receipt_obj is not None:
            obj_task = getattr(receipt_obj, "task_id", None)
            if not obj_task:
                raise RecoveryError(
                    f"Missing task binding: receipt object '{receipt_id}' lacks required task_id."
                )
            if obj_task != rec_task:
                raise RecoveryError(
                    f"Task mismatch: object task_id '{obj_task}' does not match ledger task_id '{rec_task}'."
                )

        # 4. Claim Binding: required in ledger observation and receipt object; must match expected_claim_id if provided
        rec_claim = obs_payload.get("claim_id")
        if not rec_claim:
            raise RecoveryError(
                f"Missing claim binding: ledger receipt '{receipt_id}' lacks required claim_id."
            )
        if expected_claim_id and rec_claim != expected_claim_id:
            raise RecoveryError(
                f"Claim mismatch: ledger receipt claim_id '{rec_claim}' does not match expected '{expected_claim_id}'."
            )
        if receipt_obj is not None:
            obj_claim = getattr(receipt_obj, "claim_id", None)
            if not obj_claim:
                raise RecoveryError(
                    f"Missing claim binding: receipt object '{receipt_id}' lacks required claim_id."
                )
            if obj_claim != rec_claim:
                raise RecoveryError(
                    f"Claim mismatch: object claim_id '{obj_claim}' does not match ledger claim_id '{rec_claim}'."
                )

        return obs_payload

    def _validate_canonical_verification_provenance(
        self,
        verification_result: Any,
        expected_claim_id: Optional[str] = None,
        expected_task_id: Optional[str] = None,
        expected_status: Optional[str] = None,
        ledger: Optional[LocalLedger] = None,
    ) -> None:
        """
        Validates that verification result is backed by authoritative StateRepository
        and LocalLedger records. Enforces exact binding rules.
        """
        verif_receipt_id = verification_result.receipt_id
        if not verif_receipt_id and verification_result.verification_event:
            verif_receipt_id = getattr(verification_result.verification_event, "receipt_id", None)

        if not verif_receipt_id:
            raise RecoveryError(
                "Missing receipt/verification provenance: VerificationResult lacks authoritative receipt_id."
            )

        l = ledger or self._validate_ledger()

        # 1. First validate canonical receipt provenance in LocalLedger
        obs_payload = self._validate_canonical_receipt_provenance(
            receipt_id=verif_receipt_id,
            expected_claim_id=expected_claim_id,
            expected_task_id=expected_task_id,
            ledger=l,
        )

        # 2. Check claim binding
        verif_claim_id = getattr(verification_result, "claim_id", None)
        if expected_claim_id and verif_claim_id and verif_claim_id != expected_claim_id:
            raise RecoveryError(
                f"Claim mismatch: verification claim_id '{verif_claim_id}' does not match expected '{expected_claim_id}'."
            )
        target_claim_id = expected_claim_id or verif_claim_id

        # Verification-event binding: validate event attributes before persistence checks
        if verification_result.verification_event:
            event = verification_result.verification_event
            # Bind event claim ID == recovery claim ID
            if target_claim_id and event.claim_id and event.claim_id != target_claim_id:
                raise RecoveryError(
                    f"Verification-event mismatch: event claim_id '{event.claim_id}' does not match expected '{target_claim_id}'."
                )
            # Bind event receipt ID == authoritative receipt ID
            if event.receipt_id != verif_receipt_id:
                raise RecoveryError(
                    f"Verification-event mismatch: event receipt_id '{event.receipt_id}' does not match verification receipt_id '{verif_receipt_id}'."
                )
            # Bind event result == authoritative verification status
            ev_res = str(event.result).upper()
            v_res = str(verification_result.status).upper()
            if ev_res != v_res and not (v_res in ("ACCEPT", "PASS") and ev_res in ("ACCEPT", "PASS", "CLAIM_VERIFIED")) and not (v_res in ("REJECT", "FAILED", "INVALID") and ev_res in ("REJECT", "FAILED", "INVALID")):
                raise RecoveryError(
                    f"Verification-event mismatch: event result '{event.result}' does not match verification status '{verification_result.status}'."
                )
            # Bind event receipt hash matches canonical receipt
            if obs_payload.get("receipt_hash") and event.receipt_hash:
                if event.receipt_hash != obs_payload.get("receipt_hash"):
                    raise RecoveryError(
                        f"Verification-event mismatch: event receipt_hash '{event.receipt_hash}' does not match canonical receipt_hash '{obs_payload.get('receipt_hash')}'."
                    )

        # 3. Canonical verification record lookup in StateRepository
        state_repo = StateRepository(self.workspace_dir)
        verif_rec = state_repo.get_verification(claim_id=target_claim_id, receipt_id=verif_receipt_id)

        # Check if there is any verification record for this claim with different receipt_id (receipt mismatch)
        if target_claim_id:
            claim_verifs = state_repo.list_verifications(claim_id=target_claim_id)
            if claim_verifs:
                matching_receipt_verifs = [v for v in claim_verifs if v.get("receipt_id") == verif_receipt_id]
                if not matching_receipt_verifs:
                    raise RecoveryError(
                        f"Receipt mismatch: persisted verification for claim '{target_claim_id}' expects receipt '{claim_verifs[0].get('receipt_id')}', but got '{verif_receipt_id}'."
                    )

        # Also look for verification event in LocalLedger
        all_entries = l.read_all_entries()
        verif_ledger_entries = [
            e for e in all_entries
            if e.get("event") in ("verification", "rejection", "composite_acceptance")
            and e.get("payload", {}).get("receipt_id") == verif_receipt_id
            and (not target_claim_id or e.get("payload", {}).get("claim_id") == target_claim_id)
        ]

        # Must be persisted in StateRepository OR recorded in LocalLedger
        if not verif_rec and not verif_ledger_entries:
            raise RecoveryError(
                f"Missing authoritative verification record: no canonical verification found in StateRepository or LocalLedger for claim '{target_claim_id}' and receipt '{verif_receipt_id}'."
            )

        # Verify status consistency if found in StateRepository
        if verif_rec:
            rec_status = str(verif_rec.get("status", "")).upper()
            res_status = str(verification_result.status).upper()
            if rec_status != res_status:
                raise RecoveryError(
                    f"Verification status mismatch: persisted status '{rec_status}' does not match supplied '{res_status}'."
                )
            if expected_status and rec_status != expected_status.upper():
                raise RecoveryError(
                    f"Verification status mismatch: persisted status '{rec_status}' does not match expected '{expected_status}'."
                )

        # Verify status consistency if found in LocalLedger
        if verif_ledger_entries:
            latest_entry = verif_ledger_entries[-1]
            p = latest_entry.get("payload", {})
            ledger_result = str(p.get("verification_result") or p.get("status") or p.get("decision") or "").upper()
            res_status = str(verification_result.status).upper()
            if res_status in ("ACCEPT", "PASS") and ledger_result not in ("ACCEPT", "PASS", "CLAIM_VERIFIED", "SATISFIED", "APPROVED"):
                raise RecoveryError(
                    f"Verification status mismatch: ledger verification result '{ledger_result}' does not match ACCEPT."
                )
            elif res_status in ("REJECT", "INVALID", "FAILED") and ledger_result not in ("REJECT", "INVALID", "FAILED", "REJECTION"):
                raise RecoveryError(
                    f"Verification status mismatch: ledger verification result '{ledger_result}' does not match REJECT."
                )

        # 4. Event must be part of trusted ledger/history rather than merely attached to caller object
        if verification_result.verification_event:
            event = verification_result.verification_event
            anchored_event = any(
                e.get("event") in ("verification", "rejection", "composite_acceptance")
                and (
                    e.get("payload", {}).get("event_id") == event.event_id
                    or (
                        e.get("payload", {}).get("receipt_id") == event.receipt_id
                        and e.get("payload", {}).get("claim_id") == event.claim_id
                        and (not e.get("payload", {}).get("event_id") or e.get("payload", {}).get("event_id") == event.event_id)
                    )
                )
                for e in all_entries
            )
            if not anchored_event:
                raise RecoveryError(
                    f"Unanchored verification event: event '{event.event_id}' is not anchored in trusted LocalLedger."
                )

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
        parent_event_id: Optional[str] = None,
        staleness_cause: Optional[str] = None,
        claim_id: Optional[str] = None,
        max_attempts: Optional[int] = None,
        project_state_ref: str = "",
    ) -> RecoveryRecord:
        """
        Initiates an evidence-driven recovery cycle from an authoritative failure or drift condition.
        Enforces:
        - Canonical evidence binding: accepts only established S-Class verification/evidence authority.
        - Rejects plain dicts and fabricated status-bearing objects.
        - Requires authoritative receipt/verification identity.
        - Binds failure to the affected obligation and claim.
        - Generates a durable recovery-cycle identity tied to the originating failure/event.
        - Preserves provenance without fabrication.
        """
        if not task_id or not obligation_id:
            raise RecoveryError("Recovery requires non-empty task_id and obligation_id.")

        # Invariant 1: Recovery is evidence-driven; reject textual assertions and missing evidence
        if failure_evidence is None or isinstance(failure_evidence, str):
            raise RecoveryError(
                "Recovery is evidence-driven: cannot initiate recovery from textual statement or missing evidence. "
                "Authoritative failure evidence (VerificationResult or ObservedReceipt) is required."
            )

        # Invariant 2: Reject fabricated status-bearing dicts
        if isinstance(failure_evidence, dict):
            raise RecoveryError(
                "Recovery accepts only established S-Class verification/evidence authority: plain dicts are rejected."
            )

        # Inspect failure evidence against canonical S-Class authorities
        is_failure = False
        aff_claim_id = claim_id
        aff_evidence_id = None
        ev_reason = reason
        resolved_parent_event_id = parent_event_id
        resolved_staleness_cause = staleness_cause
        resolved_project_state_ref = project_state_ref

        if isinstance(failure_evidence, AUTH_VERIFICATION_CLASSES):
            # Authoritative VerificationResult
            receipt_id = failure_evidence.receipt_id
            if not receipt_id and failure_evidence.verification_event:
                receipt_id = getattr(failure_evidence.verification_event, "receipt_id", None)

            if not receipt_id:
                raise RecoveryError(
                    "Missing receipt/verification provenance: VerificationResult lacks authoritative receipt_id."
                )

            aff_evidence_id = receipt_id

            # Bind claim
            ev_claim = getattr(failure_evidence, "claim_id", None)
            if ev_claim:
                if aff_claim_id and aff_claim_id != ev_claim:
                    raise RecoveryError(
                        f"Claim/obligation mismatch: evidence claim_id '{ev_claim}' does not match expected claim_id '{aff_claim_id}'."
                    )
                aff_claim_id = ev_claim

            # Provenance extraction (never fabricate)
            if failure_evidence.verification_event:
                if not resolved_parent_event_id:
                    resolved_parent_event_id = getattr(failure_evidence.verification_event, "event_id", None)
                if not resolved_project_state_ref:
                    resolved_project_state_ref = getattr(failure_evidence.verification_event, "repository_fingerprint", "")

            if getattr(failure_evidence, "invalidation_reason", None):
                if not resolved_staleness_cause:
                    resolved_staleness_cause = failure_evidence.invalidation_reason

            ev_reason = ev_reason or getattr(failure_evidence, "reason", "")

            # Check if this represents an authoritative failure or invalidation
            status_str = str(getattr(failure_evidence, "status", "")).upper()
            if status_str in ("REJECT", "INVALID", "FAILED", "ERROR", "INCONCLUSIVE") or not getattr(failure_evidence, "is_verified", True):
                is_failure = True

        elif isinstance(failure_evidence, AUTH_RECEIPT_CLASSES):
            # Authoritative EvidenceReceipt / ObservedReceipt
            if not failure_evidence.is_observed:
                raise RecoveryError(
                    "Forged or unobserved failure evidence: Evidence must be an authoritative ObservedReceipt with authentic observation provenance."
                )

            if not failure_evidence.receipt_id:
                raise RecoveryError(
                    "Missing receipt/verification provenance: Evidence receipt lacks authoritative receipt_id."
                )

            aff_evidence_id = failure_evidence.receipt_id

            # Check task binding
            ev_task = getattr(failure_evidence, "task_id", None)
            if ev_task and ev_task != task_id:
                raise RecoveryError(
                    f"Task mismatch: evidence task_id '{ev_task}' does not match expected task_id '{task_id}'."
                )

            # Check claim binding
            ev_claim = getattr(failure_evidence, "claim_id", None)
            if ev_claim:
                if aff_claim_id and aff_claim_id != ev_claim:
                    raise RecoveryError(
                        f"Claim/obligation mismatch: evidence claim_id '{ev_claim}' does not match expected claim_id '{aff_claim_id}'."
                    )
                aff_claim_id = ev_claim

            if not resolved_project_state_ref:
                resolved_project_state_ref = getattr(failure_evidence, "workspace_fingerprint", "")

            ev_reason = ev_reason or f"Command '{failure_evidence.command}' failed with exit code {failure_evidence.exit_code}"

            if failure_evidence.exit_code != 0:
                is_failure = True
        else:
            raise RecoveryError(
                f"Recovery accepts only established S-Class verification/evidence authority. "
                f"Received unauthoritative object of type '{type(failure_evidence).__name__}'."
            )

        if not is_failure:
            raise RecoveryError(
                "Recovery is evidence-driven: provided evidence does not represent an authoritative failure or drift condition."
            )

        # D9.1.2: Enforce failure-side canonical verification / receipt provenance
        if isinstance(failure_evidence, AUTH_VERIFICATION_CLASSES):
            self._validate_canonical_verification_provenance(
                verification_result=failure_evidence,
                expected_claim_id=aff_claim_id,
                expected_task_id=task_id,
                expected_status=failure_evidence.status,
            )
        elif isinstance(failure_evidence, AUTH_RECEIPT_CLASSES):
            self._validate_canonical_receipt_provenance(
                receipt_id=failure_evidence.receipt_id,
                expected_claim_id=aff_claim_id,
                expected_task_id=task_id,
                receipt_obj=failure_evidence,
            )

        # Durable recovery-cycle identity tied to originating failure/event
        origin_id = resolved_parent_event_id or aff_evidence_id or f"fail_{hashlib.sha256(ev_reason.encode('utf-8')).hexdigest()[:10]}"
        recovery_id = f"recov_{task_id}_{obligation_id}_{origin_id}"

        existing = self.persistence.load_recovery(recovery_id)
        if existing:
            # Idempotency: return existing recovery cycle if not terminal
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
            parent_event_id=resolved_parent_event_id,
            staleness_cause=resolved_staleness_cause,
            affected_claim_id=aff_claim_id,
            affected_evidence_id=aff_evidence_id,
            project_state_ref=resolved_project_state_ref,
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
        - Preserves provenance fields on the repair obligation.
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

        # Enforce attempt bound
        if next_attempt > record.max_attempts:
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
            staleness_cause=record.staleness_cause,
            attempt_number=next_attempt,
            parent_event_id=record.parent_event_id,
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

        if record.current_repair_obligation is None:
            raise RecoveryError("Cannot start repair without creating a repair obligation.")

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

    def determine_regression_set(
        self,
        task_id: str,
        repaired_claim_id: Optional[str] = None,
        repair_evidence: Optional[Any] = None,
    ) -> Tuple[List[Claim], List[str]]:
        """
        Determines which previously accepted claims for task_id require reassessment.
        Returns:
            (reassessment_claims, unaffected_claim_ids)

        Rules (conservative regression set determination):
        1. Definite dependency/target overlap -> reassess.
        2. Dependency information unavailable/ambiguous -> conservatively reassess.
        3. Never assume an accepted claim is unaffected merely because caller says so.
        """
        state_repo = StateRepository(self.workspace_dir)
        task_claims = state_repo.list_claims(task_id=task_id)

        # Identify previously accepted claims (excluding the claim currently under repair)
        accepted_claims: List[Claim] = []
        for c in task_claims:
            if repaired_claim_id and c.claim_id == repaired_claim_id:
                continue
            verifs = state_repo.list_verifications(claim_id=c.claim_id)
            if any(str(v.get("status", "")).upper() in ("ACCEPT", "PASS") for v in verifs):
                accepted_claims.append(c)

        if not accepted_claims:
            return [], []

        # Extract changed files from repair evidence
        repair_files: Optional[set] = None
        if repair_evidence is not None:
            raw_files = getattr(repair_evidence, "files_changed", None)
            if raw_files is None and hasattr(repair_evidence, "metadata") and isinstance(repair_evidence.metadata, dict):
                raw_files = repair_evidence.metadata.get("files_changed")
            if raw_files is not None and isinstance(raw_files, (list, tuple, set)):
                repair_files = {
                    os.path.normcase(os.path.normpath(str(f).replace("\\", "/")))
                    for f in raw_files
                    if str(f).strip()
                }

        reassessment_claims: List[Claim] = []
        unaffected_claim_ids: List[str] = []

        for claim in accepted_claims:
            # If repair files are unavailable/ambiguous (None or empty while repair evidence was not supplied or had no files):
            # Rule 2: dependency information unavailable/ambiguous -> conservatively reassess
            if repair_files is None or len(repair_files) == 0:
                reassessment_claims.append(claim)
                continue

            # Extract claim targets / scope
            claim_targets: set = set()
            if claim.target_files:
                for tf in claim.target_files:
                    claim_targets.add(os.path.normcase(os.path.normpath(str(tf).replace("\\", "/"))))
            if claim.scope:
                for p in getattr(claim.scope, "paths", ()):
                    claim_targets.add(os.path.normcase(os.path.normpath(str(p).replace("\\", "/"))))
                for tt in getattr(claim.scope, "test_targets", ()):
                    claim_targets.add(os.path.normcase(os.path.normpath(str(tt).replace("\\", "/"))))
            if claim.metadata and isinstance(claim.metadata, dict):
                for k in ("target_files", "dependencies", "paths"):
                    val = claim.metadata.get(k)
                    if isinstance(val, (list, tuple)):
                        for item in val:
                            claim_targets.add(os.path.normcase(os.path.normpath(str(item).replace("\\", "/"))))

            # If claim target information is unavailable or empty:
            # Rule 2: dependency information unavailable/ambiguous -> conservatively reassess
            if not claim_targets:
                reassessment_claims.append(claim)
                continue

            # Rule 1: definite dependency/target overlap -> reassess
            if _paths_overlap(claim_targets, repair_files):
                reassessment_claims.append(claim)
            else:
                # Canonical dependency evidence establishes no impact -> unaffected
                unaffected_claim_ids.append(claim.claim_id)

        return reassessment_claims, unaffected_claim_ids

    def assess_regression(
        self,
        recovery_id: str,
        repair_evidence: Optional[Any] = None,
        regression_verifications: Optional[List[Any]] = None,
        fail_closed: bool = True,
    ) -> RegressionAssessment:
        """
        Independently evaluates whether repairs caused regressions to previously accepted claims.
        Enforces:
        - Independent S-Class evaluation from StateRepository (not caller assertion).
        - Conservative regression set determination.
        - Strict fail-closed provenance validation (D9.1.2 / D9.1.3).
        - Fresh authoritative verification for every affected claim.
        """
        record = self.persistence.load_recovery(recovery_id)
        if not record:
            raise RecoveryError(f"Recovery record '{recovery_id}' not found.")

        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Determine regression set conservatively
        reassessment_claims, unaffected_claim_ids = self.determine_regression_set(
            task_id=record.task_id,
            repaired_claim_id=record.affected_claim_id,
            repair_evidence=repair_evidence,
        )

        # If no previously accepted claims are affected:
        if not reassessment_claims:
            assessment = RegressionAssessment(
                affected_claim_ids=(),
                reverified_claim_ids=(),
                failed_claim_ids=(),
                stale_claim_ids=(),
                regression_passed=True,
                assessment_time=now_iso,
                unaffected_claim_ids=tuple(unaffected_claim_ids),
                provenance_references={},
                reason="No previously accepted claims affected by repair.",
            )
            record.regression_assessment = assessment
            self.persistence.save_recovery(record)
            return assessment

        affected_claim_ids = tuple(c.claim_id for c in reassessment_claims)
        verif_list = list(regression_verifications or [])

        # Determine the authoritative recovery-cycle repair boundary timestamp
        repair_boundary_str = None
        for h in reversed(record.history):
            if h.get("event") in ("repair_in_progress", "repair_obligation_created"):
                repair_boundary_str = h.get("timestamp")
                break

        if not repair_boundary_str:
            if record.current_repair_obligation and record.current_repair_obligation.created_at:
                repair_boundary_str = record.current_repair_obligation.created_at
            else:
                repair_boundary_str = record.created_at

        repair_boundary_dt = _parse_iso_timestamp(repair_boundary_str)

        # Map regression verifications by claim_id
        reverified_map: Dict[str, Any] = {}
        failed_claims: List[str] = []
        stale_claims: List[str] = []
        provenance_refs: Dict[str, str] = {}

        for v in verif_list:
            if v is None:
                continue

            # Must be authoritative VerificationResult
            if not isinstance(v, AUTH_VERIFICATION_CLASSES):
                err_msg = (
                    f"Recovery accepts only established S-Class verification authority: "
                    f"regression verification must be VerificationResult, received '{type(v).__name__}'."
                )
                if fail_closed:
                    raise RecoveryError(err_msg)
                failed_claims.append("unknown_claim")
                continue

            v_claim = getattr(v, "claim_id", None)
            if not v_claim:
                err_msg = "Missing claim binding: regression verification lacks claim_id."
                if fail_closed:
                    raise RecoveryError(err_msg)
                failed_claims.append("unknown_claim")
                continue

            if v_claim not in affected_claim_ids:
                err_msg = (
                    f"Wrong claim regression result: verification claim_id '{v_claim}' "
                    f"is not in the required regression set {affected_claim_ids}."
                )
                if fail_closed:
                    raise RecoveryError(err_msg)
                failed_claims.append(v_claim)
                continue

            v_task = getattr(v, "task_id", None)
            if v_task and v_task != record.task_id:
                err_msg = (
                    f"Task mismatch: regression verification task_id '{v_task}' "
                    f"does not match expected task_id '{record.task_id}'."
                )
                if fail_closed:
                    raise RecoveryError(err_msg)
                failed_claims.append(v_claim)
                continue

            # Check staleness
            if getattr(v, "invalidation_reason", None):
                err_msg = (
                    f"Evidence is stale: regression verification for claim '{v_claim}' is invalidated: "
                    f"{v.invalidation_reason}"
                )
                if fail_closed:
                    raise RecoveryError(err_msg)
                stale_claims.append(v_claim)
                continue

            # Check status
            v_status = str(getattr(v, "status", "")).upper()
            if v_status not in ("ACCEPT", "PASS"):
                err_msg = (
                    f"Conflicting regression result: regression verification for claim '{v_claim}' "
                    f"has status '{v.status}' (reason: {getattr(v, 'reason', '')})."
                )
                if fail_closed:
                    raise RecoveryError(err_msg)
                failed_claims.append(v_claim)
                continue

            # D9.2.1: Bind verification to the current recovery-cycle repair boundary
            verif_time_str = None
            if getattr(v, "verification_event", None) and getattr(v.verification_event, "verification_time", None):
                verif_time_str = v.verification_event.verification_time
            elif getattr(v, "verification_time", None):
                verif_time_str = v.verification_time
            elif hasattr(v, "metadata") and isinstance(v.metadata, dict) and v.metadata.get("verification_time"):
                verif_time_str = v.metadata.get("verification_time")

            if not verif_time_str or not isinstance(verif_time_str, str) or not verif_time_str.strip():
                err_msg = (
                    f"Missing verification timestamp: regression verification for claim '{v_claim}' "
                    f"lacks required canonical verification timestamp."
                )
                if fail_closed:
                    raise RecoveryError(err_msg)
                failed_claims.append(v_claim)
                continue

            verif_dt = _parse_iso_timestamp(verif_time_str)
            if verif_dt is None:
                err_msg = (
                    f"Invalid verification timestamp: regression verification for claim '{v_claim}' "
                    f"has unparseable timestamp '{verif_time_str}'."
                )
                if fail_closed:
                    raise RecoveryError(err_msg)
                failed_claims.append(v_claim)
                continue

            if repair_boundary_dt and verif_dt <= repair_boundary_dt:
                err_msg = (
                    f"Stale regression verification: verification for claim '{v_claim}' "
                    f"with timestamp '{verif_time_str}' does not post-date repair boundary '{repair_boundary_str}'. "
                    f"Reusing historical verifications from before the current repair cycle is rejected."
                )
                if fail_closed:
                    raise RecoveryError(err_msg)
                stale_claims.append(v_claim)
                continue

            # Check underlying evidence observation timing where available
            v_rcpt_id = getattr(v, "receipt_id", None) or (v.verification_event.receipt_id if getattr(v, "verification_event", None) else None)
            evidence_time_str = None
            if v_rcpt_id:
                try:
                    from sclass.observation.receipt import load_receipt
                    receipt_obj = load_receipt(v_rcpt_id, self.workspace_dir)
                    if receipt_obj:
                        evidence_time_str = getattr(receipt_obj, "finished_at", None) or getattr(receipt_obj, "started_at", None)
                except Exception:
                    pass

            if evidence_time_str and isinstance(evidence_time_str, str) and evidence_time_str.strip():
                ev_dt = _parse_iso_timestamp(evidence_time_str)
                if ev_dt is not None and repair_boundary_dt and ev_dt <= repair_boundary_dt:
                    err_msg = (
                        f"Stale regression evidence: underlying receipt '{v_rcpt_id}' for claim '{v_claim}' "
                        f"with timestamp '{evidence_time_str}' does not post-date repair boundary '{repair_boundary_str}'."
                    )
                    if fail_closed:
                        raise RecoveryError(err_msg)
                    stale_claims.append(v_claim)
                    continue

            # Validate full canonical verification provenance (D9.1.2/D9.1.3)
            try:
                self._validate_canonical_verification_provenance(
                    verification_result=v,
                    expected_claim_id=v_claim,
                    expected_task_id=record.task_id,
                    expected_status=v.status,
                )
            except RecoveryError as e:
                if fail_closed:
                    raise
                failed_claims.append(v_claim)
                continue

            reverified_map[v_claim] = v
            provenance_refs[v_claim] = v.receipt_id or (v.verification_event.receipt_id if v.verification_event else "")

        # Check for missing required regression verifications
        missing_claims = [cid for cid in affected_claim_ids if cid not in reverified_map]
        if missing_claims:
            err_msg = (
                f"Missing required regression verification: affected claim(s) {missing_claims} "
                f"must be reverified from fresh authoritative evidence."
            )
            if fail_closed:
                assessment = RegressionAssessment(
                    affected_claim_ids=affected_claim_ids,
                    reverified_claim_ids=tuple(reverified_map.keys()),
                    failed_claim_ids=tuple(failed_claims + missing_claims),
                    stale_claim_ids=tuple(stale_claims),
                    regression_passed=False,
                    assessment_time=now_iso,
                    unaffected_claim_ids=tuple(unaffected_claim_ids),
                    provenance_references=provenance_refs,
                    reason=err_msg,
                )
                record.regression_assessment = assessment
                self.persistence.save_recovery(record)
                raise RecoveryError(err_msg)
            failed_claims.extend(missing_claims)

        regression_passed = len(failed_claims) == 0 and len(stale_claims) == 0 and len(missing_claims) == 0

        assessment = RegressionAssessment(
            affected_claim_ids=affected_claim_ids,
            reverified_claim_ids=tuple(reverified_map.keys()),
            failed_claim_ids=tuple(failed_claims),
            stale_claim_ids=tuple(stale_claims),
            regression_passed=regression_passed,
            assessment_time=now_iso,
            unaffected_claim_ids=tuple(unaffected_claim_ids),
            provenance_references=provenance_refs,
            reason="All affected claims independently reverified." if regression_passed else "Regression reassessment failed.",
        )
        record.regression_assessment = assessment
        self.persistence.save_recovery(record)
        return assessment

    def evaluate_convergence(
        self,
        recovery_id: str,
        verification_result: Any,
        evidence: Optional[Any] = None,
        known_accepted_obligations: Optional[List[str]] = None,
        invalidated_obligations: Optional[List[str]] = None,
        regression_verifications: Optional[List[Any]] = None,
    ) -> RecoveryResult:
        """
        Evaluates re-verification evidence against the recovery state machine.
        Enforces:
        - Canonical evidence binding: accepts only established S-Class VerificationResult.
        - Rejects plain dicts, textual assertions, and fabricated objects.
        - Requires authoritative receipt/verification identity.
        - Binds convergence to the affected obligation and claim.
        - Canonical regression reassessment: gates convergence on regression success.
        - Stale or failed verification returns to REPAIR_REQUIRED (or RECOVERY_EXHAUSTED).
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

        # Invariant: reject textual assertions and missing verification
        if verification_result is None or isinstance(verification_result, str):
            raise RecoveryError(
                "Convergence is verification, not optimism: cannot establish convergence from textual statement or missing verification."
            )

        # Invariant: reject fabricated dicts
        if isinstance(verification_result, dict):
            raise RecoveryError(
                "Recovery accepts only established S-Class verification/evidence authority: plain dicts are rejected."
            )

        # Invariant: must be authoritative VerificationResult
        if not isinstance(verification_result, AUTH_VERIFICATION_CLASSES):
            raise RecoveryError(
                f"Recovery accepts only established S-Class verification/evidence authority: VerificationResult is required, "
                f"received '{type(verification_result).__name__}'."
            )

        # Invariant: require authoritative receipt identity
        verif_receipt_id = verification_result.receipt_id
        if not verif_receipt_id and verification_result.verification_event:
            verif_receipt_id = getattr(verification_result.verification_event, "receipt_id", None)

        if not verif_receipt_id:
            raise RecoveryError(
                "Missing receipt/verification provenance: VerificationResult lacks authoritative receipt_id."
            )

        # Invariant: bind convergence to affected claim
        verif_claim_id = getattr(verification_result, "claim_id", None)
        if record.affected_claim_id and verif_claim_id:
            if verif_claim_id != record.affected_claim_id:
                raise RecoveryError(
                    f"Claim/obligation mismatch: verification claim_id '{verif_claim_id}' does not match affected claim_id '{record.affected_claim_id}'."
                )

        # Invariant: if evidence is supplied, verify observation provenance and matching receipt_id
        if evidence is not None:
            if not isinstance(evidence, AUTH_RECEIPT_CLASSES):
                raise RecoveryError(
                    f"Forged or unobserved evidence: Evidence must be an authoritative ObservedReceipt, received '{type(evidence).__name__}'."
                )
            if not evidence.is_observed:
                raise RecoveryError(
                    "Forged or unobserved evidence: Evidence must be an authoritative ObservedReceipt with authentic observation provenance."
                )
            if not evidence.receipt_id:
                raise RecoveryError(
                    "Missing receipt/verification provenance: Evidence receipt lacks authoritative receipt_id."
                )
            if evidence.receipt_id != verif_receipt_id:
                raise RecoveryError(
                    f"Receipt ID mismatch between verification result ('{verif_receipt_id}') and evidence ('{evidence.receipt_id}')."
                )

        # D9.1.2/D9.1.3: Enforce canonical receipt provenance for evidence if supplied
        if evidence is not None:
            self._validate_canonical_receipt_provenance(
                receipt_id=evidence.receipt_id,
                expected_claim_id=record.affected_claim_id,
                expected_task_id=record.task_id,
                receipt_obj=evidence,
            )

        # D9.1.2: Enforce canonical verification provenance
        self._validate_canonical_verification_provenance(
            verification_result=verification_result,
            expected_claim_id=record.affected_claim_id,
            expected_task_id=record.task_id,
            expected_status=verification_result.status,
        )

        # Evaluate verdict
        is_verified = bool(getattr(verification_result, "is_verified", False))
        verif_reason = getattr(verification_result, "reason", "")

        # Check evidence staleness
        if getattr(verification_result, "invalidation_reason", None):
            is_verified = False
            verif_reason = f"Evidence invalidated: {verification_result.invalidation_reason}"

        if evidence and getattr(evidence, "is_stale", False):
            is_verified = False
            verif_reason = "Evidence is stale: subsequent workspace modifications detected."

        prev_state = record.current_state

        if is_verified:
            # D9.2: Canonical Regression Reassessment (must pass before CONVERGED)
            reg_assessment = self.assess_regression(
                recovery_id=recovery_id,
                repair_evidence=evidence,
                regression_verifications=regression_verifications,
                fail_closed=True,
            )

            # Transition REVERIFY_REQUIRED -> CONVERGED
            RecoveryStateMachine.validate_transition(prev_state, RecoveryState.CONVERGED)
            record.current_state = RecoveryState.CONVERGED
            record.affected_evidence_id = verif_receipt_id
            record.resulting_verification = {
                "verified_at": now_iso,
                "evidence_id": verif_receipt_id,
                "reason": verif_reason,
            }
            record.regression_assessment = reg_assessment
            record.history.append({
                "event": "convergence_established",
                "from_state": prev_state.value,
                "to_state": RecoveryState.CONVERGED.value,
                "evidence_id": verif_receipt_id,
                "timestamp": now_iso,
            })
            self.persistence.save_recovery(record)

            # Regression protection: distinguish repaired, preserved, and invalidated
            known = list(known_accepted_obligations or [])
            inval = list(invalidated_obligations or [])
            for cid in reg_assessment.reverified_claim_ids:
                if cid not in known and cid not in inval and cid != record.affected_obligation_id:
                    known.append(cid)
            for cid in reg_assessment.unaffected_claim_ids:
                if cid not in known and cid not in inval and cid != record.affected_obligation_id:
                    known.append(cid)
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
                final_evidence_id=verif_receipt_id,
                reason=verif_reason or "Obligation independently reverified and converged.",
            )
        else:
            # Re-verification failed or is stale
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
                    final_evidence_id=verif_receipt_id,
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
                    final_evidence_id=verif_receipt_id,
                    reason=f"Re-verification failed: {verif_reason}. Fresh repair attempt required.",
                )
