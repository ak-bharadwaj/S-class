import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))

import sclass_semantics_v6_0_1 as S
from sclass_runtime_v6_0_1 import (
    ActorIdentity,
    ActorKind,
    DeterministicRecoveryEngine,
    Digest,
    RecoveryDecision,
    SClassControlPlane,
    SideEffectReceipt,
    SideEffectStatus,
    SQLiteEventStore,
    UtcInstant,
    genesis_engineering_state,
)


@pytest.mark.parametrize("stage,category", [
    ("K1_BEFORE_DURABLE_INTENT", "pre_commit"),
    ("K2_AFTER_COMMIT_RECORD", "pre_commit"),
    ("K3_AFTER_EVENT_ROWS", "pre_commit"),
    ("K4_AFTER_PROJECTION", "pre_commit"),
    ("K5_BEFORE_COMMIT", "pre_commit"),
    ("K6_AFTER_COMMIT", "post_commit"),
    ("K7_DURING_CHECKPOINT_WRITE", "checkpoint"),
    ("K8_DURING_VERIFICATION", "evidence"),
    ("K9_AFTER_RECEIPT_SIGNED", "assessment"),
    ("K10_DURING_RECONCILIATION", "reconciliation"),
    ("K11_DURING_HANDOFF", "handoff"),
    ("K12_DURING_GENERATION_ADVANCE", "generation"),
])
def test_s4_exit_crash_matrix_atomicity(tmp_path, stage, category):
    """S4 Hard Exit: Process termination at all K1-K12 points leaves only an atomic canonical prefix."""
    db = tmp_path / f"s4_{stage}.sqlite"
    child = tmp_path / f"child_{stage}.py"
    runtime_path = str(Path(__file__).parents[2] / "20-RUNTIME")
    conformance_path = str(Path(__file__).parents[2] / "10-CONFORMANCE")

    child.write_text(f"""import os, sys
sys.path.insert(0, {runtime_path!r})
sys.path.insert(0, {conformance_path!r})
from sclass_runtime_v6_0_1 import SQLiteEventStore, SClassControlPlane
from sclass_semantics_v6_0_1 import (
    Command, EventType, ActorIdentity, ActorKind, FrozenMap,
    GENESIS_EVENT_HASH, CanonicalEvent, CommitRecord, CommitState,
    COMMIT_SCHEMA_VERSION, Digest, UtcInstant, CheckpointRef,
    REFERENCE_REDUCER, genesis_engineering_state, commit_record_digest,
    engineering_state_digest, replace
)

def kill(s):
    if s == {stage!r}:
        os._exit(137)

store = SQLiteEventStore({str(db)!r}, fault_injector=kill)
cp = SClassControlPlane(store)
act = ActorIdentity("system", ActorKind.SYSTEM, None)

if {category!r} == "checkpoint":
    e = CanonicalEvent.create("e1", "crash", "default", 1, EventType.SHUTDOWN_REQUESTED, 1, "system", act, "caus", "corr", FrozenMap.from_items((("reason", "test"),)), GENESIS_EVENT_HASH, "pol", "sdk", UtcInstant(1))
    st = genesis_engineering_state("default")
    derived = REFERENCE_REDUCER.reduce(st, e)
    c = CommitRecord("crash", "default", (e.event_id, "state:default"), (e.event_hash, engineering_state_digest(derived)), ("event", "state"), GENESIS_EVENT_HASH, e.event_hash, derived.state_revision, 1, 1, COMMIT_SCHEMA_VERSION, Digest("sha256:"+"0"*64), CommitState.COMMITTED, 1, 1, engineering_state_digest(derived))
    c = replace(c, commit_digest=commit_record_digest(c))
    store.append(e, c, GENESIS_EVENT_HASH)
    ref = CheckpointRef("cp1", derived.event_sequence, derived.state_digest, "crash")
    store.checkpoint(ref, derived)
else:
    cmd = Command("crash-cmd", "default", act,
                  EventType.SHUTDOWN_REQUESTED, FrozenMap.from_items((("reason", {stage!r}),)),
                  GENESIS_EVENT_HASH, None, "shutdown")
    cp._submit_internal(cmd)
""")

    proc = subprocess.run([sys.executable, str(child)], capture_output=True, check=False)
    assert proc.returncode == 137

    store = SQLiteEventStore(str(db))
    head = store.head("default")

    if stage == "K6_AFTER_COMMIT":
        rows = store._db.execute("SELECT count(*) FROM runtime_commands WHERE workspace_id='default' AND command_id='crash-cmd'").fetchone()[0]
        assert head.sequence == 1 and rows == 1
        assert store.verify_chain("default", 1, 1).value == "VALID"
    elif stage == "K7_DURING_CHECKPOINT_WRITE":
        # Event 1 committed before checkpoint crash
        assert head.sequence == 1
        with pytest.raises(KeyError):
            store.restore("cp1")
        assert store.verify_chain("default", 1, 1).value == "VALID"
    else:
        # Pre-commit crashes leave strictly 0 uncommitted state
        assert head.sequence == 0
        assert head.hash == S.GENESIS_EVENT_HASH
    store.close()


def test_s4_exit_handoff_compiler_leaks_zero_authority():
    """S4 Hard Exit: HandoffPackage contains zero leases, nonces, tokens, or credentials."""
    st = genesis_engineering_state("ws-handoff")
    ob = S.Obligation(
        "ob-1", "obj-1", 1, "desc", S.ObligationKind.FUNCTIONAL,
        S.RiskTier.LOW, S.ObligationStatus.PENDING, frozenset(), "c-1", None, "p-1",
    )
    og = S.ObligationGraph(S.SemanticGraph((), ()), S.FrozenMap.from_items((("ob-1", ob),)))
    state = S.replace(st, obligations=og)

    compiler = S.CanonicalHandoffCompiler()
    pkg = compiler.compile(state, obligation_id="ob-1")

    assert pkg.workspace_id == "ws-handoff"
    assert pkg.current_obligation_id == "ob-1"
    assert pkg.package_digest is not None

    # Verify that HandoffPackage dataclass schema carries NO secret/session authority fields
    field_names = set(pkg.__dataclass_fields__.keys())
    prohibited = {"nonce", "fencing_token", "lease", "credential", "session_state", "private_key"}
    for p in prohibited:
        assert p not in field_names, f"Prohibited field {p} found in HandoffPackage"


def test_s4_exit_deterministic_recovery_reconciliation(tmp_path):
    """S4 Hard Exit: DeterministicRecoveryEngine reconciles external effects and records compensating actions."""
    db_path = str(tmp_path / "rec.sqlite")
    store = SQLiteEventStore(db_path)
    cp = SClassControlPlane(store)
    engine = DeterministicRecoveryEngine(store._db, cp)

    dummy_hash = Digest("sha256:" + "0" * 64)
    eff_digest = S.digest("sclass/external-effect/v1", S.ExternalEffect("local_fs", "fs_write", 1))
    actor = ActorIdentity("worker-1", ActorKind.WORKER, S.ExecutionIdentity("/bin/true", "/bin/true", dummy_hash, "", "", dummy_hash, dummy_hash, 1, ()))

    receipt = SideEffectReceipt(
        effect_id="eff-1",
        request_id="req-1",
        workspace_id="ws-rec",
        effect_kind="fs_write",
        target_system="local_fs",
        actor=actor,
        before_digest=dummy_hash,
        after_digest=dummy_hash,
        effect_digest=eff_digest,
        observed_at=UtcInstant(10),
        status=SideEffectStatus.UNKNOWN,
        compensation_reference=None,
        units=1,
    )

    rec_record = engine.recover("ws-rec", "node-1", "worker_crash_timeout", (receipt,))
    assert rec_record.node_id == "node-1"
    assert rec_record.decision == RecoveryDecision.IN_DOUBT
    assert rec_record.unresolved_effect_ids == ("eff-1",)

    # Recovery emits canonical IN_DOUBT_DECLARED event to preserve L1 and durability
    events = store.read("ws-rec", 1, 10)
    assert len(events) == 1
    assert events[0].event_type is S.EventType.IN_DOUBT_DECLARED
    assert events[0].payload["in_doubt"].unresolved_effect_ids == ("eff-1",)
    store.close()
