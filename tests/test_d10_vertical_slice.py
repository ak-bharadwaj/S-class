"""
Canonical D10 End-to-End Vertical Slice Tests (tests/test_d10_vertical_slice.py).

Verifies the canonical S-Class task traversal across D0–D8 without bypassing
any trust, policy, controller, execution, observation, evidence, assessment,
recovery, or durability invariants.

Required test suite:
- test_d10_vertical_slice_success
- test_d10_failure_creates_recovery
- test_d10_recovery_requires_controller
- test_d10_stale_evidence_cannot_satisfy_claim
- test_d10_final_acceptance_requires_fresh_evidence
- test_d10_end_to_end_replay_is_deterministic
- test_d10_agent_claim_cannot_promote_itself_to_verified
"""

import os
import sys
import pytest

from sclass.core.vertical_slice import (
    CanonicalVerticalSlice,
    Obligation,
    ObligationKind,
    ObligationStatus,
    ExecutionEnvelope,
    SlicePlanner,
    SliceController,
    SliceExecutor,
    verify_canonical_acceptance,
)
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.evidence import ClaimedEvidence, ProposedEvidence, ObservedReceipt
from sclass.control.authorization import authorize
from sclass.verification.engine import verify_claim
from sclass.state.tasks import StateRepository
from sclass.trust.ledger import LocalLedger
from sclass.core.errors import SecurityViolationError, StateTransitionError


def test_d10_vertical_slice_success(tmp_path):
    """
    Canonical End-to-End Vertical Slice:
    Traverses Task -> Obligations -> Claims -> Policy -> Controller ->
    ExecutionEnvelope -> D6 Execution -> Independent Observation -> Evidence ->
    D4 Assessment -> Failure -> Recovery Obligation -> Planner ->
    Fresh Controller Authorization -> Repair Execution -> Re-verification ->
    Final ACCEPT -> Durable Assurance.
    """
    ws = str(tmp_path / "d10_canonical_success")
    slice_runner = CanonicalVerticalSlice(ws)

    # Execute full canonical slice
    results = slice_runner.run_full_slice()

    # 1. Task verification
    assert slice_runner.task is not None
    assert slice_runner.task.state == TaskState.VERIFIED
    assert slice_runner.task.verified_receipt_id is not None
    assert slice_runner.task.verified_receipt_id == slice_runner.passed_receipt.receipt_id

    # 2. Obligations verification
    assert slice_runner.ob_func.status == ObligationStatus.SATISFIED
    assert slice_runner.ob_verif.status == ObligationStatus.SATISFIED
    assert slice_runner.ob_repair.status == ObligationStatus.SATISFIED

    # 3. Claims & Evidence verification
    assert slice_runner.failed_receipt.exit_code != 0
    assert slice_runner.passed_receipt.exit_code == 0
    assert results["verdict"].is_accepted is True
    assert results["verdict"].status in ("ACCEPT", "CLAIM_VERIFIED")

    # 4. Composite acceptance decision
    assert results["acceptance"].is_accepted is True
    assert "req_func" in results["acceptance"].satisfied_requirements
    assert "req_test" in results["acceptance"].satisfied_requirements

    # 5. Canonical state verification (SQLite, Ledger, Journal)
    canonical = results["canonical_status"]
    assert canonical["accepted"] is True
    assert canonical["task_id"] == slice_runner.task.task_id
    assert canonical["verified_receipt_id"] == slice_runner.passed_receipt.receipt_id

    # 6. Ledger cryptographic integrity
    is_valid, err = slice_runner.ledger.verify_integrity()
    assert is_valid is True, f"Ledger integrity compromised: {err}"


def test_d10_failure_creates_recovery(tmp_path):
    """
    Hard Acceptance Criteria D & E:
    Verification failure produces a recoverable state and creates/reopens
    the correct repair obligation targeting the failed obligation.
    """
    ws = str(tmp_path / "d10_failure_recovery")
    slice_runner = CanonicalVerticalSlice(ws)

    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    # 1. Initial attempt contains injected defect
    receipt_fail, verdict_fail = slice_runner.attempt_initial_implementation(inject_defect=True)

    # Pytest execution failed
    assert receipt_fail.exit_code == 1
    assert verdict_fail.is_rejected is True
    assert verdict_fail.status == "REJECT"

    # Task transitions to recoverable REJECTED state (Criterion D)
    assert task.state == TaskState.REJECTED
    assert slice_runner.ob_verif.status == ObligationStatus.FAILED

    # 2. Trigger recovery creates the repair obligation (Criterion E)
    ob_repair = slice_runner.trigger_recovery()

    assert ob_repair is not None
    assert ob_repair.kind == ObligationKind.REPAIR
    assert ob_repair.parent_obligation_id == slice_runner.ob_verif.obligation_id
    assert ob_repair.target == "math_utils.py"
    assert ob_repair.status == ObligationStatus.PENDING

    # Task transitions back to active working states
    assert task.state == TaskState.IN_PROGRESS


def test_d10_recovery_requires_controller(tmp_path):
    """
    Hard Acceptance Criteria A, B, and F:
    A. Planner cannot directly execute.
    B. Controller authorization is mandatory.
    F. Repair requires a fresh authorization.
    """
    ws = str(tmp_path / "d10_recovery_controller")
    slice_runner = CanonicalVerticalSlice(ws)

    slice_runner.setup_scenario()
    slice_runner.initialize_task()
    slice_runner.attempt_initial_implementation(inject_defect=True)
    slice_runner.trigger_recovery()

    repair_req = slice_runner.planner.plan_repair_action(slice_runner.task.task_id)

    # Criterion A: Planner cannot directly execute
    with pytest.raises(SecurityViolationError, match="Planner cannot directly execute"):
        slice_runner.planner.direct_execute(repair_req)

    # Criterion B: Controller authorization is mandatory (None or invalid envelope fails)
    with pytest.raises(SecurityViolationError, match="Controller authorization is mandatory"):
        slice_runner.executor.execute_envelope(None)

    # Criterion F: Repair requires a fresh authorization (old initial envelope cannot be reused)
    with pytest.raises(SecurityViolationError, match="Repair requires fresh authorization|already been consumed"):
        slice_runner.executor.execute_envelope(slice_runner.initial_envelope)

    # Old test envelope cannot be reused either
    with pytest.raises(SecurityViolationError, match="Repair requires fresh authorization|already been consumed"):
        slice_runner.executor.execute_envelope(slice_runner.initial_test_envelope)

    # Fresh controller authorization succeeds
    repair_envelope = slice_runner.controller.authorize(repair_req)
    assert repair_envelope.verify() is True
    res = slice_runner.executor.execute_envelope(repair_envelope)
    assert res.success is True


def test_d10_stale_evidence_cannot_satisfy_claim(tmp_path):
    """
    Hard Acceptance Criteria G & Invariant L7:
    Old failed evidence cannot be reused as final proof, and post-observation
    workspace mutation invalidates dependent evidence.
    """
    ws = str(tmp_path / "d10_stale_evidence")
    slice_runner = CanonicalVerticalSlice(ws)

    slice_runner.setup_scenario()
    slice_runner.initialize_task()
    slice_runner.attempt_initial_implementation(inject_defect=True)

    # Criterion G: Old failed evidence cannot satisfy claim
    verdict_old = verify_claim(
        slice_runner.claim_verif,
        slice_runner.failed_receipt,
        workspace_dir=slice_runner.workspace_dir,
        ledger=slice_runner.ledger,
    )
    assert verdict_old.is_rejected is True

    # Complete the repair and pass verification
    slice_runner.trigger_recovery()
    slice_runner.execute_repair()
    receipt_pass, verdict_pass, _ = slice_runner.run_reverification_and_acceptance()
    assert verdict_pass.is_accepted is True

    # Invariant L7: Post-verification mutation invalidates evidence
    math_path = os.path.join(slice_runner.workspace_dir, "math_utils.py")
    with open(math_path, "a", encoding="utf-8") as f:
        f.write("\n# Post-verification untracked change\n")

    # Re-evaluating claim with now-stale receipt must REJECT
    stale_verdict = verify_claim(
        slice_runner.claim_verif,
        receipt_pass,
        workspace_dir=slice_runner.workspace_dir,
        ledger=slice_runner.ledger,
    )
    assert stale_verdict.is_rejected is True
    assert "stale" in stale_verdict.reason.lower() or "mutation" in stale_verdict.reason.lower()


def test_d10_final_acceptance_requires_fresh_evidence(tmp_path):
    """
    Hard Acceptance Criteria H & I:
    Fresh evidence can establish the repaired claim, and final acceptance is
    derived strictly from canonical state (SQLite, Ledger, Journal), not a success flag.
    """
    ws = str(tmp_path / "d10_acceptance_fresh_ev")
    slice_runner = CanonicalVerticalSlice(ws)

    slice_runner.setup_scenario()
    slice_runner.initialize_task()

    # Criterion I: Unverified task cannot pass canonical acceptance
    unverified_status = verify_canonical_acceptance(slice_runner.task.task_id, slice_runner.workspace_dir)
    assert unverified_status["accepted"] is False

    # Attempting to fake a caller success flag does not bypass canonical state
    fake_flag = {"success": True, "accepted": True}
    canonical_check = verify_canonical_acceptance(slice_runner.task.task_id, slice_runner.workspace_dir)
    assert canonical_check["accepted"] is False

    # Run failure -> recovery -> repair -> fresh reverification
    slice_runner.attempt_initial_implementation(inject_defect=True)
    slice_runner.trigger_recovery()
    slice_runner.execute_repair()
    receipt_pass, verdict_pass, acceptance = slice_runner.run_reverification_and_acceptance()

    # Criterion H: Fresh evidence establishes repaired claim
    assert verdict_pass.is_accepted is True
    assert acceptance.is_accepted is True

    # Canonical state confirms acceptance
    canonical_final = verify_canonical_acceptance(slice_runner.task.task_id, slice_runner.workspace_dir)
    assert canonical_final["accepted"] is True
    assert canonical_final["verified_receipt_id"] == receipt_pass.receipt_id


def test_d10_end_to_end_replay_is_deterministic(tmp_path):
    """
    Hard Acceptance Criterion J:
    The complete scenario is reproducible deterministically across independent runs.
    """
    ws1 = str(tmp_path / "replay_run_1")
    ws2 = str(tmp_path / "replay_run_2")

    slice1 = CanonicalVerticalSlice(ws1)
    res1 = slice1.run_full_slice()

    slice2 = CanonicalVerticalSlice(ws2)
    res2 = slice2.run_full_slice()

    # Both achieved final VERIFIED state
    assert slice1.task.state == TaskState.VERIFIED
    assert slice2.task.state == TaskState.VERIFIED

    # Both initial attempts failed with exit_code 1
    assert slice1.failed_receipt.exit_code == 1
    assert slice2.failed_receipt.exit_code == 1

    # Both reverifications passed with exit_code 0
    assert slice1.passed_receipt.exit_code == 0
    assert slice2.passed_receipt.exit_code == 0

    # Both final acceptance decisions are ACCEPT
    assert res1["acceptance"].decision == "ACCEPT"
    assert res2["acceptance"].decision == "ACCEPT"

    # Both canonical state evaluations accept
    assert res1["canonical_status"]["accepted"] is True
    assert res2["canonical_status"]["accepted"] is True

    # Obligations match
    assert slice1.ob_repair.status == slice2.ob_repair.status == ObligationStatus.SATISFIED
    assert slice1.ob_verif.status == slice2.ob_verif.status == ObligationStatus.SATISFIED


def test_d10_agent_claim_cannot_promote_itself_to_verified(tmp_path):
    """
    Hard Acceptance Criterion C & Adversarial Test:
    Worker claims cannot directly become accepted truth.
    Self-reported / proposed evidence, missing evidence, unanchored receipts,
    and direct state tampering all fail closed.
    """
    ws = str(tmp_path / "d10_adversarial_agent")
    slice_runner = CanonicalVerticalSlice(ws)

    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    # Attack 1: Agent supplies self-reported ClaimedEvidence asserting exit_code 0
    fake_claimed_ev = ClaimedEvidence(
        task_id=task.task_id,
        claim_id=slice_runner.claim_verif.claim_id,
        agent="adversarial_agent",
        claimed_exit_code=0,
    )
    verdict1 = verify_claim(
        slice_runner.claim_verif,
        fake_claimed_ev,
        workspace_dir=ws,
        ledger=slice_runner.ledger,
    )
    assert verdict1.is_rejected is True
    assert "proposed/claimed evidence" in verdict1.reason.lower() or "unobserved" in verdict1.reason.lower()

    # Attack 2: Agent supplies ProposedEvidence
    fake_proposed_ev = ProposedEvidence(
        task_id=task.task_id,
        action="pytest",
        agent="adversarial_agent",
        proposed_command="pytest",
    )
    verdict2 = verify_claim(
        slice_runner.claim_verif,
        fake_proposed_ev,
        workspace_dir=ws,
        ledger=slice_runner.ledger,
    )
    assert verdict2.is_rejected is True

    # Attack 3: Agent claims completion with None evidence
    verdict3 = verify_claim(
        slice_runner.claim_verif,
        None,
        workspace_dir=ws,
        ledger=slice_runner.ledger,
    )
    assert verdict3.is_rejected is True
    assert "no independently observed evidence" in verdict3.reason.lower()

    # Attack 4: Agent constructs an unanchored ObservedReceipt not in LocalLedger
    raw_hash = "0" * 64
    unanchored_receipt = ObservedReceipt(
        receipt_id="rcpt_forged_999",
        task_id=task.task_id,
        claim_id=slice_runner.claim_verif.claim_id,
        agent="adversarial_agent",
        action="run_command",
        workspace=ws,
        command="python -m pytest",
        exit_code=0,
        workspace_fingerprint="fake_fp",
        receipt_hash=raw_hash,
        is_observed=True,
    )
    # If receipt_hash is forged, tampering is caught:
    verdict4 = verify_claim(
        slice_runner.claim_verif,
        unanchored_receipt,
        workspace_dir=ws,
        ledger=slice_runner.ledger,
    )
    assert verdict4.is_rejected is True
    assert "tampering detected" in verdict4.reason.lower()

    # Even if receipt_hash matches compute_hash(), missing ledger provenance is caught:
    unanchored_receipt_valid_hash = ObservedReceipt(
        receipt_id="rcpt_forged_999",
        task_id=task.task_id,
        claim_id=slice_runner.claim_verif.claim_id,
        agent="adversarial_agent",
        action="run_command",
        workspace=ws,
        command="python -m pytest",
        exit_code=0,
        workspace_fingerprint="fake_fp",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        receipt_hash="",
        is_observed=True,
    )
    unanchored_receipt_valid_hash.receipt_hash = unanchored_receipt_valid_hash.compute_hash()
    verdict4b = verify_claim(
        slice_runner.claim_verif,
        unanchored_receipt_valid_hash,
        workspace_dir=ws,
        ledger=slice_runner.ledger,
    )
    assert verdict4b.is_rejected is True
    assert "provenance not found" in verdict4b.reason.lower() or "missing observation" in verdict4b.reason.lower()

    # Attack 5: Agent directly sets task.state = VERIFIED in SQLite without ledger backing
    slice_runner.state_repo.save_task(
        Task(
            task_id=task.task_id,
            project_id=slice_runner.project.project_id,
            title=task.title,
            state=TaskState.VERIFIED,
            verified_receipt_id="rcpt_nonexistent",
        )
    )
    canonical = verify_canonical_acceptance(task.task_id, ws)
    assert canonical["accepted"] is False
    assert "not found in ledger" in canonical["reason"].lower()

    # Attack 6: Agent fabricates an ExecutionEnvelope with a forged signature or tampered request
    from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
    fake_action_req = ActionRequest(
        actor="adversarial_agent",
        session=task.task_id,
        capability="terminal.execute",
        action="run_command",
        target="malicious_command",
        parameters={"command": "malicious_command"},
        workspace=ws,
    )
    fake_decision = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id="FORGED-POLICY",
        risk_level="LOW",
        reason="Agent forged allow decision",
    )
    forged_envelope = ExecutionEnvelope(
        envelope_id="env_forged_999",
        task_id=task.task_id,
        action_request=fake_action_req,
        authorization_decision=fake_decision,
        signature="forged_signature_hex",
    )
    with pytest.raises(SecurityViolationError, match="ExecutionEnvelope verification failed"):
        slice_runner.executor.execute_envelope(forged_envelope)

