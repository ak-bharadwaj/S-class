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
"""

import os
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
from sclass.domain.verification import VerificationResult
from sclass.survival.models import ObservedReceipt, EvidenceReceipt


def make_observed_failure_receipt(
    receipt_id: str = "rcpt_fail_001",
    task_id: str = "",
    claim_id: str = "",
    exit_code: int = 1,
    command: str = "pytest tests/",
    workspace: str = "/tmp/ws",
) -> ObservedReceipt:
    return ObservedReceipt(
        receipt_id=receipt_id,
        task_id=task_id,
        claim_id=claim_id,
        agent="test_agent",
        action="execute",
        workspace=workspace,
        command=command,
        exit_code=exit_code,
    )


def make_observed_success_receipt(
    receipt_id: str = "rcpt_pass_001",
    task_id: str = "",
    claim_id: str = "",
    command: str = "pytest tests/",
    workspace: str = "/tmp/ws",
) -> ObservedReceipt:
    return ObservedReceipt(
        receipt_id=receipt_id,
        task_id=task_id,
        claim_id=claim_id,
        agent="test_agent",
        action="execute",
        workspace=workspace,
        command=command,
        exit_code=0,
    )


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

    evidence = make_observed_failure_receipt(exit_code=2)
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

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_002", exit_code=1)
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
    failed_res1 = VerificationResult(status="REJECT", receipt_id="rcpt_fail_002", reason="Still failing")
    res1 = engine.evaluate_convergence(record.recovery_id, verification_result=failed_res1)
    assert res1.is_converged is False
    assert res1.status == RecoveryState.REPAIR_REQUIRED.value

    # Attempt 2
    ob2 = engine.create_repair_obligation(record.recovery_id)
    assert ob2.attempt_number == 2
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Attempt 2 fails verification -> attempt limit (2) reached -> RECOVERY_EXHAUSTED
    failed_res2 = VerificationResult(status="REJECT", receipt_id="rcpt_fail_002", reason="Still failing on attempt 2")
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

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_003", exit_code=1)
    record = engine1.diagnose_failure(
        task_id="task_003",
        obligation_id="ob_func_003",
        failure_evidence=evidence,
    )
    # Attempt 1
    engine1.create_repair_obligation(record.recovery_id)
    engine1.start_repair(record.recovery_id)
    engine1.submit_for_reverification(record.recovery_id)
    engine1.evaluate_convergence(
        record.recovery_id,
        verification_result=VerificationResult(status="REJECT", receipt_id="rcpt_fail_003", reason="Fix incomplete"),
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

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_004", exit_code=1)
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
    failed_verdict = VerificationResult(status="REJECT", receipt_id="rcpt_fail_004", reason="Defect still present")
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

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_005", exit_code=1)
    record = engine.diagnose_failure(
        task_id="task_005",
        obligation_id="ob_func_multiply",
        failure_evidence=evidence,
    )
    engine.create_repair_obligation(record.recovery_id, target="math_utils.py")
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Known accepted obligations in project:
    known_accepted = ["ob_func_add", "ob_config"]

    # Provide authentic passing verification and observed evidence
    passing_verdict = VerificationResult(
        status="ACCEPT",
        claim_id="claim_repaired_multiply",
        reason="Multiply tests pass 100%",
        receipt_id="rcpt_pass_multiply",
    )
    passing_evidence = make_observed_success_receipt(
        receipt_id="rcpt_pass_multiply",
        claim_id="claim_repaired_multiply",
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

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_006", exit_code=1)
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

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_007", exit_code=1)
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
    pass_verdict = VerificationResult(status="ACCEPT", receipt_id="rcpt_pass_007", reason="Verified")
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

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_008", exit_code=1)
    record = engine.diagnose_failure(
        task_id="task_008",
        obligation_id="ob_func_008",
        failure_evidence=evidence,
    )
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Case 1: VerificationResult reports invalidation due to staleness
    stale_verdict = VerificationResult(
        status="ACCEPT",
        receipt_id="rcpt_pass_008",
        invalidation_reason="Claim rejected: Evidence is stale. Workspace mutation detected.",
        reason="Tests passed but files changed afterwards",
    )

    res1 = engine.evaluate_convergence(record.recovery_id, verification_result=stale_verdict)
    assert res1.is_converged is False
    assert res1.status == RecoveryState.REPAIR_REQUIRED.value

    # Case 2: Evidence object itself is flagged as stale
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    stale_ev = make_observed_success_receipt(receipt_id="rcpt_pass_008_fresh")
    # Mark as stale
    object.__setattr__(stale_ev, "is_stale", True) if hasattr(stale_ev, "__dataclass_fields__") else setattr(stale_ev, "is_stale", True)

    normal_verdict = VerificationResult(status="ACCEPT", receipt_id="rcpt_pass_008_fresh", reason="Passed")

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

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_real", exit_code=1)
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
    valid_verdict = VerificationResult(status="ACCEPT", receipt_id="rcpt_unobserved_pass")
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
    ev_mismatch = make_observed_failure_receipt(receipt_id="rcpt_fail_mismatch", claim_id="claim_X", exit_code=1)
    with pytest.raises(RecoveryError, match="Claim/obligation mismatch"):
        engine.diagnose_failure(
            task_id="task_01",
            obligation_id="ob_01",
            failure_evidence=ev_mismatch,
            claim_id="claim_Y",
        )

    # 2. Start valid recovery bound to claim_id="claim_A"
    ev_valid = make_observed_failure_receipt(receipt_id="rcpt_fail_a", claim_id="claim_A", exit_code=1)
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
    verdict_mismatch = VerificationResult(
        status="ACCEPT",
        claim_id="claim_B",
        receipt_id="rcpt_pass_b",
    )
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
    empty_rcpt_ev = make_observed_failure_receipt(receipt_id="", exit_code=1)
    with pytest.raises(RecoveryError, match="Missing receipt/verification provenance"):
        engine.diagnose_failure(
            task_id="task_01",
            obligation_id="ob_01",
            failure_evidence=empty_rcpt_ev,
        )

    # 3. Evaluate convergence with VerificationResult lacking receipt_id
    valid_ev = make_observed_failure_receipt(receipt_id="rcpt_f_valid", exit_code=1)
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
    ev1 = make_observed_failure_receipt(receipt_id="rcpt_fail_cycle_1", exit_code=1)
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
    verdict1 = VerificationResult(status="ACCEPT", receipt_id="rcpt_pass_cycle_1")
    res1 = engine.evaluate_convergence(cycle1_id, verification_result=verdict1)
    assert res1.is_converged is True

    # Cycle 2: later, a different failure occurs for the SAME obligation
    ev2 = make_observed_failure_receipt(receipt_id="rcpt_fail_cycle_2", exit_code=2)
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

    evidence = make_observed_failure_receipt(receipt_id="rcpt_fail_restart", exit_code=1)
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
    engine1.evaluate_convergence(
        rec_id,
        verification_result=VerificationResult(status="REJECT", receipt_id="rcpt_fail_restart", reason="Still broken"),
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
    pass_verdict = VerificationResult(status="ACCEPT", receipt_id="rcpt_pass_restart", reason="Fixed on attempt 2")
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
        claim_id="claim_prov_001",
        exit_code=1,
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
