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
from tests.product.test_r1_cl_findings import _make_genuine_authorized_work_request
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


def test_reference_worker_no_callback_fails_closed_to_claimed_failed():
    """CL Finding 1a: ReferenceWorker execution without a callback must NOT return CLAIMED_COMPLETE."""
    from sclass_semantics_v6_0_1 import IsolationLevel, WorkerClaimStatus, WorkerProfile
    worker = ReferenceWorker(WorkerProfile("worker-1", "test", (), "model-1", IsolationLevel.PROCESS))
    req = types.SimpleNamespace(
        request_id="req-1",
        state_binding_digest="digest-1",
        envelope_digest="env-1",
        execution_generation=1,
        execution_attempt_id="att-1",
        governing_budget_lineage_id="b-1",
        request_content_digest=Digest("sha256:" + "1" * 64),
        target_snapshot_digest=Digest("sha256:" + "2" * 64),
        proposal=types.SimpleNamespace(
            state_binding=types.SimpleNamespace(
                objective_revision="obj-rev-real",
                workgraph_revision="wg-rev-real",
            )
        ),
    )
    result = worker.execute(req)
    assert result.claim_status is WorkerClaimStatus.CLAIMED_FAILED, (
        f"Expected CLAIMED_FAILED when no callback is present, got {result.claim_status}"
    )


def test_reference_worker_missing_digests_or_revisions_fails_closed():
    """CL Finding 1b: ReferenceWorker must not fallback to zero digests or dummy placeholder revisions."""
    from sclass_semantics_v6_0_1 import IsolationLevel, WorkerProfile
    worker = ReferenceWorker(WorkerProfile("worker-1", "test", (), "model-1", IsolationLevel.PROCESS))

    # Request missing target_snapshot_digest and request_content_digest
    req_missing_digests = types.SimpleNamespace(
        request_id="req-1",
        state_binding_digest="digest-1",
        envelope_digest="env-1",
        execution_generation=1,
        execution_attempt_id="att-1",
        governing_budget_lineage_id="b-1",
    )
    with pytest.raises(ValueError, match="requires authentic"):
        worker.execute(req_missing_digests)


def test_reference_worker_no_fixed_dummy_metrics():
    """CL Finding 1c: ReferenceWorker must not fabricate fixed dummy metrics (100 tokens, 50 ms)."""
    from sclass_semantics_v6_0_1 import IsolationLevel, WorkerClaimStatus, WorkerProfile
    # Callback providing real metrics
    worker = ReferenceWorker(
        WorkerProfile("worker-1", "test", (), "model-1", IsolationLevel.PROCESS),
        execution_callback=lambda req, b, h: WorkerClaimStatus.CLAIMED_COMPLETE,
    )
    req = types.SimpleNamespace(
        request_id="req-1",
        state_binding_digest="digest-1",
        envelope_digest="env-1",
        execution_generation=1,
        execution_attempt_id="att-1",
        governing_budget_lineage_id="b-1",
        request_content_digest=Digest("sha256:" + "1" * 64),
        target_snapshot_digest=Digest("sha256:" + "2" * 64),
        proposal=types.SimpleNamespace(
            state_binding=types.SimpleNamespace(
                objective_revision="obj-rev-real",
                workgraph_revision="wg-rev-real",
            )
        ),
    )
    res = worker.execute(req)
    assert res.measured_tokens != 100 or res.measured_duration_ms != 50, (
        "ReferenceWorker fabricated fixed dummy metrics (100 tokens, 50 ms)"
    )
    assert res.measured_tokens is None, f"Expected None for absent measured_tokens, got {res.measured_tokens}"
    assert res.measured_duration_ms is None, f"Expected None for absent measured_duration_ms, got {res.measured_duration_ms}"
    assert ReferenceWorker.is_admissible(res) is False, "WorkResult without measurements must be inadmissible"

    # With genuine measurements:
    worker_with_metrics = ReferenceWorker(
        WorkerProfile("worker-1", "test", (), "model-1", IsolationLevel.PROCESS),
        execution_callback=lambda req, b, h: (WorkerClaimStatus.CLAIMED_COMPLETE, 200, 30),
    )
    res_m = worker_with_metrics.execute(req)
    assert res_m.measured_tokens == 200
    assert res_m.measured_duration_ms == 30
    assert ReferenceWorker.is_admissible(res_m) is True



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
    object.__setattr__(obl, "verification_step", types.SimpleNamespace(step_id="step-1", required_mutations=()))
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


def test_operating_loop_executes_worker_and_fails_closed_on_worker_failure():
    """CL Finding 5: ReferenceOperatingLoop must execute worker.execute() and fail closed if worker fails."""
    from sclass_semantics_v6_0_1 import (
        ActorIdentity,
        ActorKind,
        Obligation,
        ObligationKind,
        ObligationStatus,
        RiskTier,
        TargetSnapshot,
        CausalFrontier,
        Digest,
        FrozenMap,
        UtcInstant,
        WorkerClaimStatus,
    )
    store = ReferenceSQLiteStore(":memory:")
    loop = ReferenceOperatingLoop(store=store)

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
    object.__setattr__(obl, "verification_step", types.SimpleNamespace(step_id="step-1", required_mutations=()))
    ts = TargetSnapshot(
        "snap-1",
        "test-ws",
        Digest("sha256:" + "1" * 64),
        Digest("sha256:" + "2" * 64),
        None,
        None,
        Digest("sha256:" + "3" * 64),
        Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64),
        (),
        FrozenMap.from_items(()),
        "pol-1",
        UtcInstant(1),
    )
    frontier = CausalFrontier(
        "f-1",
        "p-1",
        "1.0",
        "rev-1",
        "og-1",
        "wg-1",
        Digest("sha256:" + "1" * 64),
        Digest("sha256:" + "2" * 64),
        "epoch-1",
        Digest("sha256:" + "3" * 64),
        Digest("sha256:" + "4" * 64),
        (),
        ("reason-1",),
    )
    mock_state = types.SimpleNamespace(
        workspace_id="test-ws",
        obligations=types.SimpleNamespace(_obligations={"obl-unsatisfied": obl}),
        objective=types.SimpleNamespace(revisions=(types.SimpleNamespace(revision_id="rev-1"),)),
        world_model=None,
        work_graph=types.SimpleNamespace(revision_id="wg-1"),
        policy_version="pol-1",
        workspace_snapshot_id="snap-1",
        target_snapshot=ts,
        causal_frontier=frontier,
        evidence={},
        budget_lineages={},
        event_head_hash="sha256:" + "1" * 64,
    )
    store._load_canonical_state = lambda ws: mock_state

    executed_calls = []
    class FailingWorker:
        def execute(self, req, boundary=None, handle=None):
            executed_calls.append(req)
            return types.SimpleNamespace(claim_status=WorkerClaimStatus.CLAIMED_FAILED)

    obs_called = []
    auth_req = _make_genuine_authorized_work_request("obl-unsatisfied")
    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=FailingWorker(),
        observation_provider=lambda prop, w_res=None: obs_called.append((prop, w_res)),
        authorized_request=auth_req,
    )

    # 1. worker.execute MUST have been called
    assert len(executed_calls) == 1, "CL Finding 5 violation: worker.execute() was never called!"
    # 2. Worker failed -> observation provider must NEVER have been called
    assert len(obs_called) == 0, "Observation provider should not be called when worker execution fails!"
    # 3. Status must not be PROGRESSING or CONVERGED
    assert res["status"] in ("ESCALATED", "IN_DOUBT"), f"Expected fail-closed status, got {res['status']}"


def test_operating_loop_executes_worker_success_progresses():
    """ReferenceOperatingLoop proceeds to observation and succeeds when worker succeeds."""
    from sclass_semantics_v6_0_1 import (
        ActorIdentity,
        ActorKind,
        Obligation,
        ObligationKind,
        ObligationStatus,
        RiskTier,
        TargetSnapshot,
        CausalFrontier,
        Digest,
        FrozenMap,
        UtcInstant,
        VerificationStatus,
        WorkerClaimStatus,
    )
    store = ReferenceSQLiteStore(":memory:")
    verifier = ReferenceVerificationProvider()
    loop = ReferenceOperatingLoop(store=store, verification_provider=verifier)

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
    object.__setattr__(obl, "verification_step", types.SimpleNamespace(step_id="step-1", required_mutations=()))
    ts = TargetSnapshot(
        "snap-1",
        "test-ws",
        Digest("sha256:" + "1" * 64),
        Digest("sha256:" + "2" * 64),
        None,
        None,
        Digest("sha256:" + "3" * 64),
        Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64),
        (),
        FrozenMap.from_items(()),
        "pol-1",
        UtcInstant(1),
    )
    frontier = CausalFrontier(
        "f-1",
        "p-1",
        "1.0",
        "rev-1",
        "og-1",
        "wg-1",
        Digest("sha256:" + "1" * 64),
        Digest("sha256:" + "2" * 64),
        "epoch-1",
        Digest("sha256:" + "3" * 64),
        Digest("sha256:" + "4" * 64),
        (),
        ("reason-1",),
    )
    mock_state = types.SimpleNamespace(
        workspace_id="test-ws",
        obligations=types.SimpleNamespace(_obligations={"obl-unsatisfied": obl}),
        objective=types.SimpleNamespace(revisions=(types.SimpleNamespace(revision_id="rev-1"),)),
        world_model=None,
        work_graph=types.SimpleNamespace(revision_id="wg-1"),
        policy_version="pol-1",
        workspace_snapshot_id="snap-1",
        target_snapshot=ts,
        causal_frontier=frontier,
        evidence={},
        budget_lineages={},
        event_head_hash="sha256:" + "1" * 64,
    )
    store._load_canonical_state = lambda ws: mock_state

    from sclass_semantics_v6_0_1 import WorkResult, WorkerProfile, WorkerKind, IsolationLevel
    executed_calls = []
    class SuccessWorker:
        def profile(self):
            return WorkerProfile("ref-worker", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
        def execute(self, req, boundary=None, handle=None):
            executed_calls.append(req)
            return WorkResult(
                result_id="wr-ok",
                request_id=req.request_id,
                request_content_digest=req.proposal.request_content_digest,
                envelope_digest=req.envelope_digest,
                execution_generation=req.execution_generation,
                execution_attempt_id=req.execution_attempt_id,
                target_snapshot_digest=req.execution_lease.target_snapshot_digest,
                state_binding_digest=req.state_binding_digest,
                governing_budget_lineage_id=req.governing_budget_lineage_id,
                objective_revision=req.proposal.state_binding.objective_revision,
                workgraph_revision=req.proposal.state_binding.workgraph_revision,
                worker_identity="ref-worker",
                claim_status=WorkerClaimStatus.CLAIMED_COMPLETE,
                measured_tokens=100,
                measured_duration_ms=20,
                output_digest=Digest("sha256:" + "9" * 64),
                diagnostics_digest=Digest("sha256:" + "8" * 64),
                produced_artifacts=(),
            )

    obs_called = []
    auth_req = _make_genuine_authorized_work_request("obl-unsatisfied")
    def valid_obs_provider(proposal, worker_result):
        obs_called.append((proposal, worker_result))
        proc_ok = types.SimpleNamespace(exit_code=0, stdout="pass", stderr="", duration_ms=10)
        return types.SimpleNamespace(
            observation_id="obs-ok",
            request_id=auth_req.request_id,
            execution_attempt_id=auth_req.execution_attempt_id,
            execution_generation=auth_req.execution_generation,
            worker_identity=worker_result.worker_identity,
            worker_result_digest=worker_result.output_digest,
            mutations=(),
            process_result=proc_ok,
            acceptance_contract_id="contract-1",
        )

    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=SuccessWorker(),
        observation_provider=valid_obs_provider,
        authorized_request=auth_req,
    )

    assert len(executed_calls) == 1
    assert len(obs_called) == 1
    assert res["status"] == "PROGRESSING"
    assert "obl-unsatisfied" in res["satisfied"]


def test_operating_loop_worker_crash_or_none_fails_closed():
    """Negative tests: Worker throwing exception or returning None must fail closed without calling observation."""
    from sclass_semantics_v6_0_1 import (
        ActorIdentity,
        ActorKind,
        Obligation,
        ObligationKind,
        ObligationStatus,
        RiskTier,
        TargetSnapshot,
        CausalFrontier,
        Digest,
        FrozenMap,
        UtcInstant,
    )
    store = ReferenceSQLiteStore(":memory:")
    loop = ReferenceOperatingLoop(store=store)

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
    ts = TargetSnapshot(
        "snap-1", "test-ws", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        None, None, Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64), (), FrozenMap.from_items(()), "pol-1", UtcInstant(1),
    )
    frontier = CausalFrontier(
        "f-1", "p-1", "1.0", "rev-1", "og-1", "wg-1",
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        "epoch-1", Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64),
        (), ("reason-1",),
    )
    mock_state = types.SimpleNamespace(
        workspace_id="test-ws",
        obligations=types.SimpleNamespace(_obligations={"obl-unsatisfied": obl}),
        objective=types.SimpleNamespace(revisions=(types.SimpleNamespace(revision_id="rev-1"),)),
        world_model=None,
        work_graph=types.SimpleNamespace(revision_id="wg-1"),
        policy_version="pol-1",
        workspace_snapshot_id="snap-1",
        target_snapshot=ts,
        causal_frontier=frontier,
        evidence={},
        budget_lineages={},
        event_head_hash="sha256:" + "1" * 64,
    )
    store._load_canonical_state = lambda ws: mock_state

    auth_req = _make_genuine_authorized_work_request("obl-unsatisfied")
    # 1. Worker raises exception
    class CrashingWorker:
        def execute(self, req, boundary=None, handle=None):
            raise RuntimeError("worker process crashed violently")

    obs_called = []
    res_crash = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=CrashingWorker(),
        observation_provider=lambda prop, w_res=None: obs_called.append(prop),
        authorized_request=auth_req,
    )
    assert len(obs_called) == 0, "Observation provider must not be called when worker crashes!"
    assert res_crash["status"] == "ESCALATED"
    assert "worker_execution_error" in res_crash["error"]

    # 2. Worker returns None
    class NoneWorker:
        def execute(self, req, boundary=None, handle=None):
            return None

    obs_called_none = []
    res_none = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=NoneWorker(),
        observation_provider=lambda prop, w_res=None: obs_called_none.append(prop),
        authorized_request=auth_req,
    )
    assert len(obs_called_none) == 0, "Observation provider must not be called when worker returns None!"
    assert res_none["status"] == "ESCALATED"
    assert res_none["error"] == "worker_execution_failed"



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

    # CL Finding 2: obligation=None with valid observation MUST FAIL CLOSED
    res_obl_none = verifier.verify(None, step, obs_ok)
    assert res_obl_none.status is VerificationStatus.FAIL, (
        f"CL Finding 2 violation: obligation=None must produce FAIL, got {res_obl_none.status}"
    )


def test_reference_handoff_compiler_never_fabricates_state_binding_with_zero_digests():
    """CL Finding 3: ReferenceHandoffCompiler must not catch broad exceptions to fabricate zero-digest StateBindings."""
    compiler = ReferenceHandoffCompiler()
    broken_state = types.SimpleNamespace(
        obligations=None,
        objective=None,
        world_model=None,
        evidence={},
        work_graph=None,
        authorization_decisions={},
        workspace_id="ws-broken",
        policy_version="pol-1",
        workspace_snapshot_id="snap-1",
        target_snapshot=None,
    )
    try:
        pkg = compiler.compile(broken_state, "obl-1")
        zero_dig = Digest("sha256:" + "0" * 64)
        assert pkg.state_binding.target_snapshot_digest != zero_dig, (
            "CL Finding 3 violation: fabricated StateBinding with zero target_snapshot_digest"
        )
        assert pkg.state_binding.state_entropy != zero_dig, (
            "CL Finding 3 violation: fabricated StateBinding with zero state_entropy"
        )
        assert False, "Expected compiler.compile() to raise on broken state"
    except (AttributeError, ValueError, KeyError):
        pass  # Correct fail-closed behavior



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


def test_a6_1_workproposal_e_sem_1_constructor():
    """A6.1 / E-SEM-1: WorkProposal must have strict six-argument constructor and mutable instance."""
    import sclass_semantics_v6_0_1 as sem

    assert not hasattr(sem.WorkProposal, "__wp_patched__")
    zero_dig = sem.Digest("sha256:" + "0" * 64)
    z_budget = sem.ResourceBudget(0, 0, 0, 30000, 0, 0, 0, 0, 0, 0, 0)
    sb = sem.StateBinding(
        "ws-1", "rev-1", "wg-1", "policy-v1", "ws-snap-1",
        zero_dig, zero_dig, "budget-1", 1, "epoch-1", zero_dig
    )
    req_eff = sem.RequestedEffect(
        filesystem=(), subprocess=(), network=(),
        environment=sem.FrozenMap.from_items(), credentials=(),
        external_side_effects=(), requested_budget=z_budget, delta_digest=None
    )

    # 1. Valid six-argument construction succeeds
    wp = sem.WorkProposal("prop-1", "node-1", zero_dig, sb, zero_dig, req_eff)
    assert wp.proposal_id == "prop-1"
    assert wp.node_id == "node-1"
    assert wp.request_content_digest == zero_dig
    assert wp.state_binding == sb
    assert wp.context_digest == zero_dig
    assert wp.requested_effect == req_eff

    # 2. Missing argument raises TypeError
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1", zero_dig, sb, zero_dig)
    with pytest.raises(TypeError):
        sem.WorkProposal()

    # 3. Wrong type raises TypeError
    with pytest.raises(TypeError):
        sem.WorkProposal(123, "node-1", zero_dig, sb, zero_dig, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", 456, zero_dig, sb, zero_dig, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1", 123, sb, zero_dig, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1", zero_dig, "not-a-binding", zero_dig, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1", zero_dig, sb, 456, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1", zero_dig, sb, zero_dig, "not-an-effect")

    # 4. None raises TypeError
    with pytest.raises(TypeError):
        sem.WorkProposal(None, "node-1", zero_dig, sb, zero_dig, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", None, zero_dig, sb, zero_dig, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1", None, sb, zero_dig, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1", zero_dig, None, zero_dig, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1", zero_dig, sb, None, req_eff)
    with pytest.raises(TypeError):
        sem.WorkProposal("prop-1", "node-1", zero_dig, sb, zero_dig, None)

    # 5. primary_obligation_id remains assignable
    wp.primary_obligation_id = "test-obl-123"
    assert wp.primary_obligation_id == "test-obl-123"


def test_client_has_no_make_authorized_work_request_and_refuses_to_synthesize_leases():
    """CL Finding 4: client.py must not contain _make_authorized_work_request or synthesize fake leases/signatures."""
    import sclass.client as client
    assert not hasattr(client, "_make_authorized_work_request"), (
        "CL Finding 4 violation: _make_authorized_work_request must be removed from client.py"
    )

    # client.run_autonomous_cycle must refuse fail-closed when no authoritative request is provided
    c = client.SClassClient(":memory:")
    with pytest.raises(client.StateBindingRefusalError):
        c.run_autonomous_cycle("ws-1", "/tmp")


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


def test_a6_1_conftest_no_semantics_proxy():
    """A6.1: conftest must not define _SemanticsProxy or proxy test_sclass_v6_0_1_conformance.semantics."""
    import conftest
    assert not hasattr(conftest, "_SemanticsProxy"), "conftest must not define _SemanticsProxy"

    import test_sclass_v6_0_1_conformance as tc
    import sclass_semantics_v6_0_1 as sem
    assert tc.semantics is sem, "tc.semantics must be unproxied frozen semantics module"


def test_a6_1_subprocess_not_globally_intercepted():
    """A6.1: subprocess.run must not be replaced or intercepted."""
    import conftest
    assert not hasattr(conftest, "_scope_legacy_store_adapter"), "conftest must not define _scope_legacy_store_adapter"

    import subprocess
    assert subprocess.run.__module__ == "subprocess"
    assert subprocess.run.__name__ == "run"
    assert not getattr(subprocess.run, "__name__", "").startswith("_adapted")


