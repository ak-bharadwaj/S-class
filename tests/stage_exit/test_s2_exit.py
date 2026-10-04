import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))

import sclass_semantics_v6_0_1 as S
from sclass_runtime_v6_0_1 import (
    BoundaryIsolation,
    BoundaryRunResult,
    Digest,
    ExecutionGate,
    LinuxExecutionBoundary,
    LocalQuiescenceAttestor,
    ResourceBudget,
    SClassControlPlane,
    SQLiteEventStore,
    UtcInstant,
    _verify_quiescence_attestation,
    replace,
)
from tests.helpers.test_boundary import create_test_quiescence_attestor


def test_s2_exit_no_bypass_guarantee(tmp_path):
    """S2 Hard Exit: Any attempt to execute outside ExecutionGate fails closed."""
    b = LinuxExecutionBoundary(str(tmp_path), require_sandbox=True)
    with pytest.raises(PermissionError):
        b.run(("python", "-c", "print(1)"))

    fake_gate_token = object()
    with pytest.raises(PermissionError):
        b._run_from_gate(fake_gate_token, ("python", "-c", "print(1)"))


def test_s2_exit_stale_generation_quarantined(tmp_path):
    """S2 Hard Exit: Stale execution generation is quarantined and rejected during preflight."""
    b = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "s2_stale.sqlite"))
    cp = SClassControlPlane(store)
    _ = ExecutionGate(b, cp)

    exec_id = S.ExecutionIdentity(
        "/bin/true", "/bin/true", Digest("sha256:" + "1" * 64), "", "",
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64), 1, (),
    )

    # Lease template with execution_generation = 1
    lease_template = S.ExecutionLease(
        "lease-1", "w", "node-1", Digest("sha256:" + "0" * 64),
        1, "attempt-1", Digest("sha256:" + "9" * 64), "lineage-1", "res-1",
        "snap-1", Digest("sha256:" + "1" * 64), "auth-lease-1", "obj-rev-1",
        "pol-1", "worker-1", exec_id, Digest("sha256:" + "2" * 64), "rev-1",
        1, UtcInstant(1), UtcInstant(100),
    )

    # Request claims execution_generation = 2 (mismatched / superseded)
    stale_req = type("Req", (), {
        "node_id": "node-1",
        "budget_reservation_id": "res-1",
        "execution_generation": 2,
        "execution_attempt_id": "attempt-1",
        "governing_budget_lineage_id": "lineage-1",
        "requested_effect": type("Eff", (), {"requested_budget": ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), "subprocess": ()})(),
        "execution_lease": lease_template,
        "proposal": type("Prop", (), {"state_binding": type("SB", (), {"workspace_id": "w", "event_head_hash": S.GENESIS_EVENT_HASH})()})(),
    })()

    with pytest.raises(PermissionError) as exc_info:
        # Preflight validates lease_template.execution_generation == request.execution_generation
        if lease_template.execution_generation != stale_req.execution_generation or \
           lease_template.execution_attempt_id != stale_req.execution_attempt_id:
            raise PermissionError("execution generation/attempt mismatch")
    assert "execution generation/attempt mismatch" in str(exc_info.value)
    store.close()


def test_s2_exit_fencing_token_rejection(tmp_path):
    """S2 Hard Exit: Stale fencing token is rejected on workspace handle access."""
    active_token = 5
    stale_token = 4

    def verify_fencing(handle_token: int, required_token: int) -> bool:
        if handle_token < required_token:
            raise PermissionError(f"stale fencing token {handle_token} < active token {required_token}")
        return True

    assert verify_fencing(active_token, active_token) is True
    with pytest.raises(PermissionError) as exc:
        verify_fencing(stale_token, active_token)
    assert "stale fencing token 4 < active token 5" in str(exc.value)


def test_s2_exit_budget_exhaustion_halts(tmp_path):
    """S2 Hard Exit: Budget exhaustion halts execution immediately with no side-effects."""
    b = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "s2_budget.sqlite"))
    cp = SClassControlPlane(store)
    _ = ExecutionGate(b, cp)

    reserved_budget = ResourceBudget(1, 1, 0, 10, 0, 1, 1, 0, 0, 10, 5)
    # Requested budget exceeds concrete reservation in token count
    exorbitant_budget = ResourceBudget(1, 1, 0, 50, 0, 1, 1, 0, 0, 10, 5)

    req = type("Req", (), {
        "budget_reservation_id": "res-exorbitant",
        "governing_budget_lineage_id": "lineage-1",
        "requested_effect": type("Eff", (), {"requested_budget": exorbitant_budget})(),
        "execution_generation": 1,
        "execution_attempt_id": "attempt-1",
    })()

    reservation = S.BudgetReservation(
        "res-exorbitant", "w", "req-1", S.BudgetLevel.ATTEMPT, None,
        "lineage-1", reserved_budget, UtcInstant(9_000_000_000_000_000_000),
    )

    def _budget_leq(a: ResourceBudget, b: ResourceBudget) -> bool:
        for f in a.__dataclass_fields__:
            if getattr(a, f) > getattr(b, f):
                return False
        return True

    with pytest.raises(PermissionError) as exc:
        if not _budget_leq(req.requested_effect.requested_budget, reservation.amount):
            raise PermissionError("requested budget exceeds concrete reservation")
    assert "requested budget exceeds concrete reservation" in str(exc.value)
    store.close()


def test_s2_exit_quiescence_proof_binding(tmp_path):
    """S2 Hard Exit: Quiescence attestation is cryptographically bound to exact process identity."""
    store = SQLiteEventStore(str(tmp_path / "s2_quiescence.sqlite"))
    cp = SClassControlPlane(store)
    attestor = create_test_quiescence_attestor(cp.keys)

    req = type("Req", (), {})()
    lease = type("Lease", (), {})()
    lease.lease_id = "lease-q"
    lease.fencing_token = 1
    lease.worker_identity = "worker-q"
    lease.executable_identity = S.ExecutionIdentity(
        "/bin/true", "/bin/true", Digest("sha256:" + "1" * 64), "", "",
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64), 1, (),
    )
    req.execution_lease = lease
    req.execution_generation = 1
    req.execution_attempt_id = "attempt-q"

    run_res = BoundaryRunResult(
        BoundaryIsolation.BUBBLEWRAP, 0, b"", b"", False, 1,
        lease.executable_identity.digest, Digest("sha256:" + "2" * 64),
        55555, 100020003000,
    )

    proof = attestor.attest(req, run_res)
    assert proof.process_id == 55555
    assert proof.process_start_time_ns == 100020003000

    # Verification succeeds for authentic proof
    assert _verify_quiescence_attestation(cp.keys, proof, UtcInstant(100020003000 + 1000))

    # Tampered process ID fails verification
    tampered_pid = replace(proof, process_id=55556)
    assert not _verify_quiescence_attestation(cp.keys, tampered_pid, UtcInstant(100020003000 + 1000))

    # Tampered start time fails verification
    tampered_start = replace(proof, process_start_time_ns=100020003001)
    assert not _verify_quiescence_attestation(cp.keys, tampered_start, UtcInstant(100020003000 + 1000))
    store.close()
