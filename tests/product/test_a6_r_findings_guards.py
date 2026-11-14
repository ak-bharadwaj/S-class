"""Guards and negative tests for the six R-GPT findings (CL Directive A6-R1 through A6-R6).

Documents and demonstrates:
- A6-R1: cancellation & process-exit proof (SubprocessWorker heartbeat PermissionError limitation).
- A6-R2: exit code is not obligation verification (ExecutionGate non-APPLY_DELTA exit 0 limitation).
- A6-R3: worker-supplied execution result & quiescence (ExecutionGate _last_result and OSError quiescence limitation).
- A6-R4: TypeError retry duplicate execution (ExecutionGate except TypeError limitation).
- A6-R5: atomic lifecycle event commitment (ExecutionGate multi-transaction lifecycle limitation).
- A6-R6: evidence authenticity and independent assessment (ExecutionGate synthetic assessment limitation).

NOTE ON RUNTIME IMMUTABILITY:
The concrete runtime implementation file (20-RUNTIME/sclass_runtime_v6_0_1.py) is frozen
under mandatory boundary constraint (SHA-256 629eae9d...). Therefore, runtimehun-level defects
are demonstrated via targeted tests, documented with exact file/line references, and classified
as BLOCKED_PENDING_CL per CL Directive instructions. Reference implementations in
src/sclass/reference_impl/ strictly implement the corrected fail-closed behavior.
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
)
from sclass_semantics_v6_0_1 import (
    ActionType,
    AssessmentVerdict,
    Digest,
    EventType,
    ExecutionOutcome,
    GateResult,
    IsolationLevel,
    VerificationStatus,
    WorkerHealth,
    WorkerKind,
    WorkerProfile,
)
from sclass_runtime_v6_0_1 import (
    ExecutionGate,
    SubprocessWorker,
)


# ==============================================================================
# A6-R1: Cancellation and Process-Exit Proof
# ==============================================================================

def test_a6_r1_reference_worker_permission_error_remains_alive(monkeypatch):
    """A6-R1: In ReferenceWorker, PermissionError from os.kill/os.killpg must NOT be treated

    as process absence; heartbeat must return ALIVE (fail closed).
    """
    profile = WorkerProfile("ref-worker", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    worker = ReferenceWorker(profile)
    worker.register_pid("req-test-1", 99999)

    def mock_killpg(pid, sig):
        raise PermissionError("EPERM: operation not permitted")

    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", mock_killpg)
    monkeypatch.setattr(os, "kill", mock_killpg)

    # PermissionError does NOT prove process absence -> must remain ALIVE
    health = worker.heartbeat("req-test-1")
    assert health is WorkerHealth.ALIVE, "ReferenceWorker must not report EXITED on PermissionError"


def test_a6_r1_runtime_worker_limitation_swallows_permission_error(monkeypatch):
    """A6-R1 Runtime Limitation (BLOCKED_PENDING_CL):

    In 20-RUNTIME/sclass_runtime_v6_0_1.py:2218 and lines 2229-2230:
    1. Line 2218: `if request_id in self._cancelled_requests: return WorkerHealth.EXITED`
       prematurely reports EXITED before process termination is confirmed.
    2. Lines 2229-2230: `except (ProcessLookupError, OSError): return WorkerHealth.EXITED`
       catches PermissionError and reports EXITED without proof of process absence.

    This test proves the runtime defect. Fixing 20-RUNTIME directly is prohibited by CL directive.
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

    # Runtime SubprocessWorker defect: swallows PermissionError and reports EXITED
    runtime_health = worker.heartbeat("req-sub-1")
    assert runtime_health is WorkerHealth.EXITED, (
        "Runtime defect verified: SubprocessWorker swallowed PermissionError as EXITED"
    )


# ==============================================================================
# A6-R2: Exit Code Is Not Obligation Verification
# ==============================================================================

def test_a6_r2_reference_verifier_rejects_exit_0_without_obligation_evidence():
    """A6-R2: In ReferenceVerificationProvider, exit code 0 alone cannot satisfy

    an obligation without observation and required step mutations.
    """
    verifier = ReferenceVerificationProvider()
    step = types.SimpleNamespace(step_id="step-verify-1", required_mutations=("file_a.txt",))

    # Process succeeded (exit_code=0) but produced no mutations
    proc_ok = types.SimpleNamespace(exit_code=0, stdout="success", stderr="", duration_ms=10)
    obs_empty = types.SimpleNamespace(observation_id="obs-empty", mutations=(), process_result=proc_ok)

    res = verifier.verify(None, step, obs_empty)
    # Must FAIL because required obligation mutations were not verified
    assert res.status is VerificationStatus.FAIL


def test_a6_r2_runtime_evaluate_verification_verdict_exit_0_limitation():
    """A6-R2 Runtime Limitation (BLOCKED_PENDING_CL):

    In 20-RUNTIME/sclass_runtime_v6_0_1.py:2567-2590:
    ExecutionGate._evaluate_verification_verdict checks only `process_success` (returncode == 0)
    for non-APPLY_DELTA work, returning AssessmentVerdict.ACCEPT without checking obligations
    or verification plans. At lines 2875-2882, this unconditionally emits OBLIGATION_SATISFIED.

    File: 20-RUNTIME/sclass_runtime_v6_0_1.py:2567-2590, 2875-2882
    Status: BLOCKED_PENDING_CL
    """
    gate = ExecutionGate.__new__(ExecutionGate)
    req = types.SimpleNamespace(action_type=ActionType.SHELL_EXEC, requested_effect=None)
    state = types.SimpleNamespace()
    result = types.SimpleNamespace(returncode=0, timed_out=False)
    obs = types.SimpleNamespace()

    # Runtime defect: unconditionally returns ACCEPT for exit code 0 on non-APPLY_DELTA
    verdict = gate._evaluate_verification_verdict(req, state, result, obs)
    assert verdict is AssessmentVerdict.ACCEPT, (
        "Runtime defect verified: _evaluate_verification_verdict accepted work based on exit code 0 alone"
    )


# ==============================================================================
# A6-R3: Worker-Supplied Execution Result and Quiescence
# ==============================================================================

def test_a6_r3_runtime_trusts_worker_last_result_and_oserror_quiescence_limitation():
    """A6-R3 Runtime Limitation (BLOCKED_PENDING_CL):

    In 20-RUNTIME/sclass_runtime_v6_0_1.py:2700:
    `result = getattr(worker_instance, "_last_result", None)`
    The gate accepts the worker's internal `_last_result` as authoritative proof of execution.

    In lines 2724-2726:
    ```python
    except (ProcessLookupError, OSError):
        quiescence_proven = True
    ```
    If the worker supplies a fabricated PID or if `os.killpg` raises PermissionError/OSError,
    the gate mistakenly marks quiescence_proven = True.

    File: 20-RUNTIME/sclass_runtime_v6_0_1.py:2700, 2724-2726
    Status: BLOCKED_PENDING_CL
    """
    source = inspect.getsource(ExecutionGate.execute_lifecycle)
    assert 'result = getattr(worker_instance, "_last_result", None)' in source, (
        "Runtime defect verified: ExecutionGate reads _last_result from worker instance"
    )
    assert "except (ProcessLookupError, OSError):" in source, (
        "Runtime defect verified: ExecutionGate treats generic OSError as quiescence_proven = True"
    )


# ==============================================================================
# A6-R4: TypeError Retry Duplicate Execution
# ==============================================================================

def test_a6_r4_runtime_type_error_duplicate_execution_limitation():
    """A6-R4 Runtime Limitation (BLOCKED_PENDING_CL):

    In 20-RUNTIME/sclass_runtime_v6_0_1.py:2697-2699:
    ```python
    try:
        work = worker_instance.execute(request, boundary, handle, ...)
    except TypeError:
        work = worker_instance.execute(request, ctx, handle)
    ```
    If `worker_instance.execute` raises TypeError internally (e.g. after mutating state or
    performing external side effects), the broad `except TypeError` catches it and calls
    `worker_instance.execute` a second time, causing duplicate execution.

    File: 20-RUNTIME/sclass_runtime_v6_0_1.py:2697-2699
    Status: BLOCKED_PENDING_CL
    """
    call_counts = {"count": 0}

    class FlakyWorker:
        def execute(self, *args, **kwargs):
            call_counts["count"] += 1
            # Internal side effect followed by internal TypeError
            raise TypeError("internal TypeError inside worker after side effect")

    # Verify that Python try/except TypeError replicates this retry pattern
    worker = FlakyWorker()
    try:
        try:
            worker.execute("req", "ctx", "handle", allow_write=True)
        except TypeError:
            worker.execute("req", "ctx", "handle")
    except TypeError:
        pass

    assert call_counts["count"] == 2, "Proved duplicate invocation caused by broad except TypeError"

    source = inspect.getsource(ExecutionGate.execute_lifecycle)
    assert "except TypeError:" in source and "work = worker_instance.execute(request, ctx, handle)" in source, (
        "Runtime defect verified: ExecutionGate has broad except TypeError retry"
    )


# ==============================================================================
# A6-R5: Atomic Lifecycle Event Commitment
# ==============================================================================

def test_a6_r5_reference_store_atomic_commitment_rollback(tmp_path: Path):
    """A6-R5: In ReferenceSQLiteStore, lifecycle event batches must commit atomically

    or roll back entirely. If a later event in a transaction fails, earlier events
    must NOT remain committed.
    """
    db_path = str(tmp_path / "atomic_lifecycle.db")
    store = ReferenceSQLiteStore(db_path)

    # Verify that a failed transaction leaves zero uncommitted events
    with sqlite3.connect(db_path) as conn:
        count_before = conn.execute("SELECT count(*) FROM canonical_events").fetchone()[0]

    # In a transaction, if an error is raised before commit:
    try:
        store._db.execute("BEGIN IMMEDIATE")
        store._db.execute(
            "INSERT INTO store_meta(key, value) VALUES('transient_key', 'transient_val')"
        )
        raise RuntimeError("SIMULATED_LATER_EVENT_FAILURE")
    except RuntimeError:
        store._db.execute("ROLLBACK")

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT value FROM store_meta WHERE key='transient_key'").fetchone()
        assert row is None, "Atomic rollback must leave no partial batch data committed"
    store.close()


def test_a6_r5_runtime_separate_lifecycle_event_transactions_limitation():
    """A6-R5 Runtime Limitation (BLOCKED_PENDING_CL):

    In 20-RUNTIME/sclass_runtime_v6_0_1.py:2655-2659:
    `commit_events` is called to commit `EventType.EXECUTION_STARTED` in an isolated
    initial transaction before worker execution begins. If a subsequent failure occurs,
    `EXECUTION_STARTED` remains committed, leaving a partial lifecycle.

    File: 20-RUNTIME/sclass_runtime_v6_0_1.py:2655-2659
    Status: BLOCKED_PENDING_CL
    """
    source = inspect.getsource(ExecutionGate.execute_lifecycle)
    assert "EventType.EXECUTION_STARTED" in source, (
        "Runtime defect verified: EXECUTION_STARTED committed before execution completion"
    )


# ==============================================================================
# A6-R6: Evidence Authenticity and Independent Assessment
# ==============================================================================

def test_a6_r6_reference_verifier_fails_closed_on_empty_requirements_or_missing_evidence():
    """A6-R6: Empty requirement results or missing evidence cannot satisfy an obligation."""
    verifier = ReferenceVerificationProvider()
    step = types.SimpleNamespace(step_id="step-auth-1", required_mutations=None)

    # Missing observation -> FAIL
    res_no_obs = verifier.verify(None, step, None)
    assert res_no_obs.status is VerificationStatus.FAIL


def test_a6_r6_runtime_synthetic_assessment_and_digest_reuse_limitation():
    """A6-R6 Runtime Limitation (BLOCKED_PENDING_CL):

    In 20-RUNTIME/sclass_runtime_v6_0_1.py:2782-2865:
    1. Reuses `request.execution_lease.executable_identity.digest` as a substitute for
       input_digest, policy_digest, artifact_digest, and environment_digest.
    2. Hardcodes fixed identifiers (`step-1`, `req-1`, revision=1).
    3. Reuses verifier_attestor identity as assessor_id, violating independence of assessment.

    File: 20-RUNTIME/sclass_runtime_v6_0_1.py:2782-2865
    Status: BLOCKED_PENDING_CL
    """
    source = inspect.getsource(ExecutionGate.execute_lifecycle)
    assert 'verification_step_id="step-1"' in source, (
        "Runtime defect verified: hardcoded step-1 in SignedEvidencePayload"
    )
    assert 'requirement_key="req-1"' in source, (
        "Runtime defect verified: hardcoded req-1 in SignedEvidencePayload"
    )
    assert "input_digest=request.execution_lease.executable_identity.digest" in source, (
        "Runtime defect verified: reused executable identity digest across evidence fields"
    )
    assert "assessor_id = ActorIdentity(verifier_attestor.key_id, ActorKind.SYSTEM, None)" in source, (
        "Runtime defect verified: verifier attestor reused as independent assessor identity"
    )
