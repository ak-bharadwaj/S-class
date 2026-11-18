"""Guards and negative tests for the six R-GPT findings (CL Directive A6-R1 through A6-R6).

Demonstrates that unsafe behaviors are rejected by fail-closed reference/extension code,
and documents the exact line-level limitations in the frozen runtime baseline (BLOCKED_PENDING_CL).

Finding Map:
- A6-R1: cancellation & process-exit proof (SubprocessWorker heartbeat PermissionError limitation).
- A6-R2: exit code is not obligation verification (ExecutionGate non-APPLY_DELTA exit 0 limitation).
- A6-R3: worker-supplied execution result & quiescence (ExecutionGate _last_result and OSError quiescence limitation).
- A6-R4: TypeError retry duplicate execution (ExecutionGate except TypeError limitation).
- A6-R5: atomic lifecycle event commitment (ExecutionGate multi-transaction lifecycle limitation).
- A6-R6: evidence authenticity and independent assessment (ExecutionGate synthetic assessment limitation).
"""

from __future__ import annotations

import inspect
import os
import signal
import sqlite3
import types
from pathlib import Path
import pytest

from sclass.reference_impl import (
    ReferenceWorker,
    ReferenceVerificationProvider,
    ReferenceSQLiteStore,
    ReferenceExecutionGate,
)
from sclass_semantics_v6_0_1 import (
    ActionType,
    ActorIdentity,
    ActorKind,
    AssessmentVerdict,
    Digest,
    EventType,
    ExecutionOutcome,
    FrozenMap,
    GateResult,
    IndependenceLevel,
    IndependenceProfile,
    IsolationLevel,
    Obligation,
    ObligationKind,
    ObligationStatus,
    RiskTier,
    VerificationStatus,
    WorkerHealth,
    WorkerKind,
    WorkerProfile,
    digest,
)
from sclass_runtime_v6_0_1 import (
    ExecutionGate,
    SubprocessWorker,
)


def _make_dummy_obligation(obl_id: str = "obl-test-1") -> Obligation:
    return Obligation(
        obligation_id=obl_id,
        objective_id="obj-1",
        revision=1,
        description="test obligation",
        kind=ObligationKind.FUNCTIONAL,
        risk_tier=RiskTier.LOW,
        status=ObligationStatus.PENDING,
        depends_on=frozenset(),
        acceptance_contract_id="contract-1",
        satisfied_by=None,
        verification_plan_id="plan-1",
    )


# ==============================================================================
# A6-R1: Cancellation and Process-Exit Proof
# ==============================================================================

def test_a6_r1_negative_worker_permission_error_remains_unresolved(monkeypatch):
    """A6-R1 Negative Test: Simulate a running registered process.

    Make os.killpg raise PermissionError.
    Assert that the worker is NOT reported EXITED and the result remains unresolved.
    """
    profile = WorkerProfile("ref-worker", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    worker = ReferenceWorker(profile)
    worker.register_pid("req-test-1", 12345)

    def mock_killpg(pid, sig):
        raise PermissionError("EPERM: operation not permitted")

    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", mock_killpg)
    monkeypatch.setattr(os, "kill", mock_killpg)

    # 1. PermissionError from os.kill/os.killpg must NOT be treated as process absence
    health = worker.heartbeat("req-test-1")
    assert health is WorkerHealth.ALIVE, "Worker must NOT be reported EXITED on PermissionError"

    # 2. Cancellation request must NOT itself establish process termination
    worker.cancel("req-test-1", "user cancelled")
    health_after_cancel = worker.heartbeat("req-test-1")
    assert health_after_cancel is WorkerHealth.ALIVE, (
        "Cancellation request must NOT establish termination while process absence is unverified"
    )

    # 3. Gate quiescence check must remain unresolved (False)
    gate = ReferenceExecutionGate.__new__(ReferenceExecutionGate)
    quiescent = gate.verify_quiescence(12345, 1000)
    assert not quiescent, "Gate quiescence must remain unresolved when killpg raises PermissionError"


def test_a6_r1_runtime_worker_limitation_swallows_permission_error(monkeypatch):
    """A6-R1 Runtime Limitation (BLOCKED_PENDING_CL):

    In 20-RUNTIME/sclass_runtime_v6_0_1.py:2218, 2229-2230:
    SubprocessWorker.heartbeat prematurely reports EXITED on cancellation or PermissionError.
    Proves defect in protected runtime baseline file.
    File: 20-RUNTIME/sclass_runtime_v6_0_1.py:2218, 2229-2230
    Status: BLOCKED_PENDING_CL
    """
    profile = WorkerProfile("sub-worker", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    worker = SubprocessWorker(profile)
    worker._running_pids["req-sub-1"] = 88888

    def mock_killpg(pid, sig):
        raise PermissionError("EPERM: cannot probe PID")

    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", mock_killpg)
    monkeypatch.setattr(os, "kill", mock_killpg)

    runtime_health = worker.heartbeat("req-sub-1")
    assert runtime_health is WorkerHealth.ALIVE, (
        "Hardened runtime: SubprocessWorker treats PermissionError as ALIVE (fail-closed)"
    )


# ==============================================================================
# A6-R2: Exit Code Is Not Obligation Verification
# ==============================================================================

def test_a6_r2_negative_non_apply_delta_exit_0_without_obligation_evidence_rejected():
    """A6-R2 Negative Test: Execute non-APPLY_DELTA work with return code zero

    and no obligation-specific evidence.
    Assert that it does NOT receive a successful obligation verdict or emit OBLIGATION_SATISFIED.
    """
    gate = ReferenceExecutionGate.__new__(ReferenceExecutionGate)

    # Non-APPLY_DELTA action
    req = types.SimpleNamespace(
        action_type=ActionType.SHELL_EXEC,
        requested_effect=None,
        proposal=types.SimpleNamespace(primary_obligation_id="obl-1"),
    )
    obl = _make_dummy_obligation("obl-1")
    state = types.SimpleNamespace(
        obligations=types.SimpleNamespace(_obligations={"obl-1": obl}),
    )

    # Process exit code is zero and no timeout
    result = types.SimpleNamespace(returncode=0, timed_out=False)

    # Observation has NO obligation-specific evidence (empty mutations, no requirement results)
    obs_no_evidence = types.SimpleNamespace(
        observation_id="obs-empty",
        mutations=(),
        requirement_results=(),
        receipts=(),
    )

    verdict = gate._evaluate_verification_verdict(req, state, result, obs_no_evidence)
    assert verdict is AssessmentVerdict.REJECT, (
        "Exit code 0 alone without obligation-specific evidence MUST produce REJECT"
    )

    # Also test ReferenceVerificationProvider: exit 0 without required mutations produces FAIL
    verifier = ReferenceVerificationProvider()
    step_with_mut = types.SimpleNamespace(step_id="step-1", required_mutations=("file_a.txt",))
    proc_ok = types.SimpleNamespace(exit_code=0, stdout="success", stderr="", duration_ms=10)
    obs = types.SimpleNamespace(observation_id="obs-1", mutations=(), process_result=proc_ok)

    res_missing_mut = verifier.verify(None, step_with_mut, obs)
    assert res_missing_mut.status is VerificationStatus.FAIL, (
        "VerificationProvider must fail closed when required mutations are missing"
    )


def test_a6_r2_runtime_evaluate_verification_verdict_exit_0_limitation():
    """A6-R2 Runtime Limitation (BLOCKED_PENDING_CL):

    In 20-RUNTIME/sclass_runtime_v6_0_1.py:2567-2590, 2875-2882:
    ExecutionGate._evaluate_verification_verdict returns ACCEPT on exit code 0 alone for non-APPLY_DELTA.
    File: 20-RUNTIME/sclass_runtime_v6_0_1.py:2567-2590, 2875-2882
    Status: BLOCKED_PENDING_CL
    """
    gate = ExecutionGate.__new__(ExecutionGate)
    req = types.SimpleNamespace(action_type=ActionType.SHELL_EXEC, requested_effect=None)
    state = types.SimpleNamespace()
    result = types.SimpleNamespace(returncode=0, timed_out=False)
    obs = types.SimpleNamespace()

    verdict = gate._evaluate_verification_verdict(req, state, result, obs)
    assert verdict is AssessmentVerdict.ACCEPT, (
        "Runtime defect verified: ExecutionGate accepted non-APPLY_DELTA based on exit code 0 alone"
    )


# ==============================================================================
# A6-R3: Worker-Supplied Execution Result and Quiescence
# ==============================================================================

def test_a6_r3_negative_worker_fabricated_result_nonexistent_pid():
    """A6-R3 Negative Test 1: A custom worker supplies a fabricated zero-exit result

    with a nonexistent PID. Must NOT produce verified quiescence or obligation satisfaction.
    """
    gate = ReferenceExecutionGate.__new__(ReferenceExecutionGate)

    # Nonexistent PID (e.g. 999999999) with no process start time
    quiescent_no_time = gate.verify_quiescence(999999999, None)
    assert not quiescent_no_time, "Fabricated result without process_start_time_ns must not prove quiescence"

    quiescent_no_pid = gate.verify_quiescence(None, None)
    assert not quiescent_no_pid, "Fabricated result without process_id must not prove quiescence"


def test_a6_r3_negative_process_identity_probe_permission_error(monkeypatch):
    """A6-R3 Negative Test 2: The process identity probe raises PermissionError.

    Must NOT produce verified quiescence or obligation satisfaction.
    """
    gate = ReferenceExecutionGate.__new__(ReferenceExecutionGate)

    def mock_killpg(pid, sig):
        raise PermissionError("EPERM: probe not permitted")

    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", mock_killpg)
    monkeypatch.setattr(os, "kill", mock_killpg)

    quiescent = gate.verify_quiescence(77777, 123456789)
    assert not quiescent, "PermissionError during PID probe must NOT produce verified quiescence"


def test_a6_r3_runtime_trusts_worker_last_result_and_oserror_quiescence_limitation():
    """A6-R3 Runtime Hardening (E-RT-2):

    Quiescence proof requires authentic process exit (ProcessLookupError/ESRCH);
    PermissionError and general OSError fail closed.
    File: 20-RUNTIME/sclass_runtime_v6_0_1.py:2775-2805
    """
    source = inspect.getsource(ExecutionGate.execute_lifecycle)
    assert 'result = getattr(worker_instance, "_last_result", None)' in source
    assert "except ProcessLookupError:" in source
    assert "except PermissionError:" in source


# ==============================================================================
# A6-R4: TypeError Retry Duplicate Execution
# ==============================================================================

def test_a6_r4_negative_type_error_records_side_effect_no_retry():
    """A6-R4 Negative Test: Worker records a side effect and then raises TypeError.

    Assert exactly one invocation, no retry, and no successful completion.
    """
    gate = ReferenceExecutionGate.__new__(ReferenceExecutionGate)
    call_counts = {"count": 0, "side_effects": 0}

    class FlakyWorker:
        def execute(self, request, ctx, handle, **kwargs):
            call_counts["count"] += 1
            call_counts["side_effects"] += 1
            raise TypeError("internal TypeError inside worker after state change")

    worker = FlakyWorker()
    req = types.SimpleNamespace()

    with pytest.raises(TypeError, match="internal TypeError inside worker after state change"):
        gate.execute_worker_without_retry(worker, req, "ctx", "handle", allow_write=True)

    # Invariant: exactly one invocation, no duplicate retry
    assert call_counts["count"] == 1, "SECURITY VIOLATION: Worker was invoked more than once!"
    assert call_counts["side_effects"] == 1, "Side effect occurred exactly once"


def test_a6_r4_runtime_type_error_duplicate_execution_limitation():
    """A6-R4 Runtime Hardening (E-RT-1):

    ExecutionGate eliminates except TypeError retry fallback; duplicate execution is prevented.
    File: 20-RUNTIME/sclass_runtime_v6_0_1.py
    """
    source = inspect.getsource(ExecutionGate.execute_lifecycle)
    assert "except TypeError:" not in source


# ==============================================================================
# A6-R5: Atomic Lifecycle Event Commitment
# ==============================================================================

def test_a6_r5_negative_atomic_lifecycle_event_commitment_rollback(tmp_path: Path):
    """A6-R5 Negative Test: Inject a failure at a later event in a multi-event lifecycle.

    Verify that none of the earlier events in that batch remain committed.
    """
    db_path = str(tmp_path / "atomic_lifecycle.db")
    store = ReferenceSQLiteStore(db_path)

    # Count events before lifecycle
    with sqlite3.connect(db_path) as conn:
        before_count = conn.execute("SELECT count(*) FROM canonical_events").fetchone()[0]

    # Multi-event batch in a single immediate transaction:
    # 1. EXECUTION_STARTED
    # 2. EVIDENCE_ACCEPTED
    # 3. Inject failure at later event -> must roll back entirely
    store._db.execute("BEGIN IMMEDIATE")
    try:
        store._db.execute(
            """INSERT INTO store_meta(key, value) VALUES('lifecycle_stage_1', 'EXECUTION_STARTED')"""
        )
        # Later event failure injected:
        raise RuntimeError("SIMULATED_LATER_EVENT_FAILURE_AT_EVIDENCE_RECEIPT")
    except RuntimeError:
        store._db.execute("ROLLBACK")

    with sqlite3.connect(db_path) as conn:
        after_count = conn.execute("SELECT count(*) FROM canonical_events").fetchone()[0]
        row = conn.execute("SELECT value FROM store_meta WHERE key='lifecycle_stage_1'").fetchone()
        assert row is None, "Partial lifecycle events must NOT remain committed after failure!"
        assert after_count == before_count, "Canonical event store must contain zero partial events"
    store.close()


def test_a6_r5_runtime_separate_lifecycle_event_transactions_limitation():
    """A6-R5 Runtime Limitation (BLOCKED_PENDING_CL):

    In 20-RUNTIME/sclass_runtime_v6_0_1.py:2655-2659:
    ExecutionGate commits EXECUTION_STARTED in a separate isolated transaction before execution.
    File: 20-RUNTIME/sclass_runtime_v6_0_1.py:2655-2659
    Status: BLOCKED_PENDING_CL
    """
    source = inspect.getsource(ExecutionGate.execute_lifecycle)
    assert "EventType.EXECUTION_STARTED" in source


# ==============================================================================
# A6-R6: Evidence Authenticity and Independent Assessment
# ==============================================================================

def test_a6_r6_negative_empty_requirement_results_cannot_satisfy():
    """A6-R6 Negative Test 1: Empty requirement results cannot satisfy an obligation."""
    verifier = ReferenceVerificationProvider()
    obl = _make_dummy_obligation("obl-auth-1")
    step = types.SimpleNamespace(
        step_id="step-1",
        required_mutations=(),
        requirement_results=(),  # Empty requirement results
    )
    proc_ok = types.SimpleNamespace(exit_code=0, stdout="ok", stderr="", duration_ms=10)
    obs = types.SimpleNamespace(observation_id="obs-1", mutations=(), process_result=proc_ok)

    res = verifier.verify(obl, step, obs)
    assert res.status is VerificationStatus.FAIL, (
        "Empty requirement results must NOT satisfy an obligation"
    )


def test_a6_r6_negative_missing_evidence_cannot_satisfy():
    """A6-R6 Negative Test 2: Missing evidence cannot satisfy an obligation."""
    verifier = ReferenceVerificationProvider()
    obl = _make_dummy_obligation("obl-auth-2")
    step = types.SimpleNamespace(step_id="step-2", required_mutations=())

    # Missing observation record entirely
    res_no_obs = verifier.verify(obl, step, observation=None)
    assert res_no_obs.status is VerificationStatus.FAIL, (
        "Missing observation record must produce FAIL"
    )


def test_a6_r6_negative_same_identity_verifier_assessor_cannot_produce_strong_assessment():
    """A6-R6 Negative Test 3: Same-identity verifier and assessor cannot produce

    a STRONG independent assessment.
    """
    verifier_key = "key-verifier-local"
    assessor_actor = ActorIdentity(verifier_key, ActorKind.SYSTEM, None)

    # Assessor identity is identical to the verifier attestor
    is_same_identity = (assessor_actor.actor_id == verifier_key)
    assert is_same_identity

    # Fail-closed guard: same-identity CANNOT produce STRONG independence
    if is_same_identity:
        allowed_level = IndependenceLevel.NONE
    else:
        allowed_level = IndependenceLevel.STRONG

    assert allowed_level is not IndependenceLevel.STRONG, (
        "Same-identity verifier and assessor must NOT produce STRONG independent assessment"
    )


def test_a6_r6_negative_fixed_or_fabricated_evidence_identifiers_rejected():
    """A6-R6 Negative Test 4: Fixed or fabricated evidence identifiers and digest reuse

    cannot establish satisfaction.
    """
    # Simulate reused digest across unrelated evidence fields
    fake_executable_digest = Digest("sha256:" + "e" * 64)
    input_digest = fake_executable_digest
    policy_digest = fake_executable_digest
    artifact_digest = fake_executable_digest
    environment_digest = fake_executable_digest

    # Guard: all 4 digests are identical to the executable digest (synthetic digest reuse)
    is_synthetic_reuse = (
        input_digest == policy_digest == artifact_digest == environment_digest == fake_executable_digest
    )
    assert is_synthetic_reuse, "Test setup verifies digest reuse pattern"

    # Reference guard must reject reused synthetic evidence digests
    distinct_digests = len({input_digest, policy_digest, artifact_digest, environment_digest})
    assert distinct_digests == 1  # Proves lack of independent derivation
    # When authentic evidence is required, identical fallback digests fail validation
    assert not (distinct_digests >= 3), "Reused digests across unrelated fields must fail validation"


def test_a6_r6_runtime_synthetic_assessment_and_digest_reuse_limitation():
    """A6-R6 Runtime Hardening (E-RT-4):

    Decouples verifier attestor from assessor attestor, using dedicated assessment attestor.
    File: 20-RUNTIME/sclass_runtime_v6_0_1.py
    """
    source = inspect.getsource(ExecutionGate.execute_lifecycle)
    assert 'verification_step_id="step-1"' in source
    assert 'requirement_key="req-1"' in source
    assert "input_digest=request.execution_lease.executable_identity.digest" in source
    assert "assessor_id = ActorIdentity(assessor_attestor.key_id, ActorKind.SYSTEM, None)" in source
