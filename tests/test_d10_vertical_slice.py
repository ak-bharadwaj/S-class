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
    Enforces deterministic replay at the semantic/canonical-trace level:
    task -> obligations -> claims -> authorized action digests -> observed exit codes ->
    verification verdicts -> recovery transition -> final accepted claim.
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

    # Compare full canonical semantic traces
    trace1 = slice1.get_canonical_trace()
    trace2 = slice2.get_canonical_trace()

    # Exact semantic trace equality across independent runs
    assert trace1 == trace2

    # Verify trace contents
    assert trace1["task"]["final_state"] == "verified"
    assert len(trace1["obligations"]) == 3
    assert len(trace1["claims"]) == 2
    assert len(trace1["authorized_actions"]) == 4

    # Requirement 5: Verify authorized action digests equality and non-empty
    assert len(trace1["authorized_action_digests"]) == 4
    assert trace1["authorized_action_digests"] == trace2["authorized_action_digests"]
    assert all(isinstance(d, str) and len(d) == 64 for d in trace1["authorized_action_digests"])

    # Observed exit codes: first fails (1), recovery passes (0)
    assert trace1["observed_exit_codes"] == [1, 0]
    assert trace1["observed_exit_codes"] == trace2["observed_exit_codes"]
    assert trace1["observed_steps"][0]["exit_code"] == 1
    assert trace1["observed_steps"][0]["verdict_status"] == "REJECT"
    assert trace1["observed_steps"][1]["recovery_obligation_kind"] == "repair"
    assert trace1["observed_steps"][2]["exit_code"] == 0
    assert trace1["observed_steps"][2]["verdict_status"] in ("ACCEPT", "CLAIM_VERIFIED")

    # Verification verdicts sequence
    assert len(trace1["verification_verdicts"]) == 2
    assert trace1["verification_verdicts"] == trace2["verification_verdicts"]
    assert trace1["verification_verdicts"][0]["status"] == "REJECT"
    assert trace1["verification_verdicts"][1]["status"] in ("ACCEPT", "CLAIM_VERIFIED")

    # Recovery transition matches
    assert trace1["recovery_transition"] is not None
    assert trace1["recovery_transition"] == trace2["recovery_transition"]
    assert trace1["recovery_transition"]["recovery_obligation_kind"] == "repair"
    assert trace1["recovery_transition"]["parent_obligation_matches"] is True

    # Final accepted claim
    assert trace1["final_accepted_claim"]["accepted_receipt_exit_code"] == 0
    assert trace1["final_accepted_claim"]["composite_decision"] == "ACCEPT"

    # Both final acceptance decisions are ACCEPT
    assert res1["acceptance"].decision == "ACCEPT"
    assert res2["acceptance"].decision == "ACCEPT"

    # Both canonical state evaluations accept
    assert res1["canonical_status"]["accepted"] is True
    assert res2["canonical_status"]["accepted"] is True


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
    assert (
        "not found in ledger" in canonical["reason"].lower()
        or "no accepted verification" in canonical["reason"].lower()
        or "not found" in canonical["reason"].lower()
    )

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


def test_d10_forged_allow_and_recomputed_envelope_rejected(tmp_path):
    """
    Adversarial Regression 1:
    A caller must NOT be able to construct an ALLOW decision and manufacture
    a valid execution envelope by recomputing a public SHA-256 digest.
    Authority authenticity and cryptographic HMAC integrity are independently verified at D6 boundary.
    """
    import hashlib
    from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
    from sclass.core.vertical_slice import CanonicalVerticalSlice, ExecutionEnvelope

    ws = str(tmp_path / "d10_forged_allow")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    # Adversary constructs forged ALLOW decision without authentic HMAC integrity token
    forged_req = ActionRequest(
        actor="adversary",
        session=task.task_id,
        capability="terminal.execute",
        action="run_command",
        target="echo pwned",
        parameters={"command": "echo pwned"},
        workspace=ws,
    )
    forged_decision = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id="FORGED-ALLOW-001",
        risk_level="low",
        reason="Adversary manufactured allow decision",
        issuer="S_CLASS",
    )

    # Attack 1a: Recompute public SHA-256 digest over envelope payload without authentic HMAC token
    env_id = "env_forged_sha256"
    recomputed_sha256 = hashlib.sha256(
        f"{env_id}:{forged_req.target}:{forged_decision.evaluated_at}".encode("utf-8")
    ).hexdigest()

    forged_env = ExecutionEnvelope(
        envelope_id=env_id,
        task_id=task.task_id,
        action_request=forged_req,
        authorization_decision=forged_decision,
        signature=recomputed_sha256,
    )

    # D6 execution boundary independently rejects the forged artifact
    with pytest.raises(SecurityViolationError, match="ExecutionEnvelope verification failed"):
        slice_runner.executor.execute_envelope(forged_env)

    # Controller validate_and_consume also rejects
    with pytest.raises(SecurityViolationError, match="ExecutionEnvelope verification failed"):
        slice_runner.controller.validate_and_consume(forged_env)

    # Attack 1b: Adversary manufactures decision with fake HMAC integrity token and recomputes envelope SHA-256
    fake_token_decision = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id="FORGED-ALLOW-002",
        risk_level="low",
        reason="Manufactured token",
        issuer="S_CLASS",
        request_hash="a" * 64,
        integrity_token="b" * 64,
    )
    fake_token_env = ExecutionEnvelope(
        envelope_id="env_forged_token",
        task_id=task.task_id,
        action_request=forged_req,
        authorization_decision=fake_token_decision,
        signature=hashlib.sha256(b"fake").hexdigest(),
    )
    with pytest.raises(SecurityViolationError, match="ExecutionEnvelope verification failed"):
        slice_runner.executor.execute_envelope(fake_token_env)
    with pytest.raises(SecurityViolationError, match="ExecutionEnvelope verification failed"):
        slice_runner.controller.validate_and_consume(fake_token_env)

    # Attack 1c: Untrusted issuer fails closed
    fake_issuer_decision = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id="FORGED-ALLOW-003",
        risk_level="low",
        reason="Untrusted issuer",
        issuer="UNTRUSTED_AGENT",
    )
    fake_issuer_env = ExecutionEnvelope(
        envelope_id="env_forged_issuer",
        task_id=task.task_id,
        action_request=forged_req,
        authorization_decision=fake_issuer_decision,
        signature="sig",
    )
    with pytest.raises(SecurityViolationError, match="Untrusted authorization issuer|ExecutionEnvelope verification failed"):
        slice_runner.executor.execute_envelope(fake_issuer_env)


def test_d10_action_tamper_after_authorization_rejected(tmp_path):
    """
    Adversarial Regression 2:
    Changing action parameters, capability, context, action name, target, or actor after controller authorization
    is strictly rejected by the D6 execution boundary.
    Enforces exact action binding and execution-context binding.
    """
    from sclass.domain.action import ActionRequest
    from sclass.core.vertical_slice import CanonicalVerticalSlice, ExecutionEnvelope

    ws = str(tmp_path / "d10_action_tamper")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    # Controller legitimately authorizes an action
    legit_req = slice_runner.planner.plan_verification_action(task.task_id)
    legit_env = slice_runner.controller.authorize(legit_req)
    assert legit_env.verify() is True

    # Attack 2a: Tampering with parameters (e.g. inject malicious command into parameters)
    tampered_params_req = ActionRequest(
        actor=legit_req.actor,
        session=legit_req.session,
        capability=legit_req.capability,
        action=legit_req.action,
        target=legit_req.target,
        parameters={"command": "malicious_payload", "cwd": ws},
        workspace=legit_req.workspace,
        context=dict(legit_req.context),
    )
    tampered_env_params = ExecutionEnvelope(
        envelope_id=legit_env.envelope_id,
        task_id=legit_env.task_id,
        action_request=tampered_params_req,
        authorization_decision=legit_env.authorization_decision,
        signature=legit_env.signature,
    )
    assert tampered_env_params.verify() is False
    with pytest.raises(SecurityViolationError, match="Action binding mismatch|verification failed"):
        slice_runner.executor.execute_envelope(tampered_env_params)
    with pytest.raises(SecurityViolationError, match="verification failed"):
        slice_runner.controller.validate_and_consume(tampered_env_params)

    # Attack 2b: Tampering with capability after authorization
    tampered_cap_req = ActionRequest(
        actor=legit_req.actor,
        session=legit_req.session,
        capability="system.unrestricted_exec",
        action=legit_req.action,
        target=legit_req.target,
        parameters=dict(legit_req.parameters),
        workspace=legit_req.workspace,
    )
    tampered_env_cap = ExecutionEnvelope(
        envelope_id=legit_env.envelope_id,
        task_id=legit_env.task_id,
        action_request=tampered_cap_req,
        authorization_decision=legit_env.authorization_decision,
        signature=legit_env.signature,
    )
    assert tampered_env_cap.verify() is False
    with pytest.raises(SecurityViolationError, match="Action binding mismatch|verification failed"):
        slice_runner.executor.execute_envelope(tampered_env_cap)
    with pytest.raises(SecurityViolationError, match="verification failed"):
        slice_runner.controller.validate_and_consume(tampered_env_cap)

    # Attack 2c: Tampering with execution-context (workspace path)
    foreign_ws = str(tmp_path / "foreign_workspace")
    tampered_ws_req = ActionRequest(
        actor=legit_req.actor,
        session=legit_req.session,
        capability=legit_req.capability,
        action=legit_req.action,
        target=legit_req.target,
        parameters=dict(legit_req.parameters),
        workspace=foreign_ws,
    )
    tampered_env_ws = ExecutionEnvelope(
        envelope_id=legit_env.envelope_id,
        task_id=legit_env.task_id,
        action_request=tampered_ws_req,
        authorization_decision=legit_env.authorization_decision,
        signature=legit_env.signature,
    )
    assert tampered_env_ws.verify() is False
    with pytest.raises(SecurityViolationError, match="Execution-context binding mismatch|Action binding mismatch|Request hash mismatch|verification failed"):
        slice_runner.executor.execute_envelope(tampered_env_ws)
    with pytest.raises(SecurityViolationError, match="Execution-context binding mismatch|verification failed"):
        slice_runner.controller.validate_and_consume(tampered_env_ws)

    # Attack 2d: Tampering with envelope task_id
    tampered_env_task = ExecutionEnvelope(
        envelope_id=legit_env.envelope_id,
        task_id="unrelated_task_999",
        action_request=legit_req,
        authorization_decision=legit_env.authorization_decision,
        signature=legit_env.signature,
    )
    assert tampered_env_task.verify() is False
    with pytest.raises(SecurityViolationError, match="Execution-context binding mismatch|verification failed"):
        slice_runner.executor.execute_envelope(tampered_env_task)
    with pytest.raises(SecurityViolationError, match="Execution-context binding mismatch|verification failed"):
        slice_runner.controller.validate_and_consume(tampered_env_task)

    # Attack 2e: Tampering with action target
    tampered_target_req = ActionRequest(
        actor=legit_req.actor,
        session=legit_req.session,
        capability=legit_req.capability,
        action=legit_req.action,
        target="rm -rf /",
        parameters=dict(legit_req.parameters),
        workspace=legit_req.workspace,
    )
    tampered_env_target = ExecutionEnvelope(
        envelope_id=legit_env.envelope_id,
        task_id=legit_env.task_id,
        action_request=tampered_target_req,
        authorization_decision=legit_env.authorization_decision,
        signature=legit_env.signature,
    )
    assert tampered_env_target.verify() is False
    with pytest.raises(SecurityViolationError, match="Action binding mismatch|verification failed"):
        slice_runner.executor.execute_envelope(tampered_env_target)
    with pytest.raises(SecurityViolationError, match="verification failed"):
        slice_runner.controller.validate_and_consume(tampered_env_target)


def test_d10_replaying_consumed_admission_rejected(tmp_path):
    """
    Adversarial Regression 3:
    Replaying a consumed admission envelope is strictly rejected.
    Enforces single-use admission protection (Criterion F) including
    under multi-threaded / concurrent process-level contention.
    """
    import threading
    from sclass.core.vertical_slice import CanonicalVerticalSlice, SliceController

    ws = str(tmp_path / "d10_replay_consumed")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    # Authorize a valid action
    req = slice_runner.planner.plan_verification_action(task.task_id)
    env = slice_runner.controller.authorize(req)

    # 1. First execution succeeds
    res = slice_runner.executor.execute_envelope(env)
    assert res is not None

    # 2. Sequential replay attempt of the exact same envelope is strictly rejected
    with pytest.raises(SecurityViolationError, match="Criterion F Violation|already been consumed"):
        slice_runner.executor.execute_envelope(env)

    # Direct controller consumption of already-consumed envelope is also rejected
    with pytest.raises(SecurityViolationError, match="Criterion F Violation|already been consumed"):
        slice_runner.controller.validate_and_consume(env)

    # 3. Concurrent contention test:
    # Authorize a fresh envelope, then run 4 concurrent controller instances racing to consume it
    fresh_req = slice_runner.planner.plan_verification_action(task.task_id)
    fresh_env = slice_runner.controller.authorize(fresh_req)

    success_count = []
    failure_count = []

    def race_worker():
        ctrl = SliceController(ws)
        try:
            ctrl.validate_and_consume(fresh_env)
            success_count.append(1)
        except SecurityViolationError:
            failure_count.append(1)

    threads = [threading.Thread(target=race_worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly ONE thread can consume; all others must fail closed with SecurityViolationError
    assert len(success_count) == 1, f"Expected exactly 1 successful consumption, got {len(success_count)}"
    assert len(failure_count) == 3, f"Expected 3 rejected replay attempts, got {len(failure_count)}"


def test_d10_replay_rejected_after_process_restart(tmp_path):
    """
    Adversarial Regression 4:
    Replay remains rejected after controller/process restart where the existing
    D5 persistence mechanism (EventJournal and trust admission store) supports this.
    """
    from sclass.core.vertical_slice import (
        CanonicalVerticalSlice,
        SliceController,
        SliceExecutor,
    )

    ws = str(tmp_path / "d10_restart_replay")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    # Authorize and execute an envelope in the first controller/executor instance
    req = slice_runner.planner.plan_verification_action(task.task_id)
    env = slice_runner.controller.authorize(req)

    res = slice_runner.executor.execute_envelope(env)
    assert res is not None

    # Simulate process termination and restart:
    # Completely destroy controller and executor, create new instances on the same workspace
    del slice_runner.controller
    del slice_runner.executor

    restarted_controller = SliceController(ws)
    restarted_executor = SliceExecutor(ws, restarted_controller)

    # Proves durable persistence: the consumed envelope ID was loaded from persistent storage
    assert restarted_controller.is_consumed(env.envelope_id) is True

    # Attempting to replay the consumed envelope in the restarted process must fail closed
    with pytest.raises(SecurityViolationError, match="Criterion F Violation|already been consumed"):
        restarted_executor.execute_envelope(env)

    with pytest.raises(SecurityViolationError, match="Criterion F Violation|already been consumed"):
        restarted_controller.validate_and_consume(env)


def test_d10_canonical_final_acceptance_binding(tmp_path):
    """
    Adversarial Regression 5:
    Tightens verify_canonical_acceptance() so final acceptance is bound to the
    exact canonical claim being accepted:
    - task ID
    - claim ID
    - final observed receipt ID
    - receipt hash/provenance
    - fresh workspace evidence (rejects mutated/stale workspace or deleted receipt)
    - accepted verification result in StateRepository
    - final composite acceptance decision

    Do not treat TaskState.VERIFIED plus any successful observation as sufficient truth.
    """
    import json
    from sclass.core.vertical_slice import CanonicalVerticalSlice, verify_canonical_acceptance
    from sclass.storage.paths import WorkspacePaths
    from sclass.state.events import EventJournal

    ws = str(tmp_path / "d10_canonical_acceptance_binding")
    slice_runner = CanonicalVerticalSlice(ws)
    results = slice_runner.run_full_slice()

    task_id = slice_runner.task.task_id
    receipt_id = slice_runner.passed_receipt.receipt_id
    claim_id = slice_runner.claim_verif.claim_id

    # Baseline: genuine canonical acceptance passes
    status = verify_canonical_acceptance(task_id, ws, claim_id=claim_id)
    assert status["accepted"] is True
    assert status["task_id"] == task_id
    assert status["claim_id"] == claim_id
    assert status["verified_receipt_id"] == receipt_id
    assert status["fresh_evidence"] is True
    assert status["composite_decision"] == "ACCEPT"

    # Binding Check 1: Non-existent task ID fails
    nonexistent = verify_canonical_acceptance("task_does_not_exist", ws)
    assert nonexistent["accepted"] is False
    assert "not found" in nonexistent["reason"].lower()

    # Binding Check 2: Unrelated / mismatched claim ID fails
    mismatched_claim = verify_canonical_acceptance(task_id, ws, claim_id="claim_unrelated_999")
    assert mismatched_claim["accepted"] is False
    assert "not found" in mismatched_claim["reason"].lower() or "does not match" in mismatched_claim["reason"].lower()

    # Binding Check 3: State repository verification result must be ACCEPT
    with slice_runner.state_repo.store.get_connection() as conn:
        conn.execute("UPDATE verifications SET status = 'REJECT' WHERE claim_id = ?", (claim_id,))
        conn.commit()

    tampered_verif = verify_canonical_acceptance(task_id, ws, claim_id=claim_id)
    assert tampered_verif["accepted"] is False
    assert "no accepted verification" in tampered_verif["reason"].lower()

    # Restore verification row to ACCEPT
    with slice_runner.state_repo.store.get_connection() as conn:
        conn.execute("UPDATE verifications SET status = 'ACCEPT' WHERE claim_id = ?", (claim_id,))
        conn.commit()

    # Binding Check 4: Workspace mutation invalidates evidence freshness (Invariant L7)
    math_path = os.path.join(ws, "math_utils.py")
    with open(math_path, "rb") as f:
        original_bytes = f.read()
    with open(math_path, "ab") as f:
        f.write(b"\n# Untracked post-acceptance backdoor\n")

    stale_check = verify_canonical_acceptance(task_id, ws, claim_id=claim_id)
    assert stale_check["accepted"] is False
    assert "stale" in stale_check["reason"].lower() or "modified" in stale_check["reason"].lower()

    # Restore workspace file so evidence is fresh again
    with open(math_path, "wb") as f:
        f.write(original_bytes)
    assert verify_canonical_acceptance(task_id, ws, claim_id=claim_id)["accepted"] is True

    # Binding Check 5: Deleted receipt file on disk fails closed
    paths = WorkspacePaths(ws)
    rcpt_file = os.path.join(paths.receipts_dir, f"{receipt_id}.json")
    legacy_rcpt_file = os.path.join(paths.legacy_receipts_dir, f"{receipt_id}.json")
    with open(rcpt_file, "r", encoding="utf-8") as f:
        saved_rcpt_content = f.read()
    os.remove(rcpt_file)
    if os.path.exists(legacy_rcpt_file):
        os.remove(legacy_rcpt_file)

    deleted_rcpt_status = verify_canonical_acceptance(task_id, ws, claim_id=claim_id)
    assert deleted_rcpt_status["accepted"] is False
    assert "not found" in deleted_rcpt_status["reason"].lower()

    # Restore receipt file
    with open(rcpt_file, "w", encoding="utf-8") as f:
        f.write(saved_rcpt_content)
    if not os.path.exists(paths.legacy_receipts_dir):
        os.makedirs(paths.legacy_receipts_dir, exist_ok=True)
    with open(legacy_rcpt_file, "w", encoding="utf-8") as f:
        f.write(saved_rcpt_content)
    assert verify_canonical_acceptance(task_id, ws, claim_id=claim_id)["accepted"] is True

    # Binding Check 6: Tampering with receipt hash on disk fails closed
    tampered_data = json.loads(saved_rcpt_content)
    tampered_data["receipt_hash"] = "f" * 64
    with open(rcpt_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(tampered_data))
    if os.path.exists(legacy_rcpt_file):
        with open(legacy_rcpt_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(tampered_data))

    tampered_rcpt_status = verify_canonical_acceptance(task_id, ws, claim_id=claim_id)
    assert tampered_rcpt_status["accepted"] is False
    assert "mismatch" in tampered_rcpt_status["reason"].lower() or "tampered" in tampered_rcpt_status["reason"].lower() or "not found" in tampered_rcpt_status["reason"].lower()

    # Restore valid receipt
    with open(rcpt_file, "w", encoding="utf-8") as f:
        f.write(saved_rcpt_content)
    if os.path.exists(legacy_rcpt_file):
        with open(legacy_rcpt_file, "w", encoding="utf-8") as f:
            f.write(saved_rcpt_content)

    # Binding Check 7: Missing / invalid composite acceptance decision in journal fails closed
    journal = EventJournal(ws)
    with open(journal.journal_file, "r", encoding="utf-8") as f:
        journal_backup = f.read()

    # Overwrite journal with event missing acceptance_decision
    with open(journal.journal_file, "w", encoding="utf-8") as f:
        pass
    journal.append(
        event_type="sclass.task.verified",
        subject=f"task:{task_id}",
        data={"task_id": task_id, "verified_receipt_id": receipt_id},
    )

    no_composite_status = verify_canonical_acceptance(task_id, ws, claim_id=claim_id)
    assert no_composite_status["accepted"] is False
    assert "no accepted composite decision" in no_composite_status["reason"].lower()

    # Restore original journal
    with open(journal.journal_file, "w", encoding="utf-8") as f:
        f.write(journal_backup)
    assert verify_canonical_acceptance(task_id, ws, claim_id=claim_id)["accepted"] is True

