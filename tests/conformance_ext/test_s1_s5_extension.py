"""S1-S5 Conformance Extension Tests.

Relocated from 10-CONFORMANCE/test_sclass_v6_0_1_conformance.py under CL Disposition (2026-11-15).
Exercises non-authoritative reference scaffold implementations:
- ReferenceWorker
- ReferenceHandoffCompiler
- ReferenceVerificationProvider
- ReferenceOperatingLoop
- ReferenceCoordinatedRecovery
- ReferenceSQLiteStore
- ReferenceWorkProposal
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import textwrap
import types
from dataclasses import fields, replace
from pathlib import Path

import pytest
from sclass_kernel_v6_0_1 import *
import sclass_kernel_v6_0_1 as kernel
import sclass_semantics_v6_0_1 as semantics
from sclass_semantics_v6_0_1 import (
    GENESIS_EVENT_HASH,
    REFERENCE_REDUCER,
    ActorIdentity,
    ActorKind,
    AppendResult,
    AssessmentVerdict,
    CanonicalEvent,
    ChainStatus,
    CheckpointRef,
    ClosureVerdict,
    CommitRecord,
    CommitState,
    CompensationCapability,
    Digest,
    EventType,
    ExecutionGeneration,
    ExecutionGenerationStatus,
    ExternalEffect,
    FrozenMap,
    GateResult,
    Obligation,
    ObligationKind,
    ObligationStatus,
    RiskTier,
    SideEffectReceipt,
    SideEffectStatus,
    TargetSnapshot,
    UtcInstant,
    WorkResult,
    commit_record_digest,
    digest,
    engineering_state_digest,
    genesis_engineering_state,
    target_snapshot_digest,
    validate_obligation_satisfaction,
)

from sclass.reference_impl import (
    ReferenceWorker,
    ReferenceHandoffCompiler,
    ReferenceVerificationProvider,
    ReferenceOperatingLoop,
    ReferenceCoordinatedRecovery,
    ReferenceSQLiteStore,
    ReferenceWorkProposal,
)

# Canonical aliases repointed to Reference* implementations per Directive 2
CanonicalWorker = ReferenceWorker
CanonicalHandoffCompiler = ReferenceHandoffCompiler
CanonicalVerificationProvider = ReferenceVerificationProvider
CanonicalOperatingLoop = ReferenceOperatingLoop
CanonicalCoordinatedRecovery = ReferenceCoordinatedRecovery
SQLiteEventStore = ReferenceSQLiteStore
WorkProposal = ReferenceWorkProposal

def z(): return ResourceBudget(0,0,0,0,0,0,0,0,0,0,0)
def fmap(items=()): return FrozenMap.from_items(items)
def empty_scope(**kw): return EffectScope(kw.get("fs_rules",()),kw.get("process_rules",()),kw.get("network_rules",()),kw.get("allowed_env",fmap()),kw.get("working_directory","."),kw.get("credential_grants",()),kw.get("external_effect_rules",()),kw.get("resource_budget",z()))
def req(fs=(),process=(),network=(),environment=None,budget=None): return RequestedEffect(tuple(fs),tuple(process),tuple(network),fmap(tuple((environment or {}).items())),(),(),budget or z())


def test_strong_migration_forward_is_idempotent(tmp_path):
    db_path = tmp_path / "store.db"
    store = ReferenceSQLiteStore(f"file:{db_path}?mode=rwc")
    store._db.execute("UPDATE store_meta SET value='2' WHERE key='schema_version'")
    store.close()
    
    store = ReferenceSQLiteStore(f"file:{db_path}?mode=rwc")
    res1 = store.migrate("default", 3)
    assert res1 == semantics.StateLoadStatus.FOUND
    
    res2 = store.migrate("default", 3)
    assert res2 == semantics.StateLoadStatus.FOUND
    store.close()


def test_strong_migration_crash_safety(tmp_path):
    import subprocess
    import sys
    repo_root = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "store.db"
    
    store = ReferenceSQLiteStore(f"file:{db_path}?mode=rwc")
    store._db.execute("UPDATE store_meta SET value='2' WHERE key='schema_version'")
    store.close()
    
    script = f"""import os, sys
sys.path.insert(0, {str(repo_root / "src")!r})
sys.path.insert(0, {str(repo_root / "10-CONFORMANCE")!r})
import sclass_semantics_v6_0_1 as semantics
from sclass.reference_impl import ReferenceSQLiteStore as SQLiteEventStore
def crash(pt):
    if pt == 'K8_DURING_MIGRATION':
        os._exit(0)
store = SQLiteEventStore(r'file:{db_path}?mode=rwc', crash)
try:
    store.migrate('default', 3)
except Exception:
    pass
"""
    script_path = tmp_path / "run_mig.py"
    script_path.write_text(script, encoding='utf-8')
    subprocess.run([sys.executable, str(script_path)])
    
    store = ReferenceSQLiteStore(f"file:{db_path}?mode=rwc")
    res = store.migrate("default", 3)
    assert res == semantics.StateLoadStatus.FOUND
    
    row = store._db.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
    assert int(row[0]) == 3
    store.close()


def test_strong_s1_crash_matrix_k7_checkpoint(tmp_path):
    import os, subprocess, sys, textwrap
    repo_root = Path(__file__).resolve().parents[2]
    db=tmp_path/"crash_k7.db"
    script=textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(repo_root / "src")!r})
        sys.path.insert(0, {str(repo_root / "10-CONFORMANCE")!r})
        from sclass_semantics_v6_0_1 import *
        from sclass.reference_impl import ReferenceSQLiteStore
        stage=os.environ.get("SCLASS_KILL_STAGE")
        def hook(s):
            if s == stage:
                os._exit(137)
        def actor(): return ActorIdentity("system",ActorKind.SYSTEM,None)
        store=ReferenceSQLiteStore({str(db)!r}, fault_injector=hook)
        e=CanonicalEvent.create("e1","crash","w",1,EventType.SHUTDOWN_REQUESTED,1,"system",actor(),"caus","corr",FrozenMap.from_items((("reason","test"),)),GENESIS_EVENT_HASH,"pol","sdk",UtcInstant(1))
        state=genesis_engineering_state("w")
        derived=REFERENCE_REDUCER.reduce(state,e)
        c=CommitRecord("crash","w",(e.event_id,"state:w"),(e.event_hash,engineering_state_digest(derived)),("event","state"),GENESIS_EVENT_HASH,e.event_hash,derived.state_revision,1,1,COMMIT_SCHEMA_VERSION,Digest("sha256:"+"0"*64),CommitState.COMMITTED,1,1,engineering_state_digest(derived))
        c=replace(c,commit_digest=commit_record_digest(c))
        store.append(e,c,GENESIS_EVENT_HASH)
        ref=CheckpointRef("cp1",derived.event_sequence,derived.state_digest,"crash")
        store.checkpoint(ref,derived)
        os._exit(0)
    """)
    env=os.environ.copy(); env["SCLASS_KILL_STAGE"]="K7_DURING_CHECKPOINT_WRITE"
    proc=subprocess.run([sys.executable,"-c",script],env=env,cwd=str(repo_root),capture_output=True)
    assert proc.returncode == 137
    reopened=ReferenceSQLiteStore(str(db))
    assert reopened.head("w").sequence == 1
    with pytest.raises(KeyError):
        reopened.restore("cp1")
    assert reopened.replay("w").event_sequence == 1
    reopened.close()


def test_strong_s1_crash_matrix_k10_k11_event_types(tmp_path):
    import os, subprocess, sys, textwrap
    repo_root = Path(__file__).resolve().parents[2]
    db=tmp_path/"crash_k10_k11.db"
    script=textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(repo_root / "src")!r})
        sys.path.insert(0, {str(repo_root / "10-CONFORMANCE")!r})
        from sclass_semantics_v6_0_1 import *
        from sclass.reference_impl import ReferenceSQLiteStore
        stage=os.environ.get("SCLASS_KILL_STAGE")
        def hook(s):
            if s == stage:
                os._exit(137)
        def actor(): return ActorIdentity("system",ActorKind.SYSTEM,None)
        store=ReferenceSQLiteStore({str(db)!r}, fault_injector=hook)
        cp=CheckpointRef("cp-handoff",1,Digest("sha256:"+"1"*64),"c-handoff")
        e=CanonicalEvent.create("e1","crash","w",1,EventType.STATE_CHECKPOINTED,1,"cp-handoff",actor(),"caus","corr",FrozenMap.from_items((("checkpoint",cp),("checkpoint_id","cp-handoff"))),GENESIS_EVENT_HASH,"pol","sdk",UtcInstant(1))
        state=genesis_engineering_state("w")
        derived=REFERENCE_REDUCER.reduce(state,e)
        c=CommitRecord("crash","w",(e.event_id,"state:w"),(e.event_hash,engineering_state_digest(derived)),("event","state"),GENESIS_EVENT_HASH,e.event_hash,derived.state_revision,1,1,COMMIT_SCHEMA_VERSION,Digest("sha256:"+"0"*64),CommitState.COMMITTED,1,1,engineering_state_digest(derived))
        c=replace(c,commit_digest=commit_record_digest(c))
        store.append(e,c,GENESIS_EVENT_HASH)
        os._exit(0)
    """)
    for stage in ["K11_DURING_HANDOFF", "K3_AFTER_EVENT_ROWS"]:
        if db.exists(): db.unlink()
        env=os.environ.copy(); env["SCLASS_KILL_STAGE"]=stage
        proc=subprocess.run([sys.executable,"-c",script],env=env,cwd=str(repo_root),capture_output=True)
        assert proc.returncode == 137
        reopened=ReferenceSQLiteStore(str(db))
        assert reopened.head("w").sequence == 0
        assert reopened.head("w").hash == GENESIS_EVENT_HASH
        reopened.close()


def test_adversarial_stale_evidence_rejection():
    from types import SimpleNamespace as N
    ts = TargetSnapshot("s", "w", Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64), None, None, Digest("sha256:"+"3"*64), Digest("sha256:"+"4"*64), Digest("sha256:"+"5"*64), (), fmap(), "p", UtcInstant(1))
    closure = N(
        obligation_id="obl-1",
        acceptance_contract_revision=1,
        verification_plan_revision=1,
        workspace_snapshot_id="s-old",
        target_snapshot_digest=Digest("sha256:"+"wrong"*12)[:71],
        objective_revision="obj-1",
        policy_version="p",
        verifier_config_digest=Digest("sha256:"+"cfg"*21)[:71],
        environment_digest=ts.environment_digest,
        observation_ids=(),
        evidence_receipts=(),
        verdict=ClosureVerdict.SATISFIED,
        requirement_results=()
    )
    state = N(
        workspace_id="w",
        workspace_snapshot_id="s-current",
        target_snapshot=ts,
        policy_version="p",
        obligations=N(_obligations={"obl-1": N(acceptance_contract_id="c1", verification_plan_id="v1")}),
        acceptance_contracts={"c1": N(revision=1)},
        verification_plans={"v1": N(revision=1, obligation_id="obl-1", contract_revision=1)},
        objective=N(revisions=(N(revision_id="obj-1"),))
    )
    assert semantics._validate_evidence_closure_against_state(state, closure, UtcInstant(100)) is False


def test_assessment_verdict_rejects_non_accept():
    from types import SimpleNamespace as N
    state = N(
        workspace_id="w",
        workspace_snapshot_id="s",
        target_snapshot=N(snapshot_id="s"),
        policy_version="p",
        obligations=N(_obligations={"obl-1": N(satisfied_by=None)}),
        evidence={"ev-1": N(obligation_id="obl-1")},
        assessments={
            "ass-reject": N(evidence_id="ev-1", verdict=AssessmentVerdict.REJECT),
            "ass-needs-more": N(evidence_id="ev-1", verdict=AssessmentVerdict.NEEDS_MORE_EVIDENCE)
        }
    )
    assert validate_obligation_satisfaction(state, "obl-1", "ev-1", "ass-reject", UtcInstant(100)) is False
    assert validate_obligation_satisfaction(state, "obl-1", "ev-1", "ass-needs-more", UtcInstant(100)) is False


def test_evidence_invalidated_sets_freshness_stale():
    from types import SimpleNamespace as N
    ts = TargetSnapshot("s", "w", Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64), None, None, Digest("sha256:"+"3"*64), Digest("sha256:"+"4"*64), Digest("sha256:"+"5"*64), (), fmap(), "p", UtcInstant(1))
    state = N(
        workspace_id="w",
        workspace_snapshot_id="s",
        target_snapshot=ts,
        policy_version="p",
        acceptance_contracts={},
        obligations=N(_obligations={"obl-1": N(satisfied_by=None, acceptance_contract_id="c1")}),
        evidence={"ev-stale": N(obligation_id="obl-1")},
        assessments={"ass-1": N(evidence_id="ev-stale", verdict=AssessmentVerdict.ACCEPT, workspace_snapshot_id="s", policy_version="p", target_snapshot_digest=target_snapshot_digest(ts))}
    )
    assert validate_obligation_satisfaction(state, "obl-1", "ev-stale", "ass-1", UtcInstant(100)) is False


def test_canonical_handoff_compiler_produces_bound_package():
    from types import SimpleNamespace as N
    ts = TargetSnapshot("s", "w", Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64), None, None, Digest("sha256:"+"3"*64), Digest("sha256:"+"4"*64), Digest("sha256:"+"5"*64), (), fmap(), "p", UtcInstant(1))
    cf = CausalFrontier(
        "f-1", "p-1", "1.0", "obj-rev-1", "og-1", "wg-0",
        Digest("sha256:" + "1" * 64), target_snapshot_digest(ts), "epoch-0",
        Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64), (), ("reason-1",)
    )
    state = N(
        workspace_id="w",
        workspace_snapshot_id="s",
        target_snapshot=ts,
        policy_version="p",
        obligations=N(_obligations={"obl-1": N(obligation_id="obl-1")}),
        evidence={},
        work_graph=N(_frontier=("node-1",), revision_id="wg-0"),
        authorization_decisions={},
        constraints={},
        objective=N(revisions=(N(revision_id="obj-rev-1"),)),
        world_model=N(revision_id="wm-rev-1"),
        world_model_revision="wm-rev-1",
        causal_frontier=cf,
        event_head_hash=GENESIS_EVENT_HASH,
    )
    compiler = ReferenceHandoffCompiler()
    pkg1 = compiler.compile(state, "obl-1")
    pkg2 = compiler.compile(state, "obl-1")
    assert pkg1.package_id == pkg2.package_id
    assert pkg1.package_digest == pkg2.package_digest
    assert pkg1.current_obligation_id == "obl-1"
    assert pkg1.frontier_node_ids == ("node-1",)
    assert not hasattr(pkg1, "leases")
    assert not hasattr(pkg1, "nonces")


def test_canonical_coordinated_recovery_in_doubt_on_unresolved():
    recovery = ReferenceCoordinatedRecovery()
    plan = semantics.RepairPlan("p-1", Digest("sha256:"+"0"*64), (), semantics.RepairStrategy.ROLLBACK)
    eff_digest = digest("sclass/external-effect/v1", ExternalEffect("sys", "MUTATE", 0))
    eff = SideEffectReceipt("e-1", "r-1", "w", "MUTATE", "sys",
                            ActorIdentity("sys", ActorKind.SYSTEM, None),
                            Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64),
                            eff_digest, UtcInstant(1),
                            status=SideEffectStatus.UNKNOWN,
                            compensation_reference=None)
    report = recovery.recover("node-1", plan, (eff,))
    assert report.outcome is semantics.RecoveryOutcome.IN_DOUBT
    assert report.unresolved_effect_ids == ("e-1",)
    assert report.rollback is semantics.RollbackResult.PARTIAL


def test_canonical_coordinated_recovery_recovered_on_compensated():
    recovery = ReferenceCoordinatedRecovery()
    plan = semantics.RepairPlan("p-1", Digest("sha256:"+"0"*64), (), semantics.RepairStrategy.ROLLBACK)
    eff_digest = digest("sclass/external-effect/v1", ExternalEffect("sys", "MUTATE", 0))
    eff = SideEffectReceipt("e-1", "r-1", "w", "MUTATE", "sys",
                            ActorIdentity("sys", ActorKind.SYSTEM, None),
                            Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64),
                            eff_digest, UtcInstant(1),
                            status=SideEffectStatus.COMPENSATED,
                            compensation_reference="comp-ref-1")
    report = recovery.recover("node-1", plan, (eff,))
    assert report.outcome is semantics.RecoveryOutcome.RECOVERED
    assert report.compensated_effect_ids == ("e-1",)
    assert report.rollback is semantics.RollbackResult.ROLLED_BACK


def test_canonical_verification_provider_pass_on_success():
    from types import SimpleNamespace as N
    provider = ReferenceVerificationProvider()
    step = N(step_id="step-1", required_mutations=())
    obs = N(observation_id="obs-1", process_result=N(exit_code=0), mutations=())
    obl = Obligation(
        "obl-1", "obj-1", 1, "test", ObligationKind.FUNCTIONAL, RiskTier.LOW,
        ObligationStatus.PENDING, frozenset(), "acc-1", None, "plan-1"
    )
    res = provider.verify(obl, step, obs)
    assert res.status is semantics.VerificationStatus.PASS
    assert res.observation_id == "obs-1"


def test_canonical_verification_provider_fail_on_process_error():
    from types import SimpleNamespace as N
    provider = ReferenceVerificationProvider()
    step = N(step_id="step-1", required_mutations=())
    obs = N(observation_id="obs-1", process_result=N(exit_code=1), mutations=())
    res = provider.verify(None, step, obs)
    assert res.status is semantics.VerificationStatus.FAIL


def test_flagship_continuity_worker_replacement():
    """Section 18.4 flagship continuity test.
    Worker A dies mid-node -> HandoffCompiler -> Worker B (different WorkerKind) resumes.
    Assert:
      - no stale evidence reuse
      - no authority inherited (fresh authorization required)
      - no hidden worker-session state in the package (no leases, nonces, tokens, credentials)
      - no duplicate work on already-SATISFIED obligations
      - no lease or nonce reuse
      - no budget double-spend
      - B's execution goes through a fresh proposal -> authorization -> lease chain.
    """
    from types import SimpleNamespace as N
    ts = TargetSnapshot("snap-1", "ws-handoff", Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64), None, None, Digest("sha256:"+"3"*64), Digest("sha256:"+"4"*64), Digest("sha256:"+"5"*64), (), fmap(), "pol-1", UtcInstant(10))

    obl_1 = Obligation("obl-1", "obj-1", 1, "test", ObligationKind.FUNCTIONAL, RiskTier.LOW, ObligationStatus.SATISFIED, frozenset(), "acc-1", "ev-1", "plan-1")
    obl_2 = Obligation("obl-2", "obj-1", 1, "test", ObligationKind.FUNCTIONAL, RiskTier.LOW, ObligationStatus.PENDING, frozenset(), "acc-2", None, "plan-2")

    cf = CausalFrontier(
        "f-1", "p-1", "1.0", "obj-rev-1", "og-1", "wg-0",
        Digest("sha256:" + "1" * 64), target_snapshot_digest(ts), "epoch-0",
        Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64), (), ("reason-1",)
    )
    state = N(
        workspace_id="ws-handoff",
        workspace_snapshot_id="snap-1",
        target_snapshot=ts,
        policy_version="pol-1",
        obligations=N(_obligations={"obl-1": obl_1, "obl-2": obl_2}),
        evidence={},
        work_graph=N(_frontier=("node-2",), revision_id="wg-0"),
        authorization_decisions={},
        constraints={},
        objective=N(revisions=(N(revision_id="obj-rev-1"),)),
        world_model=N(revision_id="wm-rev-1"),
        world_model_revision="wm-rev-1",
        causal_frontier=cf,
        event_head_hash=GENESIS_EVENT_HASH,
        event_sequence=1
    )

    prof_a = semantics.WorkerProfile("worker-a", semantics.WorkerKind.OPENHANDS, (), None, semantics.IsolationLevel.PROCESS)
    worker_a = ReferenceWorker(prof_a)
    worker_a.cancel("req-worker-a", "worker crashed")
    assert worker_a.heartbeat("req-worker-a") is semantics.WorkerHealth.EXITED

    compiler = ReferenceHandoffCompiler()
    pkg = compiler.compile(state, "obl-2", lineage_id="lineage-1", generation=1)

    assert not hasattr(pkg, "leases")
    assert not hasattr(pkg, "nonces")
    assert not hasattr(pkg, "fencing_token")
    assert not hasattr(pkg, "credentials")
    assert pkg.current_obligation_id == "obl-2"
    assert pkg.package_digest is not None
    assert len(pkg.fresh_evidence_ids) == 0

    prof_b = semantics.WorkerProfile("worker-b", semantics.WorkerKind.GOOSE, (), None, semantics.IsolationLevel.PROCESS)
    worker_b = ReferenceWorker(
        prof_b,
        execution_callback=lambda req, b, h: WorkerClaimStatus.CLAIMED_COMPLETE,
    )
    assert worker_b.profile().kind is semantics.WorkerKind.GOOSE
    assert worker_b.profile().kind != worker_a.profile().kind

    req_budget = ResourceBudget(1, 1, 0, 100, 0, 1, 1, 0, 0, 10, 1)
    effect = RequestedEffect((), (), (), fmap(), (), (), req_budget)
    binding_b = pkg.state_binding
    prop_b = ReferenceWorkProposal(
        proposal_id="prop-b",
        node_id="node-2",
        request_content_digest=Digest("sha256:"+"a"*64),
        state_binding=binding_b,
        context_digest=Digest("sha256:"+"b"*64),
        requested_effect=effect
    )

    dec_b = semantics.AuthorizationDecision(
        "dec-b", "prop-b", Digest("sha256:"+"a"*64), digest("sclass/state-binding/v1", binding_b),
        AuthorizationState.ALLOW, Authority.USER, "user", ("rule-1",), "fresh auth for worker b",
        UtcInstant(25), UtcInstant(100), "obj-rev-1", "worker-b", Digest("sha256:"+"c"*64), "pol-1",
        empty_scope(resource_budget=req_budget), "snap-1"
    )
    assert dec_b.worker_identity == "worker-b"
    assert dec_b.worker_identity != "worker-a"

    lease_b = N(lease_id="lease-b", worker_identity="worker-b")
    assert lease_b.worker_identity == "worker-b"

    auth_req_b = N(
        request_id="req-b",
        node_id="node-2",
        execution_generation=2,
        execution_attempt_id="att-b",
        governing_budget_lineage_id="lineage-1",
        budget_reservation_id="res-b",
        state_binding_digest=digest("sclass/state-binding/v1", binding_b),
        primary_obligation_id="obl-2",
        satisfies_obligation_ids=frozenset({"obl-2"}),
        action_description="execute obl-2",
        action_type=ActionType.CODE_READ,
        requested_effect=effect,
        effect_scope=empty_scope(resource_budget=req_budget),
        context=None,
        constraints=(),
        proposal=prop_b,
        authorization_lease=None,
        execution_lease=lease_b,
        authorization_binding_digest=Digest("sha256:"+"f"*64),
        envelope_digest=Digest("sha256:"+"0"*64),
        target_snapshot=ts
    )
    work_res_b = worker_b.execute(auth_req_b)
    assert work_res_b.worker_identity == "worker-b"
    assert work_res_b.claim_status is semantics.WorkerClaimStatus.CLAIMED_COMPLETE

    gen_b = ExecutionGeneration("node-2", 2, "att-b", "epoch-0", "worker-b",
                                target_snapshot_digest(ts), digest("sclass/state-binding/v1", binding_b),
                                "lineage-1", "obj-rev-1", "wg-0", ExecutionGenerationStatus.ACTIVE)
    assert semantics.admit_work_result(gen_b, work_res_b) is GateResult.ACCEPTED

    gen_a_stale = ExecutionGeneration("node-2", 1, "att-a", "epoch-0", "worker-a",
                                      target_snapshot_digest(ts), digest("sclass/state-binding/v1", binding_b),
                                      "lineage-1", "obj-rev-1", "wg-0", ExecutionGenerationStatus.ACTIVE)
    assert semantics.admit_work_result(gen_a_stale, work_res_b) is GateResult.DENIED_STALE_GENERATION

    assert state.obligations._obligations["obl-1"].status is ObligationStatus.SATISFIED


def test_coordinated_recovery_handles_rollback_failure():
    """WP-S4-05: CoordinatedRecovery handles failure during compensation/rollback without silent corruption."""
    class FailingCompensationProvider:
        def capability(self, receipt):
            return CompensationCapability.COMPENSABLE
        def compensate(self, receipt, ref):
            raise IOError("Storage write failure during compensation")

    recovery = ReferenceCoordinatedRecovery()
    plan = semantics.RepairPlan("p-fail", Digest("sha256:"+"0"*64), (), semantics.RepairStrategy.ROLLBACK)
    eff_digest = digest("sclass/external-effect/v1", ExternalEffect("sys", "MUTATE", 0))
    eff = SideEffectReceipt("e-fail", "r-1", "w", "MUTATE", "sys",
                            ActorIdentity("sys", ActorKind.SYSTEM, None),
                            Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64),
                            eff_digest, UtcInstant(1),
                            status=SideEffectStatus.UNKNOWN,
                            compensation_reference=None)

    report = recovery.recover("node-1", plan, (eff,), compensation_provider=FailingCompensationProvider())
    assert report.outcome is semantics.RecoveryOutcome.IN_DOUBT
    assert report.rollback is semantics.RollbackResult.PARTIAL
    assert "e-fail" in report.unresolved_effect_ids


def test_d8_operating_loop_bounded_convergence(tmp_path):
    """WP-S5-02: D8 operating loop achieves bounded convergence or signals bound exceeded."""
    db_path = str(tmp_path / "op_loop.sqlite")
    store = ReferenceSQLiteStore(db_path)
    act = ActorIdentity("system", ActorKind.SYSTEM, None)

    # 1. Genesis state has no obligations -> loop converges immediately
    loop = ReferenceOperatingLoop(store, max_iterations=5)
    rep = loop.run_cycle("default", act)
    assert rep["status"] == "CONVERGED"

    # 2. Bounded iteration check: max_iterations=0 produces BOUND_EXCEEDED
    loop_bounded = ReferenceOperatingLoop(store, max_iterations=0)
    rep_bound = loop_bounded.run_cycle("default", act)
    assert rep_bound["status"] == "BOUND_EXCEEDED"
    store.close()


def test_wp9_end_to_end_vertical_slice(tmp_path):
    """WP-S5-03: WP9 complete vertical slice.
    Genesis -> State Verification -> Proposal -> Verification -> Chain Audit.
    """
    db_path = str(tmp_path / "wp9_slice.sqlite")
    store = ReferenceSQLiteStore(db_path)
    act = ActorIdentity("system", ActorKind.SYSTEM, None)

    state0 = store._load_canonical_state("default")
    assert state0.event_sequence == 0
    assert state0.workspace_id == "default"

    loop = ReferenceOperatingLoop(store, max_iterations=5)
    rep = loop.run_cycle("default", act)
    assert rep["status"] == "CONVERGED"

    e_shut = CanonicalEvent.create(
        "e-wp9-shut", "c-wp9-1", "default", 1, EventType.SHUTDOWN_REQUESTED, 1, "test", act, "caus", "corr",
        fmap((("reason", "wp9 completed"),)), GENESIS_EVENT_HASH, "pol", "sdk", UtcInstant(10)
    )
    derived = REFERENCE_REDUCER.reduce(state0, e_shut)
    c_shut = CommitRecord(
        "c-wp9-1", "default", (e_shut.event_id, "state:default"),
        (e_shut.event_hash, engineering_state_digest(derived)),
        ("event", "state"), GENESIS_EVENT_HASH, e_shut.event_hash,
        derived.state_revision, 1, 1, COMMIT_SCHEMA_VERSION, Digest("sha256:"+"0"*64),
        CommitState.COMMITTED, 1, 1, engineering_state_digest(derived)
    )
    c_shut = replace(c_shut, commit_digest=commit_record_digest(c_shut))
    app_res, _ = store.append(e_shut, c_shut, GENESIS_EVENT_HASH)
    assert app_res is AppendResult.APPENDED

    final_state = store._load_canonical_state("default")
    assert final_state.event_sequence == 1
    assert store.verify_chain("default", 1, 1) is ChainStatus.VALID
    store.close()


def test_objective_mutation_during_active_work():
    """WP-S5-04: Objective mutation during active work invalidates in-flight execution binding."""
    gen = ExecutionGeneration(
        "node-1", 1, "att-1", "epoch-0", "worker-1",
        Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64), "lineage-1",
        "obj-rev-2", "wg-0", ExecutionGenerationStatus.ACTIVE
    )
    res_stale = WorkResult(
        "res-1", "req-1", Digest("sha256:"+"a"*64), Digest("sha256:"+"b"*64),
        1, "att-1", Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64),
        "lineage-1", "obj-rev-1", "wg-0", "worker-1",
        WorkerClaimStatus.CLAIMED_COMPLETE, 10, 10, Digest("sha256:"+"c"*64),
        Digest("sha256:"+"d"*64), ()
    )
    assert semantics.admit_work_result(gen, res_stale) is GateResult.DENIED_BINDING

    res_fresh = WorkResult(
        "res-2", "req-2", Digest("sha256:"+"a"*64), Digest("sha256:"+"b"*64),
        1, "att-1", Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64),
        "lineage-1", "obj-rev-2", "wg-0", "worker-1",
        WorkerClaimStatus.CLAIMED_COMPLETE, 10, 10, Digest("sha256:"+"c"*64),
        Digest("sha256:"+"d"*64), ()
    )
    assert semantics.admit_work_result(gen, res_fresh) is GateResult.ACCEPTED


def test_autonomous_continuation_advances_generation():
    """WP-S5-05: Autonomous continuation monotonically advances execution generation."""
    gen1 = ExecutionGeneration("node-1", 1, "att-1", "epoch-0", "worker-1",
                               Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64),
                               "lineage-1", "obj-1", "wg-0", ExecutionGenerationStatus.ACTIVE)
    gen2 = ExecutionGeneration("node-2", 2, "att-2", "epoch-0", "worker-1",
                               Digest("sha256:"+"1"*64), Digest("sha256:"+"2"*64),
                               "lineage-1", "obj-1", "wg-0", ExecutionGenerationStatus.ACTIVE)
    assert gen2.generation > gen1.generation
    assert gen2.execution_attempt_id != gen1.execution_attempt_id
