"""
S-Class D9.1 Recovery Contract and Bounded Convergence Kernel Tests.
Covers Required Adversarial Scenarios:
- Test A: Illegal transition rejected, authoritative state unchanged.
- Test B: Retry exhaustion fails closed at attempt limit.
- Test C: Restart persistence preserves state and monotonic attempts.
- Test D: False convergence rejected without authentic independent verification.
- Test E: Regression preservation: unaffected accepted obligations remain accepted.
- Test F: Corrupt recovery persistence fails closed.
- Test G: Duplicate transition replay is idempotent without duplicate attempt increments.
- Test H: Stale recovery evidence cannot conclude convergence.

D9.1.1 Required Specific Adversarial Tests:
- forged failure evidence rejected
- forged ACCEPT verification rejected
- claim/obligation mismatch rejected
- missing receipt/verification provenance rejected
- two recovery cycles for the same obligation remain distinct
- canonical state survives restart
- provenance fields survive reconstruction

D9.1.2 Required Canonical Verification Provenance Closure Tests:
- Test A: forged canonical VerificationResult rejected
- Test B: forged canonical failure result not created
- Test C: unregistered real receipt rejected
- Test D: verification record / receipt mismatch rejected
- Test E: verification-event mismatch rejected
- Test F: ledger provenance absence rejected
- Test G: ledger corruption fails closed
- Test H: valid canonical verification converges

D9.1.3 Required Fail-Closed Receipt Binding and Certification Closure Tests:
- Test A: workspace mismatch rejected
- Test B: missing task binding rejected
- Test C: missing claim binding rejected
- Test D: missing receipt hash rejected
- Test E: receipt hash mismatch rejected
- Test F: valid canonical receipt converges

D9.2 Required Canonical Regression Reassessment Tests:
- previously accepted claim affected by repair -> must be reverified
- affected claim missing fresh verification -> rejected
- stale regression evidence -> rejected
- wrong claim regression result -> rejected
- wrong-task regression result -> rejected
- forged/unanchored regression receipt -> rejected
- conflicting regression result -> rejected
- unaffected accepted claim preserved when canonical dependency evidence establishes no impact
- restart preserves regression assessment
- valid target verification + valid regression verification -> CONVERGED

D9.2.1 Required Repair-Cycle Regression Timing Tests:
- canonical old ACCEPT reused after repair -> rejected
- verification timestamp missing -> rejected
- verification before repair but otherwise perfectly canonical -> rejected
- verification after repair -> accepted
"""

import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import pytest

from sclass.recovery import (
    RecoveryState,
    RecoveryStateMachine,
    RepairObligation,
    RecoveryAttempt,
    RecoveryRecord,
    RecoveryResult,
    RecoveryEngine,
    RecoveryPersistence,
    RecoveryError,
    RecoveryStateTransitionError,
    RecoveryExhaustedError,
    RecoveryPersistenceError,
)
from sclass.domain.verification import VerificationResult, VerificationEvent
from sclass.domain.claim import Claim
from sclass.domain.task import Task
from sclass.domain.project import Project, ProjectBoundary
from sclass.survival.models import ObservedReceipt, EvidenceReceipt
from sclass.survival.verification import verify_claim
from sclass.survival.evidence import observe_command
from sclass.observation.receipt import save_receipt, create_observed_receipt
from sclass.trust.ledger import LocalLedger
from sclass.state.tasks import StateRepository


def make_observed_failure_receipt(
    receipt_id: str = "rcpt_fail_001",
    task_id: str = "",
    claim_id: str = "",
    exit_code: int = 1,
    command: str = "pytest tests/",
    workspace: str = "/tmp/ws",
    anchor_in_ledger: bool = True,
) -> ObservedReceipt:
    ws = os.path.abspath(workspace)
    t_id = task_id or (f"task_{receipt_id.replace('rcpt_fail_', '').replace('rcpt_', '')}" if receipt_id else "task_default")
    c_id = claim_id or f"claim_{t_id.replace('task_', '')}"
    receipt = ObservedReceipt(
        receipt_id=receipt_id,
        task_id=t_id,
        claim_id=c_id,
        agent="test_agent",
        action="execute",
        workspace=ws,
        command=command,
        exit_code=exit_code,
    )
    receipt.receipt_hash = receipt.compute_hash()
    if anchor_in_ledger:
        save_receipt(receipt, ws)
        ledger = LocalLedger(workspace_dir=ws)
        ledger.append(
            event="OBSERVATION",
            payload={
                "receipt_id": receipt.receipt_id,
                "receipt_hash": receipt.receipt_hash,
                "task_id": t_id,
                "claim_id": c_id,
                "exit_code": exit_code,
                "workspace": ws,
                "command": command,
            },
        )
    return receipt


def make_observed_success_receipt(
    receipt_id: str = "rcpt_pass_001",
    task_id: str = "",
    claim_id: str = "",
    command: str = "pytest tests/",
    workspace: str = "/tmp/ws",
    anchor_in_ledger: bool = True,
) -> ObservedReceipt:
    ws = os.path.abspath(workspace)
    t_id = task_id or (f"task_{receipt_id.replace('rcpt_pass_', '').replace('rcpt_', '')}" if receipt_id else "task_default")
    c_id = claim_id or f"claim_{t_id.replace('task_', '')}"
    receipt = ObservedReceipt(
        receipt_id=receipt_id,
        task_id=t_id,
        claim_id=c_id,
        agent="test_agent",
        action="execute",
        workspace=ws,
        command=command,
        exit_code=0,
    )
    receipt.receipt_hash = receipt.compute_hash()
    if anchor_in_ledger:
        save_receipt(receipt, ws)
        ledger = LocalLedger(workspace_dir=ws)
        ledger.append(
            event="OBSERVATION",
            payload={
                "receipt_id": receipt.receipt_id,
                "receipt_hash": receipt.receipt_hash,
                "task_id": t_id,
                "claim_id": c_id,
                "exit_code": 0,
                "workspace": ws,
                "command": command,
            },
        )
    return receipt


def make_canonical_verification_result(
    receipt: ObservedReceipt,
    status: str = "ACCEPT",
    reason: str = "Verified",
    workspace: Optional[str] = None,
    claim_id: Optional[str] = None,
    invalidation_reason: Optional[str] = None,
    anchor_in_ledger: bool = True,
    save_in_state: bool = True,
) -> VerificationResult:
    ws = os.path.abspath(workspace or receipt.workspace)
    c_id = claim_id or receipt.claim_id or "claim_default"
    ledger = LocalLedger(workspace_dir=ws)
    event_type = "verification" if status in ("ACCEPT", "PASS") else "rejection"
    event_res = "CLAIM_VERIFIED" if status in ("ACCEPT", "PASS") else "REJECT"

    verif_event = VerificationEvent(
        claim_id=c_id,
        receipt_id=receipt.receipt_id,
        receipt_hash=receipt.receipt_hash,
        verifier="test_verifier",
        verification_time=datetime.now(timezone.utc).isoformat(),
        result=event_res,
        reason=reason,
        repository_fingerprint=getattr(receipt, "workspace_fingerprint", "") or "",
        previous_ledger_hash=ledger.get_last_hash(),
    )

    verdict = VerificationResult(
        status=status,
        claim_id=c_id,
        reason=reason,
        observed_exit_code=receipt.exit_code,
        invalidation_reason=invalidation_reason,
        receipt_id=receipt.receipt_id,
        verification_event=verif_event,
    )

    if anchor_in_ledger:
        ledger.append(
            event=event_type,
            payload={
                "receipt_id": receipt.receipt_id,
                "receipt_hash": receipt.receipt_hash,
                "claim_id": c_id,
                "verification_result": event_res,
                "status": status,
                "event_id": verif_event.event_id,
                "workspace": ws,
            },
        )

    if save_in_state:
        state_repo = StateRepository(workspace_dir=ws)
        t_id = getattr(receipt, "task_id", "task_dummy")
        proj_id = "proj_01"
        if not state_repo.get_project(proj_id):
            state_repo.save_project(Project(project_id=proj_id, name="Project 01", boundary=ProjectBoundary(root_path=ws)))
        if not state_repo.get_task(t_id):
            state_repo.save_task(Task(task_id=t_id, project_id=proj_id, title=f"Task {t_id}"))
        if not state_repo.get_claim(c_id):
            state_repo.save_claim(Claim(claim_id=c_id, task_id=t_id, statement=f"Claim {c_id}", claim_type="test"))
        state_repo.save_verification(verdict)

    return verdict



# --------------------------------------------------------------------------
# Test A: Illegal Transition
# --------------------------------------------------------------------------
def test_d9_test_a_illegal_transition_rejected(tmp_path):
    """
    Test A:
    Attempt an invalid recovery-state transition.
    Expected: rejected with RecoveryStateTransitionError, authoritative state unchanged.
    """
    ws = str(tmp_path / "d9_test_a")
    engine = RecoveryEngine(workspace_dir=ws)

    evidence = make_observed_failure_receipt(exit_code=2, workspace=ws)
    record = engine.diagnose_failure(
        task_id="task_001",
        obligation_id="ob_func_001",
        failure_evidence=evidence,
        reason="Test suite failed with exit code 2",
    )
    assert record.current_state == RecoveryState.DIAGNOSING

    # Attempt illegal jump: DIAGNOSING -> CONVERGED
    with pytest.raises(RecoveryStateTransitionError):
        RecoveryStateMachine.validate_transition(record.current_state, RecoveryState.CONVERGED)

    # Attempt illegal jump: DIAGNOSING -> REVERIFY_REQUIRED
    with pytest.raises(RecoveryStateTransitionError):
        RecoveryStateMachine.validate_transition(record.current_state, RecoveryState.REVERIFY_REQUIRED)

    # Verify authoritative state remains DIAGNOSING
    fresh_record = engine.get_recovery(record.recovery_id)
    assert fresh_record.current_state == RecoveryState.DIAGNOSING

    # Create repair obligation -> enters REPAIR_REQUIRED
    engine.create_repair_obligation(record.recovery_id, target="math_utils.py")
    fresh_record = engine.get_recovery(record.recovery_id)
    assert fresh_record.current_state == RecoveryState.REPAIR_REQUIRED

    # Attempt illegal jump: REPAIR_REQUIRED -> CONVERGED
    with pytest.raises(RecoveryStateTransitionError):
        engine.evaluate_convergence(
            recovery_id=record.recovery_id,
            verification_result=VerificationResult(status="ACCEPT", receipt_id="rcpt_pass_001"),
        )

    # Verify authoritative state remains REPAIR_REQUIRED
    fresh_record = engine.get_recovery(record.recovery_id)
    assert fresh_record.current_state == RecoveryState.REPAIR_REQUIRED


# --------------------------------------------------------------------------
# Test B: Retry Exhaustion
# --------------------------------------------------------------------------
def test_d9_test_b_retry_exhaustion_fails_closed(tmp_path):
    """
    Test B:
    Run recovery until the maximum attempt count is reached.
    Expected: transitions to RECOVERY_EXHAUSTED and further repair attempts fail closed.
    """
    ws = str(tmp_path / "d9_test_b")
    engine = RecoveryEngine(workspace_dir=ws, default_max_attempts=2)

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_002", exit_code=1, workspace=ws)
    record = engine.diagnose_failure(
        task_id="task_002",
        obligation_id="ob_func_002",
        failure_evidence=evidence,
    )

    # Attempt 1
    ob1 = engine.create_repair_obligation(record.recovery_id)
    assert ob1.attempt_number == 1
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Attempt 1 fails verification -> returns to REPAIR_REQUIRED
    failed_res1 = make_canonical_verification_result(evidence, status="REJECT", reason="Still failing", workspace=ws)
    res1 = engine.evaluate_convergence(record.recovery_id, verification_result=failed_res1)
    assert res1.is_converged is False
    assert res1.status == RecoveryState.REPAIR_REQUIRED.value

    # Attempt 2
    ob2 = engine.create_repair_obligation(record.recovery_id)
    assert ob2.attempt_number == 2
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Attempt 2 fails verification -> attempt limit (2) reached -> RECOVERY_EXHAUSTED
    failed_res2 = make_canonical_verification_result(evidence, status="REJECT", reason="Still failing on attempt 2", workspace=ws)
    res2 = engine.evaluate_convergence(record.recovery_id, verification_result=failed_res2)
    assert res2.is_converged is False
    assert res2.status == RecoveryState.RECOVERY_EXHAUSTED.value

    # Authoritative record is RECOVERY_EXHAUSTED
    fresh_record = engine.get_recovery(record.recovery_id)
    assert fresh_record.current_state == RecoveryState.RECOVERY_EXHAUSTED
    assert fresh_record.attempt_number == 2

    # Any further repair attempt fails closed
    with pytest.raises(RecoveryExhaustedError, match="attempt budget exhausted"):
        engine.create_repair_obligation(record.recovery_id)


# --------------------------------------------------------------------------
# Test C: Restart Persistence
# --------------------------------------------------------------------------
def test_d9_test_c_restart_persistence_preserves_state_and_attempts(tmp_path):
    """
    Test C:
    Create recovery state, reconstruct the controller from persisted state, and continue.
    Expected: attempt number preserved, state preserved, no retry reset.
    """
    ws = str(tmp_path / "d9_test_c")
    engine1 = RecoveryEngine(workspace_dir=ws, default_max_attempts=3)

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_003", exit_code=1, workspace=ws)
    record = engine1.diagnose_failure(
        task_id="task_003",
        obligation_id="ob_func_003",
        failure_evidence=evidence,
    )
    # Attempt 1
    engine1.create_repair_obligation(record.recovery_id)
    engine1.start_repair(record.recovery_id)
    engine1.submit_for_reverification(record.recovery_id)
    failed_res = make_canonical_verification_result(evidence, status="REJECT", reason="Fix incomplete", workspace=ws)
    engine1.evaluate_convergence(
        record.recovery_id,
        verification_result=failed_res,
    )

    # Attempt 2
    engine1.create_repair_obligation(record.recovery_id)
    engine1.start_repair(record.recovery_id)

    rec1 = engine1.get_recovery(record.recovery_id)
    assert rec1.current_state == RecoveryState.REPAIR_IN_PROGRESS
    assert rec1.attempt_number == 2

    # Simulate process restart by instantiating a completely new RecoveryEngine
    engine2 = RecoveryEngine(workspace_dir=ws, default_max_attempts=3)
    rec2 = engine2.get_recovery(record.recovery_id)

    # State and attempt must be preserved across restart
    assert rec2 is not None
    assert rec2.current_state == RecoveryState.REPAIR_IN_PROGRESS
    assert rec2.attempt_number == 2
    assert rec2.max_attempts == 3

    # Can cleanly continue from persisted state
    engine2.submit_for_reverification(record.recovery_id)
    rec_after_submit = engine2.get_recovery(record.recovery_id)
    assert rec_after_submit.current_state == RecoveryState.REVERIFY_REQUIRED
    assert rec_after_submit.attempt_number == 2


# --------------------------------------------------------------------------
# Test D: False Convergence
# --------------------------------------------------------------------------
def test_d9_test_d_false_convergence_rejected_without_verification(tmp_path):
    """
    Test D:
    Mark repair as completed without satisfying independent verification.
    Expected: must NOT become CONVERGED.
    """
    ws = str(tmp_path / "d9_test_d")
    engine = RecoveryEngine(workspace_dir=ws)

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_004", exit_code=1, workspace=ws)
    record = engine.diagnose_failure(
        task_id="task_004",
        obligation_id="ob_func_004",
        failure_evidence=evidence,
    )
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # 1. Plain text assertion ("the fix is complete") is strictly rejected
    with pytest.raises(RecoveryError, match="Convergence is verification, not optimism"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result="The fix is complete and all bugs are resolved.",
        )

    # Authoritative state is still REVERIFY_REQUIRED
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED

    # 2. None verification result is rejected
    with pytest.raises(RecoveryError, match="Convergence is verification, not optimism"):
        engine.evaluate_convergence(record.recovery_id, verification_result=None)

    # 3. Rejected verification verdict does NOT converge
    failed_verdict = make_canonical_verification_result(evidence, status="REJECT", reason="Defect still present", workspace=ws)
    res = engine.evaluate_convergence(record.recovery_id, verification_result=failed_verdict)
    assert res.is_converged is False
    assert res.status != RecoveryState.CONVERGED.value


# --------------------------------------------------------------------------
# Test E: Regression Preservation
# --------------------------------------------------------------------------
def test_d9_test_e_regression_preservation_unaffected_obligations_remain_accepted(tmp_path):
    """
    Test E:
    Recover one obligation while another accepted obligation remains valid.
    Expected: repaired obligation becomes verified, unrelated accepted obligation remains accepted.
    """
    ws = str(tmp_path / "d9_test_e")
    engine = RecoveryEngine(workspace_dir=ws)

    evidence = make_observed_failure_receipt(
        receipt_id="rcpt_fail_005",
        task_id="task_005",
        claim_id="claim_repaired_multiply",
        exit_code=1,
        workspace=ws,
    )
    record = engine.diagnose_failure(
        task_id="task_005",
        obligation_id="ob_func_multiply",
        failure_evidence=evidence,
        claim_id="claim_repaired_multiply",
    )
    engine.create_repair_obligation(record.recovery_id, target="math_utils.py")
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Known accepted obligations in project:
    known_accepted = ["ob_func_add", "ob_config"]

    # Provide authentic passing verification and observed evidence
    passing_evidence = make_observed_success_receipt(
        receipt_id="rcpt_pass_multiply",
        task_id="task_005",
        claim_id="claim_repaired_multiply",
        workspace=ws,
    )
    passing_verdict = make_canonical_verification_result(
        passing_evidence,
        status="ACCEPT",
        claim_id="claim_repaired_multiply",
        reason="Multiply tests pass 100%",
        workspace=ws,
    )

    res = engine.evaluate_convergence(
        recovery_id=record.recovery_id,
        verification_result=passing_verdict,
        evidence=passing_evidence,
        known_accepted_obligations=known_accepted,
    )

    assert res.is_converged is True
    assert res.status == RecoveryState.CONVERGED.value
    assert res.repaired_obligation_id == "ob_func_multiply"

    # Invariant: Unaffected obligations must remain preserved in authoritative result
    assert "ob_func_add" in res.preserved_obligation_ids
    assert "ob_config" in res.preserved_obligation_ids
    assert len(res.invalidated_obligation_ids) == 0



# --------------------------------------------------------------------------
# Test F: Corrupt Persistence
# --------------------------------------------------------------------------
def test_d9_test_f_corrupt_persistence_fails_closed(tmp_path):
    """
    Test F:
    Corrupt the authoritative recovery SQLite database.
    Expected: recovery operation fails closed (RecoveryPersistenceError), no fabricated state is accepted.
    """
    ws = str(tmp_path / "d9_test_f")
    engine = RecoveryEngine(workspace_dir=ws)

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_006", exit_code=1, workspace=ws)
    record = engine.diagnose_failure(
        task_id="task_006",
        obligation_id="ob_func_006",
        failure_evidence=evidence,
    )
    engine.create_repair_obligation(record.recovery_id)

    # Corrupt the SQLite database file
    db_file = os.path.join(ws, ".sclass", "state", "project.db")
    assert os.path.exists(db_file)
    wal_file = db_file + "-wal"
    if os.path.exists(wal_file):
        try:
            os.remove(wal_file)
        except Exception:
            with open(wal_file, "wb") as wf:
                wf.write(b"CORRUPTED_WAL_GARBAGE\x00\xff")
    with open(db_file, "wb") as f:
        f.write(b"CORRUPTED_SQLITE_DATABASE_HEADER_GARBAGE\x00\xff")

    # Loading corrupted persistence must fail closed
    with pytest.raises(RecoveryPersistenceError):
        engine.persistence.load_all()

    with pytest.raises(RecoveryPersistenceError):
        engine.get_recovery(record.recovery_id)

    # Attempting an operation on the corrupted store must fail closed
    with pytest.raises(RecoveryPersistenceError):
        engine.start_repair(record.recovery_id)


# --------------------------------------------------------------------------
# Test G: Duplicate Transition
# --------------------------------------------------------------------------
def test_d9_test_g_duplicate_transition_idempotent(tmp_path):
    """
    Test G:
    Replay the same recovery transition.
    Expected: idempotent, no contradictory state, no duplicate attempt increment.
    """
    ws = str(tmp_path / "d9_test_g")
    engine = RecoveryEngine(workspace_dir=ws)

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_007", exit_code=1, workspace=ws)
    record1 = engine.diagnose_failure(
        task_id="task_007",
        obligation_id="ob_func_007",
        failure_evidence=evidence,
    )
    rec_id = record1.recovery_id

    # Replay diagnose_failure -> idempotent, returns existing record
    record2 = engine.diagnose_failure(
        task_id="task_007",
        obligation_id="ob_func_007",
        failure_evidence=evidence,
    )
    assert record1.recovery_id == record2.recovery_id
    assert record2.current_state == RecoveryState.DIAGNOSING

    # Create repair obligation -> attempt 1
    ob1 = engine.create_repair_obligation(rec_id)
    assert ob1.attempt_number == 1

    # Replay create_repair_obligation -> idempotent, returns same obligation, does not increment
    ob1_replay = engine.create_repair_obligation(rec_id)
    assert ob1_replay.obligation_id == ob1.obligation_id
    assert ob1_replay.attempt_number == 1
    assert engine.get_recovery(rec_id).attempt_number == 1

    # Start repair -> idempotent
    rep1 = engine.start_repair(rec_id)
    rep2 = engine.start_repair(rec_id)
    assert rep1 == rep2
    assert engine.get_recovery(rec_id).current_state == RecoveryState.REPAIR_IN_PROGRESS

    # Submit for reverify -> idempotent
    engine.submit_for_reverification(rec_id)
    engine.submit_for_reverification(rec_id)
    assert engine.get_recovery(rec_id).current_state == RecoveryState.REVERIFY_REQUIRED

    # Convergence -> idempotent
    pass_evidence = make_observed_success_receipt(receipt_id="rcpt_pass_007", workspace=ws)
    pass_verdict = make_canonical_verification_result(pass_evidence, status="ACCEPT", reason="Verified", workspace=ws)
    res1 = engine.evaluate_convergence(rec_id, verification_result=pass_verdict)
    res2 = engine.evaluate_convergence(rec_id, verification_result=pass_verdict)
    assert res1.is_converged is True
    assert res2.is_converged is True
    assert res1.status == res2.status == RecoveryState.CONVERGED.value


# --------------------------------------------------------------------------
# Test H: Stale Recovery
# --------------------------------------------------------------------------
def test_d9_test_h_stale_recovery_evidence_cannot_converge(tmp_path):
    """
    Test H:
    Use recovery evidence derived from state that has subsequently been invalidated.
    Expected: recovery cannot conclude convergence from stale evidence.
    """
    ws = str(tmp_path / "d9_test_h")
    engine = RecoveryEngine(workspace_dir=ws, default_max_attempts=3)

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_008", exit_code=1, workspace=ws)
    record = engine.diagnose_failure(
        task_id="task_008",
        obligation_id="ob_func_008",
        failure_evidence=evidence,
    )
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Case 1: VerificationResult reports invalidation due to staleness
    stale_receipt = make_observed_success_receipt(receipt_id="rcpt_pass_008", workspace=ws)
    stale_verdict = make_canonical_verification_result(
        stale_receipt,
        status="ACCEPT",
        invalidation_reason="Claim rejected: Evidence is stale. Workspace mutation detected.",
        reason="Tests passed but files changed afterwards",
        workspace=ws,
    )

    res1 = engine.evaluate_convergence(record.recovery_id, verification_result=stale_verdict)
    assert res1.is_converged is False
    assert res1.status == RecoveryState.REPAIR_REQUIRED.value

    # Case 2: Evidence object itself is flagged as stale
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    stale_ev = make_observed_success_receipt(
        receipt_id="rcpt_pass_008_fresh",
        task_id="task_008",
        claim_id="claim_008",
        workspace=ws,
    )
    # Mark as stale
    object.__setattr__(stale_ev, "is_stale", True) if hasattr(stale_ev, "__dataclass_fields__") else setattr(stale_ev, "is_stale", True)

    normal_verdict = make_canonical_verification_result(
        stale_ev,
        status="ACCEPT",
        claim_id="claim_008",
        reason="Passed",
        workspace=ws,
    )

    res2 = engine.evaluate_convergence(
        record.recovery_id,
        verification_result=normal_verdict,
        evidence=stale_ev,
    )
    assert res2.is_converged is False
    assert res2.status == RecoveryState.REPAIR_REQUIRED.value
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REPAIR_REQUIRED



# ==========================================================================
# D9.1.1 SPECIFIC ADVERSARIAL TESTS
# ==========================================================================

# --------------------------------------------------------------------------
# Test 1: Forged Failure Evidence Rejected
# --------------------------------------------------------------------------
def test_d9_forged_failure_evidence_rejected(tmp_path):
    """
    Certifies that plain dicts, arbitrary unauthoritative objects, and unobserved
    receipts cannot initiate recovery.
    """
    ws = str(tmp_path / "forged_failure")
    engine = RecoveryEngine(workspace_dir=ws)

    # 1. Plain dictionary claiming failure
    with pytest.raises(RecoveryError, match="plain dicts are rejected"):
        engine.diagnose_failure(
            task_id="task_fake",
            obligation_id="ob_fake",
            failure_evidence={"status": "REJECT", "exit_code": 1, "receipt_id": "rcpt_fake"},
        )

    # 2. Fabricated object with failure attributes
    class FakeFailure:
        status = "REJECT"
        exit_code = 1
        receipt_id = "rcpt_fake_obj"
        is_verified = False

    with pytest.raises(RecoveryError, match="Recovery accepts only established S-Class verification/evidence authority"):
        engine.diagnose_failure(
            task_id="task_fake",
            obligation_id="ob_fake",
            failure_evidence=FakeFailure(),
        )

    # 3. Unobserved EvidenceReceipt (constructed without private observation token)
    unobserved = EvidenceReceipt(
        receipt_id="rcpt_unobserved",
        task_id="task_fake",
        claim_id="claim_fake",
        agent="attacker",
        action="execute",
        workspace=ws,
        exit_code=1,
    )
    assert unobserved.is_observed is False
    with pytest.raises(RecoveryError, match="Forged or unobserved failure evidence"):
        engine.diagnose_failure(
            task_id="task_fake",
            obligation_id="ob_fake",
            failure_evidence=unobserved,
        )


# --------------------------------------------------------------------------
# Test 2: Forged ACCEPT Verification Rejected
# --------------------------------------------------------------------------
def test_d9_forged_accept_verification_rejected(tmp_path):
    """
    Certifies that plain dicts, arbitrary objects, and unobserved evidence
    cannot establish convergence.
    """
    ws = str(tmp_path / "forged_accept")
    engine = RecoveryEngine(workspace_dir=ws)

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_real", task_id="task_01", claim_id="claim_01", exit_code=1, workspace=ws)
    record = engine.diagnose_failure(task_id="task_01", obligation_id="ob_01", failure_evidence=evidence)
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # 1. Plain dictionary claiming ACCEPT
    with pytest.raises(RecoveryError, match="plain dicts are rejected"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result={"status": "ACCEPT", "receipt_id": "rcpt_fake_pass"},
        )

    # 2. Arbitrary object claiming ACCEPT
    class FakeAcceptVerdict:
        status = "ACCEPT"
        receipt_id = "rcpt_fake_pass"
        is_verified = True

    with pytest.raises(RecoveryError, match="Recovery accepts only established S-Class verification/evidence authority"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=FakeAcceptVerdict(),
        )

    # 3. Authentic VerificationResult but paired with unobserved EvidenceReceipt
    valid_ev = make_observed_success_receipt(receipt_id="rcpt_unobserved_pass", task_id="task_01", claim_id="claim_01", workspace=ws)
    valid_verdict = make_canonical_verification_result(valid_ev, status="ACCEPT", workspace=ws)
    unobserved_ev = EvidenceReceipt(
        receipt_id="rcpt_unobserved_pass",
        task_id="task_01",
        claim_id="claim_01",
        agent="attacker",
        action="execute",
        workspace=ws,
        exit_code=0,
    )
    assert unobserved_ev.is_observed is False
    with pytest.raises(RecoveryError, match="Forged or unobserved evidence"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=valid_verdict,
            evidence=unobserved_ev,
        )


# --------------------------------------------------------------------------
# Test 3: Claim / Obligation Mismatch Rejected
# --------------------------------------------------------------------------
def test_d9_claim_obligation_mismatch_rejected(tmp_path):
    """
    Certifies that failure evidence or verification results with mismatched
    claim or task identifiers are strictly rejected.
    """
    ws = str(tmp_path / "claim_mismatch")
    engine = RecoveryEngine(workspace_dir=ws)

    # 1. Failure evidence has claim_id="claim_X", caller expects "claim_Y"
    ev_mismatch = make_observed_failure_receipt(receipt_id="rcpt_fail_mismatch", task_id="task_01", claim_id="claim_X", exit_code=1, workspace=ws)
    with pytest.raises(RecoveryError, match="Claim/obligation mismatch"):
        engine.diagnose_failure(
            task_id="task_01",
            obligation_id="ob_01",
            failure_evidence=ev_mismatch,
            claim_id="claim_Y",
        )

    # 2. Start valid recovery bound to claim_id="claim_A"
    ev_valid = make_observed_failure_receipt(receipt_id="rcpt_fail_a", task_id="task_01", claim_id="claim_A", exit_code=1, workspace=ws)
    record = engine.diagnose_failure(
        task_id="task_01",
        obligation_id="ob_01",
        failure_evidence=ev_valid,
        claim_id="claim_A",
    )
    assert record.affected_claim_id == "claim_A"

    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Reverification verdict claims "claim_B" instead of "claim_A"
    ev_b = make_observed_success_receipt(receipt_id="rcpt_pass_b", task_id="task_01", claim_id="claim_B", workspace=ws)
    verdict_mismatch = make_canonical_verification_result(ev_b, status="ACCEPT", claim_id="claim_B", workspace=ws)
    with pytest.raises(RecoveryError, match="Claim/obligation mismatch"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict_mismatch,
        )


# --------------------------------------------------------------------------
# Test 4: Missing Receipt / Verification Provenance Rejected
# --------------------------------------------------------------------------
def test_d9_missing_receipt_verification_provenance_rejected(tmp_path):
    """
    Certifies that failure evidence or verification results lacking authoritative
    receipt identities are strictly rejected.
    """
    ws = str(tmp_path / "missing_provenance")
    engine = RecoveryEngine(workspace_dir=ws)

    # 1. VerificationResult without receipt_id passed as failure evidence
    verif_no_receipt = VerificationResult(status="REJECT", reason="Tests failed")
    with pytest.raises(RecoveryError, match="Missing receipt/verification provenance"):
        engine.diagnose_failure(
            task_id="task_01",
            obligation_id="ob_01",
            failure_evidence=verif_no_receipt,
        )

    # 2. ObservedReceipt with empty receipt_id
    empty_rcpt_ev = make_observed_failure_receipt(receipt_id="", exit_code=1, workspace=ws, anchor_in_ledger=False)
    with pytest.raises(RecoveryError, match="Missing receipt/verification provenance"):
        engine.diagnose_failure(
            task_id="task_01",
            obligation_id="ob_01",
            failure_evidence=empty_rcpt_ev,
        )

    # 3. Evaluate convergence with VerificationResult lacking receipt_id
    valid_ev = make_observed_failure_receipt(receipt_id="rcpt_f_valid", task_id="task_01", claim_id="claim_01", exit_code=1, workspace=ws)
    record = engine.diagnose_failure(task_id="task_01", obligation_id="ob_01", failure_evidence=valid_ev)
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    verif_pass_no_receipt = VerificationResult(status="ACCEPT", reason="Passed")
    with pytest.raises(RecoveryError, match="Missing receipt/verification provenance"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verif_pass_no_receipt,
        )


# --------------------------------------------------------------------------
# Test 5: Two Recovery Cycles for the Same Obligation Remain Distinct
# --------------------------------------------------------------------------
def test_d9_two_recovery_cycles_for_same_obligation_remain_distinct(tmp_path):
    """
    Certifies that every recovery cycle gets a unique stable identity tied to
    the originating failure/event, and subsequent failures of the same obligation
    produce new, distinct recovery cycles without overwriting earlier cycles.
    """
    ws = str(tmp_path / "distinct_cycles")
    engine = RecoveryEngine(workspace_dir=ws)

    # Cycle 1: initial failure
    ev1 = make_observed_failure_receipt(receipt_id="rcpt_fail_cycle_1", task_id="task_cycle", claim_id="claim_cycle", exit_code=1, workspace=ws)
    rec1 = engine.diagnose_failure(
        task_id="task_cycle",
        obligation_id="ob_recurring",
        failure_evidence=ev1,
        parent_event_id="evt_failure_001",
    )
    cycle1_id = rec1.recovery_id
    assert "evt_failure_001" in cycle1_id or "rcpt_fail_cycle_1" in cycle1_id

    # Advance cycle 1 to CONVERGED
    engine.create_repair_obligation(cycle1_id)
    engine.start_repair(cycle1_id)
    engine.submit_for_reverification(cycle1_id)
    pass_ev1 = make_observed_success_receipt(receipt_id="rcpt_pass_cycle_1", task_id="task_cycle", claim_id="claim_cycle", workspace=ws)
    verdict1 = make_canonical_verification_result(pass_ev1, status="ACCEPT", workspace=ws)
    res1 = engine.evaluate_convergence(cycle1_id, verification_result=verdict1)
    assert res1.is_converged is True

    # Cycle 2: later, a different failure occurs for the SAME obligation
    ev2 = make_observed_failure_receipt(receipt_id="rcpt_fail_cycle_2", task_id="task_cycle", claim_id="claim_cycle", exit_code=2, workspace=ws)
    rec2 = engine.diagnose_failure(
        task_id="task_cycle",
        obligation_id="ob_recurring",
        failure_evidence=ev2,
        parent_event_id="evt_failure_002",
    )
    cycle2_id = rec2.recovery_id

    # The two cycles must have distinct IDs
    assert cycle1_id != cycle2_id

    # Both cycles exist concurrently in authoritative state store
    fresh_rec1 = engine.get_recovery(cycle1_id)
    fresh_rec2 = engine.get_recovery(cycle2_id)
    assert fresh_rec1 is not None
    assert fresh_rec2 is not None

    # Cycle 1 remains CONVERGED, Cycle 2 is in DIAGNOSING
    assert fresh_rec1.current_state == RecoveryState.CONVERGED
    assert fresh_rec2.current_state == RecoveryState.DIAGNOSING
    assert fresh_rec1.affected_evidence_id == "rcpt_pass_cycle_1"
    assert fresh_rec2.affected_evidence_id == "rcpt_fail_cycle_2"


# --------------------------------------------------------------------------
# Test 6: Canonical State Survives Restart
# --------------------------------------------------------------------------
def test_d9_canonical_state_survives_restart(tmp_path):
    """
    Certifies that recovery state is stored in the authoritative SQLite store
    and fully reconstructs across process restarts.
    """
    ws = str(tmp_path / "restart_state")
    engine1 = RecoveryEngine(workspace_dir=ws, default_max_attempts=3)

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_restart", task_id="task_restart", claim_id="claim_restart", exit_code=1, workspace=ws)
    record = engine1.diagnose_failure(
        task_id="task_restart",
        obligation_id="ob_restart",
        failure_evidence=evidence,
    )
    rec_id = record.recovery_id

    # Advance attempt 1 -> fail reverify -> advance to attempt 2 in progress
    engine1.create_repair_obligation(rec_id)
    engine1.start_repair(rec_id)
    engine1.submit_for_reverification(rec_id)
    fail_verdict = make_canonical_verification_result(evidence, status="REJECT", reason="Still broken", workspace=ws)
    engine1.evaluate_convergence(
        rec_id,
        verification_result=fail_verdict,
    )

    ob2 = engine1.create_repair_obligation(rec_id)
    assert ob2.attempt_number == 2
    engine1.start_repair(rec_id)

    rec_before = engine1.get_recovery(rec_id)
    assert rec_before.current_state == RecoveryState.REPAIR_IN_PROGRESS
    assert rec_before.attempt_number == 2

    # Verify SQLite database file exists in canonical state directory
    db_file = os.path.join(ws, ".sclass", "state", "project.db")
    assert os.path.exists(db_file)

    # Reconstruct fresh RecoveryEngine from same workspace (simulate process reboot)
    engine2 = RecoveryEngine(workspace_dir=ws, default_max_attempts=3)
    rec_after = engine2.get_recovery(rec_id)

    assert rec_after is not None
    assert rec_after.recovery_id == rec_id
    assert rec_after.current_state == RecoveryState.REPAIR_IN_PROGRESS
    assert rec_after.attempt_number == 2
    assert rec_after.current_repair_obligation is not None
    assert rec_after.current_repair_obligation.attempt_number == 2

    # Cleanly continue and converge using engine2
    engine2.submit_for_reverification(rec_id)
    pass_ev = make_observed_success_receipt(receipt_id="rcpt_pass_restart", workspace=ws)
    pass_verdict = make_canonical_verification_result(pass_ev, status="ACCEPT", reason="Fixed on attempt 2", workspace=ws)
    res = engine2.evaluate_convergence(rec_id, verification_result=pass_verdict)
    assert res.is_converged is True
    assert res.attempts_used == 2

    rec_final = engine2.get_recovery(rec_id)
    assert rec_final.current_state == RecoveryState.CONVERGED


# --------------------------------------------------------------------------
# Test 7: Provenance Fields Survive Reconstruction
# --------------------------------------------------------------------------
def test_d9_provenance_fields_survive_reconstruction(tmp_path):
    """
    Certifies that parent_event_id, staleness_cause, claim/evidence identities,
    and project_state_ref are preserved and reconstruct faithfully without fabrication.
    """
    ws = str(tmp_path / "provenance_reconstruction")
    engine1 = RecoveryEngine(workspace_dir=ws)

    evidence = make_observed_failure_receipt(
        receipt_id="rcpt_fail_provenance",
        task_id="task_prov",
        claim_id="claim_prov_001",
        exit_code=1,
        workspace=ws,
    )
    # Set workspace fingerprint on evidence
    object.__setattr__(evidence, "workspace_fingerprint", "fp_sha256_workspace_state_999")

    record1 = engine1.diagnose_failure(
        task_id="task_prov",
        obligation_id="ob_prov",
        failure_evidence=evidence,
        failure_classification="DRIFT_STALENESS",
        reason="Detected drift in workspace fingerprint",
        parent_event_id="evt_parent_cloud_001",
        staleness_cause="untracked modification to src/core.py",
        claim_id="claim_prov_001",
        project_state_ref="fp_sha256_workspace_state_999",
    )

    ob1 = engine1.create_repair_obligation(record1.recovery_id)

    # Verify provenance on repair obligation
    assert ob1.parent_event_id == "evt_parent_cloud_001"
    assert ob1.staleness_cause == "untracked modification to src/core.py"
    assert ob1.affected_claim_id == "claim_prov_001"
    assert ob1.affected_evidence_id == "rcpt_fail_provenance"
    assert ob1.project_state_ref == "fp_sha256_workspace_state_999"
    assert ob1.failure_classification == "DRIFT_STALENESS"

    # Reconstruct from SQLite in a new RecoveryEngine
    engine2 = RecoveryEngine(workspace_dir=ws)
    record2 = engine2.get_recovery(record1.recovery_id)

    assert record2 is not None
    assert record2.parent_event_id == "evt_parent_cloud_001"
    assert record2.staleness_cause == "untracked modification to src/core.py"
    assert record2.affected_claim_id == "claim_prov_001"
    assert record2.affected_evidence_id == "rcpt_fail_provenance"
    assert record2.project_state_ref == "fp_sha256_workspace_state_999"
    assert record2.failure_classification == "DRIFT_STALENESS"
    assert record2.reason == "Detected drift in workspace fingerprint"

    # Verify repair obligation within record
    reconstructed_ob = record2.current_repair_obligation
    assert reconstructed_ob is not None
    assert reconstructed_ob.parent_event_id == "evt_parent_cloud_001"
    assert reconstructed_ob.staleness_cause == "untracked modification to src/core.py"
    assert reconstructed_ob.affected_claim_id == "claim_prov_001"
    assert reconstructed_ob.affected_evidence_id == "rcpt_fail_provenance"
    assert reconstructed_ob.project_state_ref == "fp_sha256_workspace_state_999"
    assert reconstructed_ob.failure_classification == "DRIFT_STALENESS"


# ==========================================================================
# D9.1.2 CANONICAL VERIFICATION PROVENANCE CLOSURE TESTS
# ==========================================================================

# --------------------------------------------------------------------------
# Test A — Forged Canonical VerificationResult
# --------------------------------------------------------------------------
def test_d9_1_2_test_a_forged_canonical_verification_result_rejected(tmp_path):
    """
    Test A:
    Construct a real S-Class VerificationResult object manually:
    status=ACCEPT, claim_id=<valid claim>, receipt_id=<fake receipt>
    Expected: RECOVERY REJECTED. It must not converge.
    """
    ws = str(tmp_path / "d9_1_2_test_a")
    engine = RecoveryEngine(workspace_dir=ws)

    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_fail_a", claim_id="claim_a", workspace=ws)
    record = engine.diagnose_failure(task_id="task_a", obligation_id="ob_a", failure_evidence=ev_fail, claim_id="claim_a")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Manually constructed real VerificationResult with fake receipt
    forged_verdict = VerificationResult(
        status="ACCEPT",
        claim_id="claim_a",
        receipt_id="rcpt_fake_unanchored_999",
        reason="Manual assertion that everything passed",
    )

    with pytest.raises(RecoveryError, match="Missing authoritative receipt"):
        engine.evaluate_convergence(record.recovery_id, verification_result=forged_verdict)

    # State must not converge
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


# --------------------------------------------------------------------------
# Test B — Forged Canonical Failure Result
# --------------------------------------------------------------------------
def test_d9_1_2_test_b_forged_canonical_failure_result_not_created(tmp_path):
    """
    Test B:
    Construct a real canonical VerificationResult with:
    status=REJECT, receipt_id=<fake receipt>
    Expected: RECOVERY NOT CREATED
    """
    ws = str(tmp_path / "d9_1_2_test_b")
    engine = RecoveryEngine(workspace_dir=ws)

    forged_fail = VerificationResult(
        status="REJECT",
        claim_id="claim_b",
        receipt_id="rcpt_fake_unanchored_fail",
        reason="Manual assertion that tests failed",
    )

    with pytest.raises(RecoveryError, match="Missing authoritative receipt"):
        engine.diagnose_failure(
            task_id="task_b",
            obligation_id="ob_b",
            failure_evidence=forged_fail,
            claim_id="claim_b",
        )

    # Confirm no recovery record was created
    assert len(engine.persistence.load_all()) == 0


# --------------------------------------------------------------------------
# Test C — Unregistered Real Receipt
# --------------------------------------------------------------------------
def test_d9_1_2_test_c_unregistered_real_receipt_rejected(tmp_path):
    """
    Test C:
    Create a real-looking receipt object whose identity is not present in authoritative evidence/ledger state.
    Expected: RECOVERY REJECTED
    """
    ws = str(tmp_path / "d9_1_2_test_c")
    engine = RecoveryEngine(workspace_dir=ws)

    # Real-looking ObservedReceipt without ledger anchoring
    unregistered_ev = make_observed_failure_receipt(
        receipt_id="rcpt_unregistered_fail",
        task_id="task_c",
        claim_id="claim_c",
        workspace=ws,
        anchor_in_ledger=False,
    )

    with pytest.raises(RecoveryError, match="Missing authoritative receipt"):
        engine.diagnose_failure(
            task_id="task_c",
            obligation_id="ob_c",
            failure_evidence=unregistered_ev,
            claim_id="claim_c",
        )

    assert len(engine.persistence.load_all()) == 0


# --------------------------------------------------------------------------
# Test D — Verification Record / Receipt Mismatch
# --------------------------------------------------------------------------
def test_d9_1_2_test_d_verification_record_receipt_mismatch_rejected(tmp_path):
    """
    Test D:
    verification.receipt_id = A, supplied receipt_id = B.
    Expected rejection.
    """
    ws = str(tmp_path / "d9_1_2_test_d")
    engine = RecoveryEngine(workspace_dir=ws)

    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_fail_d", task_id="task_d", claim_id="claim_d", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d", obligation_id="ob_d", failure_evidence=ev_fail, claim_id="claim_d")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Persist verification record with receipt_id = "rcpt_canonical_A" in StateRepository
    rec_a = make_observed_success_receipt(receipt_id="rcpt_canonical_A", task_id="task_d", claim_id="claim_d", workspace=ws)
    make_canonical_verification_result(rec_a, status="ACCEPT", claim_id="claim_d", workspace=ws)

    # Supply receipt_id = "rcpt_different_B" to evaluate_convergence
    rec_b = make_observed_success_receipt(receipt_id="rcpt_different_B", task_id="task_d", claim_id="claim_d", workspace=ws)
    verif_b = VerificationResult(
        status="ACCEPT",
        claim_id="claim_d",
        receipt_id=rec_b.receipt_id,
        reason="Passing with receipt B",
    )

    with pytest.raises(RecoveryError, match="Receipt mismatch"):
        engine.evaluate_convergence(record.recovery_id, verification_result=verif_b)


# --------------------------------------------------------------------------
# Test E — Verification-Event Mismatch
# --------------------------------------------------------------------------
def test_d9_1_2_test_e_verification_event_mismatch_rejected(tmp_path):
    """
    Test E:
    Use canonical-looking verification event with wrong: claim, receipt, result, receipt hash.
    Expected rejection.
    """
    ws = str(tmp_path / "d9_1_2_test_e")
    engine = RecoveryEngine(workspace_dir=ws)

    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_fail_e", claim_id="claim_e", workspace=ws)
    record = engine.diagnose_failure(task_id="task_e", obligation_id="ob_e", failure_evidence=ev_fail, claim_id="claim_e")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    rec_pass = make_observed_success_receipt(receipt_id="rcpt_pass_e", claim_id="claim_e", workspace=ws)
    ledger = LocalLedger(workspace_dir=ws)

    # Subcase 1: Wrong claim in event
    event_wrong_claim = VerificationEvent(
        claim_id="wrong_claim_xyz",
        receipt_id=rec_pass.receipt_id,
        receipt_hash=rec_pass.receipt_hash,
        verifier="test",
        verification_time="2026-09-20T12:00:00Z",
        result="CLAIM_VERIFIED",
        reason="ok",
        repository_fingerprint="",
        previous_ledger_hash=ledger.get_last_hash(),
    )
    verif_wrong_claim = VerificationResult(
        status="ACCEPT",
        claim_id="claim_e",
        receipt_id=rec_pass.receipt_id,
        verification_event=event_wrong_claim,
    )
    with pytest.raises(RecoveryError, match="Verification-event mismatch"):
        engine.evaluate_convergence(record.recovery_id, verification_result=verif_wrong_claim)

    # Subcase 2: Wrong receipt in event
    event_wrong_receipt = VerificationEvent(
        claim_id="claim_e",
        receipt_id="wrong_rcpt_xyz",
        receipt_hash=rec_pass.receipt_hash,
        verifier="test",
        verification_time="2026-09-20T12:00:00Z",
        result="CLAIM_VERIFIED",
        reason="ok",
        repository_fingerprint="",
        previous_ledger_hash=ledger.get_last_hash(),
    )
    verif_wrong_receipt = VerificationResult(
        status="ACCEPT",
        claim_id="claim_e",
        receipt_id=rec_pass.receipt_id,
        verification_event=event_wrong_receipt,
    )
    with pytest.raises(RecoveryError, match="Verification-event mismatch"):
        engine.evaluate_convergence(record.recovery_id, verification_result=verif_wrong_receipt)

    # Subcase 3: Wrong result in event
    event_wrong_res = VerificationEvent(
        claim_id="claim_e",
        receipt_id=rec_pass.receipt_id,
        receipt_hash=rec_pass.receipt_hash,
        verifier="test",
        verification_time="2026-09-20T12:00:00Z",
        result="REJECT",
        reason="ok",
        repository_fingerprint="",
        previous_ledger_hash=ledger.get_last_hash(),
    )
    verif_wrong_res = VerificationResult(
        status="ACCEPT",
        claim_id="claim_e",
        receipt_id=rec_pass.receipt_id,
        verification_event=event_wrong_res,
    )
    with pytest.raises(RecoveryError, match="Verification-event mismatch"):
        engine.evaluate_convergence(record.recovery_id, verification_result=verif_wrong_res)

    # Subcase 4: Wrong receipt hash in event
    event_wrong_hash = VerificationEvent(
        claim_id="claim_e",
        receipt_id=rec_pass.receipt_id,
        receipt_hash="0" * 64,
        verifier="test",
        verification_time="2026-09-20T12:00:00Z",
        result="CLAIM_VERIFIED",
        reason="ok",
        repository_fingerprint="",
        previous_ledger_hash=ledger.get_last_hash(),
    )
    verif_wrong_hash = VerificationResult(
        status="ACCEPT",
        claim_id="claim_e",
        receipt_id=rec_pass.receipt_id,
        verification_event=event_wrong_hash,
    )
    with pytest.raises(RecoveryError, match="Verification-event mismatch"):
        engine.evaluate_convergence(record.recovery_id, verification_result=verif_wrong_hash)


# --------------------------------------------------------------------------
# Test F — Ledger Provenance Absence
# --------------------------------------------------------------------------
def test_d9_1_2_test_f_ledger_provenance_absence_rejected(tmp_path):
    """
    Test F:
    Use a verification object that has a plausible receipt/event but is not anchored in the trusted ledger.
    Expected rejection.
    """
    ws = str(tmp_path / "d9_1_2_test_f")
    engine = RecoveryEngine(workspace_dir=ws)

    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_fail_f", claim_id="claim_f", workspace=ws)
    record = engine.diagnose_failure(task_id="task_f", obligation_id="ob_f", failure_evidence=ev_fail, claim_id="claim_f")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    rec_pass = make_observed_success_receipt(receipt_id="rcpt_pass_f", claim_id="claim_f", workspace=ws)
    # Save to state repo, but DO NOT anchor the event in LocalLedger
    verif = make_canonical_verification_result(
        rec_pass,
        status="ACCEPT",
        claim_id="claim_f",
        workspace=ws,
        anchor_in_ledger=False,
        save_in_state=True,
    )

    with pytest.raises(RecoveryError, match="Unanchored verification event"):
        engine.evaluate_convergence(record.recovery_id, verification_result=verif)


# --------------------------------------------------------------------------
# Test G — Ledger Corruption Fails Closed
# --------------------------------------------------------------------------
def test_d9_1_2_test_g_ledger_corruption_fails_closed(tmp_path):
    """
    Test G:
    Corrupt the authoritative ledger/state required for verification provenance.
    Expected: fail closed, no convergence.
    """
    ws = str(tmp_path / "d9_1_2_test_g")
    engine = RecoveryEngine(workspace_dir=ws)

    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_fail_g", claim_id="claim_g", workspace=ws)
    record = engine.diagnose_failure(task_id="task_g", obligation_id="ob_g", failure_evidence=ev_fail, claim_id="claim_g")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    rec_pass = make_observed_success_receipt(receipt_id="rcpt_pass_g", claim_id="claim_g", workspace=ws)
    verif = make_canonical_verification_result(rec_pass, status="ACCEPT", claim_id="claim_g", workspace=ws)

    # Corrupt the ledger file
    ledger = LocalLedger(workspace_dir=ws)
    for lfile in (ledger.ledger_file, ledger.legacy_ledger_file):
        if os.path.exists(lfile):
            with open(lfile, "a", encoding="utf-8") as f:
                f.write('{"sequence": 999, "event": "CORRUPTED", "hash": "bad"}\n')

    # Evaluating convergence must fail closed
    with pytest.raises(RecoveryError, match="Ledger integrity compromised"):
        engine.evaluate_convergence(record.recovery_id, verification_result=verif)

    # Authoritative state remains unchanged
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


# --------------------------------------------------------------------------
# Test H — Valid Canonical Verification Converges
# --------------------------------------------------------------------------
def test_d9_1_2_test_h_valid_canonical_verification_converges(tmp_path):
    """
    Test H:
    Use the actual existing verification/observation pipeline to produce valid evidence.
    Expected: CONVERGED. This proves the fix does not simply reject everything.
    """
    ws = str(tmp_path / "d9_1_2_test_h")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)

    # 1. Use real pipeline to produce failure evidence
    fail_receipt = create_observed_receipt(
        task_id="task_real_01",
        claim_id="claim_real_01",
        agent="sclass_agent",
        action="run_command",
        workspace=ws,
        command="pytest tests/unit",
        exit_code=1,
        started_at="2026-09-20T12:00:00Z",
        finished_at="2026-09-20T12:00:01Z",
        stdout_content="",
        stderr_content="FAILED tests/unit/test_math.py",
    )
    # Anchor failure receipt in LocalLedger
    ledger = LocalLedger(workspace_dir=ws)
    ledger.append(
        event="OBSERVATION",
        payload={
            "receipt_id": fail_receipt.receipt_id,
            "receipt_hash": fail_receipt.receipt_hash,
            "task_id": "task_real_01",
            "claim_id": "claim_real_01",
            "exit_code": 1,
            "workspace": ws,
        },
    )

    # Initiate recovery from authoritative failure
    record = engine.diagnose_failure(
        task_id="task_real_01",
        obligation_id="ob_real_01",
        failure_evidence=fail_receipt,
        claim_id="claim_real_01",
    )
    assert record.current_state == RecoveryState.DIAGNOSING

    # Advance through repair obligation and start repair
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # 2. Use real pipeline to produce passing ObservedReceipt
    from sclass.verification.engine import verify_claim as verify_canonical_claim
    pass_receipt = create_observed_receipt(
        task_id="task_real_01",
        claim_id="claim_real_01",
        agent="sclass_agent",
        action="run_command",
        workspace=ws,
        command="pytest tests/unit",
        exit_code=0,
        started_at="2026-09-20T12:05:00Z",
        finished_at="2026-09-20T12:05:01Z",
        stdout_content="1 passed in 0.05s",
        stderr_content="",
        execution_kind="test_runner",
        verifier="pytest",
    )
    fp_before = pass_receipt.metadata.get("workspace_fingerprint_before")
    fp_after = pass_receipt.workspace_fingerprint
    ledger.append(
        event="OBSERVATION",
        payload={
            "receipt_id": pass_receipt.receipt_id,
            "receipt_hash": pass_receipt.receipt_hash,
            "fingerprint_before": fp_before,
            "fingerprint_after": fp_after,
            "task_id": "task_real_01",
            "claim_id": "claim_real_01",
            "exit_code": 0,
            "execution_kind": "test_runner",
            "verifier": "pytest",
            "workspace": ws,
        },
    )

    # 3. Use verify_claim from sclass.verification.engine to verify claim
    claim = Claim(
        claim_id="claim_real_01",
        task_id="task_real_01",
        statement="all tests pass clean",
        claim_type="test_pass",
        verifier="pytest",
    )
    verdict = verify_canonical_claim(
        claim=claim,
        evidence=pass_receipt,
        workspace_dir=ws,
        ledger=ledger,
    )
    assert verdict.status == "ACCEPT"

    # Persist verification in StateRepository
    state_repo = StateRepository(workspace_dir=ws)
    if not state_repo.get_project("proj_01"):
        state_repo.save_project(Project(project_id="proj_01", name="Project 01", boundary=ProjectBoundary(root_path=ws)))
    if not state_repo.get_task("task_real_01"):
        state_repo.save_task(Task(task_id="task_real_01", project_id="proj_01", title="Task Real"))
    if not state_repo.get_claim("claim_real_01"):
        state_repo.save_claim(claim)
    state_repo.save_verification(verdict)

    # 4. Evaluate convergence
    res = engine.evaluate_convergence(
        recovery_id=record.recovery_id,
        verification_result=verdict,
        evidence=pass_receipt,
    )
    assert res.is_converged is True
    assert res.status == RecoveryState.CONVERGED.value
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.CONVERGED


# --------------------------------------------------------------------------
# D9.1.3 Test A — Workspace Mismatch Rejected
# --------------------------------------------------------------------------
def test_d9_1_3_test_a_workspace_mismatch_rejected(tmp_path):
    """
    Test A:
    Receipt claims foreign workspace.
    Expected: recovery rejects immediately (fail closed), state unchanged, no convergence.
    """
    target_ws = str(tmp_path / "target_ws")
    foreign_ws = str(tmp_path / "foreign_ws")
    os.makedirs(target_ws, exist_ok=True)
    os.makedirs(foreign_ws, exist_ok=True)

    engine = RecoveryEngine(workspace_dir=target_ws)

    # 1. Foreign workspace in diagnose_failure failure evidence must reject
    fail_ev_foreign = make_observed_failure_receipt(
        receipt_id="rcpt_fail_foreign",
        task_id="task_foreign",
        claim_id="claim_foreign",
        workspace=foreign_ws,
    )
    with pytest.raises(RecoveryError, match="Workspace/project mismatch"):
        engine.diagnose_failure(
            task_id="task_foreign",
            obligation_id="ob_foreign",
            failure_evidence=fail_ev_foreign,
        )

    # 2. Setup a valid recovery cycle in target_ws
    ev_fail = make_observed_failure_receipt(
        receipt_id="rcpt_fail_target",
        task_id="task_target",
        claim_id="claim_target",
        workspace=target_ws,
    )
    record = engine.diagnose_failure(
        task_id="task_target",
        obligation_id="ob_target",
        failure_evidence=ev_fail,
    )
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # 3. Foreign workspace in evaluate_convergence must reject and leave state unchanged
    pass_ev_foreign = make_observed_success_receipt(
        receipt_id="rcpt_pass_foreign",
        task_id="task_target",
        claim_id="claim_target",
        workspace=foreign_ws,
    )
    verdict_foreign = make_canonical_verification_result(
        pass_ev_foreign,
        status="ACCEPT",
        claim_id="claim_target",
        workspace=foreign_ws,
    )
    with pytest.raises(RecoveryError, match="Workspace/project mismatch"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict_foreign,
            evidence=pass_ev_foreign,
        )

    # Invariant: Authoritative state remains unchanged, no convergence
    recovery = engine.get_recovery(record.recovery_id)
    assert recovery.current_state == RecoveryState.REVERIFY_REQUIRED
    assert recovery.current_state != RecoveryState.CONVERGED


# --------------------------------------------------------------------------
# D9.1.3 Test B — Missing Task Binding Rejected
# --------------------------------------------------------------------------
def test_d9_1_3_test_b_missing_task_binding_rejected(tmp_path):
    """
    Test B:
    Observation has no task binding (missing in ledger or receipt object).
    Expected: fails closed immediately, no convergence.
    """
    ws = str(tmp_path / "d9_1_3_test_b")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)

    ev_fail = make_observed_failure_receipt(
        receipt_id="rcpt_fail_b",
        task_id="task_b",
        claim_id="claim_b",
        workspace=ws,
    )
    record = engine.diagnose_failure(
        task_id="task_b",
        obligation_id="ob_b",
        failure_evidence=ev_fail,
    )
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Case B1: Ledger entry lacks task_id
    receipt_pass = make_observed_success_receipt(
        receipt_id="rcpt_pass_b",
        task_id="task_b",
        claim_id="claim_b",
        workspace=ws,
        anchor_in_ledger=False,
    )
    save_receipt(receipt_pass, ws)
    ledger = LocalLedger(workspace_dir=ws)
    ledger.append(
        event="OBSERVATION",
        payload={
            "receipt_id": receipt_pass.receipt_id,
            "receipt_hash": receipt_pass.receipt_hash,
            # task_id omitted
            "claim_id": "claim_b",
            "exit_code": 0,
            "workspace": ws,
        },
    )
    verdict = make_canonical_verification_result(
        receipt_pass,
        status="ACCEPT",
        claim_id="claim_b",
        workspace=ws,
    )

    with pytest.raises(RecoveryError, match="Missing task binding"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=receipt_pass,
        )

    # State unchanged
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


# --------------------------------------------------------------------------
# D9.1.3 Test C — Missing Claim Binding Rejected
# --------------------------------------------------------------------------
def test_d9_1_3_test_c_missing_claim_binding_rejected(tmp_path):
    """
    Test C:
    Observation has no claim binding (missing in ledger or receipt object).
    Expected: fails closed immediately, no convergence.
    """
    ws = str(tmp_path / "d9_1_3_test_c")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)

    ev_fail = make_observed_failure_receipt(
        receipt_id="rcpt_fail_c",
        task_id="task_c",
        claim_id="claim_c",
        workspace=ws,
    )
    record = engine.diagnose_failure(
        task_id="task_c",
        obligation_id="ob_c",
        failure_evidence=ev_fail,
    )
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Case C1: Ledger entry lacks claim_id
    receipt_pass = make_observed_success_receipt(
        receipt_id="rcpt_pass_c",
        task_id="task_c",
        claim_id="claim_c",
        workspace=ws,
        anchor_in_ledger=False,
    )
    save_receipt(receipt_pass, ws)
    ledger = LocalLedger(workspace_dir=ws)
    ledger.append(
        event="OBSERVATION",
        payload={
            "receipt_id": receipt_pass.receipt_id,
            "receipt_hash": receipt_pass.receipt_hash,
            "task_id": "task_c",
            # claim_id omitted
            "exit_code": 0,
            "workspace": ws,
        },
    )
    verdict = make_canonical_verification_result(
        receipt_pass,
        status="ACCEPT",
        claim_id="claim_c",
        workspace=ws,
    )

    with pytest.raises(RecoveryError, match="Missing claim binding"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=receipt_pass,
        )

    # State unchanged
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


# --------------------------------------------------------------------------
# D9.1.3 Test D — Missing Receipt Hash Rejected
# --------------------------------------------------------------------------
def test_d9_1_3_test_d_missing_receipt_hash_rejected(tmp_path):
    """
    Test D:
    Receipt object or ledger entry lacks receipt_hash.
    Expected: fails closed without fallback hashing.
    """
    ws = str(tmp_path / "d9_1_3_test_d")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)

    ev_fail = make_observed_failure_receipt(
        receipt_id="rcpt_fail_d",
        task_id="task_d",
        claim_id="claim_d",
        workspace=ws,
    )
    record = engine.diagnose_failure(
        task_id="task_d",
        obligation_id="ob_d",
        failure_evidence=ev_fail,
    )
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Case D1: Ledger entry lacks receipt_hash
    receipt_pass = make_observed_success_receipt(
        receipt_id="rcpt_pass_d",
        task_id="task_d",
        claim_id="claim_d",
        workspace=ws,
        anchor_in_ledger=False,
    )
    save_receipt(receipt_pass, ws)
    ledger = LocalLedger(workspace_dir=ws)
    ledger.append(
        event="OBSERVATION",
        payload={
            "receipt_id": receipt_pass.receipt_id,
            # receipt_hash omitted
            "task_id": "task_d",
            "claim_id": "claim_d",
            "exit_code": 0,
            "workspace": ws,
        },
    )
    verdict = make_canonical_verification_result(
        receipt_pass,
        status="ACCEPT",
        claim_id="claim_d",
        workspace=ws,
    )

    with pytest.raises(RecoveryError, match="Missing authoritative receipt hash"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=receipt_pass,
        )

    # Case D2: Receipt object lacks receipt_hash
    receipt_pass_nohash = make_observed_success_receipt(
        receipt_id="rcpt_pass_d2",
        task_id="task_d",
        claim_id="claim_d",
        workspace=ws,
        anchor_in_ledger=True,
    )
    receipt_pass_nohash.receipt_hash = None  # strip hash from object
    verdict_d2 = make_canonical_verification_result(
        receipt_pass_nohash,
        status="ACCEPT",
        claim_id="claim_d",
        workspace=ws,
    )
    with pytest.raises(RecoveryError, match="Missing authoritative receipt hash"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict_d2,
            evidence=receipt_pass_nohash,
        )

    # State unchanged
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


# --------------------------------------------------------------------------
# D9.1.3 Test E — Receipt Hash Mismatch Rejected
# --------------------------------------------------------------------------
def test_d9_1_3_test_e_receipt_hash_mismatch_rejected(tmp_path):
    """
    Test E:
    Receipt hash differs from ledger record.
    Expected: fails closed immediately, no convergence.
    """
    ws = str(tmp_path / "d9_1_3_test_e")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)

    ev_fail = make_observed_failure_receipt(
        receipt_id="rcpt_fail_e",
        task_id="task_e",
        claim_id="claim_e",
        workspace=ws,
    )
    record = engine.diagnose_failure(
        task_id="task_e",
        obligation_id="ob_e",
        failure_evidence=ev_fail,
    )
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    receipt_pass = make_observed_success_receipt(
        receipt_id="rcpt_pass_e",
        task_id="task_e",
        claim_id="claim_e",
        workspace=ws,
        anchor_in_ledger=True,
    )
    # Modify receipt_hash on object so it mismatches ledger
    receipt_pass.receipt_hash = "tampered_receipt_hash_value"
    verdict = make_canonical_verification_result(
        receipt_pass,
        status="ACCEPT",
        claim_id="claim_e",
        workspace=ws,
    )

    with pytest.raises(RecoveryError, match="Receipt hash mismatch"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=receipt_pass,
        )

    # State unchanged
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


# --------------------------------------------------------------------------
# D9.1.3 Test F — Valid Canonical Receipt Converges
# --------------------------------------------------------------------------
def test_d9_1_3_test_f_valid_canonical_receipt_converges(tmp_path):
    """
    Test F:
    Valid canonical receipt with matching workspace, task, claim, and receipt hash.
    Expected: CONVERGED. State transitions to CONVERGED.
    """
    ws = str(tmp_path / "d9_1_3_test_f")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)

    # 1. Failure evidence correctly anchored
    ev_fail = make_observed_failure_receipt(
        receipt_id="rcpt_fail_f",
        task_id="task_f",
        claim_id="claim_f",
        workspace=ws,
    )
    record = engine.diagnose_failure(
        task_id="task_f",
        obligation_id="ob_f",
        failure_evidence=ev_fail,
        claim_id="claim_f",
    )
    assert record.current_state == RecoveryState.DIAGNOSING

    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # 2. Success evidence correctly anchored with matching workspace, task, claim, hash
    receipt_pass = make_observed_success_receipt(
        receipt_id="rcpt_pass_f",
        task_id="task_f",
        claim_id="claim_f",
        workspace=ws,
        anchor_in_ledger=True,
    )
    verdict = make_canonical_verification_result(
        receipt_pass,
        status="ACCEPT",
        claim_id="claim_f",
        workspace=ws,
    )

    res = engine.evaluate_convergence(
        record.recovery_id,
        verification_result=verdict,
        evidence=receipt_pass,
    )

    assert res.is_converged is True
    assert res.status == RecoveryState.CONVERGED.value
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.CONVERGED


# ==========================================================================
# D9.2 CANONICAL REGRESSION REASSESSMENT TESTS
# ==========================================================================


def _save_test_claim(state_repo: StateRepository, ws: str, claim: Claim, proj_id: str = "proj_01") -> None:
    if not state_repo.get_project(proj_id):
        state_repo.save_project(Project(project_id=proj_id, name="Project 01", boundary=ProjectBoundary(root_path=ws)))
    if not state_repo.get_task(claim.task_id):
        state_repo.save_task(Task(task_id=claim.task_id, project_id=proj_id, title=f"Task {claim.task_id}"))
    state_repo.save_claim(claim)


def test_d9_2_previously_accepted_claim_affected_by_repair_must_be_reverified(tmp_path):
    """
    Test 1:
    Previously accepted claim affected by repair must be reverified.
    When caller provides no regression verification, convergence fails closed.
    State remains non-terminal (REVERIFY_REQUIRED).
    """
    ws = str(tmp_path / "d9_2_test_1")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    # 1. Previously accepted claim on math.py
    claim_prev = Claim(
        claim_id="claim_prev_01",
        task_id="task_d9_2_1",
        statement="Math utils functions pass",
        target_files=("src/math.py",),
    )
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_prev = make_observed_success_receipt(
        receipt_id="rcpt_prev_01",
        task_id="task_d9_2_1",
        claim_id="claim_prev_01",
        workspace=ws,
    )
    make_canonical_verification_result(rcpt_prev, status="ACCEPT", claim_id="claim_prev_01", workspace=ws)

    # 2. Repair cycle for claim_repair on math.py
    claim_repair = Claim(
        claim_id="claim_repair_01",
        task_id="task_d9_2_1",
        statement="Multiply fix passes",
        target_files=("src/math.py",),
    )
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(
        receipt_id="rcpt_fail_01",
        task_id="task_d9_2_1",
        claim_id="claim_repair_01",
        workspace=ws,
    )
    record = engine.diagnose_failure(
        task_id="task_d9_2_1",
        obligation_id="ob_repair_01",
        failure_evidence=ev_fail,
        claim_id="claim_repair_01",
    )
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # 3. Target claim passes, changed file is src/math.py (which overlaps with claim_prev_01)
    ev_pass = make_observed_success_receipt(
        receipt_id="rcpt_pass_01",
        task_id="task_d9_2_1",
        claim_id="claim_repair_01",
        workspace=ws,
    )
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_repair_01", workspace=ws)

    # Attempting convergence without regression verification must fail closed
    with pytest.raises(RecoveryError, match="Missing required regression verification"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
        )

    # State remains non-terminal
    recovery = engine.get_recovery(record.recovery_id)
    assert recovery.current_state == RecoveryState.REVERIFY_REQUIRED
    assert recovery.current_state != RecoveryState.CONVERGED


def test_d9_2_affected_claim_missing_fresh_verification_rejected(tmp_path):
    """
    Test 2:
    Multiple claims affected, but only a subset provided in regression verification.
    Expected: fails closed on missing required regression verification.
    """
    ws = str(tmp_path / "d9_2_test_2")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    # Two previously accepted claims targeting src/math.py
    claim_a = Claim(claim_id="claim_a", task_id="task_d9_2_2", statement="A", target_files=("src/math.py",))
    claim_b = Claim(claim_id="claim_b", task_id="task_d9_2_2", statement="B", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_a)
    _save_test_claim(state_repo, ws, claim_b)
    rcpt_a = make_observed_success_receipt(receipt_id="rcpt_a", task_id="task_d9_2_2", claim_id="claim_a", workspace=ws)
    rcpt_b = make_observed_success_receipt(receipt_id="rcpt_b", task_id="task_d9_2_2", claim_id="claim_b", workspace=ws)
    make_canonical_verification_result(rcpt_a, status="ACCEPT", claim_id="claim_a", workspace=ws)
    make_canonical_verification_result(rcpt_b, status="ACCEPT", claim_id="claim_b", workspace=ws)

    # Repair cycle
    claim_repair = Claim(claim_id="claim_rep_2", task_id="task_d9_2_2", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_2", task_id="task_d9_2_2", claim_id="claim_rep_2", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_2", obligation_id="ob_rep_2", failure_evidence=ev_fail, claim_id="claim_rep_2")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_2", task_id="task_d9_2_2", claim_id="claim_rep_2", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_2", workspace=ws)

    # Provide regression verification ONLY for claim_a (claim_b missing)
    rcpt_reg_a = make_observed_success_receipt(receipt_id="rcpt_reg_a", task_id="task_d9_2_2", claim_id="claim_a", workspace=ws)
    verif_reg_a = make_canonical_verification_result(rcpt_reg_a, status="ACCEPT", claim_id="claim_a", workspace=ws)

    with pytest.raises(RecoveryError, match="Missing required regression verification.*claim_b"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
            regression_verifications=[verif_reg_a],
        )

    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


def test_d9_2_stale_regression_evidence_rejected(tmp_path):
    """
    Test 3:
    Regression verification has stale evidence.
    Expected: fails closed immediately.
    """
    ws = str(tmp_path / "d9_2_test_3")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    claim_prev = Claim(claim_id="claim_p3", task_id="task_d9_2_3", statement="P3", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_p3 = make_observed_success_receipt(receipt_id="rcpt_p3", task_id="task_d9_2_3", claim_id="claim_p3", workspace=ws)
    make_canonical_verification_result(rcpt_p3, status="ACCEPT", claim_id="claim_p3", workspace=ws)

    claim_repair = Claim(claim_id="claim_rep_3", task_id="task_d9_2_3", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_3", task_id="task_d9_2_3", claim_id="claim_rep_3", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_3", obligation_id="ob_rep_3", failure_evidence=ev_fail, claim_id="claim_rep_3")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_3", task_id="task_d9_2_3", claim_id="claim_rep_3", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_3", workspace=ws)

    # Regression verification flagged as stale
    rcpt_reg = make_observed_success_receipt(receipt_id="rcpt_reg_3", task_id="task_d9_2_3", claim_id="claim_p3", workspace=ws)
    verif_reg = make_canonical_verification_result(
        rcpt_reg,
        status="ACCEPT",
        claim_id="claim_p3",
        invalidation_reason="Evidence is stale: subsequent modifications detected",
        workspace=ws,
    )

    with pytest.raises(RecoveryError, match="Evidence is stale"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
            regression_verifications=[verif_reg],
        )

    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


def test_d9_2_wrong_claim_regression_result_rejected(tmp_path):
    """
    Test 4:
    Regression verification supplied for a claim that is not in the required regression set.
    Expected: fails closed on wrong claim.
    """
    ws = str(tmp_path / "d9_2_test_4")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    claim_prev = Claim(claim_id="claim_p4", task_id="task_d9_2_4", statement="P4", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_p4 = make_observed_success_receipt(receipt_id="rcpt_p4", task_id="task_d9_2_4", claim_id="claim_p4", workspace=ws)
    make_canonical_verification_result(rcpt_p4, status="ACCEPT", claim_id="claim_p4", workspace=ws)

    claim_repair = Claim(claim_id="claim_rep_4", task_id="task_d9_2_4", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_4", task_id="task_d9_2_4", claim_id="claim_rep_4", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_4", obligation_id="ob_rep_4", failure_evidence=ev_fail, claim_id="claim_rep_4")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_4", task_id="task_d9_2_4", claim_id="claim_rep_4", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_4", workspace=ws)

    # Verification has wrong claim_id
    rcpt_wrong = make_observed_success_receipt(receipt_id="rcpt_wrong_4", task_id="task_d9_2_4", claim_id="claim_completely_unrelated", workspace=ws)
    verif_wrong = make_canonical_verification_result(rcpt_wrong, status="ACCEPT", claim_id="claim_completely_unrelated", workspace=ws, save_in_state=False)

    with pytest.raises(RecoveryError, match="Wrong claim regression result"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
            regression_verifications=[verif_wrong],
        )

    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


def test_d9_2_wrong_task_regression_result_rejected(tmp_path):
    """
    Test 5:
    Regression verification supplied for a different task.
    Expected: fails closed on task mismatch.
    """
    ws = str(tmp_path / "d9_2_test_5")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    claim_prev = Claim(claim_id="claim_p5", task_id="task_d9_2_5", statement="P5", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_p5 = make_observed_success_receipt(receipt_id="rcpt_p5", task_id="task_d9_2_5", claim_id="claim_p5", workspace=ws)
    make_canonical_verification_result(rcpt_p5, status="ACCEPT", claim_id="claim_p5", workspace=ws)

    claim_repair = Claim(claim_id="claim_rep_5", task_id="task_d9_2_5", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_5", task_id="task_d9_2_5", claim_id="claim_rep_5", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_5", obligation_id="ob_rep_5", failure_evidence=ev_fail, claim_id="claim_rep_5")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_5", task_id="task_d9_2_5", claim_id="claim_rep_5", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_5", workspace=ws)

    # Verification has wrong task_id
    rcpt_wrong_task = make_observed_success_receipt(receipt_id="rcpt_wt_5", task_id="task_foreign_999", claim_id="claim_p5", workspace=ws)
    verif_wrong_task = make_canonical_verification_result(rcpt_wrong_task, status="ACCEPT", claim_id="claim_p5", workspace=ws)
    object.__setattr__(verif_wrong_task, "task_id", "task_foreign_999") if hasattr(verif_wrong_task, "__dataclass_fields__") else setattr(verif_wrong_task, "task_id", "task_foreign_999")

    with pytest.raises(RecoveryError, match="Task mismatch"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
            regression_verifications=[verif_wrong_task],
        )

    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


def test_d9_2_forged_unanchored_regression_receipt_rejected(tmp_path):
    """
    Test 6:
    Regression verification references a receipt not anchored in canonical LocalLedger.
    Expected: fails closed on missing authoritative receipt provenance.
    """
    ws = str(tmp_path / "d9_2_test_6")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    claim_prev = Claim(claim_id="claim_p6", task_id="task_d9_2_6", statement="P6", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_p6 = make_observed_success_receipt(receipt_id="rcpt_p6", task_id="task_d9_2_6", claim_id="claim_p6", workspace=ws)
    make_canonical_verification_result(rcpt_p6, status="ACCEPT", claim_id="claim_p6", workspace=ws)

    claim_repair = Claim(claim_id="claim_rep_6", task_id="task_d9_2_6", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_6", task_id="task_d9_2_6", claim_id="claim_rep_6", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_6", obligation_id="ob_rep_6", failure_evidence=ev_fail, claim_id="claim_rep_6")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_6", task_id="task_d9_2_6", claim_id="claim_rep_6", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_6", workspace=ws)

    # Forged regression verification referencing unanchored receipt
    forged_receipt = make_observed_success_receipt(
        receipt_id="rcpt_unanchored_6",
        task_id="task_d9_2_6",
        claim_id="claim_p6",
        workspace=ws,
        anchor_in_ledger=False,
    )
    forged_verif = make_canonical_verification_result(
        forged_receipt,
        status="ACCEPT",
        claim_id="claim_p6",
        workspace=ws,
        anchor_in_ledger=False,
    )

    with pytest.raises(RecoveryError, match="Missing authoritative receipt"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
            regression_verifications=[forged_verif],
        )

    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


def test_d9_2_conflicting_regression_result_rejected(tmp_path):
    """
    Test 7:
    Regression verification has contradictory/failing status (status="REJECT").
    Expected: fails closed on conflicting regression result.
    """
    ws = str(tmp_path / "d9_2_test_7")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    claim_prev = Claim(claim_id="claim_p7", task_id="task_d9_2_7", statement="P7", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_p7 = make_observed_success_receipt(receipt_id="rcpt_p7", task_id="task_d9_2_7", claim_id="claim_p7", workspace=ws)
    make_canonical_verification_result(rcpt_p7, status="ACCEPT", claim_id="claim_p7", workspace=ws)

    claim_repair = Claim(claim_id="claim_rep_7", task_id="task_d9_2_7", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_7", task_id="task_d9_2_7", claim_id="claim_rep_7", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_7", obligation_id="ob_rep_7", failure_evidence=ev_fail, claim_id="claim_rep_7")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_7", task_id="task_d9_2_7", claim_id="claim_rep_7", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_7", workspace=ws)

    # Conflicting/failing regression verification
    rcpt_failing = make_observed_failure_receipt(receipt_id="rcpt_failing_7", task_id="task_d9_2_7", claim_id="claim_p7", workspace=ws)
    verif_failing = make_canonical_verification_result(rcpt_failing, status="REJECT", reason="Regression detected in math.py", claim_id="claim_p7", workspace=ws)

    with pytest.raises(RecoveryError, match="Conflicting regression result"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
            regression_verifications=[verif_failing],
        )

    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


def test_d9_2_unaffected_accepted_claim_preserved_when_no_impact(tmp_path):
    """
    Test 8:
    Previously accepted claim targets an unrelated file with no overlap with repair changed files.
    Expected: canonical dependency evidence establishes no impact; claim is preserved as unaffected
    without requiring regression verification. Reaches CONVERGED.
    """
    ws = str(tmp_path / "d9_2_test_8")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    # Claim targeting unrelated file
    claim_unaffected = Claim(
        claim_id="claim_unaffected_08",
        task_id="task_d9_2_8",
        statement="Database connection works",
        target_files=("src/database.py",),
    )
    _save_test_claim(state_repo, ws, claim_unaffected)
    rcpt_unaff = make_observed_success_receipt(receipt_id="rcpt_unaff_08", task_id="task_d9_2_8", claim_id="claim_unaffected_08", workspace=ws)
    make_canonical_verification_result(rcpt_unaff, status="ACCEPT", claim_id="claim_unaffected_08", workspace=ws)

    # Repair targeting src/math.py
    claim_repair = Claim(
        claim_id="claim_rep_08",
        task_id="task_d9_2_8",
        statement="Fix math",
        target_files=("src/math.py",),
    )
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_08", task_id="task_d9_2_8", claim_id="claim_rep_08", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_8", obligation_id="ob_rep_08", failure_evidence=ev_fail, claim_id="claim_rep_08")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Repair evidence only touches src/math.py (no overlap with src/database.py)
    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_08", task_id="task_d9_2_8", claim_id="claim_rep_08", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_08", workspace=ws)

    # Convergence succeeds without needing regression verification for claim_unaffected_08
    res = engine.evaluate_convergence(
        record.recovery_id,
        verification_result=verdict,
        evidence=ev_pass,
    )

    assert res.is_converged is True
    assert res.status == RecoveryState.CONVERGED.value
    assert "claim_unaffected_08" in res.preserved_obligation_ids
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.CONVERGED


def test_d9_2_restart_preserves_regression_assessment(tmp_path):
    """
    Test 9:
    Regression assessment survives restart and reconstructs faithfully from canonical SQLite state.
    """
    ws = str(tmp_path / "d9_2_test_9")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    claim_prev = Claim(claim_id="claim_p9", task_id="task_d9_2_9", statement="P9", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_p9 = make_observed_success_receipt(receipt_id="rcpt_p9", task_id="task_d9_2_9", claim_id="claim_p9", workspace=ws)
    make_canonical_verification_result(rcpt_p9, status="ACCEPT", claim_id="claim_p9", workspace=ws)

    claim_repair = Claim(claim_id="claim_rep_9", task_id="task_d9_2_9", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_9", task_id="task_d9_2_9", claim_id="claim_rep_9", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_9", obligation_id="ob_rep_9", failure_evidence=ev_fail, claim_id="claim_rep_9")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_9", task_id="task_d9_2_9", claim_id="claim_rep_9", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_9", workspace=ws)

    rcpt_reg = make_observed_success_receipt(receipt_id="rcpt_reg_9", task_id="task_d9_2_9", claim_id="claim_p9", workspace=ws)
    verif_reg = make_canonical_verification_result(rcpt_reg, status="ACCEPT", claim_id="claim_p9", workspace=ws)

    res = engine.evaluate_convergence(
        record.recovery_id,
        verification_result=verdict,
        evidence=ev_pass,
        regression_verifications=[verif_reg],
    )
    assert res.is_converged is True

    # Simulate restart by instantiating fresh RecoveryEngine
    engine_restarted = RecoveryEngine(workspace_dir=ws)
    reloaded_record = engine_restarted.get_recovery(record.recovery_id)

    assert reloaded_record is not None
    assert reloaded_record.current_state == RecoveryState.CONVERGED
    assert reloaded_record.regression_assessment is not None
    assert reloaded_record.regression_assessment.regression_passed is True
    assert "claim_p9" in reloaded_record.regression_assessment.affected_claim_ids
    assert "claim_p9" in reloaded_record.regression_assessment.reverified_claim_ids
    assert len(reloaded_record.regression_assessment.failed_claim_ids) == 0
    assert len(reloaded_record.regression_assessment.stale_claim_ids) == 0
    assert "claim_p9" in reloaded_record.regression_assessment.provenance_references


def test_d9_2_valid_target_and_regression_verification_converges(tmp_path):
    """
    Test 10:
    Both target claim and affected previously accepted claim have valid canonical verification.
    Expected: CONVERGED. Full lifecycle succeeds.
    """
    ws = str(tmp_path / "d9_2_test_10")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    # 1. Previously accepted claim
    claim_prev = Claim(claim_id="claim_p10", task_id="task_d9_2_10", statement="P10", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_p10 = make_observed_success_receipt(receipt_id="rcpt_p10", task_id="task_d9_2_10", claim_id="claim_p10", workspace=ws)
    make_canonical_verification_result(rcpt_p10, status="ACCEPT", claim_id="claim_p10", workspace=ws)

    # 2. Repair cycle
    claim_repair = Claim(claim_id="claim_rep_10", task_id="task_d9_2_10", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_10", task_id="task_d9_2_10", claim_id="claim_rep_10", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_10", obligation_id="ob_rep_10", failure_evidence=ev_fail, claim_id="claim_rep_10")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # 3. Target verification
    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_10", task_id="task_d9_2_10", claim_id="claim_rep_10", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_10", workspace=ws)

    # 4. Valid canonical regression verification
    rcpt_reg = make_observed_success_receipt(receipt_id="rcpt_reg_10", task_id="task_d9_2_10", claim_id="claim_p10", workspace=ws)
    verif_reg = make_canonical_verification_result(rcpt_reg, status="ACCEPT", claim_id="claim_p10", workspace=ws)

    # 5. Evaluate convergence with valid regression verification
    res = engine.evaluate_convergence(
        record.recovery_id,
        verification_result=verdict,
        evidence=ev_pass,
        regression_verifications=[verif_reg],
    )

    assert res.is_converged is True
    assert res.status == RecoveryState.CONVERGED.value
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.CONVERGED
    assert "claim_p10" in res.preserved_obligation_ids
    assert engine.get_recovery(record.recovery_id).regression_assessment.regression_passed is True


# ==========================================================================
# D9.2.1 REPAIR-CYCLE REGRESSION TIMING TESTS
# ==========================================================================


def test_d9_2_1_canonical_old_accept_reused_after_repair_rejected(tmp_path):
    """
    D9.2.1 Test 1:
    A historically valid canonical ACCEPT from before the current repair cycle
    is reused as regression verification.
    Expected: fails closed (rejected), state remains REVERIFY_REQUIRED.
    """
    ws = str(tmp_path / "d9_2_1_test_1")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    # 1. Previously accepted claim, verified in the past
    claim_prev = Claim(claim_id="claim_p_old", task_id="task_d9_2_1_1", statement="Math ok", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_old = make_observed_success_receipt(receipt_id="rcpt_old_1", task_id="task_d9_2_1_1", claim_id="claim_p_old", workspace=ws)
    verif_old = make_canonical_verification_result(rcpt_old, status="ACCEPT", claim_id="claim_p_old", workspace=ws)

    # 2. Repair cycle occurs strictly later
    claim_repair = Claim(claim_id="claim_rep_1", task_id="task_d9_2_1_1", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_1", task_id="task_d9_2_1_1", claim_id="claim_rep_1", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_1_1", obligation_id="ob_rep_1", failure_evidence=ev_fail, claim_id="claim_rep_1")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # 3. Target claim verified
    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_1", task_id="task_d9_2_1_1", claim_id="claim_rep_1", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_1", workspace=ws)

    # Reusing historical verif_old from before repair must be rejected
    with pytest.raises(RecoveryError, match="Stale regression verification"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
            regression_verifications=[verif_old],
        )

    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


def test_d9_2_1_verification_timestamp_missing_rejected(tmp_path):
    """
    D9.2.1 Test 2:
    Regression verification has missing or empty verification timestamp.
    Expected: fails closed on missing verification timestamp.
    """
    ws = str(tmp_path / "d9_2_1_test_2")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    claim_prev = Claim(claim_id="claim_p_m2", task_id="task_d9_2_1_2", statement="P2", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_prev = make_observed_success_receipt(receipt_id="rcpt_p_m2", task_id="task_d9_2_1_2", claim_id="claim_p_m2", workspace=ws)
    make_canonical_verification_result(rcpt_prev, status="ACCEPT", claim_id="claim_p_m2", workspace=ws)

    claim_repair = Claim(claim_id="claim_rep_2", task_id="task_d9_2_1_2", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_2", task_id="task_d9_2_1_2", claim_id="claim_rep_2", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_1_2", obligation_id="ob_rep_2", failure_evidence=ev_fail, claim_id="claim_rep_2")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_2", task_id="task_d9_2_1_2", claim_id="claim_rep_2", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_2", workspace=ws)

    # Regression verification missing timestamp
    rcpt_reg = make_observed_success_receipt(receipt_id="rcpt_reg_2", task_id="task_d9_2_1_2", claim_id="claim_p_m2", workspace=ws)
    verif_no_ts = make_canonical_verification_result(rcpt_reg, status="ACCEPT", claim_id="claim_p_m2", workspace=ws)
    if verif_no_ts.verification_event:
        object.__setattr__(verif_no_ts.verification_event, "verification_time", "")
    verif_no_ts.verification_time = "" if hasattr(verif_no_ts, "verification_time") else None

    with pytest.raises(RecoveryError, match="Missing verification timestamp"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
            regression_verifications=[verif_no_ts],
        )

    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


def test_d9_2_1_verification_before_repair_rejected(tmp_path):
    """
    D9.2.1 Test 3:
    Regression verification has a timestamp before repair started, but is otherwise perfectly canonical.
    Expected: fails closed on pre-repair timestamp.
    """
    ws = str(tmp_path / "d9_2_1_test_3")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    claim_prev = Claim(claim_id="claim_p_b3", task_id="task_d9_2_1_3", statement="P3", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_prev = make_observed_success_receipt(receipt_id="rcpt_p_b3", task_id="task_d9_2_1_3", claim_id="claim_p_b3", workspace=ws)
    make_canonical_verification_result(rcpt_prev, status="ACCEPT", claim_id="claim_p_b3", workspace=ws)

    claim_repair = Claim(claim_id="claim_rep_3", task_id="task_d9_2_1_3", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_3", task_id="task_d9_2_1_3", claim_id="claim_rep_3", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_1_3", obligation_id="ob_rep_3", failure_evidence=ev_fail, claim_id="claim_rep_3")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_3", task_id="task_d9_2_1_3", claim_id="claim_rep_3", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_3", workspace=ws)

    # Canonical verification but with timestamp before repair
    rcpt_reg = make_observed_success_receipt(receipt_id="rcpt_reg_3", task_id="task_d9_2_1_3", claim_id="claim_p_b3", workspace=ws)
    verif_before = make_canonical_verification_result(rcpt_reg, status="ACCEPT", claim_id="claim_p_b3", workspace=ws)
    old_iso = "2020-01-01T00:00:00+00:00"
    if verif_before.verification_event:
        object.__setattr__(verif_before.verification_event, "verification_time", old_iso)
    if hasattr(verif_before, "verification_time"):
        verif_before.verification_time = old_iso

    with pytest.raises(RecoveryError, match="Stale regression verification"):
        engine.evaluate_convergence(
            record.recovery_id,
            verification_result=verdict,
            evidence=ev_pass,
            regression_verifications=[verif_before],
        )

    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REVERIFY_REQUIRED


def test_d9_2_1_verification_after_repair_accepted(tmp_path):
    """
    D9.2.1 Test 4:
    Regression verification has valid canonical verification with timestamp strictly after repair.
    Expected: CONVERGED.
    """
    ws = str(tmp_path / "d9_2_1_test_4")
    os.makedirs(ws, exist_ok=True)
    engine = RecoveryEngine(workspace_dir=ws)
    state_repo = StateRepository(workspace_dir=ws)

    claim_prev = Claim(claim_id="claim_p_a4", task_id="task_d9_2_1_4", statement="P4", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_prev)
    rcpt_prev = make_observed_success_receipt(receipt_id="rcpt_p_a4", task_id="task_d9_2_1_4", claim_id="claim_p_a4", workspace=ws)
    make_canonical_verification_result(rcpt_prev, status="ACCEPT", claim_id="claim_p_a4", workspace=ws)

    claim_repair = Claim(claim_id="claim_rep_4", task_id="task_d9_2_1_4", statement="Rep", target_files=("src/math.py",))
    _save_test_claim(state_repo, ws, claim_repair)
    ev_fail = make_observed_failure_receipt(receipt_id="rcpt_f_4", task_id="task_d9_2_1_4", claim_id="claim_rep_4", workspace=ws)
    record = engine.diagnose_failure(task_id="task_d9_2_1_4", obligation_id="ob_rep_4", failure_evidence=ev_fail, claim_id="claim_rep_4")
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    ev_pass = make_observed_success_receipt(receipt_id="rcpt_p_4", task_id="task_d9_2_1_4", claim_id="claim_rep_4", workspace=ws)
    ev_pass.files_changed = ["src/math.py"]
    verdict = make_canonical_verification_result(ev_pass, status="ACCEPT", claim_id="claim_rep_4", workspace=ws)

    # Fresh regression verification after repair
    rcpt_reg = make_observed_success_receipt(receipt_id="rcpt_reg_4", task_id="task_d9_2_1_4", claim_id="claim_p_a4", workspace=ws)
    verif_after = make_canonical_verification_result(rcpt_reg, status="ACCEPT", claim_id="claim_p_a4", workspace=ws)

    res = engine.evaluate_convergence(
        record.recovery_id,
        verification_result=verdict,
        evidence=ev_pass,
        regression_verifications=[verif_after],
    )

    assert res.is_converged is True
    assert res.status == RecoveryState.CONVERGED.value
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.CONVERGED
    assert "claim_p_a4" in res.preserved_obligation_ids
    assert engine.get_recovery(record.recovery_id).regression_assessment.regression_passed is True
