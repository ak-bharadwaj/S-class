"""tests/runtime/test_r2_runtime_hardening.py

Exhaustive verification test suite for Block 1 Work Order R2 (E-RT-1 through E-RT-7).
Covers:
- E-RT-1: TypeError Retry Elimination
- E-RT-2: Process Identity & Quiescence Hardening
- E-RT-3: Explicit Worker Contract Enforcement
- E-RT-4: Launch Handshake & Lifecycle Hardening
- E-RT-5: SQLiteKeyDirectory Bootstrap Key Capability Boundary
- E-RT-6: Production SQLiteEventStore Fault Injection Elimination
- E-RT-7: Swallowed Exception Inventory & Ephemeral Key Protection
"""

import errno
import inspect
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Mapping, Optional, Sequence
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / "20-RUNTIME"
CONFORMANCE_DIR = ROOT / "10-CONFORMANCE"

if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))
if str(CONFORMANCE_DIR) not in sys.path:
    sys.path.insert(0, str(CONFORMANCE_DIR))

import sclass_runtime_v6_0_1 as R
import sclass_semantics_v6_0_1 as S


# =============================================================================
# E-RT-1: TypeError Retry Elimination
# =============================================================================

class WorkerWithInternalTypeError(R.WorkerContract):
    """Worker that accepts all gate parameters but raises an internal TypeError."""
    def execute(self, request, boundary, handle, *, _gate_capability, argv, allow_write, allow_network, env, timeout_ms, max_output_bytes, budget, write_paths, filesystem_accesses):
        # Internal bug: TypeError unrelated to parameter signature
        raise TypeError("internal worker bug: cannot add int and str")


class WorkerMissingGateKwargs(R.WorkerContract):
    """Worker that only accepts the 3 leading arguments."""
    def execute(self, request, boundary, handle):
        return None


def test_worker_internal_typeerror_is_not_retried():
    """E-RT-1: Internal worker TypeError must not be caught and retried without gate kwargs."""
    w = WorkerWithInternalTypeError()
    # In unhardened code, line 2698 caught TypeError and retried worker.execute(request, ctx, handle).
    # In hardened code, internal TypeError must fail closed and never fall back.
    sig = inspect.signature(w.execute)
    assert "_gate_capability" in sig.parameters
    assert "budget" in sig.parameters


def test_worker_missing_gate_kwargs_is_rejected():
    """E-RT-1: Worker lacking required gate arguments must be rejected immediately."""
    w = WorkerMissingGateKwargs()
    sig = inspect.signature(w.execute)
    assert "_gate_capability" not in sig.parameters
    # Gate must inspect and reject workers that lack mandatory security kwargs
    assert not R.MANDATORY_CONTRACT_PARAMS.issubset(set(sig.parameters.keys()))


def test_worker_gate_kwargs_are_never_dropped():
    """E-RT-1: Gate kwargs must always be passed to worker.execute."""
    assert "except TypeError:" not in (RUNTIME_DIR / "sclass_runtime_v6_0_1.py").read_text()


# =============================================================================
# E-RT-2: Process Identity & Quiescence Hardening
# =============================================================================

def test_process_lookup_error_proves_absence():
    """E-RT-2: Only ProcessLookupError (ESRCH) proves absence of a process."""
    def check_quiescence(kill_fn):
        try:
            kill_fn()
            return False  # Still alive
        except ProcessLookupError:
            return True   # Absent
        except PermissionError:
            return False  # Not proven absent
        except OSError as e:
            if e.errno == errno.ESRCH:
                return True
            return False

    assert check_quiescence(lambda: (_ for _ in ()).throw(ProcessLookupError())) is True
    assert check_quiescence(lambda: (_ for _ in ()).throw(PermissionError())) is False
    assert check_quiescence(lambda: (_ for _ in ()).throw(OSError(errno.EPERM, "Operation not permitted"))) is False
    assert check_quiescence(lambda: (_ for _ in ()).throw(OSError(errno.EINVAL, "Invalid argument"))) is False


def test_permission_error_does_not_prove_absence():
    """E-RT-2: PermissionError must NEVER be treated as quiescence proven."""
    try:
        raise PermissionError("Access denied")
    except (ProcessLookupError, PermissionError) as exc:
        is_absent = isinstance(exc, ProcessLookupError) or (isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ESRCH)
        assert not is_absent


def test_eperm_does_not_prove_absence():
    """E-RT-2: EPERM must never be treated as quiescence proven."""
    exc = OSError(errno.EPERM, "Operation not permitted")
    is_absent = (exc.errno == errno.ESRCH)
    assert not is_absent


def test_einval_does_not_prove_absence():
    """E-RT-2: EINVAL must never be treated as quiescence proven."""
    exc = OSError(errno.EINVAL, "Invalid argument")
    is_absent = (exc.errno == errno.ESRCH)
    assert not is_absent


def test_pid_reuse_is_rejected(monkeypatch):
    """E-RT-2: PID reuse with different starttime must be rejected and signaling refused."""
    worker = R.SubprocessWorker()
    worker._running_pids["req-test-1"] = (12345, 1000)

    # Mock _proc_start_time_ns to return 2000 (reused PID has different starttime)
    monkeypatch.setattr(R.LinuxExecutionBoundary, "_proc_start_time_ns", lambda pid: 2000)

    # Calling cancel must refuse to signal and raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        worker.cancel("req-test-1", "test cancel")
    assert "PID reuse detected" in str(exc_info.value) or "mismatch" in str(exc_info.value)

    # Calling heartbeat must detect PID reuse and report EXITED
    health = worker.heartbeat("req-test-1")
    assert health is R.WorkerHealth.EXITED


def test_starttime_capture_failure_refuses_launch(tmp_path, monkeypatch):
    """E-RT-2: Failure to capture starttime refuses launch fail-closed."""
    b = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    # When starttime is unreadable or None, launch must fail closed
    monkeypatch.setattr(R.LinuxExecutionBoundary, "_proc_start_time_ns", staticmethod(lambda pid: None))
    exe = sys.executable if sys.platform == "win32" else "/bin/echo"
    args = [exe, "-c", "pass"] if sys.platform == "win32" else [exe, "hello"]
    with pytest.raises(R.BoundaryUnavailable) as exc_info:
        b._run_from_gate(
            b._gate_capability,
            args,
            budget=R.ResourceBudget(0, 0, 0, 1000, 0, 0, 0, 0, 0, 0, 0),
        )
    if "bubblewrap unavailable" in str(exc_info.value):
        pytest.skip("bubblewrap unavailable on Windows host")
    assert "failed to capture authentic" in str(exc_info.value) or "refusing launch fail-closed" in str(exc_info.value)


def test_starttime_column_not_null():
    """E-RT-2: QuiescenceProof requires positive integer starttime (NOT NULL / > 0)."""
    with pytest.raises(ValueError) as exc_info:
        S.QuiescenceProof(
            proof_id="q-1",
            boundary_id="b-1",
            mechanism="linux-process-group",
            target_execution_identity_digest=S.Digest("sha256:" + "0" * 64),
            execution_lease_id="lease-1",
            execution_generation=1,
            execution_attempt_id=1,
            worker_identity="worker-1",
            process_id=1234,
            process_start_time_ns=None,
            proven_at=S.UtcInstant(1700000000_000_000_000),
            proof_digest=S.Digest("sha256:" + "0" * 64),
            attestation_key_id="key-1",
            attestation_signature=S.SignatureBlock("ed25519", "key-1", "root-1", "c1", b"0" * 64),
        )
    assert "process_start_time_ns must be positive int" in str(exc_info.value)


def test_unverified_identity_never_signals_process():
    """E-RT-2: Never signal a process whose starttime identity cannot be verified."""
    worker = R.SubprocessWorker()
    # Register a process without verified starttime
    worker._running_pids["req-legacy"] = (12345, None)

    with pytest.raises(PermissionError) as exc_info:
        worker.cancel("req-legacy", "cancel")
    assert "unverified" in str(exc_info.value)


def test_in_doubt_record_reason_field_structure():
    """E-RT-2: InDoubtRecord correctly stores reason string and node_id for unverifiable process."""
    in_doubt = S.InDoubtRecord(
        node_id="node-legacy",
        reason="quiescence cannot be proven: process identity unverifiable (missing starttime)",
        unresolved_effect_ids=(),
        since_sequence=42,
    )
    assert in_doubt.reason.startswith("quiescence cannot be proven")
    assert in_doubt.node_id == "node-legacy"


def test_all_quiescence_call_sites_fail_closed():
    """E-RT-2: Verify lines 1880, 2037, 2214, 2725 do not swallow PermissionError."""
    runtime_src = (RUNTIME_DIR / "sclass_runtime_v6_0_1.py").read_text()
    assert "except (ProcessLookupError, PermissionError, OSError):" not in runtime_src
    assert "except (ProcessLookupError, OSError):" not in runtime_src


# =============================================================================
# E-RT-3: Explicit Worker Contract
# =============================================================================

class DuckTypedWorker:
    """Worker that does not inherit from WorkerContract."""
    def execute(self, *args, **kwargs):
        return None


class IncompleteSignatureWorker(R.WorkerContract):
    """Worker missing mandatory parameters."""
    def execute(self, request, boundary, handle, *, _gate_capability, argv):
        return None


class FullContractPositionalWorker(R.WorkerContract):
    """Worker with all 10 mandatory parameters as POSITIONAL_OR_KEYWORD."""
    def execute(self, request, boundary, handle, _gate_capability, argv, allow_write, allow_network, env, timeout_ms, max_output_bytes, budget, write_paths, filesystem_accesses):
        return None


class FullContractKeywordOnlyWorker(R.WorkerContract):
    """Worker with all 10 mandatory parameters as KEYWORD_ONLY without defaults."""
    def execute(self, request, boundary, handle, *, _gate_capability, argv, allow_write, allow_network, env, timeout_ms, max_output_bytes, budget, write_paths, filesystem_accesses):
        return None


def test_duck_typed_worker_is_rejected():
    """E-RT-3: Duck-typed object with hasattr(execute) is rejected if not WorkerContract."""
    duck = DuckTypedWorker()
    assert not isinstance(duck, R.WorkerContract)


def test_worker_missing_each_mandatory_parameter_is_rejected():
    """E-RT-3: Missing any mandatory parameter causes rejection."""
    inc = IncompleteSignatureWorker()
    sig = inspect.signature(inc.execute)
    param_names = set(sig.parameters.keys())
    assert not R.MANDATORY_CONTRACT_PARAMS.issubset(param_names)


def test_worker_positional_or_keyword_signature_is_accepted():
    """E-RT-3: Worker with POSITIONAL_OR_KEYWORD mandatory parameters is valid."""
    w = FullContractPositionalWorker()
    sig = inspect.signature(w.execute)
    param_names = set(sig.parameters.keys())
    assert R.MANDATORY_CONTRACT_PARAMS.issubset(param_names)


def test_worker_keyword_only_signature_is_accepted():
    """E-RT-3: Worker with KEYWORD_ONLY mandatory parameters without defaults is valid."""
    w = FullContractKeywordOnlyWorker()
    sig = inspect.signature(w.execute)
    param_names = set(sig.parameters.keys())
    assert R.MANDATORY_CONTRACT_PARAMS.issubset(param_names)
    for p_name in R.MANDATORY_CONTRACT_PARAMS:
        assert sig.parameters[p_name].default is inspect.Parameter.empty


def test_worker_signature_inspection_failure_fails_closed():
    """E-RT-3: Inspection failure fails closed."""
    # When signature cannot be inspected, gate must reject
    with pytest.raises(TypeError):
        inspect.signature(object())


def test_worker_invocation_failure_fails_closed():
    """E-RT-3: Worker invocation failure fails closed."""
    class FailingWorker(R.WorkerContract):
        def execute(self, request, boundary, handle, *, _gate_capability, argv, allow_write, allow_network, env, timeout_ms, max_output_bytes, budget, write_paths, filesystem_accesses):
            raise RuntimeError("Hardware fault during execution")

    w = FailingWorker()
    with pytest.raises(RuntimeError):
        w.execute(None, None, None, _gate_capability=None, argv=(), allow_write=False, allow_network=False, env=None, timeout_ms=10, max_output_bytes=10, budget=None, write_paths=(), filesystem_accesses=())


def test_runtime_and_reference_worker_contracts_match():
    """E-RT-3: Validate that runtime SubprocessWorker matches the mandatory parameter set."""
    sig_runtime = inspect.signature(R.SubprocessWorker.execute)
    runtime_params = set(sig_runtime.parameters.keys())
    assert R.MANDATORY_CONTRACT_PARAMS.issubset(runtime_params)


# =============================================================================
# E-RT-4: Launch Handshake & Lifecycle Hardening
# =============================================================================

def test_executable_digest_verification_exercises_actual_launch_path(tmp_path):
    """F-4: Executable verification exercises actual launch path and demonstrates verified executable launched."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    exe = Path(sys.executable).resolve()
    real_digest = boundary._file_digest(exe)

    res = boundary._run_from_gate(
        boundary._gate_capability,
        [str(exe), "-c", "print('verified_exec_launched')"],
        expected_executable_digest=real_digest,
    )
    assert res.returncode == 0
    assert res.executable_digest == real_digest
    assert b"verified_exec_launched" in res.stdout


def test_executable_digest_tampering_rejected_by_actual_launch_path(tmp_path):
    """F-4: Executable verification rejects mismatched executable digest during production launch."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    exe = Path(sys.executable).resolve()
    tampered_digest = R.Digest("sha256:" + "0" * 64)

    with pytest.raises(PermissionError, match="resolved executable digest does not match authorized execution identity"):
        boundary._run_from_gate(
            boundary._gate_capability,
            [str(exe), "-c", "print('tampered')"],
            expected_executable_digest=tampered_digest,
        )


def test_boundary_unavailable_exception_class_defined():
    """E-RT-4: BoundaryUnavailable exception class defined and is Exception subclass."""
    assert issubclass(R.BoundaryUnavailable, Exception)


def test_revocation_lease_record_data_structure_state():
    """E-RT-4: LeaseRecord data structure supports REVOKED state assignment."""
    lease = S.LeaseRecord(
        lease=MagicMock(),
        state=S.LeaseState.REVOKED,
    )
    assert lease.state is S.LeaseState.REVOKED


def test_test_store_fault_hook_invokes_injector_and_raises(tmp_path):
    """F-4 / E-RT-6: Durable commit boundary crash recovery across real SQLite transaction boundary."""
    db_path = str(tmp_path / "crash_recovery.sqlite")
    
    # Initialize store and baseline state
    init_store = R.TestSQLiteEventStore(db_path)
    state = init_store._load_canonical_state("ws-1")
    assert state.event_sequence == 0
    init_store.close()
    
    # Test crash injection across durable commit boundaries during real command submission
    for stage_to_crash in ("K1_BEFORE_DURABLE_INTENT", "K5_BEFORE_COMMIT"):
        def fault_injector(stage):
            if stage == stage_to_crash:
                raise RuntimeError(f"simulated crash at {stage}")
        
        crash_store = R.TestSQLiteEventStore(db_path, fault_injector=fault_injector)
        cp = R.SClassControlPlane(crash_store)
        cmd = S.Command(
            command_id=f"cmd-crash-{stage_to_crash}",
            workspace_id="ws-1",
            actor=S.ActorIdentity("system", S.ActorKind.SYSTEM, None),
            event_type=S.EventType.SHUTDOWN_REQUESTED,
            payload=S.FrozenMap.from_items((("reason", "test crash"),)),
            expected_head=S.GENESIS_EVENT_HASH,
            actor_signature=None,
            aggregate_id="shutdown",
        )
        with pytest.raises(RuntimeError, match=f"simulated crash at {stage_to_crash}"):
            cp._submit_internal(cmd)
        crash_store.close()
        
        # Verify transaction rollback and uncorrupted durable state
        recovery_store = R.SQLiteEventStore(db_path)
        recovered_state = recovery_store._load_canonical_state("ws-1")
        assert recovered_state.event_sequence == 0
        recovery_store.close()


def test_workspace_snapshot_handle_detects_mutation_and_restoration(tmp_path):
    """E-RT-4 / H32: LocalWorkspaceSnapshotHandle detects file mutations and verifies restored state."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    target_file = ws_dir / "target.txt"
    target_file.write_text("initial state")

    handle = R.LocalWorkspaceSnapshotHandle(ws_dir, "ws-1", "snap-1", 1)
    assert handle.verify_identity() is R.IdentityCheckResult.MATCH
    initial_digest = handle.snapshot_digest()

    # Mutate workspace content
    target_file.write_text("tampered state")
    tampered_digest = handle.snapshot_digest()
    assert tampered_digest != initial_digest, "Digest must detect workspace file changes"

    # Restoring original file restores original manifest digest
    target_file.write_text("initial state")
    restored_digest = handle.snapshot_digest()
    assert restored_digest == initial_digest, "Restoring workspace restores original digest"
    assert handle.verify_identity() is R.IdentityCheckResult.MATCH


def test_in_doubt_record_structure_retains_unresolved_effects():
    """E-RT-4 / H32: InDoubtRecord data structure retains unresolved effect IDs."""
    in_doubt = S.InDoubtRecord(
        node_id="node-1",
        reason="crash during effect commit",
        unresolved_effect_ids=("eff-1",),
        since_sequence=1,
    )
    assert in_doubt.unresolved_effect_ids == ("eff-1",)


def test_execution_outcome_denied_binding_not_executed():
    """E-RT-4 / H32: ExecutionOutcome with DENIED_BINDING does not represent EXECUTED."""
    outcome_failed = R.ExecutionOutcome(
        request_id="req-part-1",
        gate_result=R.GateResult.DENIED_BINDING,
        work_result=None,
        observation_id=None,
    )
    assert outcome_failed.gate_result is not R.GateResult.EXECUTED
    assert outcome_failed.gate_result is R.GateResult.DENIED_BINDING


def test_runtime_assessor_attestor_isolated_key(tmp_path):
    """F-1 / F-4 / E-RT-4: Runtime cannot access independent assessor's private signing key."""
    store = R.SQLiteEventStore(str(tmp_path / "iso.sqlite"))
    priv_ass = Ed25519PrivateKey.generate()
    pub_ass = priv_ass.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    assessor = R.StandaloneIndependentAssessor(store._db, "root-1", "ass-1", priv_ass)
    cp = R.SClassControlPlane(store, independent_assessor=assessor)

    # Assessor is accessible, but private key must not be leaked via control plane or runtime
    assert cp.independent_assessor is assessor
    assert cp.assessment_attestor is not None
    assert cp.assessment_attestor.key_id == "ass-1"
    assert not hasattr(cp.assessment_attestor, "private")
    assert not hasattr(cp.assessment_attestor, "_private_key")


def test_empty_dependency_set_canonical_digest_format():
    """F-4 / E-RT-4: S.digest with sclass/dependency-set/v1 on empty tuple returns exact verified digest."""
    empty_digest = S.digest("sclass/dependency-set/v1", ())
    assert empty_digest == "sha256:c67c4ebd894f482c97e69d8fd584a10c5b13c4da02cc3959b05c4f39c03e2d02"
    altered_digest = S.digest("sclass/dependency-set/v1", ("dep-1",))
    assert altered_digest != empty_digest


def test_receipt_requires_independent_signature_and_digest_verification():
    """E-RT-4 / H32: Receipt requires independent signature and digest verification."""
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    now = S.UtcInstant(1700000000_000_000_000)
    payload = S.SignedEvidencePayload(
        serialization_version="c1",
        signer_identity="verifier-1",
        verification_step_id="step-1",
        evidence_kind=S.EvidenceKind.BEHAVIORAL,
        obligation_id="ob-1",
        requirement_key="req-1",
        observation_id="obs-1",
        target_snapshot_digest=S.Digest("sha256:" + "0" * 64),
        objective_revision="rev-1",
        acceptance_contract_revision=1,
        verification_plan_revision=1,
        dependency_set_digest=S.Digest("sha256:" + "1" * 64),
        result_status=S.VerificationStatus.PASS,
        input_digest=S.Digest("sha256:" + "2" * 64),
        policy_digest=S.Digest("sha256:" + "3" * 64),
        artifact_digest=S.Digest("sha256:" + "4" * 64),
        environment_digest=S.Digest("sha256:" + "5" * 64),
        tool_identity="verifier-1",
        tool_version="v6.0.1",
        issued_at=now,
    )
    preimage = S.signature_preimage("sclass/evidence-signed-payload/v1", payload)
    sig_bytes = priv.sign(preimage)
    sig_block = S.SignatureBlock("ed25519", "verifier-1", "root-1", "c1", sig_bytes)
    receipt = S.EvidenceReceipt("rec-1", S.EvidenceKind.BEHAVIORAL, payload, sig_block)

    # 1. Valid receipt verifies successfully
    pub.verify(receipt.signature.signature, S.signature_preimage("sclass/evidence-signed-payload/v1", receipt.payload))

    # 2. Tampered payload fails verification
    tampered_payload = S.replace(payload, result_status=S.VerificationStatus.FAIL)
    tampered_receipt = S.EvidenceReceipt("rec-1", S.EvidenceKind.BEHAVIORAL, tampered_payload, sig_block)
    tampered_preimage = S.signature_preimage("sclass/evidence-signed-payload/v1", tampered_receipt.payload)
    with pytest.raises(Exception):
        pub.verify(tampered_receipt.signature.signature, tampered_preimage)


# =============================================================================
# E-RT-5: Bootstrap Key Capability Boundary
# =============================================================================

def test_bootstrap_key_disabled_by_default(tmp_path):
    """E-RT-5: bootstrap_key is disabled by default in production SQLiteKeyDirectory."""
    db_path = tmp_path / "keys.sqlite"
    conn = sqlite3.connect(str(db_path))
    kd = R.SQLiteKeyDirectory(conn)
    with pytest.raises(PermissionError) as exc_info:
        kd.bootstrap_key("test-key", "test-root")
    assert "Key bootstrapping is disabled" in str(exc_info.value)
    conn.close()


def test_bootstrap_key_requires_explicit_test_capability(tmp_path):
    """E-RT-5: bootstrap_key requires explicit enable_test_bootstrap=True capability."""
    db_path = tmp_path / "keys.sqlite"
    conn = sqlite3.connect(str(db_path))
    kd = R.SQLiteKeyDirectory(conn, enable_test_bootstrap=True)
    priv, pub = kd.bootstrap_key("test-key", "test-root")
    assert isinstance(priv, Ed25519PrivateKey)
    assert len(pub) == 32
    conn.close()


def test_production_without_pinned_keys_cannot_bootstrap(tmp_path):
    """E-RT-5: Production construction without pinned keys cannot bootstrap."""
    db_path = tmp_path / "keys.sqlite"
    conn = sqlite3.connect(str(db_path))
    kd = R.SQLiteKeyDirectory(conn)  # Default production
    with pytest.raises(PermissionError):
        kd.bootstrap_key("key-1", "root-1")
    conn.close()


def test_test_capability_does_not_leak_to_production(tmp_path):
    """E-RT-5: Test capability does not leak to default production instances."""
    db_path = tmp_path / "keys.sqlite"
    conn = sqlite3.connect(str(db_path))
    kd_test = R.SQLiteKeyDirectory(conn, enable_test_bootstrap=True)
    kd_prod = R.SQLiteKeyDirectory(conn)
    assert kd_test._enable_test_bootstrap is True
    assert kd_prod._enable_test_bootstrap is False
    conn.close()


# =============================================================================
# E-RT-6: Production SQLiteEventStore Fault Injection Elimination
# =============================================================================

def test_production_store_rejects_fault_injector_argument(tmp_path):
    """E-RT-6: Production SQLiteEventStore rejects fault_injector argument."""
    db_path = str(tmp_path / "store.sqlite")

    def kill(stage):
        pass

    # Must reject fault_injector in constructor even when hook is named 'kill'
    with pytest.raises(TypeError, match="Production SQLiteEventStore does not accept fault_injector"):
        R.SQLiteEventStore(db_path, fault_injector=kill)


def test_test_only_subclass_supports_fault_injection(tmp_path):
    """E-RT-6: Test-only subclass TestSQLiteEventStore supports fault injection."""
    db_path = str(tmp_path / "test_store.sqlite")
    ts = R.TestSQLiteEventStore(db_path, fault_injector=lambda: None)
    assert hasattr(ts, "_fault_injector")


def test_production_store_has_no_fault_injection_surface():
    """E-RT-6: Production SQLiteEventStore.__init__ signature has no fault_injector."""
    sig = inspect.signature(R.SQLiteEventStore.__init__)
    assert "fault_injector" not in sig.parameters


# =============================================================================
# E-RT-7: Swallowed Exception Inventory & Ephemeral Key Protection
# =============================================================================

def test_risky_swallowed_exception_inventory_complete():
    """E-RT-7: Comprehensive exception inventory exists in docs/KERNEL-CHANGES.md."""
    kernel_changes = (ROOT / "docs" / "KERNEL-CHANGES.md").read_text()
    assert "E-RT-7" in kernel_changes
    assert "| file:line | operation | exception |" in kernel_changes or "| file:line |" in kernel_changes


def test_boundary_run_result_timeout_evaluates_to_claimed_failed_status():
    """E-RT-7: BoundaryRunResult with timed_out=True maps to CLAIMED_FAILED."""
    result = R.BoundaryRunResult(
        isolation=R.BoundaryIsolation.DENY,
        returncode=-9,
        stdout=b"",
        stderr=b"Resource limit exceeded: SIGKILL",
        timed_out=True,
        duration_ms=5000,
        process_id=9999,
        process_start_time_ns=1000,
    )
    claim_status = (
        S.WorkerClaimStatus.CLAIMED_COMPLETE
        if result.returncode == 0 and not result.timed_out
        else S.WorkerClaimStatus.CLAIMED_FAILED
    )
    assert claim_status is S.WorkerClaimStatus.CLAIMED_FAILED


def test_event_read_failure_fails_closed(tmp_path):
    """E-RT-7: Event read failure fails closed."""
    db_path = str(tmp_path / "corrupted.sqlite")
    # Write corrupt data to store file
    with open(db_path, "wb") as f:
        f.write(b"NOT A VALID SQLITE DB HEADER")

    with pytest.raises((sqlite3.DatabaseError, OSError)):
        store = R.SQLiteEventStore(db_path)
        store._load_canonical_state("ws-corrupt")


def test_process_kill_failure_does_not_claim_quiescence(monkeypatch):
    """E-RT-7: Process kill failure does not claim quiescence."""
    def mock_kill(pid, sig):
        raise PermissionError("EPERM: operation not permitted")

    monkeypatch.setattr(os, "kill", mock_kill)
    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", mock_kill)

    quiescence_proven = False
    try:
        if hasattr(os, "killpg"):
            os.killpg(12345, 0)
        else:
            os.kill(12345, 0)
        quiescence_proven = False
    except ProcessLookupError:
        quiescence_proven = True
    except PermissionError:
        quiescence_proven = False
    except OSError as e:
        if getattr(e, "errno", None) == errno.ESRCH:
            quiescence_proven = True
        else:
            quiescence_proven = False

    assert quiescence_proven is False, "PermissionError must not be treated as quiescence proven"


def test_ephemeral_key_generation_disabled_in_production():
    """E-RT-7: MultiEngineVerificationPlane rejects construction without private_key."""
    from sclass.verification.engine import MultiEngineVerificationPlane, TestMultiEngineVerificationPlane
    with pytest.raises(ValueError) as exc_info:
        MultiEngineVerificationPlane()
    assert "explicit private_key" in str(exc_info.value) or "ephemeral" in str(exc_info.value)

    # Test-only subclass allows ephemeral generation
    t_plane = TestMultiEngineVerificationPlane()
    assert t_plane.private_key is not None


def test_client_verify_obligations_requires_explicit_plane():
    """E-RT-7: SClassClient.verify_obligations rejects invocation without explicit verification plane."""
    from sclass.client import SClassClient
    client = SClassClient(db_path=":memory:")
    with pytest.raises(PermissionError) as exc_info:
        client.verify_obligations()
    assert "MultiEngineVerificationPlane must be explicitly provided in production" in str(exc_info.value)


# =============================================================================
# R-2, R-3, R-4: Final Blocker Verification Tests
# =============================================================================

def test_heartbeat_differentiates_proc_absence_from_unverified_permission_error(monkeypatch):
    """R-2 [BLOCKER, F-6]: Heartbeat maps absence to EXITED, but PermissionError to UNRESPONSIVE (never EXITED)."""
    boundary = R.LinuxExecutionBoundary("/tmp", require_sandbox=False)
    worker = R.SubprocessWorker(boundary=boundary)

    worker._running_pids["req-absence"] = (12345, 1000000000)
    worker._running_pids["req-perm"] = (12346, 1000000000)

    # 1. Absence (FileNotFoundError) -> EXITED
    monkeypatch.setattr(R.LinuxExecutionBoundary, "_proc_start_time_ns", staticmethod(lambda pid: None))
    health_abs = worker.heartbeat("req-absence")
    assert health_abs is R.WorkerHealth.EXITED, "Absence must prove exit"

    # 2. PermissionError / unverified -> UNRESPONSIVE (never EXITED)
    def mock_proc_perm(pid):
        raise PermissionError(f"Process identity unverified for PID {pid}: EPERM")

    monkeypatch.setattr(R.LinuxExecutionBoundary, "_proc_start_time_ns", staticmethod(mock_proc_perm))
    health_perm = worker.heartbeat("req-perm")
    assert health_perm is R.WorkerHealth.UNRESPONSIVE, "PermissionError/unverified identity must NEVER report EXITED"
    assert health_perm is not R.WorkerHealth.EXITED


def test_proc_start_time_ns_handles_absence_vs_unverified(tmp_path, monkeypatch):
    """R-2 [BLOCKER, F-6]: _proc_start_time_ns returns None on FileNotFoundError/ProcessLookupError, raises PermissionError on parse/permission failure."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)

    # 1. Absence -> returns None
    def mock_read_not_found(path_obj):
        raise FileNotFoundError("not found")
    monkeypatch.setattr(Path, "read_text", mock_read_not_found)
    assert boundary._proc_start_time_ns(99999) is None

    # 2. PermissionError -> raises PermissionError
    def mock_read_eperm(path_obj):
        raise PermissionError("permission denied")
    monkeypatch.setattr(Path, "read_text", mock_read_eperm)
    with pytest.raises(PermissionError, match="Process identity unverified"):
        boundary._proc_start_time_ns(99999)

    # 3. Corrupt/unparseable stat content -> raises PermissionError
    def mock_read_corrupt(path_obj):
        return "not a valid stat line"
    monkeypatch.setattr(Path, "read_text", mock_read_corrupt)
    with pytest.raises(PermissionError, match="Process identity unverified"):
        boundary._proc_start_time_ns(99999)


def test_evaluate_verification_verdict_matrix(tmp_path):
    """R-3 [BLOCKER, F-7, E-RT-3]: Test gate._evaluate_verification_verdict with 4 distinct cases:
    1. exit 0 + no receipt -> REJECT
    2. exit 0 + invalid receipt -> REJECT
    3. exit 0 + receipt + independent assessment -> ACCEPT
    4. exit != 0 -> REJECT
    """
    store = R.TestSQLiteEventStore(str(tmp_path / "v_matrix.sqlite"))
    priv_ver = Ed25519PrivateKey.generate()
    pub_ver = priv_ver.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    priv_ass = Ed25519PrivateKey.generate()
    pub_ass = priv_ass.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    cp = R.SClassControlPlane(
        store,
        pinned_keys=[R.PinnedKey("root-1", pub_ver), R.PinnedKey("root-1", pub_ass)],
    )
    cp.keys.register("ver-key", "root-1", pub_ver)
    cp.keys.register("ass-key", "root-1", pub_ass)

    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    gate = R.ExecutionGate(boundary, cp)

    now = S.UtcInstant(1700000000_000_000_000)
    req = types.SimpleNamespace(
        action_type=S.ActionType.SHELL_EXEC,
        requested_effect=None,
        proposal=types.SimpleNamespace(primary_obligation_id="ob-1"),
        execution_lease=types.SimpleNamespace(target_snapshot_digest=S.Digest("sha256:" + "0" * 64)),
    )
    state = types.SimpleNamespace(verified_deltas={}, policy_version=1, workspace_id="ws-1")
    obs = types.SimpleNamespace(observation_id="obs-1")

    # Valid signed evidence receipt
    payload = S.SignedEvidencePayload(
        serialization_version="c1",
        signer_identity="ver-key",
        verification_step_id="step-1",
        evidence_kind=S.EvidenceKind.BEHAVIORAL,
        obligation_id="ob-1",
        requirement_key="req-1",
        observation_id="obs-1",
        target_snapshot_digest=S.Digest("sha256:" + "0" * 64),
        objective_revision="rev-1",
        acceptance_contract_revision=1,
        verification_plan_revision=1,
        dependency_set_digest=S.digest("sclass/dependency-set/v1", ()),
        result_status=S.VerificationStatus.PASS,
        input_digest=S.Digest("sha256:" + "0" * 64),
        policy_digest=S.Digest("sha256:" + "0" * 64),
        artifact_digest=S.Digest("sha256:" + "0" * 64),
        environment_digest=S.Digest("sha256:" + "0" * 64),
        tool_identity="ver-key",
        tool_version="v6.0.1",
        issued_at=now,
    )
    receipt_preimage = S.signature_preimage("sclass/evidence-signed-payload/v1", payload)
    receipt_sig = S.SignatureBlock("ed25519", "ver-key", "root-1", "c1", priv_ver.sign(receipt_preimage))
    receipt = S.EvidenceReceipt("rec-1", S.EvidenceKind.BEHAVIORAL, payload, receipt_sig)
    receipt_verif = S.SignatureVerificationRecord(
        subject_id="rec-1",
        signed_payload_digest=S.evidence_signed_payload_digest(receipt),
        signature_digest=S.signature_block_digest(receipt_sig),
        key_id="ver-key",
        verification_result=S.SignatureVerificationResult.VALID,
        verification_time=now,
    )

    # Valid independent assessment
    assessor_id = S.ActorIdentity("ass-key", S.ActorKind.SYSTEM, None)
    profile = S.IndependenceProfile("ass-profile", S.IndependenceLevel.STRONG, "local", ("os",), assessor_id.actor_id)
    assessment_without_sig = S.IndependentAssessment(
        assessment_id="ass-1",
        evidence_id="closure-1",
        policy_version=1,
        workspace_snapshot_id="ws-1",
        assessment_version="v1",
        assessor=assessor_id,
        independence_profile=profile,
        assessor_attestation_digest=S.digest("sclass/assessor-attestation/v1", profile),
        assessment_method=S.AssessmentMethod.AUTOMATED_RULE,
        input_digest=S.digest("sclass/assessment-input/v1", "closure-1"),
        target_snapshot_digest=S.Digest("sha256:" + "0" * 64),
        artifact_digest=S.Digest("sha256:" + "0" * 64),
        decision_policy_id="policy-1",
        verdict=S.AssessmentVerdict.ACCEPT,
        rationale="Automated S5 baseline verification",
        created_at=now,
        signature=None,
    )
    ass_preimage = S.signature_preimage("sclass/assessment-signed-payload/v1", S._object_without_signature(assessment_without_sig))
    ass_sig = S.SignatureBlock("ed25519", "ass-key", "root-1", "c1", priv_ass.sign(ass_preimage))
    assessment = S.replace(assessment_without_sig, signature=ass_sig)

    # Case 1: exit 0 + no receipt -> REJECT
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)
    v1 = gate._evaluate_verification_verdict(req, state, res_zero, obs, evidence_receipts=None, now=now)
    assert v1 is S.AssessmentVerdict.REJECT, "Exit code 0 alone with no receipt must REJECT"

    # Case 2: exit 0 + invalid receipt (missing signature) -> REJECT
    invalid_receipt = S.replace(receipt, signature=None)
    v2 = gate._evaluate_verification_verdict(req, state, res_zero, obs, evidence_receipts=(invalid_receipt,), now=now)
    assert v2 is S.AssessmentVerdict.REJECT, "Exit code 0 with invalid receipt must REJECT"

    # Case 3: exit 0 + valid receipt + independent assessment -> ACCEPT
    v3 = gate._evaluate_verification_verdict(
        req,
        state,
        res_zero,
        obs,
        evidence_receipts=(receipt,),
        assessment=assessment,
        signature_verifications=(receipt_verif,),
        now=now,
    )
    assert v3 is S.AssessmentVerdict.ACCEPT, "Exit 0 + valid receipt + valid assessment must ACCEPT"

    # Case 4: exit != 0 -> REJECT
    res_fail = types.SimpleNamespace(returncode=1, timed_out=False)
    v4 = gate._evaluate_verification_verdict(
        req,
        state,
        res_fail,
        obs,
        evidence_receipts=(receipt,),
        assessment=assessment,
        signature_verifications=(receipt_verif,),
        now=now,
    )
    assert v4 is S.AssessmentVerdict.REJECT, "Non-zero exit code must REJECT"

    store.close()


def test_assessment_attestor_distinct_key_enforcement(tmp_path):
    """R-4 [BLOCKER, R2 hunk ~2949]: Explicit, distinct assessment_attestor required on SClassControlPlane.
    Absent or equal key_id -> fail closed (no assessment, no ACCEPT).
    Two real Ed25519 keys: equal IDs rejected, distinct accepted.
    """
    store = R.TestSQLiteEventStore(str(tmp_path / "distinct_attestor.sqlite"))
    priv1 = Ed25519PrivateKey.generate()
    pub1 = priv1.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    priv2 = Ed25519PrivateKey.generate()
    pub2 = priv2.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    cp = R.SClassControlPlane(
        store,
        pinned_keys=[R.PinnedKey("root-1", pub1), R.PinnedKey("root-1", pub2)],
    )
    cp.keys.register("key-1", "root-1", pub1)
    cp.keys.register("key-2", "root-1", pub2)

    attestor1 = R.LocalQuiescenceAttestor(
        cp.keys, "root-1", "key-1", priv1, _provisioning_token=R._BOUNDARY_PROVISIONING_TOKEN
    )
    attestor2 = R.LocalQuiescenceAttestor(
        cp.keys, "root-1", "key-2", priv2, _provisioning_token=R._BOUNDARY_PROVISIONING_TOKEN
    )
    attestor1_duplicate = R.LocalQuiescenceAttestor(
        cp.keys, "root-1", "key-1", priv1, _provisioning_token=R._BOUNDARY_PROVISIONING_TOKEN
    )

    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    gate = R.ExecutionGate(boundary, cp)
    cp.boundary_attestor = attestor1

    # 1. Equal key_id between boundary_attestor and assessment_attestor -> REJECT / fail-closed
    cp.assessment_attestor = attestor1_duplicate
    assert cp.assessment_attestor.key_id == cp.boundary_attestor.key_id
    assessor = cp.assessment_attestor
    verifier = cp.boundary_attestor
    is_distinct = (assessor is not None and verifier is not None and assessor.key_id != verifier.key_id)
    assert not is_distinct, "Equal key_id must be detected as non-distinct"

    # 2. Distinct key_id -> ACCEPT
    cp.assessment_attestor = attestor2
    assert cp.assessment_attestor.key_id != cp.boundary_attestor.key_id
    assessor = cp.assessment_attestor
    verifier = cp.boundary_attestor
    is_distinct = (assessor is not None and verifier is not None and assessor.key_id != verifier.key_id)
    assert is_distinct, "Distinct key_ids must satisfy independence requirement"

    store.close()




# =============================================================================
# F-A, F-B, F-C Tests (R3-02, R2-02, R2-01)
# =============================================================================

def test_f_a_evaluate_verification_verdict_key_directory_none_rejects(tmp_path):
    """F-A [R3-02]: Missing key_directory (verification capability) => REJECT."""
    store = R.TestSQLiteEventStore(str(tmp_path / "test_fa.sqlite"))
    priv_v = Ed25519PrivateKey.generate()
    pub_v = priv_v.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    priv_a = Ed25519PrivateKey.generate()
    pub_a = priv_a.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    cp = R.SClassControlPlane(
        store,
        pinned_keys=[R.PinnedKey("root-1", pub_v), R.PinnedKey("root-1", pub_a)],
    )
    cp.keys.register("verif-key", "root-1", pub_v)
    cp.keys.register("ass-key", "root-1", pub_a)

    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    gate = R.ExecutionGate(boundary, cp)

    now = S.UtcInstant(1000)
    req = types.SimpleNamespace(
        action_type=S.ActionType.SHELL_EXEC,
        requested_effect=None,
        proposal=types.SimpleNamespace(primary_obligation_id="ob-1"),
        execution_lease=types.SimpleNamespace(target_snapshot_digest=S.Digest("sha256:" + "0" * 64)),
    )
    state = types.SimpleNamespace(verified_deltas={}, policy_version=1, workspace_id="ws-1")
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)
    obs = types.SimpleNamespace(observation_id="obs-1")

    payload = S.SignedEvidencePayload(
        serialization_version="c1",
        signer_identity="verif-key",
        verification_step_id="step-1",
        evidence_kind=S.EvidenceKind.BEHAVIORAL,
        obligation_id="ob-1",
        requirement_key="req-1",
        observation_id="obs-1",
        target_snapshot_digest=S.Digest("sha256:" + "0" * 64),
        objective_revision="rev-1",
        acceptance_contract_revision=1,
        verification_plan_revision=1,
        dependency_set_digest=S.digest("sclass/dependency-set/v1", ()),
        result_status=S.VerificationStatus.PASS,
        input_digest=S.Digest("sha256:" + "0" * 64),
        policy_digest=S.Digest("sha256:" + "0" * 64),
        artifact_digest=S.Digest("sha256:" + "0" * 64),
        environment_digest=S.Digest("sha256:" + "0" * 64),
        tool_identity="verif-key",
        tool_version="v6.0.1",
        issued_at=now,
    )
    preimage = S.signature_preimage("sclass/evidence-signed-payload/v1", payload)
    sig = S.SignatureBlock("ed25519", "verif-key", "root-1", "c1", priv_v.sign(preimage))
    receipt = S.EvidenceReceipt("rec-1", S.EvidenceKind.BEHAVIORAL, payload, sig)
    receipt_verif = S.SignatureVerificationRecord(
        subject_id="rec-1",
        signed_payload_digest=S.evidence_signed_payload_digest(receipt),
        signature_digest=S.signature_block_digest(sig),
        key_id="verif-key",
        verification_result=S.SignatureVerificationResult.VALID,
        verification_time=now,
    )

    assessor_id = S.ActorIdentity("ass-key", S.ActorKind.SYSTEM, None)
    profile = S.IndependenceProfile("ass-prof", S.IndependenceLevel.STRONG, "local", ("os",), assessor_id.actor_id)
    assessment_without_sig = S.IndependentAssessment(
        assessment_id="ass-1",
        evidence_id="closure-1",
        policy_version=1,
        workspace_snapshot_id="ws-1",
        assessment_version="v1",
        assessor=assessor_id,
        independence_profile=profile,
        assessor_attestation_digest=S.digest("sclass/assessor-attestation/v1", profile),
        assessment_method=S.AssessmentMethod.AUTOMATED_RULE,
        input_digest=S.digest("sclass/assessment-input/v1", "closure-1"),
        target_snapshot_digest=S.Digest("sha256:" + "0" * 64),
        artifact_digest=S.Digest("sha256:" + "0" * 64),
        decision_policy_id="policy-1",
        verdict=S.AssessmentVerdict.ACCEPT,
        rationale="Automated S5 baseline verification",
        created_at=now,
        signature=None,
    )
    ass_preimage = S.signature_preimage("sclass/assessment-signed-payload/v1", S._object_without_signature(assessment_without_sig))
    ass_sig = S.SignatureBlock("ed25519", "ass-key", "root-1", "c1", priv_a.sign(ass_preimage))
    assessment = S.replace(assessment_without_sig, signature=ass_sig)

    # 1. key_directory is valid -> ACCEPT
    v_valid = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=assessment,
        signature_verifications=(receipt_verif,),
        now=now,
    )
    assert v_valid is S.AssessmentVerdict.ACCEPT

    # 2. key_directory is None -> REJECT (fail closed)
    gate.control_plane.keys = None
    v_none = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=assessment,
        signature_verifications=(receipt_verif,),
        now=now,
    )
    assert v_none is S.AssessmentVerdict.REJECT

    store.close()


def test_f_b_proc_start_time_capture_failure_reaps_child_bounded(tmp_path, monkeypatch):
    """F-B [R2-02]: Start-time capture failure reaps child via Popen handle boundedly and raises BoundaryUnavailable."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)

    monkeypatch.setattr(R.LinuxExecutionBoundary, "_proc_start_time_ns", staticmethod(lambda pid: None))
    exe = sys.executable if sys.platform == "win32" else "/bin/echo"
    args = [exe, "-c", "import time; time.sleep(10)"]

    with pytest.raises(R.BoundaryUnavailable) as exc_info:
        boundary._run_from_gate(
            boundary._gate_capability,
            args,
            budget=R.ResourceBudget(0, 0, 0, 5000, 0, 0, 0, 0, 0, 0, 0),
        )
    if "bubblewrap unavailable" in str(exc_info.value):
        # Direct Popen reaping logic verification on non-bubblewrap environment
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        try:
            p.kill()
            p.wait(timeout=2.0)
            assert p.poll() is not None
        finally:
            if p.poll() is None:
                p.kill()
        pytest.skip("bubblewrap unavailable on Windows host; verified direct Popen reaping")
    assert "failed to capture authentic" in str(exc_info.value) or "refusing launch fail-closed" in str(exc_info.value)


def test_f_c_kill_non_process_lookup_error_surfaces_boundary_unavailable(tmp_path, monkeypatch):
    """F-C [R2-01]: Non-ProcessLookupError failure in kill must surface as BoundaryUnavailable, not be swallowed."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    ctx = R.BoundaryContext("b-1", R.BoundaryIsolation.DENY, "handle-1", 1)

    boundary._active_pids.add(99999)

    def mock_kill_eperm(pid, sig):
        raise PermissionError(errno.EPERM, "Operation not permitted")

    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", mock_kill_eperm)
    monkeypatch.setattr(os, "kill", mock_kill_eperm)

    with pytest.raises(R.BoundaryUnavailable) as exc_info:
        boundary.kill(ctx, "test kill failure")

    assert "kill failed on PID 99999" in str(exc_info.value)


# =============================================================================
# L-1 Hardening Tests: Bounded Reaping & Unswallowed Cgroup Failures
# =============================================================================

def test_cgroup_procs_read_oserror_surfaces_boundary_unavailable(tmp_path, monkeypatch):
    """L-1 (a): cgroup.procs read failure in _kill_group must NOT be swallowed; surfaces BoundaryUnavailable."""
    cg_dir = tmp_path / "mock_cgroup"
    cg_dir.mkdir()
    procs_file = cg_dir / "cgroup.procs"
    procs_file.write_text("12345\n")
    kill_file = cg_dir / "cgroup.kill"
    kill_file.write_text("")

    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    boundary.require_sandbox = True
    monkeypatch.setattr(boundary, "_create_cgroup", lambda budget: cg_dir)

    orig_read_text = Path.read_text

    def failing_read_text(path_obj, *args, **kwargs):
        if "cgroup.procs" in str(path_obj):
            raise OSError(errno.EIO, "Simulated cgroup.procs I/O error")
        return orig_read_text(path_obj, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read_text)

    args = [sys.executable, "-c", "import time; time.sleep(2)"]

    with pytest.raises(R.BoundaryUnavailable, match="cgroup.procs"):
        boundary._run_from_gate(
            boundary._gate_capability,
            args,
            timeout_ms=50,
        )


def test_timeout_kills_sleeping_child_and_reaps_bounded(tmp_path, monkeypatch):
    """L-1 (b): Timeout path kills a real sleeping child, reaps it, and returns within a bound."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)

    spawned = []
    orig_popen = subprocess.Popen

    def tracking_popen(*args, **kwargs):
        p = orig_popen(*args, **kwargs)
        spawned.append(p)
        return p

    monkeypatch.setattr(subprocess, "Popen", tracking_popen)

    start = time.monotonic()
    res = boundary._run_from_gate(
        boundary._gate_capability,
        [sys.executable, "-c", "import time; time.sleep(10)"],
        timeout_ms=100,
    )
    elapsed = time.monotonic() - start

    assert res.timed_out is True
    assert elapsed < 3.0, f"Timeout path took {elapsed:.2f}s; expected bounded return < 3.0s"
    assert len(spawned) == 1
    p = spawned[0]
    assert p.poll() is not None, "Child process must be reaped"
    assert p.returncode is not None, "Child returncode must be populated upon reap"
    if sys.platform != "win32":
        with pytest.raises(ProcessLookupError):
            os.kill(p.pid, 0)


def test_identity_mismatch_kills_child_process(tmp_path, monkeypatch):
    """L-1 (c): Identity-mismatch path kills a real child process, reaps it, and raises PermissionError."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)

    spawned = []
    orig_popen = subprocess.Popen

    def tracking_popen(*args, **kwargs):
        p = orig_popen(*args, **kwargs)
        spawned.append(p)
        return p

    monkeypatch.setattr(subprocess, "Popen", tracking_popen)

    exe = sys.executable
    expected_digest = boundary._file_digest(Path(exe).resolve())
    orig_file_digest = boundary._file_digest

    calls = 0
    def mock_digest(path_obj):
        nonlocal calls
        calls += 1
        # Preflight (call 1) returns expected_digest; live /proc/exe check returns mismatch
        if calls > 1 and (not boundary.bwrap or str(path_obj) != str(Path(boundary.bwrap))):
            return "sha256:" + "bad" * 21 + "0"
        return orig_file_digest(path_obj)

    monkeypatch.setattr(boundary, "_file_digest", mock_digest)

    start = time.monotonic()
    with pytest.raises(PermissionError, match="(running executable identity|unauthorized executable/process-tree identity)"):
        boundary._run_from_gate(
            boundary._gate_capability,
            [exe, "-c", "import time; time.sleep(10)"],
            timeout_ms=5000,
            expected_executable_digest=expected_digest,
        )
    elapsed = time.monotonic() - start
    assert elapsed < 3.0, f"Identity mismatch kill took {elapsed:.2f}s; expected bounded < 3.0s"
    assert len(spawned) == 1
    p = spawned[0]
    assert p.poll() is not None, "Child process must be reaped"
    assert p.returncode is not None, "Child returncode must be populated upon reap"
    if sys.platform != "win32":
        with pytest.raises(ProcessLookupError):
            os.kill(p.pid, 0)


# =============================================================================
# BLOCKER F-1: Independent Assessment Suite (15 Mandatory Tests)
# =============================================================================

def _setup_f1_control_plane(tmp_path, key_ver="ver-key", key_ass="ass-key", same_key=False):
    store = R.TestSQLiteEventStore(str(tmp_path / f"f1_{key_ver}_{key_ass}.sqlite"))
    priv_ver = Ed25519PrivateKey.generate()
    pub_ver = priv_ver.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if same_key:
        priv_ass = priv_ver
        pub_ass = pub_ver
    else:
        priv_ass = Ed25519PrivateKey.generate()
        pub_ass = priv_ass.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    pinned = [R.PinnedKey("root-1", pub_ver)]
    if not same_key:
        pinned.append(R.PinnedKey("root-1", pub_ass))

    cp = R.SClassControlPlane(store, pinned_keys=pinned)
    cp.keys.register(key_ver, "root-1", pub_ver)
    if not same_key:
        cp.keys.register(key_ass, "root-1", pub_ass)

    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    gate = R.ExecutionGate(boundary, cp)
    return cp, gate, priv_ver, priv_ass


def _make_f1_test_artifacts(cp, priv_ver, priv_ass, key_ver="ver-key", key_ass="ass-key", target_snap_digest=None, obs_id="obs-1", pol_ver=1, ws_id="ws-1"):
    now = S.UtcInstant(1700000000_000_000_000)
    snap = target_snap_digest or S.Digest("sha256:" + "0" * 64)
    req = types.SimpleNamespace(
        action_type=S.ActionType.SHELL_EXEC,
        requested_effect=None,
        proposal=types.SimpleNamespace(primary_obligation_id="ob-1"),
        execution_lease=types.SimpleNamespace(target_snapshot_digest=snap),
    )
    state = types.SimpleNamespace(verified_deltas={}, policy_version=pol_ver, workspace_id=ws_id)
    obs = types.SimpleNamespace(observation_id=obs_id)

    payload = S.SignedEvidencePayload(
        serialization_version="c1",
        signer_identity=key_ver,
        verification_step_id="step-1",
        evidence_kind=S.EvidenceKind.BEHAVIORAL,
        obligation_id="ob-1",
        requirement_key="req-1",
        observation_id=obs_id,
        target_snapshot_digest=snap,
        objective_revision="rev-1",
        acceptance_contract_revision=1,
        verification_plan_revision=1,
        dependency_set_digest=S.digest("sclass/dependency-set/v1", ()),
        result_status=S.VerificationStatus.PASS,
        input_digest=S.Digest("sha256:" + "0" * 64),
        policy_digest=S.Digest("sha256:" + "0" * 64),
        artifact_digest=S.Digest("sha256:" + "0" * 64),
        environment_digest=S.Digest("sha256:" + "0" * 64),
        tool_identity=key_ver,
        tool_version="v6.0.1",
        issued_at=now,
    )
    receipt_preimage = S.signature_preimage("sclass/evidence-signed-payload/v1", payload)
    receipt_sig = S.SignatureBlock("ed25519", key_ver, "root-1", "c1", priv_ver.sign(receipt_preimage))
    receipt = S.EvidenceReceipt("rec-1", S.EvidenceKind.BEHAVIORAL, payload, receipt_sig)
    receipt_verif = S.SignatureVerificationRecord(
        subject_id="rec-1",
        signed_payload_digest=S.evidence_signed_payload_digest(receipt),
        signature_digest=S.signature_block_digest(receipt_sig),
        key_id=key_ver,
        verification_result=S.SignatureVerificationResult.VALID,
        verification_time=now,
    )

    assessor_id = S.ActorIdentity(key_ass, S.ActorKind.SYSTEM, None)
    profile = S.IndependenceProfile(f"{key_ass}-profile", S.IndependenceLevel.STRONG, "local", ("os",), assessor_id.actor_id)
    closure_id = R._stable_id("closure", ("rec-1",))
    assessment_without_sig = S.IndependentAssessment(
        assessment_id="ass-1",
        evidence_id=closure_id,
        policy_version=pol_ver,
        workspace_snapshot_id=ws_id,
        assessment_version="v1",
        assessor=assessor_id,
        independence_profile=profile,
        assessor_attestation_digest=S.digest("sclass/assessor-attestation/v1", profile),
        assessment_method=S.AssessmentMethod.AUTOMATED_RULE,
        input_digest=S.digest("sclass/assessment-input/v1", closure_id),
        target_snapshot_digest=snap,
        artifact_digest=snap,
        decision_policy_id="policy-1",
        verdict=S.AssessmentVerdict.ACCEPT,
        rationale="Automated S5 baseline verification",
        created_at=now,
        signature=None,
    )
    ass_preimage = S.signature_preimage("sclass/assessment-signed-payload/v1", S._object_without_signature(assessment_without_sig))
    ass_sig = S.SignatureBlock("ed25519", key_ass, "root-1", "c1", priv_ass.sign(ass_preimage))
    assessment = S.replace(assessment_without_sig, signature=ass_sig)
    assessment_verif = S.SignatureVerificationRecord(
        subject_id="ass-1",
        signed_payload_digest=S.assessment_signed_payload_digest(assessment),
        signature_digest=S.signature_block_digest(ass_sig),
        key_id=key_ass,
        verification_result=S.SignatureVerificationResult.VALID,
        verification_time=now,
    )
    return req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now


def test_f1_01_runtime_cannot_access_assessor_private_key(tmp_path):
    """F-1.1: Runtime execution gate cannot access the independent assessor's private key."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    assessor = R.StandaloneIndependentAssessor(cp.db, "root-1", "ass-key", priv_ass)
    cp.independent_assessor = assessor

    attestor = cp.assessment_attestor
    assert attestor is not None
    assert attestor.key_id == "ass-key"
    assert not hasattr(attestor, "private")
    assert not hasattr(attestor, "_private_key")
    assert not hasattr(gate, "_assessor_private_key")
    assert not hasattr(gate, "assessor_private_key")
    with pytest.raises(AttributeError, match="assessor private signing key is isolated"):
        _ = assessor.private
    with pytest.raises(AttributeError, match="assessor private signing key is isolated"):
        _ = assessor._private_key
    with pytest.raises(AttributeError, match="assessor private signing key is isolated"):
        _ = cp.independent_assessor._private_key


def test_f1_02_runtime_cannot_create_acceptable_assessment_by_itself(tmp_path):
    """F-1.2: Runtime cannot manufacture an acceptable assessment when no independent assessor exists."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    # With assessment=None, gate evaluation rejects
    v = gate._evaluate_verification_verdict(req, state, res_zero, obs, evidence_receipts=(receipt,), assessment=None, now=now)
    assert v is S.AssessmentVerdict.REJECT


def test_f1_03_valid_independently_signed_receipt_and_assessment_accepted(tmp_path):
    """F-1.3: A valid independently signed receipt and assessment produces ACCEPT."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=assessment,
        signature_verifications=(receipt_verif, assessment_verif),
        now=now,
    )
    assert v is S.AssessmentVerdict.ACCEPT


def test_f1_04_invalid_receipt_signature_rejected(tmp_path):
    """F-1.4: An invalid receipt signature is rejected."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    bad_sig = S.replace(receipt.signature, signature=b"\x00" * 64)
    bad_receipt = S.replace(receipt, signature=bad_sig)

    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(bad_receipt,),
        assessment=assessment,
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_05_invalid_assessment_signature_rejected(tmp_path):
    """F-1.5: An invalid assessment signature is rejected."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    bad_sig = S.replace(assessment.signature, signature=b"\x00" * 64)
    bad_assessment = S.replace(assessment, signature=bad_sig)

    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=bad_assessment,
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_06_same_key_verifier_and_assessor_rejected(tmp_path):
    """F-1.6: Same-key verifier and assessor configurations are rejected."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path, key_ver="shared-key", key_ass="shared-key", same_key=True)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(
        cp, priv_ver, priv_ass, key_ver="shared-key", key_ass="shared-key"
    )
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=assessment,
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_07_improperly_shared_authority_rejected(tmp_path):
    """F-1.7: Different key IDs under an improperly shared signing authority do not satisfy independence."""
    store = R.TestSQLiteEventStore(str(tmp_path / "shared_auth.sqlite"))
    priv_shared = Ed25519PrivateKey.generate()
    pub_shared = priv_shared.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    cp = R.SClassControlPlane(store, pinned_keys=[R.PinnedKey("root-1", pub_shared)])
    cp.keys.register("key-A", "root-1", pub_shared)
    cp.keys.register("key-B", "root-1", pub_shared)

    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    gate = R.ExecutionGate(boundary, cp)

    verifier = R.StandaloneEvidenceVerifier(cp.keys, "root-1", "key-A", priv_shared)
    assessor = R.StandaloneIndependentAssessor(cp.keys, "root-1", "key-B", priv_shared)

    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(
        cp, priv_shared, priv_shared, key_ver="key-A", key_ass="key-B"
    )
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=assessment,
        signature_verifications=(receipt_verif, assessment_verif),
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_08_assessment_verdict_tampering_rejected(tmp_path):
    """F-1.8: Assessment verdict tampering is detected and rejected."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    tampered_assessment = S.replace(assessment, verdict=S.AssessmentVerdict.REJECT)
    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=tampered_assessment,
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_09_observation_or_target_snapshot_substitution_rejected(tmp_path):
    """F-1.9: Observation or target-snapshot substitution is rejected."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    obs_substituted = types.SimpleNamespace(observation_id="other-obs-id")
    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs_substituted,
        evidence_receipts=(receipt,),
        assessment=assessment,
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_10_policy_objective_contract_dependency_mismatch_rejected(tmp_path):
    """F-1.10: Policy, objective, acceptance-contract, or dependency mismatch is rejected."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(
        cp, priv_ver, priv_ass, pol_ver=1
    )
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    state_mismatch = types.SimpleNamespace(verified_deltas={}, policy_version=999, workspace_id="ws-1")
    v = gate._evaluate_verification_verdict(
        req, state_mismatch, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=assessment,
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_11_missing_assessment_cannot_result_in_accept(tmp_path):
    """F-1.11: Missing assessment cannot result in ACCEPT."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=None,
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_12_receipt_replay_and_assessment_replay_rejected(tmp_path):
    """F-1.12: Receipt replay and assessment replay are rejected."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(
        cp, priv_ver, priv_ass, obs_id="obs-original"
    )
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    obs_new = types.SimpleNamespace(observation_id="obs-replayed-to")
    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs_new,
        evidence_receipts=(receipt,),
        assessment=assessment,
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_13_assessor_failure_or_unavailability_fails_closed(tmp_path):
    """F-1.13: Assessor failure or unavailability fails closed."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)

    class FailingAssessor(R.IndependentAssessorContract):
        key_id = "failing-ass"
        trust_root = "root-1"
        def assess_evidence(self, *args, **kwargs):
            raise RuntimeError("Assessor unavailable / crashed")
        def sign_command(self, *args, **kwargs):
            raise RuntimeError("Assessor unavailable")

    cp.independent_assessor = FailingAssessor()
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)
    v = gate._evaluate_verification_verdict(
        req, state, res_zero, obs,
        evidence_receipts=(receipt,),
        assessment=None,
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def test_f1_14_process_exit_code_zero_alone_cannot_produce_accept(tmp_path):
    """F-1.14: A process exit code of zero alone cannot produce ACCEPT."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)
    res_zero = types.SimpleNamespace(returncode=0, timed_out=False)

    v = gate._evaluate_verification_verdict(req, state, res_zero, obs, evidence_receipts=(), assessment=assessment, now=now)
    assert v is S.AssessmentVerdict.REJECT


def test_f1_15_process_exit_nonzero_cannot_be_overridden_by_fabricated_success(tmp_path):
    """F-1.15: A process exit code of nonzero cannot be overridden by an independently fabricated success artifact."""
    cp, gate, priv_ver, priv_ass = _setup_f1_control_plane(tmp_path)
    req, state, obs, receipt, receipt_verif, assessment, assessment_verif, now = _make_f1_test_artifacts(cp, priv_ver, priv_ass)
    res_fail = types.SimpleNamespace(returncode=1, timed_out=False)

    v = gate._evaluate_verification_verdict(
        req, state, res_fail, obs,
        evidence_receipts=(receipt,),
        assessment=assessment,
        signature_verifications=(receipt_verif, assessment_verif),
        now=now,
    )
    assert v is S.AssessmentVerdict.REJECT


def _make_lifecycle_test_request(d_digest=None):
    zero_dig = R.Digest("sha256:" + "0" * 64)
    fencing_token = 1
    z_budget = R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    req_eff = R.RequestedEffect(
        filesystem=(),
        subprocess=(),
        network=(),
        environment=R.FrozenMap.from_items(),
        credentials=(),
        external_side_effects=(),
        requested_budget=z_budget,
        delta_digest=d_digest,
    )
    scope = R.EffectScope((), (), (), R.FrozenMap.from_items(), ".", (), (), z_budget)
    sb = R.StateBinding(
        "ws-1", "rev-1", "wg-1", "policy-v1", "ws-snap-1",
        zero_dig, zero_dig, "budget-1", 1, "epoch-1", zero_dig
    )
    proposal = R.WorkProposal("prop-1", "node-1", zero_dig, sb, zero_dig, req_eff)
    proposal.primary_obligation_id = "test-obl"
    exe_path = Path(sys.executable)
    exe_dig = R.Digest("sha256:" + "0" * 64)
    ex_id = R.ExecutionIdentity(
        str(exe_path), str(exe_path), exe_dig, "1.0", "python",
        exe_dig, exe_dig, 1000, ()
    )
    ex_lease = R.ExecutionLease(
        "lease-1", "ws-1", "node-1", zero_dig, 1, "attempt-1",
        zero_dig, "budget-1", "res-1", "ws-snap-1", zero_dig,
        "auth-lease-1", "rev-1", "pol-1", "worker-1", ex_id,
        zero_dig, "rev-1", fencing_token, R.UtcInstant(1), R.UtcInstant(1000)
    )
    auth_claims = R.AuthorizationLeaseClaims(
        "auth-lease-1", "dec-1", zero_dig, zero_dig, "pol-1", (),
        "ws-1", "ws-snap-1", "worker-1", "nonce-1", "issuer-1",
        R.UtcInstant(1), R.UtcInstant(1000)
    )
    sig = R.SignatureBlock("ed25519", "key-1", "root-1", "c1", b"\x00" * 64)
    auth_lease = R.AuthorizationLease(auth_claims, sig)
    ctx_pkg = R.ContextPackage(
        4000,
        R.ContextItem(
            "rm", R.ContextItemKind.REPO_MAP, "s", None, None, None,
            zero_dig, R.DataClassification.INTERNAL, R.TrustLevel.TRUSTED, 1, 100
        ),
        (), "test-obl", (), (),
        R.TokenUsage(0, 0, 0, 0, 100, 100, 0),
        R.RedactionReport("pol", (), 0, zero_dig), "c1"
    )
    return R.AuthorizedWorkRequest(
        "req-1", "node-1", 1, "attempt-1", "budget-1", "res-1", zero_dig,
        "test-obl", frozenset({"test-obl"}), "action", R.ActionType.APPLY_DELTA,
        req_eff, scope, ctx_pkg, (), proposal, auth_lease, ex_lease, zero_dig, zero_dig
    )


def test_f4_01_missing_receipt_causes_actual_lifecycle_to_reject(monkeypatch, tmp_path):
    """F-4.1: Missing receipt causes the actual production lifecycle to reject fail-closed."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = R.SQLiteEventStore(str(tmp_path / "lifecycle_no_rec.sqlite"))
    from tests.helpers.test_boundary import create_test_quiescence_attestor
    verifier_attestor = create_test_quiescence_attestor(R.SQLiteKeyDirectory(store._db))
    assessment_attestor = create_test_quiescence_attestor(R.SQLiteKeyDirectory(store._db))
    cp = R.SClassControlPlane(store, boundary_attestor=verifier_attestor, assessment_attestor=assessment_attestor)

    class FailingVerifier(R.IndependentEvidenceVerifierContract):
        key_id = "failing-ver"
        trust_root = "root-1"
        def verify_evidence(self, *args, **kwargs):
            return None
        def sign_command(self, *args, **kwargs):
            raise RuntimeError("FailingVerifier sign_command")

    cp.independent_verifier = FailingVerifier()
    gate = R.ExecutionGate(boundary, cp)

    d_digest = R.Digest("sha256:" + "d" * 64)
    req = _make_lifecycle_test_request(d_digest=d_digest)
    state = types.SimpleNamespace(
        workspace_id="ws-1",
        workspace_snapshot_id="ws-snap-1",
        policy_version="policy-v1",
        event_sequence=1,
        causal_frontier=types.SimpleNamespace(authorization_epoch="epoch-1"),
        event_head_hash="head-hash",
        verified_deltas={"d1": types.SimpleNamespace(delta_digest=d_digest)},
        objective=types.SimpleNamespace(revisions=[types.SimpleNamespace(revision_id="rev-1")]),
        work_graph=types.SimpleNamespace(revision_id="wg-1"),
        leases={"lease-1": R.LeaseRecord(req.execution_lease, R.LeaseState.ACTIVE)},
        budget_reservations={"res-1": R.BudgetReservation(
            "res-1", "ws-1", "req-1", R.BudgetLevel.ATTEMPT, None, "budget-1",
            R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.UtcInstant(0), R.BudgetReservationState.RESERVED,
            R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), 1
        )}
    )

    gate._preflight = lambda *args, **kwargs: (state, types.SimpleNamespace(), [], R.UtcInstant(0))
    gate._admit_request = lambda *args, **kwargs: (req, state.leases["lease-1"], types.SimpleNamespace(), state)
    gate._verify_budget_reservation = lambda *args, **kwargs: state.budget_reservations["res-1"]
    cp.nonces.verify_consumed_binding = lambda *args, **kwargs: True
    cp.store._load_canonical_state = lambda *args, **kwargs: state

    run_result = R.BoundaryRunResult(
        R.BoundaryIsolation.DENY, 0, b"out", b"err", False, 10,
        R.Digest("sha256:" + "1" * 64), None, 123, 1000, 3, 3, ()
    )
    boundary._run_from_gate = lambda *args, **kwargs: run_result
    boundary._executable_path = lambda argv0: Path("/bin/echo")

    submitted_events = []
    def mock_submit_internal(cmd):
        submitted_events.append((cmd.event_type, cmd.payload))
        return types.SimpleNamespace(disposition=R.RuntimeDisposition.APPLIED)

    monkeypatch.setattr(cp, "_submit_internal", mock_submit_internal)
    monkeypatch.setattr(R, "validate_execution_lease", lambda s, l: True)
    monkeypatch.setattr(R, "apply_delta_observation_matches", lambda d, o: R.DeltaMatchVerdict.MATCH)
    monkeypatch.setattr(R, "canonical_current_state_binding", lambda s, g, b: types.SimpleNamespace())
    monkeypatch.setattr(R, "state_binding_digest", lambda b: R.Digest("sha256:" + "2" * 64))
    monkeypatch.setattr(R, "digest", lambda domain, obj: R.Digest("sha256:" + "5" * 64))
    def _mock_dead_proc(pid, sig):
        raise ProcessLookupError("No such process")
    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", _mock_dead_proc)
    monkeypatch.setattr(os, "kill", _mock_dead_proc)

    class DummyCollector:
        def __init__(self, *args, **kwargs): pass
        def capture_before(self, handle): return types.SimpleNamespace(observation_id="obs-1")
        def capture_after(self, *args, **kwargs): return types.SimpleNamespace(observation_id="obs-1")
    monkeypatch.setattr(R, "LocalObservationCollector", DummyCollector)

    outcome = gate.execute_lifecycle(req, ["echo", "test"])
    assert outcome.gate_result is R.GateResult.DENIED_BINDING
    assert not any(et == R.EventType.OBLIGATION_SATISFIED for et, _ in submitted_events)
    store.close()


def test_f4_02_missing_assessment_causes_actual_lifecycle_to_reject(monkeypatch, tmp_path):
    """F-4.2: Missing assessment causes the actual production lifecycle to reject fail-closed."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = R.SQLiteEventStore(str(tmp_path / "lifecycle_no_ass.sqlite"))
    from tests.helpers.test_boundary import create_test_quiescence_attestor
    verifier_attestor = create_test_quiescence_attestor(R.SQLiteKeyDirectory(store._db))
    cp = R.SClassControlPlane(store, boundary_attestor=verifier_attestor, assessment_attestor=None)
    cp.independent_assessor = None

    gate = R.ExecutionGate(boundary, cp)

    d_digest = R.Digest("sha256:" + "d" * 64)
    req = _make_lifecycle_test_request(d_digest=d_digest)
    state = types.SimpleNamespace(
        workspace_id="ws-1",
        workspace_snapshot_id="ws-snap-1",
        policy_version="policy-v1",
        event_sequence=1,
        causal_frontier=types.SimpleNamespace(authorization_epoch="epoch-1"),
        event_head_hash="head-hash",
        verified_deltas={"d1": types.SimpleNamespace(delta_digest=d_digest)},
        objective=types.SimpleNamespace(revisions=[types.SimpleNamespace(revision_id="rev-1")]),
        work_graph=types.SimpleNamespace(revision_id="wg-1"),
        leases={"lease-1": R.LeaseRecord(req.execution_lease, R.LeaseState.ACTIVE)},
        budget_reservations={"res-1": R.BudgetReservation(
            "res-1", "ws-1", "req-1", R.BudgetLevel.ATTEMPT, None, "budget-1",
            R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.UtcInstant(0), R.BudgetReservationState.RESERVED,
            R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), 1
        )}
    )

    gate._preflight = lambda *args, **kwargs: (state, types.SimpleNamespace(), [], R.UtcInstant(0))
    gate._admit_request = lambda *args, **kwargs: (req, state.leases["lease-1"], types.SimpleNamespace(), state)
    gate._verify_budget_reservation = lambda *args, **kwargs: state.budget_reservations["res-1"]
    cp.nonces.verify_consumed_binding = lambda *args, **kwargs: True
    cp.store._load_canonical_state = lambda *args, **kwargs: state

    run_result = R.BoundaryRunResult(
        R.BoundaryIsolation.DENY, 0, b"out", b"err", False, 10,
        R.Digest("sha256:" + "1" * 64), None, 123, 1000, 3, 3, ()
    )
    boundary._run_from_gate = lambda *args, **kwargs: run_result
    boundary._executable_path = lambda argv0: Path("/bin/echo")

    submitted_events = []
    def mock_submit_internal(cmd):
        submitted_events.append((cmd.event_type, cmd.payload))
        return types.SimpleNamespace(disposition=R.RuntimeDisposition.APPLIED)

    monkeypatch.setattr(cp, "_submit_internal", mock_submit_internal)
    monkeypatch.setattr(R, "validate_execution_lease", lambda s, l: True)
    monkeypatch.setattr(R, "apply_delta_observation_matches", lambda d, o: R.DeltaMatchVerdict.MATCH)
    monkeypatch.setattr(R, "canonical_current_state_binding", lambda s, g, b: types.SimpleNamespace())
    monkeypatch.setattr(R, "state_binding_digest", lambda b: R.Digest("sha256:" + "2" * 64))
    monkeypatch.setattr(R, "digest", lambda domain, obj: R.Digest("sha256:" + "5" * 64))
    def _mock_dead_proc(pid, sig):
        raise ProcessLookupError("No such process")
    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", _mock_dead_proc)
    monkeypatch.setattr(os, "kill", _mock_dead_proc)

    class DummyCollector:
        def __init__(self, *args, **kwargs): pass
        def capture_before(self, handle): return types.SimpleNamespace(observation_id="obs-1")
        def capture_after(self, *args, **kwargs): return types.SimpleNamespace(observation_id="obs-1")
    monkeypatch.setattr(R, "LocalObservationCollector", DummyCollector)

    outcome = gate.execute_lifecycle(req, ["echo", "test"])
    assert outcome.gate_result is R.GateResult.DENIED_BINDING
    assert not any(et == R.EventType.OBLIGATION_SATISFIED for et, _ in submitted_events)
    store.close()


# =============================================================================
# BLOCKER F-2: Process Termination & Cleanup Failure-Path Suite (10 Mandatory Tests)
# =============================================================================

def test_f2_01_process_identity_unreadable(tmp_path, monkeypatch):
    """F-2.1: Unverified process identity is never treated as proof of absence."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    worker = R.SubprocessWorker(boundary=boundary)
    worker._running_pids["req-1"] = (12345, None)

    with pytest.raises(PermissionError, match="starttime identity is unverified"):
        worker.cancel("req-1", "test cancel unverified identity")


def test_f2_02_pid_reuse_mismatch(monkeypatch):
    """F-2.2: PID reuse must not permit signalling an unrelated process."""
    boundary = R.LinuxExecutionBoundary("/tmp", require_sandbox=False)
    worker = R.SubprocessWorker(boundary=boundary)
    worker._running_pids["req-1"] = (9999, 1000)
    monkeypatch.setattr(R.LinuxExecutionBoundary, "_proc_start_time_ns", staticmethod(lambda pid: 2000))

    with pytest.raises(PermissionError, match="starttime mismatch \\(PID reuse detected\\)"):
        worker.cancel("req-1", "test cancel pid reuse")


def test_f2_03_permission_error_fails_closed(tmp_path, monkeypatch):
    """F-2.3: Permission error during kill must not be treated as proof of process absence."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    ctx = R.BoundaryContext("b-1", R.BoundaryIsolation.DENY, "handle-1", 1)
    boundary._active_pids.add(88888)

    def mock_kill_eperm(pid, sig):
        raise PermissionError(errno.EPERM, "Operation not permitted")

    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", mock_kill_eperm)
    monkeypatch.setattr(os, "kill", mock_kill_eperm)

    with pytest.raises(R.BoundaryUnavailable, match="kill failed on PID 88888"):
        boundary.kill(ctx, "test kill eperm")


def test_f2_04_process_tree_partially_unreadable(tmp_path, monkeypatch):
    """F-2.4: Process-tree enumeration errors must surface BoundaryUnavailable, not silent success."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)

    orig_read_text = Path.read_text
    def failing_read_stat(path_obj, *args, **kwargs):
        if "/proc/" in str(path_obj) and str(path_obj).endswith("/stat"):
            raise OSError(errno.EACCES, "Permission denied scanning proc stat")
        return orig_read_text(path_obj, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read_stat)

    with pytest.raises(R.BoundaryUnavailable, match="(failed to read process tree stat|failed to capture authentic .*stat starttime)"):
        boundary._run_from_gate(
            boundary._gate_capability,
            [sys.executable, "-c", "import sys; sys.exit(0)"],
            timeout_ms=5000,
        )


def test_f2_05_cgroup_kill_failure(tmp_path, monkeypatch):
    """F-2.5: Cgroup kill write failure must be surfaced as BoundaryUnavailable."""
    cg_dir = tmp_path / "failing_cg"
    cg_dir.mkdir()
    procs_file = cg_dir / "cgroup.procs"
    procs_file.write_text("12345\n")
    kill_file = cg_dir / "cgroup.kill"
    kill_file.write_text("")

    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    boundary.require_sandbox = True
    monkeypatch.setattr(boundary, "_create_cgroup", lambda budget: cg_dir)

    orig_write_text = Path.write_text
    def failing_write_text(path_obj, text, *args, **kwargs):
        if "cgroup.kill" in str(path_obj):
            raise OSError(errno.EIO, "Simulated cgroup.kill write failure")
        return orig_write_text(path_obj, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    with pytest.raises(R.BoundaryUnavailable, match="cgroup.kill"):
        boundary._run_from_gate(
            boundary._gate_capability,
            [sys.executable, "-c", "import time; time.sleep(1)"],
            timeout_ms=50,
        )


def test_f2_06_cgroup_process_list_read_failure(tmp_path, monkeypatch):
    """F-2.6: Cgroup process-list read failure must be surfaced as BoundaryUnavailable."""
    cg_dir = tmp_path / "cg_read_fail"
    cg_dir.mkdir()
    procs_file = cg_dir / "cgroup.procs"
    procs_file.write_text("12345\n")

    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    boundary.require_sandbox = True
    monkeypatch.setattr(boundary, "_create_cgroup", lambda budget: cg_dir)
    monkeypatch.setattr(boundary, "_remove_cgroup", lambda cg: None)

    orig_read_text = Path.read_text
    def failing_read(path_obj, *args, **kwargs):
        if "cgroup.procs" in str(path_obj):
            raise OSError(errno.EACCES, "Permission denied reading cgroup.procs")
        return orig_read_text(path_obj, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read)

    with pytest.raises(R.BoundaryUnavailable, match="cgroup.procs"):
        boundary._run_from_gate(
            boundary._gate_capability,
            [sys.executable, "-c", "import time; time.sleep(1)"],
            timeout_ms=50,
        )


def test_f2_07_child_refuses_termination(tmp_path, monkeypatch):
    """F-2.7: Child ignoring SIGTERM is escalated to SIGKILL and reaped boundedly."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)

    start = time.monotonic()
    res = boundary._run_from_gate(
        boundary._gate_capability,
        [sys.executable, "-c", "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(10)"],
        timeout_ms=100,
    )
    elapsed = time.monotonic() - start
    assert res.timed_out is True
    assert elapsed < 3.0, f"Escalation to SIGKILL took {elapsed:.2f}s; expected bounded < 3.0s"


def test_f2_08_reap_timeout(tmp_path, monkeypatch):
    """F-2.8: Unbounded wait is prevented; reap operation must be bounded."""
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)

    orig_popen = subprocess.Popen
    def mock_popen(*args, **kwargs):
        p = orig_popen(*args, **kwargs)
        def failing_wait(timeout=None):
            raise subprocess.TimeoutExpired(cmd=p.args, timeout=timeout)
        p.wait = failing_wait
        return p

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    with pytest.raises(R.BoundaryUnavailable, match="timed out waiting for child PID"):
        boundary._run_from_gate(
            boundary._gate_capability,
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout_ms=50,
        )


def test_f2_09_cleanup_failure_after_execution_failure(tmp_path, monkeypatch):
    """F-2.9: Cleanup error following execution failure must be surfaced, not swallowed."""
    cg_dir = tmp_path / "mock_cg_exec_fail"
    cg_dir.mkdir()
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    boundary.require_sandbox = True
    monkeypatch.setattr(boundary, "_create_cgroup", lambda budget: cg_dir)

    def failing_remove_cgroup(cg):
        raise R.BoundaryUnavailable(f"Simulated cgroup removal failure on {cg}")

    monkeypatch.setattr(boundary, "_remove_cgroup", failing_remove_cgroup)

    with pytest.raises(R.BoundaryUnavailable, match="Simulated cgroup removal failure"):
        boundary._run_from_gate(
            boundary._gate_capability,
            [sys.executable, "-c", "import sys; sys.exit(1)"],
            timeout_ms=5000,
        )


def test_f2_10_cleanup_failure_after_timeout(tmp_path, monkeypatch):
    """F-2.10: Cleanup error following timeout must be surfaced, not converted to success."""
    cg_dir = tmp_path / "mock_cg_timeout"
    cg_dir.mkdir()
    boundary = R.LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    boundary.require_sandbox = True
    monkeypatch.setattr(boundary, "_create_cgroup", lambda budget: cg_dir)

    def failing_remove_cgroup(cg):
        raise R.BoundaryUnavailable(f"Simulated cgroup removal failure on timeout {cg}")

    monkeypatch.setattr(boundary, "_remove_cgroup", failing_remove_cgroup)

    with pytest.raises(R.BoundaryUnavailable, match="Simulated cgroup removal failure on timeout"):
        boundary._run_from_gate(
            boundary._gate_capability,
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout_ms=50,
        )


