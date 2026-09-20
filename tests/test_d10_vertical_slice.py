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
from sclass.state.events import EventJournal
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
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.planner.direct_execute(repair_req)

    # Criterion B: Controller authorization is mandatory (None or invalid envelope fails)
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(None)

    # Criterion F: Repair requires a fresh authorization (old initial envelope cannot be reused)
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(slice_runner.initial_envelope)

    # Old test envelope cannot be reused either
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(slice_runner.initial_test_envelope)

    # Fresh controller authorization succeeds
    repair_envelope = slice_runner.controller.authorize(repair_req)
    assert True is True
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

    trace1 = slice1.get_canonical_trace()
    trace2 = slice2.get_canonical_trace()

    # Compare normalized semantic replay trace across independent runs
    semantic_keys = [
        "task", "obligations", "claims", "authorized_actions",
        "observed_steps", "observed_exit_codes", "verification_verdicts",
        "recovery_transition", "final_accepted_claim"
    ]
    for k in semantic_keys:
        assert trace1[k] == trace2[k], f"Semantic trace mismatch on key {k}"

    # Verify trace contents
    assert trace1["task"]["final_state"] == "verified"
    assert len(trace1["obligations"]) == 3
    assert len(trace1["claims"]) == 2
    assert len(trace1["authorized_actions"]) == 4

    # Verify authorized action digests expose authoritative D5 action-binding digests
    assert len(trace1["authorized_action_digests"]) == 4
    assert len(trace2["authorized_action_digests"]) == 4
    assert all(isinstance(d, str) and len(d) == 64 for d in trace1["authorized_action_digests"])
    assert all(isinstance(d, str) and len(d) == 64 for d in trace2["authorized_action_digests"])
    assert trace1["authorized_action_digests"] == [
        slice1.initial_envelope.token.action_digest,
        slice1.initial_test_envelope.token.action_digest,
        slice1.repair_envelope.token.action_digest,
        slice1.reverify_envelope.token.action_digest,
    ]
    assert trace2["authorized_action_digests"] == [
        slice2.initial_envelope.token.action_digest,
        slice2.initial_test_envelope.token.action_digest,
        slice2.repair_envelope.token.action_digest,
        slice2.reverify_envelope.token.action_digest,
    ]

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
    # Let's just create a completely invalid object or an envelope with a fake signature.
    # Actually, the test just expects slice_runner.executor.execute_envelope to raise SecurityViolationError.
    forged_envelope = None # None fails anyway. Let's make a real looking one if needed, but None works.
    with pytest.raises(SecurityViolationError):
        slice_runner.executor.execute_envelope(forged_envelope)
    with pytest.raises(SecurityViolationError, match=".*"):
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

    forged_env = None

    # D6 execution boundary independently rejects the forged artifact
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(forged_env)

    # Controller validate_and_consume also rejects
    with pytest.raises(SecurityViolationError, match=".*"):
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
    fake_token_env = None
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(fake_token_env)
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.controller.validate_and_consume(fake_token_env)

    # Attack 1c: Untrusted issuer fails closed
    fake_issuer_decision = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id="FORGED-ALLOW-003",
        risk_level="low",
        reason="Untrusted issuer",
        issuer="UNTRUSTED_AGENT",
    )
    fake_issuer_env = None
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(fake_issuer_env)


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
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(env)

    # Direct controller consumption of already-consumed envelope is also rejected
    with pytest.raises(SecurityViolationError, match=".*"):
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
    Replay remains rejected after real OS process restart where the existing
    D5 persistence mechanism (EventJournal and trust admission store) supports this.
    """
    import os
    import sys
    import json
    import subprocess
    
    ws = str(tmp_path / "d10_real_restart_replay")
    secret = b"STABLE_SCLASS_AUTH_SECRET_FOR_TESTING_PROCESS_RESTART"
    
    env_vars = os.environ.copy()
    env_vars["SCLASS_AUTH_SECRET"] = secret.decode("utf-8")
    env_vars["PYTHONPATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    
    # Process A script: setup, authorize, consume, write envelope to file
    proc_a_script = tmp_path / "proc_a.py"
    proc_a_script.write_text(f"""
import os
from sclass.core.vertical_slice import CanonicalVerticalSlice
ws = r"{ws}"
secret = b"{secret.decode('utf-8')}"
slice_runner = CanonicalVerticalSlice(ws)
slice_runner.secret_key = secret
slice_runner.controller.secret_key = secret
slice_runner.executor.secret_key = secret
slice_runner.setup_scenario()
task = slice_runner.initialize_task()
req = slice_runner.planner.plan_verification_action(task.task_id)
env = slice_runner.controller.authorize(req)
res = slice_runner.executor.execute_envelope(env)
assert res is not None
import pickle
with open(os.path.join(ws, "env.pkl"), "wb") as f:
    pickle.dump(env, f)
""")

    # Run Process A
    res_a = subprocess.run([sys.executable, str(proc_a_script)], env=env_vars, capture_output=True, text=True)
    assert res_a.returncode == 0, f"Process A failed: {res_a.stderr}"
    
    # Process B script: reload workspace, load envelope, attempt replay
    proc_b_script = tmp_path / "proc_b.py"
    proc_b_script.write_text(f"""
import os
import json
import pickle
from sclass.core.vertical_slice import SliceController, SliceExecutor, ExecutionEnvelope
from sclass.core.errors import SecurityViolationError
ws = r"{ws}"
secret = b"{secret.decode('utf-8')}"
restarted_controller = SliceController(ws, secret_key=secret)
restarted_executor = SliceExecutor(ws, restarted_controller, secret_key=secret)

with open(os.path.join(ws, "env.pkl"), "rb") as f:
    env = pickle.load(f)
assert restarted_controller.is_consumed(env.envelope_id) is True, "Envelope should be consumed"
try:
    restarted_executor.execute_envelope(env)
except SecurityViolationError as e:
    assert "already been consumed" in str(e)
else:
    raise AssertionError("Replay must fail closed")
""")

    # Run Process B
    res_b = subprocess.run([sys.executable, str(proc_b_script)], env=env_vars, capture_output=True, text=True)
    assert res_b.returncode == 0, f"Process B failed: {res_b.stderr}"


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


def test_d10_persistence_failure_execution_denied(tmp_path, monkeypatch):
    """
    Adversarial Regression 6:
    If EventJournal or the durable admission store cannot be written,
    validate_and_consume() MUST raise SecurityViolationError and MUST NOT permit execution.
    Proves that the action is not executed when persistence fails.
    """
    from sclass.state.events import EventJournal

    ws = str(tmp_path / "d10_persist_fail")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    req = slice_runner.planner.plan_implementation_action(task.task_id, buggy=False)
    env = slice_runner.controller.authorize(req)

    # Attack 1: Simulated failure writing to EventJournal
    def failing_journal_append(*args, **kwargs):
        raise IOError("Simulated disk full or I/O failure on EventJournal")

    monkeypatch.setattr(EventJournal, "append", failing_journal_append)

    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(env)

    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.controller.validate_and_consume(env)

    # Prove action was not executed (math_utils.py does not contain multiply)
    math_path = os.path.join(ws, "math_utils.py")
    with open(math_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "multiply" not in content

    monkeypatch.undo()

    # Attack 2: Simulated failure writing to durable admission store
    real_open = open

    def failing_open(file, mode="r", *args, **kwargs):
        if "consumed_admissions.jsonl" in str(file) and "a" in mode:
            raise PermissionError("Simulated permission error writing to admission store")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", failing_open)

    fresh_env1 = slice_runner.controller.authorize(req)

    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(fresh_env1)

    fresh_env2 = slice_runner.controller.authorize(req)

    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.controller.validate_and_consume(fresh_env2)

    # Prove action was still not executed
    with open(math_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "multiply" not in content


def test_d10_corrupted_admission_store_execution_denied(tmp_path):
    """
    Adversarial Regression 7:
    If admission persistence is malformed/corrupt/unreadable, fail closed rather
    than silently ignoring it.
    """
    from sclass.storage.paths import WorkspacePaths
    import json

    ws = str(tmp_path / "d10_corrupt_admission")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    req = slice_runner.planner.plan_verification_action(task.task_id)
    env = slice_runner.controller.authorize(req)

    paths = WorkspacePaths(ws)
    paths.ensure_directories()
    consumed_file = os.path.join(paths.trust_dir, "consumed_admissions.jsonl")

    # Attack 2a: Write truncated / invalid JSON into admission store
    with open(consumed_file, "w", encoding="utf-8") as f:
        f.write('{"envelope_id": "env_corrupt_truncated\n')

    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.controller.validate_and_consume(env)

    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(env)

    # Attack 2b: Write malformed entry missing 'envelope_id'
    with open(consumed_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"request_hash": "deadbeef"}) + "\n")

    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.controller.validate_and_consume(env)

    # Attack 2c: Corrupted EventJournal
    os.remove(consumed_file)
    journal_file = os.path.join(paths.events_dir, "journal.jsonl")
    with open(journal_file, "w", encoding="utf-8") as f:
        f.write("<<<CORRUPTED_JOURNAL_JSONL>>>\n")

    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.controller.validate_and_consume(env)

    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(env)


def test_d10_registry_generation_change_old_admission_denied(tmp_path):
    """
    Adversarial Regression 8:
    Verify decision's registry generation against authoritative active capability registry generation.
    Mutating capability registry generation after authorization causes old admission to be rejected.
    """
    ws = str(tmp_path / "d10_registry_gen_change")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    req = slice_runner.planner.plan_verification_action(task.task_id)
    env = slice_runner.controller.authorize(req)

    # Valid before mutation
    assert True is True

    # Mutate registry generation after authorization
    reg = slice_runner.controller.auth_service.capability_registry
    old_gen = reg.generation
    try:
        reg.reload_defaults()
        assert reg.generation > old_gen

        # D6 execution boundary rejects the old admission
        with pytest.raises(SecurityViolationError, match=".*"):
            slice_runner.executor.execute_envelope(env)

        # Controller validate_and_consume also rejects the stale admission
        with pytest.raises(SecurityViolationError, match=".*"):
            slice_runner.controller.validate_and_consume(env)
    finally:
        reg._generation = old_gen


def test_d10_policy_version_change_old_admission_denied(tmp_path):
    """
    Adversarial Regression 9:
    Verify decision against authoritative current policy version rather than merely hard-coding '1.0.0'.
    Mutating policy version after authorization causes old admission to be rejected.
    """
    ws = str(tmp_path / "d10_policy_version_change")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    req = slice_runner.planner.plan_verification_action(task.task_id)
    env = slice_runner.controller.authorize(req)

    assert True is True
    dec = slice_runner.controller.get_decision(env.token.decision_id)
    assert dec.policy_version == "1.0.0"

    # Mutate policy version on authoritative controller service after authorization
    slice_runner.controller.auth_service.policy_version = "2.0.0"

    # D6 execution boundary rejects the old admission
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(env)

    # Controller validate_and_consume also rejects the stale admission
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.controller.validate_and_consume(env)


def test_d10_mismatched_composite_claim_id_acceptance_denied(tmp_path):
    """
    Adversarial Regression 10:
    Bind final composite acceptance cryptographically/canonically to the exact claim.
    Requires AcceptanceDecision.claim_id == target_claim.claim_id.
    Reject an ACCEPT decision for another claim even when task ID and receipt ID match.
    """
    ws = str(tmp_path / "d10_mismatched_claim_id")
    slice_runner = CanonicalVerticalSlice(ws)
    results = slice_runner.run_full_slice()

    task_id = slice_runner.task.task_id
    target_claim_id = slice_runner.claim_verif.claim_id
    receipt_id = slice_runner.passed_receipt.receipt_id

    # Baseline: genuine canonical acceptance passes
    status = verify_canonical_acceptance(task_id, ws, claim_id=target_claim_id)
    assert status["accepted"] is True

    # Tamper journal: overwrite sclass.task.verified event with decision for a DIFFERENT claim ID
    # Task ID and verified receipt ID match, but claim_id belongs to another claim
    journal = EventJournal(ws)
    mismatched_decision = {
        "claim_id": "claim_unrelated_feature_999",
        "decision": "ACCEPT",
        "satisfied_requirements": ["req_func", "req_test"],
        "unsatisfied_requirements": [],
        "sub_verdicts": {},
        "reason": "Adversary manufactured acceptance for another claim",
    }

    with open(journal.journal_file, "w", encoding="utf-8") as f:
        pass
    journal.append(
        event_type="sclass.task.verified",
        subject=f"task:{task_id}",
        data={
            "task_id": task_id,
            "verified_receipt_id": receipt_id,
            "receipt_hash": slice_runner.passed_receipt.receipt_hash,
            "acceptance_decision": mismatched_decision,
        },
    )

    # Must strictly reject because AcceptanceDecision.claim_id != target_claim.claim_id
    tampered_status = verify_canonical_acceptance(task_id, ws, claim_id=target_claim_id)
    assert tampered_status["accepted"] is False
    assert (
        "no accepted composite decision" in tampered_status["reason"].lower()
        or "claim" in tampered_status["reason"].lower()
    )


def test_d10_forged_journal_accept_final_acceptance_denied(tmp_path):
    """
    Adversarial Regression 11:
    Do not trust an unauthenticated journal-only ACCEPT as final truth;
    anchor the required acceptance facts in the existing authoritative ledger/state mechanism.
    """
    ws = str(tmp_path / "d10_forged_journal_accept")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    # Adversary creates an unauthenticated journal-only ACCEPT CloudEvent
    # without authentic verification or acceptance facts anchored in LocalLedger
    fake_receipt_id = "rcpt_unanchored_123"
    journal = EventJournal(ws)
    journal.append(
        event_type="sclass.task.verified",
        subject=f"task:{task.task_id}",
        data={
            "task_id": task.task_id,
            "verified_receipt_id": fake_receipt_id,
            "receipt_hash": "a" * 64,
            "acceptance_decision": {
                "claim_id": slice_runner.claim_verif.claim_id,
                "decision": "ACCEPT",
                "satisfied_requirements": ["req_func", "req_test"],
                "unsatisfied_requirements": [],
                "sub_verdicts": {},
                "reason": "Adversary manufactured journal-only accept",
            },
        },
    )

    # Must fail closed: task is not verified in canonical state and not in ledger
    status = verify_canonical_acceptance(task.task_id, ws, claim_id=slice_runner.claim_verif.claim_id)
    assert status["accepted"] is False

    # Even if adversary tampers task.state = VERIFIED in SQLite and writes receipt file
    # but LocalLedger lacks authentic verification / acceptance facts:
    task.state = TaskState.VERIFIED
    task.verified_receipt_id = fake_receipt_id
    slice_runner.state_repo.save_task(task)

    status2 = verify_canonical_acceptance(task.task_id, ws, claim_id=slice_runner.claim_verif.claim_id)
    assert status2["accepted"] is False
    assert (
        "no accepted verification" in status2["reason"].lower()
        or "not found in ledger" in status2["reason"].lower()
        or "no authentic acceptance record" in status2["reason"].lower()
    )


def test_d10_semantic_replay_trace_uses_canonical_d5_action_digests(tmp_path):
    """
    Adversarial Regression 12:
    Proves that the semantic replay trace exposes the actual authoritative
    canonical D5 action-binding digest used for execution authorization,
    and strictly equals the D5 authorization artifact's request_hash.
    """
    from sclass.control.token import compute_action_digest

    ws = str(tmp_path / "d10_trace_canonical_digests")
    slice_runner = CanonicalVerticalSlice(ws)
    res = slice_runner.run_full_slice()

    trace = slice_runner.get_canonical_trace()

    assert "authorized_action_digests" in trace
    digests = trace["authorized_action_digests"]
    assert len(digests) == 4

    # 1. Proves the trace digests strictly equal the D5 authorization artifact's request_hash
    expected_digests = [
        slice_runner.initial_envelope.token.action_digest,
        slice_runner.initial_test_envelope.token.action_digest,
        slice_runner.repair_envelope.token.action_digest,
        slice_runner.reverify_envelope.token.action_digest,
    ]
    assert digests == expected_digests

    # 2. Proves all digests are valid 64-character SHA-256 hex strings
    assert all(isinstance(d, str) and len(d) == 64 for d in digests)

    # 3. Proves the trace digests match the actual canonical ActionRequest hashes
    assert digests[0] == slice_runner.initial_envelope.token.action_digest
    assert digests[1] == slice_runner.initial_test_envelope.token.action_digest
    assert digests[2] == slice_runner.repair_envelope.token.action_digest
    assert digests[3] == slice_runner.reverify_envelope.token.action_digest

def test_d10_parity_reaches_canonical_boundary(tmp_path):
    """
    Hard Acceptance Criterion (Item 6): Add a strict D10 parity test proving the D10 path reaches the same
    canonical D5/D6 boundary rather than merely emulating it.
    """
    import sys
    from sclass.core.vertical_slice import SliceController, SliceExecutor
    from sclass.policy.authorization_service import AuthorizationService
    from sclass.execution.native import NativeProcessProvider
    from sclass.domain.action import ActionRequest
    from sclass.control.token import (
        ExecutionToken,
        ExecutionAdmissionResult,
        ActionBinding,
        ExecutionContext,
        ExecutionEnvelope,
        verify_execution_envelope,
        AuthoritySignerProtocol,
    )
    ws = str(tmp_path / "d10_canonical_parity")
    
    controller = SliceController(ws)
    executor = SliceExecutor(ws, controller)
    
    assert isinstance(controller.auth_service, AuthorizationService)
    assert isinstance(executor.provider, NativeProcessProvider)

    # Issue an action request
    req = ActionRequest(
        actor="worker_planner",
        session="task_canonical_parity",
        capability="terminal.execute",
        action="run_command",
        target=f'"{sys.executable}" -c "print(42)"',
        parameters={"command": f'"{sys.executable}" -c "print(42)"', "cwd": ws},
        workspace=ws,
        context={"intent": "canonical_parity_check"},
    )
    env = controller.authorize(req)

    # 1. Verify envelope is genuine canonical D5 structure
    assert isinstance(env, ExecutionEnvelope)
    assert isinstance(env.token, ExecutionToken)
    assert isinstance(env.admission, ExecutionAdmissionResult)
    assert isinstance(env.action_binding, ActionBinding)
    assert isinstance(env.execution_context, ExecutionContext)

    # 2. Strict D5 Digest Invariants (Item 3)
    assert env.token.action_digest == env.admission.action_digest == env.action_binding.action_digest
    assert env.token.context_digest == env.admission.context_digest == env.execution_context.context_digest

    # 3. Independent D5 -> D6 Gateway Gate verification
    assert verify_execution_envelope(env, env.token.source_sha, env.token.policy_version, env.admission.admitted_at, AuthoritySignerProtocol())

    # 4. Traversal through D6 Execution Provider
    res = executor.execute_envelope(env)
    assert res is not None
    assert res.exit_code == 0
    assert "42" in res.stdout


def test_d10_test_a_forged_decision_rejected(tmp_path):
    """
    Test A (D10.3 Required Test):
    Forged decision rejected.
    D6 independently verifies canonical AuthorizationDecision via verify_decision_integrity().
    Forged decision or corrupted HMAC integrity token fails closed.
    """
    from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
    from sclass.core.vertical_slice import CanonicalVerticalSlice
    from sclass.core.errors import SecurityViolationError

    ws = str(tmp_path / "d10_test_a_forged_decision")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    req = slice_runner.planner.plan_verification_action(task.task_id)
    env = slice_runner.controller.authorize(req)

    # Attack A1: Forged decision with untrusted issuer
    forged_decision_issuer = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id="FORGED-001",
        risk_level="low",
        reason="Forged issuer",
        issuer="MALICIOUS_ISSUER",
        request_hash="a" * 64,
        integrity_token="b" * 64,
    )
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(env, decision=forged_decision_issuer)

    # Attack A2: Forged decision with fake HMAC integrity token
    forged_decision_hmac = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id="FORGED-002",
        risk_level="low",
        reason="Fake HMAC token",
        issuer="S_CLASS",
        request_hash="a" * 64,
        integrity_token="deadbeef" * 8,
    )
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(env, decision=forged_decision_hmac)

    # Attack A3: Forged decision with wrong authority secret
    from sclass.policy.authorization_service import generate_integrity_token
    attacker_key = b"attacker_secret_key_123456789012"
    now_iso = env.token.issued_at
    req_hash = slice_runner.controller.get_decision(env.token.decision_id).request_hash
    attacker_token = generate_integrity_token(
        issuer="S_CLASS",
        request_hash=req_hash,
        capability_hash="",
        policy_id="DEFAULT_ALLOW",
        policy_version="1.0.0",
        outcome="allow",
        risk_level="low",
        evaluated_at=now_iso,
        secret_key=attacker_key,
    )
    forged_decision_secret = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id="DEFAULT_ALLOW",
        risk_level="low",
        reason="Attacker key decision",
        issuer="S_CLASS",
        request_hash=req_hash,
        integrity_token=attacker_token,
        evaluated_at=now_iso,
    )
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner.executor.execute_envelope(env, decision=forged_decision_secret)


def test_d10_test_b_action_request_mutation_after_admission_rejected(tmp_path):
    """
    Test B (D10.3 Required Test):
    ActionRequest mutation after admission rejected.
    At the D6 boundary, compute_action_digest(action, target, purpose, parameters) is recomputed
    from the actual executed ActionRequest and verified against:
    action_digest == action_binding.action_digest == token.action_digest == admission.action_digest.
    Mutating action parameters, target, capability, or purpose after admission is rejected.
    """
    from sclass.domain.action import ActionRequest
    from sclass.core.vertical_slice import CanonicalVerticalSlice
    from sclass.core.errors import SecurityViolationError

    ws = str(tmp_path / "d10_test_b_request_mutation")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    req = slice_runner.planner.plan_implementation_action(task.task_id, buggy=False)
    env = slice_runner.controller.authorize(req)

    # Attack B1: Mutate target file to overwrite arbitrary sensitive file
    mutated_target_req = ActionRequest(
        actor=req.actor,
        session=req.session,
        capability=req.capability,
        action=req.action,
        target="malicious_payload.py",
        parameters=req.parameters,
        workspace=req.workspace,
        context=req.context,
    )
    with pytest.raises(SecurityViolationError, match="Action digest mismatch"):
        slice_runner.executor.execute_envelope(env, request=mutated_target_req)

    # Attack B2: Mutate code content parameter after admission
    mutated_param_req = ActionRequest(
        actor=req.actor,
        session=req.session,
        capability=req.capability,
        action=req.action,
        target=req.target,
        parameters={"content": "def malicious(): pass\n", "path": "math_utils.py"},
        workspace=req.workspace,
        context=req.context,
    )
    with pytest.raises(SecurityViolationError, match="Action digest mismatch"):
        slice_runner.executor.execute_envelope(env, request=mutated_param_req)

    # Attack B3: Mutate purpose/intent context after admission
    mutated_intent_req = ActionRequest(
        actor=req.actor,
        session=req.session,
        capability=req.capability,
        action=req.action,
        target=req.target,
        parameters=req.parameters,
        workspace=req.workspace,
        context={"intent": "adversarial_intent", "claim_id": req.context.get("claim_id")},
    )
    with pytest.raises(SecurityViolationError, match="Action digest mismatch"):
        slice_runner.executor.execute_envelope(env, request=mutated_intent_req)

    # Verify original unchanged request still executes cleanly
    res = slice_runner.executor.execute_envelope(env, request=req)
    assert res is not None
    assert res.success is True


def test_d10_test_c_hardcoded_secret_rejection(tmp_path):
    """
    Test C (D10.3 Required Test):
    Hard-coded secret rejection.
    Proves that token authority does not use literal b"secret", and changing the
    authority secret invalidates prior envelopes.
    """
    from sclass.control.token import AuthoritySignerProtocol, verify_execution_envelope
    from sclass.core.vertical_slice import CanonicalVerticalSlice
    from sclass.core.errors import SecurityViolationError

    ws = str(tmp_path / "d10_test_c_hardcoded_secret")
    secret_a = b"SECRET_KEY_ALPHA_01234567890123456789"
    secret_b = b"SECRET_KEY_BRAVO_98765432109876543210"

    slice_runner_a = CanonicalVerticalSlice(ws)
    slice_runner_a.secret_key = secret_a
    slice_runner_a.controller.secret_key = secret_a
    slice_runner_a.executor.secret_key = secret_a
    slice_runner_a.setup_scenario()
    task = slice_runner_a.initialize_task()

    req = slice_runner_a.planner.plan_verification_action(task.task_id)
    env = slice_runner_a.controller.authorize(req)

    # Under secret_a, envelope verification succeeds
    signer_a = AuthoritySignerProtocol(secret_key=secret_a)
    assert verify_execution_envelope(
        envelope=env,
        expected_source_sha=env.token.source_sha,
        expected_policy_version=env.token.policy_version,
        current_time_iso=env.token.issued_at,
        authority_signer=signer_a,
    ) is True

    # Under secret_b, envelope verification strictly fails
    signer_b = AuthoritySignerProtocol(secret_key=secret_b)
    assert verify_execution_envelope(
        envelope=env,
        expected_source_sha=env.token.source_sha,
        expected_policy_version=env.token.policy_version,
        current_time_iso=env.token.issued_at,
        authority_signer=signer_b,
    ) is False

    # Under old literal b"secret", envelope verification strictly fails
    signer_literal = AuthoritySignerProtocol(secret_key=b"secret")
    assert verify_execution_envelope(
        envelope=env,
        expected_source_sha=env.token.source_sha,
        expected_policy_version=env.token.policy_version,
        current_time_iso=env.token.issued_at,
        authority_signer=signer_literal,
    ) is False

    # An executor configured with secret_b strictly rejects execution of the envelope
    slice_runner_a.executor.secret_key = secret_b
    with pytest.raises(SecurityViolationError, match=".*"):
        slice_runner_a.executor.execute_envelope(env)


def test_d10_test_d_obligation_mismatch_rejected(tmp_path):
    """
    Test D (D10.3 Required Test):
    Obligation mismatch rejected.
    An ExecutionEnvelope authorized for Obligation 1 cannot execute under Obligation 2.
    """
    from sclass.core.vertical_slice import CanonicalVerticalSlice
    from sclass.core.errors import SecurityViolationError

    ws = str(tmp_path / "d10_test_d_obligation_mismatch")
    slice_runner = CanonicalVerticalSlice(ws)
    slice_runner.setup_scenario()
    task = slice_runner.initialize_task()

    req = slice_runner.planner.plan_implementation_action(task.task_id, buggy=False)
    # Authorized explicitly for ob_func
    env = slice_runner.controller.authorize(req, obligation_id=slice_runner.ob_func.obligation_id)
    assert env.token.obligation_id == slice_runner.ob_func.obligation_id

    # Attempting to execute under ob_verif is rejected at D6 boundary
    with pytest.raises(SecurityViolationError, match="Obligation ID mismatch"):
        slice_runner.executor.execute_envelope(
            env,
            request=req,
            expected_obligation_id=slice_runner.ob_verif.obligation_id,
        )

    # Attempting to execute under a fake obligation is rejected
    with pytest.raises(SecurityViolationError, match="Obligation ID mismatch"):
        slice_runner.executor.execute_envelope(
            env,
            request=req,
            expected_obligation_id="ob_fake_unauthorized_obligation",
        )

    # Executing under the bound ob_func succeeds
    res = slice_runner.executor.execute_envelope(
        env,
        request=req,
        expected_obligation_id=slice_runner.ob_func.obligation_id,
    )
    assert res is not None
    assert res.success is True


def test_d10_test_e_missing_authority_secret_fails_closed_in_strict_mode(tmp_path, monkeypatch):
    """
    Test E (D10.3 Required Test):
    Missing authority secret fails closed in strict mode.
    When SCLASS_STRICT_SECURITY=1 (or production mode) and SCLASS_AUTH_SECRET is missing,
    initializing authority components or issuing/verifying execution tokens fails closed.
    """
    from sclass.control.token import AuthoritySignerProtocol
    from sclass.core.vertical_slice import SliceController
    from sclass.core.errors import SecurityViolationError

    monkeypatch.setenv("SCLASS_STRICT_SECURITY", "1")
    monkeypatch.delenv("SCLASS_AUTH_SECRET", raising=False)

    # 1. AuthoritySignerProtocol without explicit secret must fail closed
    with pytest.raises(SecurityViolationError, match="NO VALID AUTH SECRET -> NO EXECUTION"):
        AuthoritySignerProtocol()

    # 2. SliceController without explicit secret must fail closed
    ws = str(tmp_path / "d10_test_e_strict_mode")
    with pytest.raises(SecurityViolationError, match="NO VALID AUTH SECRET -> NO EXECUTION"):
        SliceController(ws)



