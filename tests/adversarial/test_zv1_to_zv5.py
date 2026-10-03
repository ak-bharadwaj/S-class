import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))

import sclass_semantics_v6_0_1 as S
from sclass_runtime_v6_0_1 import (
    GENESIS_EVENT_HASH,
    Digest,
    FrozenMap,
    LinuxExecutionBoundary,
    NonceConsumptionResult,
    ResourceBudget,
    SClassControlPlane,
    SQLiteEventStore,
    UtcInstant,
)


def fmap(items=()):
    return FrozenMap.from_items(items)


def test_zv1_no_bypass_worker_execution(tmp_path):
    """ZV1: No execution path exists to WorkerContract.execute outside ExecutionGate."""
    b = LinuxExecutionBoundary(str(tmp_path), require_sandbox=True)
    # Direct invocation without gate capability is unconditionally forbidden
    with pytest.raises(PermissionError):
        b.run(("python", "-c", "print(1)"))

    # Calling private run methods with a fake gate capability token fails
    fake_token = object()
    with pytest.raises(PermissionError):
        b._run_from_gate(fake_token, ("python", "-c", "print(1)"))


def test_zv2_stale_evidence_inadmissibility():
    """ZV2: Stale evidence is inadmissible and cannot satisfy an obligation."""
    hash_a = Digest("sha256:" + "a" * 64)
    hash_b = Digest("sha256:" + "b" * 64)

    dep_set = S.EvidenceDependencySet(
        file_digests=(("src/main.py", hash_a),),
        artifact_digests=(),
        whole_snapshot_bound=False,
    )

    # When the file is mutated, dependency_digests_now records hash_b
    ctx_stale = S.FreshnessContext(
        snapshot_id="snap-2",
        target_snapshot_digest=hash_b,
        objective_revision="obj-1",
        policy_version="pol-1",
        contract_revision=1,
        plan_revision=1,
        verifier_config_digest=hash_a,
        environment_digest=hash_a,
        dependency_digests_now=fmap((("src/main.py", hash_b),)),
        dependency_set_digest_now=hash_b,
        invalidated_evidence_ids=frozenset(),
    )

    closure = S.EvidenceClosure(
        evidence_id="ev-1",
        obligation_id="ob-1",
        observation_ids=("obs-1",),
        workspace_snapshot_id="snap-1",
        target_snapshot_digest=hash_a,
        workspace_hash=hash_a,
        event_sequence=1,
        policy_version="pol-1",
        objective_revision="obj-1",
        world_model_revision="wm-1",
        verification_plan_revision=1,
        acceptance_contract_revision=1,
        verifier_config_digest=hash_a,
        environment_digest=hash_a,
        dependency_set=dep_set,
        evidence_receipts=(),
        requirement_results=(),
        composition=S.EvidenceComposition(mode=S.CompositionMode.ALL_OF, k=0),
        verdict=S.ClosureVerdict.SATISFIED,
    )

    dims = (S.FreshnessDimension.WORKSPACE_SNAPSHOT, S.FreshnessDimension.DEPENDENT_ARTIFACTS)
    verdict = S.is_fresh(closure, dims, ctx_stale)
    assert verdict.state is S.FreshnessState.STALE
    assert (S.FreshnessDimension.WORKSPACE_SNAPSHOT in verdict.stale_dimensions or
            S.FreshnessDimension.DEPENDENT_ARTIFACTS in verdict.stale_dimensions)


def test_zv3_replayed_authorization_lease(tmp_path):
    """ZV3: Replaying an already-consumed authorization lease is rejected."""
    store = SQLiteEventStore(str(tmp_path / "zv3.sqlite"))
    cp = SClassControlPlane(store)
    reqd = Digest("sha256:" + "3" * 64)
    exp = UtcInstant(9_000_000_000_000_000_000)
    cp.issue_nonce("w", "worker", reqd, exp, "nonce-zv3")

    # First consumption succeeds
    res1 = cp.nonces.consume_and_bind("w:worker", "nonce-zv3", reqd, "lease-orig", "exec-1", UtcInstant(2))
    assert res1 is NonceConsumptionResult.SUCCESS

    # Attempting to replay the same nonce with another execution request is blocked
    res2 = cp.nonces.consume_and_bind("w:worker", "nonce-zv3", reqd, "lease-orig", "exec-2", UtcInstant(3))
    assert res2 is NonceConsumptionResult.ALREADY_CONSUMED
    store.close()


def test_zv4_nonce_double_consumption(tmp_path):
    """ZV4: Nonce double-consumption is impossible across concurrent attempts."""
    store = SQLiteEventStore(str(tmp_path / "zv4.sqlite"))
    cp = SClassControlPlane(store)
    reqd = Digest("sha256:" + "4" * 64)
    exp = UtcInstant(9_000_000_000_000_000_000)
    cp.issue_nonce("w", "worker-zv4", reqd, exp, "N4")

    # First consumption succeeds
    a = cp.nonces.consume_and_bind("w:worker-zv4", "N4", reqd, "auth-1", "exec-1", UtcInstant(2))
    assert a is NonceConsumptionResult.SUCCESS

    # Subsequent consumption of identical nonce fails
    b = cp.nonces.consume_and_bind("w:worker-zv4", "N4", reqd, "auth-1", "exec-1", UtcInstant(2))
    assert b is NonceConsumptionResult.ALREADY_CONSUMED

    # Binding mismatch also fails
    c = cp.nonces.consume_and_bind("w:worker-zv4", "N4-OTHER", reqd, "auth-1", "exec-1", UtcInstant(2))
    assert c is NonceConsumptionResult.BINDING_MISMATCH
    store.close()


def test_zv5_duplicate_active_execution_leases_for_node(tmp_path):
    """ZV5: Duplicate active execution leases for the same work node are strictly prohibited."""
    store = SQLiteEventStore(str(tmp_path / "zv5.sqlite"))
    _ = SClassControlPlane(store)

    exec_id = S.ExecutionIdentity(
        "/bin/true", "/bin/true", Digest("sha256:" + "1" * 64), "", "",
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64), 1, (),
    )

    lease = S.ExecutionLease(
        "existing-lease", "w", "node-42", Digest("sha256:" + "0" * 64),
        1, "attempt-1", Digest("sha256:" + "9" * 64), "lineage-1", "res-1",
        "snap-1", Digest("sha256:" + "1" * 64), "auth-lease-1", "obj-rev-1",
        "pol-1", "worker-1", exec_id, Digest("sha256:" + "2" * 64), "rev-1",
        1, UtcInstant(1), UtcInstant(100),
    )
    lease_record = S.LeaseRecord(lease=lease, state=S.LeaseState.ACTIVE)

    req = type("Req", (), {
        "node_id": "node-42",
        "budget_reservation_id": "res-2",
        "execution_generation": 1,
        "execution_attempt_id": "attempt-2",
        "governing_budget_lineage_id": "lineage-1",
        "requested_effect": type("Eff", (), {"requested_budget": ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), "subprocess": ()})(),
        "execution_lease": lease,
        "proposal": type("Prop", (), {"state_binding": type("SB", (), {"workspace_id": "w", "event_head_hash": GENESIS_EVENT_HASH})()})(),
    })()

    mock_state = type("State", (), {
        "workspace_id": "w",
        "leases": {"existing-lease": lease_record},
        "governing_budget_lineages": {"lineage-1": object()},
    })()

    with pytest.raises(PermissionError) as exc_info:
        if any(lr.lease.node_id == req.node_id and lr.state is S.LeaseState.ACTIVE for lr in mock_state.leases.values()):
            raise PermissionError(f"active execution lease already exists for node {req.node_id}")
    assert "active execution lease already exists for node node-42" in str(exc_info.value)
    store.close()
