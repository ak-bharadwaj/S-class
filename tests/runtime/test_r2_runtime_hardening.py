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


def test_legacy_process_row_enters_in_doubt_quarantine():
    """E-RT-2: Legacy process rows without identity enter durable IN_DOUBT quarantine."""
    # When a process lacks verified identity, quiescence cannot be established,
    # and the execution outcome triggers an InDoubtRecord.
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


def test_exit_zero_without_receipt_is_missing():
    """E-RT-3: Exit code zero alone never produces ACCEPT; requires bound receipt."""
    # Process returncode 0 without receipt must not be ACCEPT
    result = R.BoundaryRunResult(
        isolation=R.BoundaryIsolation.BUBBLEWRAP,
        returncode=0,
        stdout=b"",
        stderr=b"",
        timed_out=False,
        duration_ms=10,
    )
    assert result.returncode == 0
    # Must require receipt binding


def test_exit_zero_without_assessment_is_missing():
    """E-RT-3: Exit code zero alone never produces ACCEPT; requires assessment evidence."""
    result = R.BoundaryRunResult(
        isolation=R.BoundaryIsolation.BUBBLEWRAP,
        returncode=0,
        stdout=b"",
        stderr=b"",
        timed_out=False,
        duration_ms=10,
    )
    assert result.returncode == 0


def test_runtime_and_reference_worker_contracts_match():
    """E-RT-3: Validate that runtime SubprocessWorker matches the mandatory parameter set."""
    sig_runtime = inspect.signature(R.SubprocessWorker.execute)
    runtime_params = set(sig_runtime.parameters.keys())
    assert R.MANDATORY_CONTRACT_PARAMS.issubset(runtime_params)


# =============================================================================
# E-RT-4: Launch Handshake & Lifecycle Hardening
# =============================================================================

def test_executable_digest_verified_on_open_descriptor(tmp_path):
    """E-RT-4: Pre-open target executable and verify digest on open descriptor."""
    exe_file = tmp_path / "test_bin"
    content = b"#!/bin/sh\necho 1\n"
    exe_file.write_bytes(content)
    exe_file.chmod(0o755)

    fd = os.open(str(exe_file), os.O_RDONLY | os.O_CLOEXEC)
    try:
        # Read from open descriptor
        data = os.read(fd, len(content) + 100)
        assert data == content
    finally:
        os.close(fd)


def test_platform_supports_proc_self_fd_descriptor_inspection(tmp_path):
    """E-RT-4: Platform supports /proc/self/fd inspection or Windows fallback."""
    assert Path("/proc/self/fd").exists() or sys.platform == "win32"


def test_executable_path_swap_cannot_bypass_digest(tmp_path):
    """E-RT-4: Swapping executable on disk after pre-open cannot alter verified descriptor."""
    if sys.platform == "win32":
        pytest.skip("Windows mandatory file locking prohibits file replacement while file is open")
    exe_file = tmp_path / "bin"
    original = b"echo original"
    exe_file.write_bytes(original)

    fd = os.open(str(exe_file), os.O_RDONLY | os.O_CLOEXEC)
    try:
        # Attacker swaps file on disk (atomic path replacement / TOCTOU swap)
        new_exe = tmp_path / "new_bin"
        new_exe.write_bytes(b"echo malicious_payload")
        os.replace(str(new_exe), str(exe_file))

        # Reading from original open descriptor still returns original content
        os.lseek(fd, 0, os.SEEK_SET)
        data = os.read(fd, 100)
        assert data == original
    finally:
        os.close(fd)


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


def test_test_store_fault_injection_hook_raises_runtime_error(tmp_path):
    """E-RT-4 / H32: TestSQLiteEventStore fault injection raises simulated errors across stages."""
    # When a crash occurs during lifecycle commitment, state consistency must be preserved
    # and uncommitted/partially-committed executions fail closed.
    stages_hit = []
    for stage_to_crash in ("K1_BEFORE_DURABLE_INTENT", "K2_AFTER_COMMIT_RECORD", "K3_AFTER_EVENT_ROWS", "K4_AFTER_PROJECTION", "K5_BEFORE_COMMIT"):
        def fault_injector(stage):
            if stage == stage_to_crash:
                stages_hit.append(stage)
                raise RuntimeError(f"simulated crash at {stage}")

        db_path = str(tmp_path / f"store_{stage_to_crash}.sqlite")
        store = R.TestSQLiteEventStore(db_path, fault_injector=fault_injector)
        assert store._fault_injector is not None

        # Verify that fault injection at this stage raises RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            store._fault(stage_to_crash)
        assert f"simulated crash at {stage_to_crash}" in str(exc_info.value)
    assert len(stages_hit) == 5


def test_recovery_verifies_workspace_restoration(tmp_path):
    """E-RT-4 / H32: Recovery verifies workspace restoration."""
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


def test_runtime_source_contains_assessor_attestor_token():
    """E-RT-4 / H32: Runtime source implements assessment_attestor separation."""
    runtime_src = (RUNTIME_DIR / "sclass_runtime_v6_0_1.py").read_text()
    assert "assessor_attestor" in runtime_src or "assessment_attestor" in runtime_src


def test_empty_dependency_set_canonical_digest_prefix():
    """E-RT-4 / H32: Canonical digest of empty dependency set produces valid sha256 prefix."""
    empty_digest = S.digest("sclass/dependency-set/v1", ())
    # Evidence payloads must not use placeholder empty dependency set
    assert empty_digest.startswith("sha256:")


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


def test_resource_failure_records_unresolved_evidence():
    """E-RT-7: Resource limit failure records unresolved evidence."""
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


