"""Tests for A6 reference implementations (CL Directives A6.1, A6.2, A6.3, A6.4).

Verifies:
1. All five Reference* classes have the non-authoritative scaffold docstring (A6.1).
2. Fail-closed behavior across reference classes: no fabricated observations, synthetic process results, or default-pass (A6.2).
3. Safe schema policy in ReferenceSQLiteStore: older migrated, newer rejected, missing/non-integer rejected (A6.3).
4. Fault injection inert when None, SQLite URI restricted strictly to file: paths (A6.4).
"""

from __future__ import annotations

import types
import sqlite3
from pathlib import Path
import pytest

from sclass.reference_impl import (
    ReferenceWorker,
    ReferenceHandoffCompiler,
    ReferenceVerificationProvider,
    ReferenceOperatingLoop,
    ReferenceCoordinatedRecovery,
    ReferenceSQLiteStore,
    ReferenceExecutionGate,
)
from sclass_semantics_v6_0_1 import (
    ActorIdentity,
    ActorKind,
    Digest,
    EngineeringState,
    FrozenMap,
    GENESIS_EVENT_HASH,
    ImmutableWorkspace,
    RecoveryOutcome,
    RepairPlan,
    SideEffectReceipt,
    SideEffectStatus,
    StateLoadStatus,
    VerificationStatus,
    VerificationStep,
    WorkerHealth,
    WorkerProfile,
    genesis_engineering_state,
)


def test_a6_1_reference_classes_non_authoritative_scaffold_docstring():
    """A6.1: Relocate all five Canonical* classes into src/sclass/reference_impl/

    with the required non-authoritative scaffold docstring.
    """
    classes = [
        ReferenceWorker,
        ReferenceHandoffCompiler,
        ReferenceVerificationProvider,
        ReferenceOperatingLoop,
        ReferenceCoordinatedRecovery,
        ReferenceSQLiteStore,
        ReferenceExecutionGate,
    ]
    for cls in classes:
        doc = cls.__doc__
        assert doc is not None, f"{cls.__name__} must have a docstring"
        assert "non-authoritative" in doc.lower(), f"{cls.__name__} docstring must indicate non-authoritative"
        assert "scaffold" in doc.lower() or "reference" in doc.lower(), f"{cls.__name__} docstring must indicate scaffold/reference"


def test_a6_2_operating_loop_missing_worker_fails_closed_in_doubt():
    """A6.2: Missing worker or observation capability must produce IN_DOUBT / unresolved outcomes,

    never fabricate observations or default-pass.
    """
    db_path = ":memory:"
    store = ReferenceSQLiteStore(db_path)
    loop = ReferenceOperatingLoop(store=store)

    # In a blank state with no obligations, loop converges safely
    actor = ActorIdentity("system", ActorKind.SYSTEM, None)
    res_converged = loop.run_cycle("test-ws", actor, worker=None)
    assert res_converged["status"] == "CONVERGED"

    # In a state with an unsatisfied obligation and missing worker: must fail closed with IN_DOUBT
    from sclass_semantics_v6_0_1 import Obligation, ObligationKind, ObligationStatus, RiskTier
    obl = Obligation(
        obligation_id="obl-unsatisfied",
        objective_id="obj-1",
        revision=1,
        description="needs work",
        kind=ObligationKind.FUNCTIONAL,
        risk_tier=RiskTier.LOW,
        status=ObligationStatus.PENDING,
        depends_on=frozenset(),
        acceptance_contract_id="contract-1",
        satisfied_by=None,
        verification_plan_id="plan-1",
    )
    fake_state = types.SimpleNamespace(
        workspace_id="test-ws",
        obligations=types.SimpleNamespace(_obligations={"obl-unsatisfied": obl}),
    )
    store._load_canonical_state = lambda ws: fake_state
    res_in_doubt = loop.run_cycle("test-ws", actor, worker=None)
    assert res_in_doubt["status"] == "IN_DOUBT"
    assert res_in_doubt["error"] == "missing_worker_capability"

    # In a state with unsatisfied obligation and worker provided but missing observation capability:
    worker = types.SimpleNamespace()
    res_no_obs = loop.run_cycle("test-ws", actor, worker=worker, observation_provider=None)
    assert res_no_obs["status"] == "IN_DOUBT"
    assert res_no_obs["error"] == "missing_observation_capture_capability"


def test_a6_2_verification_provider_fails_closed():
    """A6.2: Missing observation or process failure must produce FAIL."""
    verifier = ReferenceVerificationProvider()
    step = types.SimpleNamespace(step_id="step-1", required_mutations=())

    # Missing observation -> FAIL
    res_none = verifier.verify(None, step, None)
    assert res_none.status is VerificationStatus.FAIL

    # Failed process exit code -> FAIL
    proc_fail = types.SimpleNamespace(exit_code=1, stdout="err", stderr="failed", duration_ms=10)
    obs_fail = types.SimpleNamespace(observation_id="obs-1", mutations=(), process_result=proc_fail)
    res_proc_fail = verifier.verify(None, step, obs_fail)
    assert res_proc_fail.status is VerificationStatus.FAIL

    # Missing required mutations -> FAIL (A6.2 fail-closed)
    step_with_mut = types.SimpleNamespace(step_id="step-mut", required_mutations=("missing_file.txt",))
    proc_ok = types.SimpleNamespace(exit_code=0, stdout="ok", stderr="", duration_ms=10)
    obs_ok = types.SimpleNamespace(observation_id="obs-ok", mutations=(), process_result=proc_ok)
    res_mut_fail = verifier.verify(None, step_with_mut, obs_ok)
    assert res_mut_fail.status is VerificationStatus.FAIL

    # Empty requirement results -> FAIL (A6-R6 fail-closed)
    step_empty_res = types.SimpleNamespace(step_id="step-empty-res", required_mutations=(), requirement_results=())
    res_empty_res = verifier.verify(None, step_empty_res, obs_ok)
    assert res_empty_res.status is VerificationStatus.FAIL


def test_a6_2_coordinated_recovery_fails_closed_in_doubt():
    """A6.2: Uncompensated effects must transition to IN_DOUBT, never assumed resolved."""
    recovery = ReferenceCoordinatedRecovery()
    plan = types.SimpleNamespace(repair_id="repair-1")
    receipt = types.SimpleNamespace(
        effect_id="eff-1",
        status=SideEffectStatus.OBSERVED,  # Uncompensated
    )

    # Without compensation provider -> IN_DOUBT
    report = recovery.recover("node-1", plan, (receipt,), compensation_provider=None)
    assert report.outcome is RecoveryOutcome.IN_DOUBT
    assert "eff-1" in report.unresolved_effect_ids
    assert len(report.compensated_effect_ids) == 0


def test_a6_3_safe_schema_policy_older_migrated_newer_rejected(tmp_path: Path):
    """A6.3: Safe schema policy. Older versions migrated; newer versions rejected;

    missing/non-integer rejected.
    """
    # 1. Schema version 1: opens, migrates to 3 idempotently
    db_v1 = tmp_path / "v1.db"
    with sqlite3.connect(str(db_v1)) as conn:
        conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO store_meta (key, value) VALUES ('schema_version', '1')")

    store1 = ReferenceSQLiteStore(str(db_v1))
    assert store1.migrate("ws-1", 3) is StateLoadStatus.FOUND
    # Idempotent second run
    assert store1.migrate("ws-1", 3) is StateLoadStatus.FOUND
    store1.close()

    # 2. Schema version 4 (newer): opening rejected
    db_v4 = tmp_path / "v4.db"
    with sqlite3.connect(str(db_v4)) as conn:
        conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO store_meta (key, value) VALUES ('schema_version', '4')")

    with pytest.raises(ValueError, match="unsupported SQLiteEventStore schema version: 4"):
        ReferenceSQLiteStore(str(db_v4))

    # 3. Non-integer schema version: opening rejected
    db_bad = tmp_path / "bad.db"
    with sqlite3.connect(str(db_bad)) as conn:
        conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO store_meta (key, value) VALUES ('schema_version', 'invalid_str')")

    with pytest.raises(ValueError, match="invalid non-integer schema version"):
        ReferenceSQLiteStore(str(db_bad))

    # 4. Missing schema_version key in existing store_meta: rejected
    db_missing = tmp_path / "missing.db"
    with sqlite3.connect(str(db_missing)) as conn:
        conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO store_meta (key, value) VALUES ('other_key', 'some_val')")

    with pytest.raises(ValueError, match="missing schema version in store_meta"):
        ReferenceSQLiteStore(str(db_missing))

    # 5. Non-positive schema version (0 or negative): rejected
    db_zero = tmp_path / "zero.db"
    with sqlite3.connect(str(db_zero)) as conn:
        conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO store_meta (key, value) VALUES ('schema_version', '0')")

    with pytest.raises(ValueError, match="unsupported SQLiteEventStore schema version: 0"):
        ReferenceSQLiteStore(str(db_zero))


def test_a6_3_migration_crash_safety_rollback(tmp_path: Path):
    """A6.3: Schema migration is transactional and crash-safe against injected faults."""
    db_path = tmp_path / "migration_crash.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT INTO store_meta (key, value) VALUES ('schema_version', '1')")

    def fault_injector(stage: str):
        if stage == "K8_DURING_MIGRATION":
            raise RuntimeError("CRASH_DURING_MIGRATION")

    store = ReferenceSQLiteStore(str(db_path), fault_injector=fault_injector)
    with pytest.raises(RuntimeError, match="CRASH_DURING_MIGRATION"):
        store.migrate("ws-1", 3)

    # After rollback, schema version remains 1 (uncommitted)
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
        assert row[0] == "1"


def test_a6_4_fault_injection_inert_when_none(tmp_path: Path):
    """A6.4: Fault injection must be inert when fault_injector is None."""
    db_path = str(tmp_path / "fault_inert.db")
    store = ReferenceSQLiteStore(db_path, fault_injector=None)
    # Calling internal fault triggers does not raise or fail
    store._fault("K1_BEFORE_DURABLE_INTENT")
    store._fault("K8_DURING_VERIFICATION")
    store._fault("NONEXISTENT_STAGE")
    store.close()


def test_a6_4_sqlite_uri_restricted_to_file():
    """A6.4: SQLite URI acceptance must be restricted strictly to file: paths."""
    # file: paths are permitted
    valid_uri = "file:test_store_mem?mode=memory&cache=shared"
    store = ReferenceSQLiteStore(valid_uri)
    store.close()

    # Other schemes are strictly rejected
    invalid_schemes = [
        "http://example.com/db.sqlite",
        "postgres://localhost:5432/db",
        "sqlite://local.db",
        "mem://database",
    ]
    for bad_uri in invalid_schemes:
        with pytest.raises(ValueError, match="unsupported SQLite URI scheme: only file: paths are accepted"):
            ReferenceSQLiteStore(bad_uri)


def test_a6_1_frozen_semantics_has_no_relocated_canonical_classes():
    """A6.1: Prove importing sclass_semantics_v6_0_1 directly does not expose relocated Canonical* classes."""
    import sclass_semantics_v6_0_1 as sem

    for name in [
        "CanonicalWorker",
        "CanonicalHandoffCompiler",
        "CanonicalVerificationProvider",
        "CanonicalOperatingLoop",
        "CanonicalCoordinatedRecovery",
    ]:
        assert not hasattr(sem, name), f"Semantics module must not expose {name}"


def test_a6_1_workproposal_unpatched_constructor():
    """A6.1: WorkProposal must have no __wp_patched__ marker and retains object.__init__."""
    import sclass_semantics_v6_0_1 as sem

    assert not hasattr(sem.WorkProposal, "__wp_patched__")
    assert sem.WorkProposal.__init__ is object.__init__
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1")


def test_a6_1_sitecustomize_no_semantic_mutations_or_meta_path_hooks():
    """A6.1: sitecustomize must not install meta_path hooks or mutate normative module semantics."""
    import sitecustomize  # noqa: F401
    import sys

    assert not any("Semantics" in str(h) or "WrappedLoader" in str(h) for h in sys.meta_path)
    import sclass_semantics_v6_0_1 as sem

    assert not hasattr(sem.WorkProposal, "__wp_patched__")
    assert not hasattr(sem, "CanonicalWorker")


def test_a6_1_reference_implementations_export_contract():
    """A6.1: Reference implementations must only be exported under Reference* names."""
    import sclass.reference_impl as ref

    for name in [
        "CanonicalWorker",
        "CanonicalHandoffCompiler",
        "CanonicalVerificationProvider",
        "CanonicalOperatingLoop",
        "CanonicalCoordinatedRecovery",
        "SQLiteCanonicalStore",
    ]:
        assert not hasattr(ref, name), f"reference_impl must not expose {name}"
        assert name not in ref.__all__, f"{name} must not be in ref.__all__"


def test_a6_1_conftest_semantics_proxy_no_workproposal_override():
    """A6.1: _SemanticsProxy must not supply a custom WorkProposal compatibility subclass."""
    import conftest
    import sclass_semantics_v6_0_1 as sem

    proxy = conftest._SemanticsProxy(sem)
    assert proxy.WorkProposal is sem.WorkProposal
    assert proxy.WorkProposal.__init__ is object.__init__
    # Positional args rejected
    with pytest.raises(TypeError):
        proxy.WorkProposal("prop-1", "node-1")
    # Keyword args (as exercised by legacy test) rejected
    with pytest.raises(TypeError):
        proxy.WorkProposal(proposal_id="prop-b", node_id="node-2")


def test_a6_1_subprocess_not_globally_intercepted():
    """A6.1: subprocess.run must not be replaced session-wide or intercepted globally."""
    import subprocess

    assert subprocess.run.__module__ == "subprocess"
    assert subprocess.run.__name__ == "run"
    assert not getattr(subprocess.run, "__name__", "").startswith("_adapted")


