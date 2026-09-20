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
"""

import os
import json
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


class MockFailureEvidence:
    """Mock failure evidence with authentic failure exit code."""
    def __init__(self, exit_code: int = 1, receipt_id: str = "rcpt_fail_001"):
        self.exit_code = exit_code
        self.receipt_id = receipt_id
        self.is_verified = False
        self.reason = "Process exited with code 1"


class MockVerifiedEvidence:
    """Mock verification evidence with authentic passing verdict."""
    def __init__(self, receipt_id: str = "rcpt_pass_001", is_stale: bool = False):
        self.exit_code = 0
        self.receipt_id = receipt_id
        self.is_verified = True
        self.is_stale = is_stale
        self.reason = "All 2 tests passed successfully"


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

    # 1. Diagnose failure -> enters DIAGNOSING
    evidence = MockFailureEvidence(exit_code=2)
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
            verification_result=VerificationResult(status="ACCEPT"),
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
    # Bound max attempts to 2
    engine = RecoveryEngine(workspace_dir=ws, default_max_attempts=2)

    evidence = MockFailureEvidence(exit_code=1)
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
    failed_res1 = VerificationResult(status="REJECT", reason="Still failing")
    res1 = engine.evaluate_convergence(record.recovery_id, verification_result=failed_res1)
    assert res1.is_converged is False
    assert res1.status == RecoveryState.REPAIR_REQUIRED.value

    # Attempt 2
    ob2 = engine.create_repair_obligation(record.recovery_id)
    assert ob2.attempt_number == 2
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Attempt 2 fails verification -> attempt limit (2) reached -> RECOVERY_EXHAUSTED
    failed_res2 = VerificationResult(status="REJECT", reason="Still failing on attempt 2")
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

    evidence = MockFailureEvidence(exit_code=1)
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
        verification_result=VerificationResult(status="REJECT", reason="Fix incomplete"),
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

    evidence = MockFailureEvidence(exit_code=1)
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
    failed_verdict = VerificationResult(status="REJECT", reason="Defect still present")
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

    evidence = MockFailureEvidence(exit_code=1)
    record = engine.diagnose_failure(
        task_id="task_005",
        obligation_id="ob_func_multiply",
        failure_evidence=evidence,
    )
    engine.create_repair_obligation(record.recovery_id, target="math_utils.py")
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    # Known accepted obligations in project:
    # - ob_func_add: unrelated, unaffected obligation
    # - ob_config: unrelated, unaffected obligation
    known_accepted = ["ob_func_add", "ob_config"]

    # Provide authentic passing verification
    passing_verdict = VerificationResult(
        status="ACCEPT",
        claim_id="claim_repaired_multiply",
        reason="Multiply tests pass 100%",
        receipt_id="rcpt_pass_multiply",
    )

    res = engine.evaluate_convergence(
        recovery_id=record.recovery_id,
        verification_result=passing_verdict,
        evidence=MockVerifiedEvidence(receipt_id="rcpt_pass_multiply"),
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
    Corrupt the authoritative recovery record.
    Expected: recovery operation fails closed (RecoveryPersistenceError), no fabricated state is accepted.
    """
    ws = str(tmp_path / "d9_test_f")
    engine = RecoveryEngine(workspace_dir=ws)

    evidence = MockFailureEvidence(exit_code=1)
    record = engine.diagnose_failure(
        task_id="task_006",
        obligation_id="ob_func_006",
        failure_evidence=evidence,
    )
    engine.create_repair_obligation(record.recovery_id)

    # Corrupt the recoveries.jsonl file with malformed JSON
    rec_file = engine.persistence.recoveries_file
    with open(rec_file, "a", encoding="utf-8") as f:
        f.write("CORRUPTED_JSON_DATA_GARBAGE_LINE\n")

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

    evidence = MockFailureEvidence(exit_code=1)
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
    pass_verdict = VerificationResult(status="ACCEPT", reason="Verified")
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

    evidence = MockFailureEvidence(exit_code=1)
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
        status="ACCEPT",  # Even if status claims accept
        invalidation_reason="Claim rejected: Evidence is stale. Workspace mutation detected.",
        reason="Tests passed but files changed afterwards",
    )

    res1 = engine.evaluate_convergence(record.recovery_id, verification_result=stale_verdict)
    assert res1.is_converged is False
    # Stale evidence forces return to REPAIR_REQUIRED
    assert res1.status == RecoveryState.REPAIR_REQUIRED.value

    # Case 2: Evidence object itself is flagged as stale
    engine.create_repair_obligation(record.recovery_id)
    engine.start_repair(record.recovery_id)
    engine.submit_for_reverification(record.recovery_id)

    stale_ev = MockVerifiedEvidence(is_stale=True)
    normal_verdict = VerificationResult(status="ACCEPT", reason="Passed")

    res2 = engine.evaluate_convergence(
        record.recovery_id,
        verification_result=normal_verdict,
        evidence=stale_ev,
    )
    assert res2.is_converged is False
    assert res2.status == RecoveryState.REPAIR_REQUIRED.value
    assert engine.get_recovery(record.recovery_id).current_state == RecoveryState.REPAIR_REQUIRED
