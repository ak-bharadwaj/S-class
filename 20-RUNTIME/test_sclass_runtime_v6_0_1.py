from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1]/"10-CONFORMANCE"))

import pytest
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sclass_runtime_v6_0_1 import *
import sclass_semantics_v6_0_1 as S

def fmap(items=()): return FrozenMap.from_items(items)


def actor(kind=ActorKind.HUMAN, aid="human"):
    return ActorIdentity(aid,kind,None)


def command(workspace="w", cid="cmd-1", reason="clean shutdown", head=None, sig=None, aggregate="shutdown"):
    head=head or GENESIS_EVENT_HASH
    return Command(cid,workspace,actor(),EventType.SHUTDOWN_REQUESTED,fmap((("reason",reason),)),head,sig,aggregate)


def internal_command(workspace="w", cid="cmd-1", reason="clean shutdown", head=None, aggregate="shutdown"):
    head=head or GENESIS_EVENT_HASH
    return Command(cid,workspace,ActorIdentity("system",ActorKind.SYSTEM,None),EventType.SHUTDOWN_REQUESTED,fmap((("reason",reason),)),head,None,aggregate)


def signed_command(cp, cmd):
    private=Ed25519PrivateKey.generate()
    raw=private.public_key().public_bytes_raw()
    cp.keys.add_root("root")
    cp.keys.register("k1","root",raw,0,2**63-1)
    unsigned=replace(cmd, actor_signature=None)
    sig=private.sign(command_signature_message(unsigned))
    return replace(unsigned, actor_signature=SignatureBlock("ed25519","k1","root","c1",sig))


def test_command_aggregate_identity_is_canonical(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"s.sqlite")); cp=SClassControlPlane(store)
    cmd=internal_command(aggregate="shutdown-canonical")
    result=cp._submit_internal(cmd)
    assert result.disposition is RuntimeDisposition.APPLIED
    event=store.read("w",1,1)[0]
    assert event.aggregate_id == "shutdown-canonical"
    assert event.aggregate_id != cmd.command_id
    store.close()


def test_command_commit_idempotency_and_no_caller_projection(tmp_path):
    p=tmp_path/"s.sqlite"
    store=SQLiteEventStore(str(p)); cp=SClassControlPlane(store)
    c=internal_command()
    r1=cp._submit_internal(c, )
    assert r1.disposition is RuntimeDisposition.APPLIED
    assert r1.new_head.sequence==1
    # The second delivery cannot mutate canonical history.
    r2=cp._submit_internal(c, )
    assert r2.disposition is RuntimeDisposition.IDEMPOTENT_REPLAY
    assert r2.new_head==r1.new_head
    assert len(store.read("w",1,99))==1
    bad=internal_command(reason="different payload")
    with pytest.raises(ValueError): cp._submit_internal(bad, )
    store.close()


def test_public_privileged_ingress_is_rejected(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"s.sqlite")); cp=SClassControlPlane(store)
    forged=Command("forged-system","w",ActorIdentity("attacker",ActorKind.SYSTEM,None),EventType.SHUTDOWN_REQUESTED,fmap((("reason","x"),)),GENESIS_EVENT_HASH,None,"shutdown")
    result=cp.submit(forged)
    assert result.disposition is RuntimeDisposition.DENIED
    assert store.head("w").sequence == 0
    with pytest.raises(ValueError): cp._submit_internal(replace(forged, actor=actor()))
    store.close()


def test_command_signature_is_content_bound(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"s.sqlite")); cp=SClassControlPlane(store)
    good=signed_command(cp,command())
    r=cp.submit(good)
    assert r.disposition is RuntimeDisposition.APPLIED
    bad=replace(good,payload=fmap((("reason","tampered"),)))
    # Signature preimage changes, so authorization is denied before mutation.
    with pytest.raises(ValueError): cp.submit(bad)
    assert store.head("w").sequence==1
    store.close()


def test_nonce_replay_and_binding_are_atomic(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"s.sqlite")); cp=SClassControlPlane(store)
    reqd=Digest("sha256:"+"1"*64)
    exp=UtcInstant(9_000_000_000_000_000_000)
    cp.issue_nonce("w","worker",reqd,exp,"N")
    a=cp.nonces.consume_and_bind("w:worker","N",reqd,"auth","exec",UtcInstant(2))
    assert a is NonceConsumptionResult.SUCCESS
    b=cp.nonces.consume_and_bind("w:worker","N",reqd,"auth","exec2",UtcInstant(3))
    assert b is NonceConsumptionResult.ALREADY_CONSUMED
    assert cp.nonces.consume_and_bind("w:worker","M",reqd,"auth","exec",UtcInstant(2)) is NonceConsumptionResult.BINDING_MISMATCH
    store.close()


def test_budget_allocator_is_cumulative_and_versioned(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"s.sqlite")); cp=SClassControlPlane(store)
    lim=ResourceBudget(4,4,0,100,0,4,4,0,0,100,10)
    cp.budgets._set_workspace_limit_for_test("w",lim)
    amt=ResourceBudget(3,1,0,20,0,1,1,0,0,10,6)
    r=cp.budgets._reserve_for_test("w","req-1","L1",amt,UtcInstant(9_000_000_000_000_000_000),reservation_id="R1")
    assert r.lifecycle_state is BudgetReservationState.RESERVED
    with pytest.raises(ValueError):
        cp.budgets._reserve_for_test("w","req-2","L1",ResourceBudget(2,1,0,20,0,1,1,0,0,1,5),UtcInstant(9_000_000_000_000_000_000),reservation_id="R2")
    cp.budgets.settle("w","R1",ResourceBudget(2,1,0,10,0,1,1,0,0,4,4))
    with pytest.raises(ValueError): cp.budgets.settle("w","R1",ResourceBudget(1,1,0,1,0,1,1,0,0,1,1))
    store.close()


def test_atomic_nonce_plus_budget_rolls_back_as_one_unit(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"s.sqlite")); cp=SClassControlPlane(store)
    cp.budgets._set_workspace_limit_for_test("w",ResourceBudget(2,2,0,20,0,2,2,0,0,10,10))
    reqd=Digest("sha256:"+"2"*64)
    cp.issue_nonce("w","worker",reqd,UtcInstant(9_000_000_000_000_000_000),"N")
    # Bad nonce binding must roll back the budget reservation as well.
    with pytest.raises(ValueError):
        cp.atomic_reserve_and_consume_nonce("w","worker","N",Digest("sha256:"+"3"*64),"auth","exec","L",
                                             ResourceBudget(1,1,0,10,0,1,1,0,0,1,1),UtcInstant(9_000_000_000_000_000_000))
    row=store._db.execute("SELECT count(*) FROM runtime_reservations").fetchone()[0]
    nonce=store._db.execute("SELECT status FROM runtime_nonces WHERE namespace='w:worker' AND nonce='N'").fetchone()[0]
    assert row==0 and nonce=="ISSUED"
    store.close()


def test_ed25519_trust_registry_rotation_and_revocation(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"s.sqlite")); cp=SClassControlPlane(store)
    private=Ed25519PrivateKey.generate(); pub=private.public_key().public_bytes_raw()
    cp.keys.add_root("root")
    cp.keys.register("key","root",pub,0,10**18)
    msg=b"canonical control-plane bytes"
    block=SignatureBlock("ed25519","key","root","c1",private.sign(msg))
    assert cp.keys.verify_current(block,msg,UtcInstant(1)) is SignatureVerificationResult.VALID
    cp.keys.rotate_out("key")
    assert cp.keys.status("key","root",UtcInstant(1)) is KeyStatus.ROTATED_OUT
    assert cp.keys.verify_current(block,msg,UtcInstant(1)) is not SignatureVerificationResult.VALID
    assert cp.keys.verify_historical(block,msg,UtcInstant(1)) is SignatureVerificationResult.VALID
    cp.keys.revoke("key")
    assert cp.keys.verify_current(block,msg,UtcInstant(1)) is SignatureVerificationResult.REVOKED
    assert cp.keys.verify_historical(block,msg,UtcInstant(1)) is SignatureVerificationResult.VALID
    store.close()


def test_fail_closed_os_boundary_without_sandbox(tmp_path):
    b=LinuxExecutionBoundary(str(tmp_path),require_sandbox=True)
    with pytest.raises(PermissionError): b.run(("python","-c","print(1)"))
    assert not hasattr(b, "run_for_test")
    assert not hasattr(LinuxExecutionBoundary, "run_for_test")


def test_c1_persistence_is_not_pickle(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"s.sqlite")); cp=SClassControlPlane(store)
    assert cp._submit_internal(internal_command(), ).disposition is RuntimeDisposition.APPLIED
    blob=store._db.execute("SELECT event_blob FROM canonical_events LIMIT 1").fetchone()[0]
    assert bytes(blob).startswith(b"{\"$type\":\"CanonicalEvent\"")
    store.close()

@pytest.mark.parametrize("stage", CrashHarness.STAGES)
def test_real_process_kill_recovery_matrix(tmp_path, stage):
    """A real process death must leave only an atomic canonical prefix.

    K1-K5 die before commit: no event or command ledger record may be visible.
    K6 dies immediately after COMMIT: the event and command record must both survive.
    """
    import subprocess, textwrap, sys
    db=tmp_path/f"{stage}.sqlite"
    child=tmp_path/"crash_child.py"
    child.write_text(textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(Path(__file__).parents[1]).__repr__()})
        sys.path.insert(0, {str(Path(__file__).parents[1]/'10-CONFORMANCE').__repr__()})
        from 20-RUNTIME.sclass_runtime_v6_0_1 import SQLiteEventStore, SClassControlPlane, Command, EventType, ActorIdentity, ActorKind, FrozenMap, GENESIS_EVENT_HASH
    """).replace("from 20-RUNTIME.sclass_runtime_v6_0_1", "from sclass_runtime_v6_0_1"))
    # Make imports explicit and keep the crash child intentionally tiny.
    child.write_text(f'''import os,sys\nsys.path.insert(0,{str(Path(__file__).parents[1]/"20-RUNTIME").__repr__()})\nsys.path.insert(0,{str(Path(__file__).parents[1]/"10-CONFORMANCE").__repr__()})\nfrom sclass_runtime_v6_0_1 import SQLiteEventStore,SClassControlPlane\nfrom sclass_semantics_v6_0_1 import Command,EventType,ActorIdentity,ActorKind,FrozenMap,GENESIS_EVENT_HASH\ndef kill(s):\n    if s=={stage!r}: os._exit(137)\nstore=SQLiteEventStore({str(db).__repr__()},fault_injector=kill)\ncp=SClassControlPlane(store)\ncmd=Command("crash-cmd","default",ActorIdentity("system",ActorKind.SYSTEM,None),EventType.SHUTDOWN_REQUESTED,FrozenMap.from_items((("reason","crash"),)),GENESIS_EVENT_HASH,None,"shutdown")\ncp._submit_internal(cmd, )\n''')
    proc=subprocess.run([sys.executable,str(child)],capture_output=True)
    assert proc.returncode==137
    store=SQLiteEventStore(str(db)); cp=SClassControlPlane(store)
    head=store.head("default")
    rows=store._db.execute("SELECT count(*) FROM runtime_commands WHERE workspace_id='default' AND command_id='crash-cmd'").fetchone()[0]
    if stage=="K6_AFTER_COMMIT":
        assert head.sequence==1 and rows==1
    else:
        assert head.sequence==0 and rows==0
    store.verify_chain("default",1,1) if head.sequence else None
    store.close()


def test_c1_rejects_unknown_envelope_keys():
    import json
    with pytest.raises(ValueError): canonical_c1_unpack(json.dumps({"$bytes":"YQ==","junk":1}).encode())
    with pytest.raises(ValueError): canonical_c1_unpack(json.dumps({"$enum":"CommitState","$name":"COMMITTED","junk":1}).encode())


def test_rotated_out_key_cannot_verify_current_authority(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"s.sqlite")); cp=SClassControlPlane(store)
    private=Ed25519PrivateKey.generate(); pub=private.public_key().public_bytes_raw()
    cp.keys.add_root("root"); cp.keys.register("key","root",pub,0,10**18)
    msg=b"canonical control-plane bytes"
    block=SignatureBlock("ed25519","key","root","c1",private.sign(msg))
    cp.keys.rotate_out("key")
    assert cp.keys.verify_current(block,msg,UtcInstant(1)) is not SignatureVerificationResult.VALID
    assert cp.keys.verify_historical(block,msg,UtcInstant(1)) is SignatureVerificationResult.VALID
    store.close()


def test_direct_break_glass_consumption_cannot_bypass_canonical_history(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"bg.sqlite")); cp=SClassControlPlane(store)
    authority=BreakGlassAuthority("bg-1","key",(),"w","pol",1,UtcInstant(100),True,
                                   Digest("sha256:"+"1"*64),
                                   SignatureBlock("ed25519","key","root","c1",b"sig"))
    cp.break_glass.register(authority)
    with pytest.raises(PermissionError): cp.break_glass.consume(authority,"requester","reason",UtcInstant(1))
    store.close()


def test_external_effect_reconciliation_is_canonical_and_restart_durable(tmp_path):
    import sclass_runtime_v6_0_1 as R
    db=tmp_path/"effect.sqlite"
    store=SQLiteEventStore(str(db)); cp=SClassControlPlane(store)
    effect=ExternalEffect("provider-A","MUTATE",1)
    effect_id=R._stable_id("effect", ("w","req-1",effect.target_system,effect.effect_kind,effect.units))
    receipt=SideEffectReceipt(effect_id,"req-1","w",effect.effect_kind,effect.target_system,
                              ActorIdentity("system",ActorKind.SYSTEM,None),
                              Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),
                              digest("sclass/external-effect/v1",effect),UtcInstant(1),
                              SideEffectStatus.OBSERVED,"provider-ref",effect.units)
    cp.reconcile_external_effect(receipt,now=UtcInstant(2))
    state=store._load_canonical_state("w")
    assert state.external_effect_receipts[effect_id] == receipt
    store.close()
    store2=SQLiteEventStore(str(db)); cp2=SClassControlPlane(store2)
    assert cp2.effects.reconcile(effect,"w","req-1") is SideEffectStatus.OBSERVED
    assert store2._load_canonical_state("w").external_effect_receipts[effect_id] == receipt
    store2.close()


def test_recovery_is_append_only_and_canonical(tmp_path):
    db=tmp_path/"recovery.sqlite"
    store=SQLiteEventStore(str(db)); cp=SClassControlPlane(store)
    effect=SideEffectReceipt("effect-1","req-1","w","MUTATE","provider-A",
                              ActorIdentity("system",ActorKind.SYSTEM,None),
                              Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),
                              digest("sclass/external-effect/v1",ExternalEffect("provider-A","MUTATE",1)),
                              UtcInstant(1),SideEffectStatus.UNKNOWN,None,1)
    engine=DeterministicRecoveryEngine(store._db,cp)
    rec=engine.recover("w","node-1","worker crashed",[effect])
    assert rec.decision is RecoveryDecision.IN_DOUBT
    engine.recover("w","node-1","worker crashed",[effect])
    rows=store._db.execute("SELECT attempt_no FROM runtime_recovery_cases WHERE case_id=? ORDER BY attempt_no",(rec.case_id,)).fetchall()
    assert [r[0] for r in rows] == [1,2]
    events=store.read("w",1,99)
    assert [e.event_type for e in events] == [EventType.IN_DOUBT_DECLARED, EventType.IN_DOUBT_DECLARED]
    assert events[0].payload["in_doubt"].unresolved_effect_ids == ("effect-1",)
    store.close()


def test_raw_os_execution_cannot_bypass_execution_gate(tmp_path):
    b=LinuxExecutionBoundary(str(tmp_path))
    with pytest.raises(PermissionError):
        b.run(("python","-c","print(1)"))
    with pytest.raises(PermissionError):
        b._run_from_gate(object(),("python","-c","print(1)"))


def test_execution_gate_budget_reservation_is_concrete_and_live(tmp_path):
    import sclass_runtime_v6_0_1 as R
    b=LinuxExecutionBoundary(str(tmp_path),require_sandbox=True)
    class Budgets:
        def _read(self,w,r):
            return ("req", canonical_c1_pack(amount), "L", None, "RESERVED", 1, 10**18, canonical_c1_pack(ResourceBudget(0,0,0,0,0,0,0,0,0,0,0)))
    class Store: pass
    class CP: pass
    cp=CP(); cp.budgets=Budgets()
    gate=ExecutionGate(b,cp)
    now=UtcInstant(10)
    amount=ResourceBudget(1,1,0,100,0,1,1,0,0,10,1)
    reservation=BudgetReservation("R", "w", "req", BudgetLevel.WORK_NODE, None, "L", amount, UtcInstant(10**6), BudgetReservationState.RESERVED, amount, ResourceBudget(0,0,0,0,0,0,0,0,0,0,0), ResourceBudget(0,0,0,0,0,0,0,0,0,0,0), ResourceBudget(0,0,0,0,0,0,0,0,0,0,0), 1)
    state=type('State',(),{'workspace_id':'w','budget_reservations':{'R':reservation}})()
    effect=RequestedEffect((),(),(),fmap(),(),(),amount)
    req=type('Req',(),{'budget_reservation_id':'R','request_id':'req','governing_budget_lineage_id':'L','requested_effect':effect})()
    got=gate._verify_budget_reservation(req,state,now)
    assert got is reservation
    expired=replace(reservation,expires_at=UtcInstant(5))
    state.budget_reservations={'R':expired}
    with pytest.raises(PermissionError): gate._verify_budget_reservation(req,state,now)


def test_execution_gate_refuses_raw_boundary_and_requires_valid_policy(tmp_path):
    b=LinuxExecutionBoundary(str(tmp_path),require_sandbox=True)
    with pytest.raises(PermissionError): b.run(("python","-c","print(1)"))
    empty_scope=EffectScope((),(),(),fmap(),".",(),(),ResourceBudget(0,0,0,0,0,0,0,0,0,0,0))
    decision=AuthorizationDecision("d","p",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),AuthorizationState.ALLOW,Authority.USER,"u",(),"r",UtcInstant(1),UtcInstant(100),"obj", "worker",Digest("sha256:"+"3"*64),"p",empty_scope,"s")
    state=type('State',(),{'workspace_snapshot_id':'s','policy_version':'p','objective':None,'active_policy':None})()
    assert S.validate_authorization_decision(state,decision,UtcInstant(2)) is False


def test_execution_gate_execute_is_the_full_lifecycle_entrypoint(monkeypatch, tmp_path):
    b=LinuxExecutionBoundary(str(tmp_path),require_sandbox=True)
    gate=ExecutionGate(b,object())
    sentinel=object()
    monkeypatch.setattr(gate,"execute_lifecycle",lambda *a,**k: sentinel)
    assert gate.execute(object(),("python","-c","print(1)")) is sentinel


def test_execution_boundary_checks_authorized_executable_digest(tmp_path):
    from tests.helpers.test_boundary import TestOnlyUnsandboxedBoundary
    b=TestOnlyUnsandboxedBoundary(tmp_path)
    exe=b._executable_path("python")
    good=b._file_digest(exe)
    bad=Digest("sha256:"+"f"*64)
    with pytest.raises(PermissionError):
        b._run_from_gate(b._gate_capability,("python","-c","print(1)"),expected_executable_digest=bad)
    assert good != bad


def test_quiescence_attestation_is_bound_to_exact_process_identity(tmp_path):
    import sclass_runtime_v6_0_1 as R
    from tests.helpers.test_boundary import create_test_quiescence_attestor
    store=SQLiteEventStore(str(tmp_path/"q.sqlite")); cp=SClassControlPlane(store)
    cp.boundary_attestor=create_test_quiescence_attestor(cp.keys)
    request=type("Req",(),{})()
    lease=type("Lease",(),{})()
    lease.lease_id="lease-1"; lease.fencing_token=1; lease.worker_identity="worker-1"
    lease.executable_identity=ExecutionIdentity("/bin/true","/bin/true",Digest("sha256:"+"1"*64),"","",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),1,())
    request.execution_lease=lease; request.execution_generation=1; request.execution_attempt_id="attempt-1"
    result=BoundaryRunResult(BoundaryIsolation.BUBBLEWRAP,0,b"",b"",False,1,lease.executable_identity.digest,Digest("sha256:"+"2"*64),12345,987654321)
    proof=cp.boundary_attestor.attest(request,result)
    assert proof.process_id==12345 and proof.process_start_time_ns==987654321
    tampered=replace(proof,process_start_time_ns=987654322)
    assert not R._verify_quiescence_attestation(cp.keys,tampered,UtcInstant(time.time_ns()))
    store.close()


def test_authority_envelope_digest_is_canonical():
    envelope=AuthorityEnvelope(
        "env-1","user","w",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),
        Digest("sha256:"+"3"*64),Digest("sha256:"+"4"*64),"epoch-1",UtcInstant(1),UtcInstant(100))
    d1=authority_envelope_digest(envelope)
    d2=authority_envelope_digest(replace(envelope, target_digest=Digest("sha256:"+"5"*64)))
    assert d1 != d2


def test_execution_admission_is_not_public():
    store=SQLiteEventStore("file::memory:?cache=shared"); cp=SClassControlPlane(store)
    assert not hasattr(cp,"execution")
    assert hasattr(cp,"_execution_admission")
    with pytest.raises(PermissionError):
        cp._execution_admission._admit(None,authorization_lease=None,execution_lease_template=None,budget_amount=ResourceBudget(0,0,0,0,0,0,0,0,0,0,0),audience="x")
    store.close()


def test_budget_reservation_capacity_uses_canonical_state_not_projection(tmp_path):
    db=sqlite3.connect(str(tmp_path/"b.sqlite"))
    alloc=SQLiteBudgetAllocator(db)
    limit=ResourceBudget(4,4,0,4,0,4,4,0,0,4,4)
    db.execute("BEGIN")
    # Corrupt/overstate the runtime projection; canonical reservations must be authoritative when supplied.
    db.execute("INSERT INTO runtime_budgets VALUES(?,?,?)",("w",canonical_c1_pack(limit),1))
    db.execute("COMMIT")
    existing=BudgetReservation("r1","w","req1",BudgetLevel.ATTEMPT,None,"L",ResourceBudget(1,1,0,1,0,1,1,0,0,1,1),UtcInstant(10**18))
    new=alloc.reserve_in_transaction("w","req2","L",ResourceBudget(1,1,0,1,0,1,1,0,0,1,1),UtcInstant(time.time_ns()+10**12),canonical_limit=limit,canonical_reservations=FrozenMap.from_items(((existing.reservation_id,existing),)))
    assert new.lifecycle_state is BudgetReservationState.RESERVED
    db.execute("ROLLBACK")
    db.close()


def test_production_quiescence_authority_is_not_self_generated(tmp_path, monkeypatch):
    """F1 (c): Prove no public/classmethod constructor yields production-provisioned attestor without external trust root."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import _BOUNDARY_TEST_TOKEN

    store = SQLiteEventStore(str(tmp_path / "trust.sqlite"))
    cp = SClassControlPlane(store)

    # 1. Unprovisioned default authority check
    assert not getattr(cp.boundary_attestor, "is_provisioned", False)
    assert cp.boundary_attestor.is_production_provisioned() is False
    with pytest.raises(PermissionError):
        cp.boundary_attestor.attest(object(), object())

    # 2. LocalQuiescenceAttestor has NO for_test method in production kernel
    assert not hasattr(LocalQuiescenceAttestor, "for_test")

    # 3. Direct constructor without explicit provisioning token raises PermissionError
    priv = Ed25519PrivateKey.generate()
    with pytest.raises(PermissionError, match="explicit provisioning/test factory"):
        LocalQuiescenceAttestor(cp.keys, "root", "key", priv)

    # 4. Direct constructor with _BOUNDARY_TEST_TOKEN yields is_production_provisioned()==False
    test_att = LocalQuiescenceAttestor(cp.keys, "test-root", "test-key", priv, _provisioning_token=_BOUNDARY_TEST_TOKEN)
    assert test_att._test_only is True
    assert test_att.is_production_provisioned() is False

    # 5. from_environment classmethod is deleted from LocalQuiescenceAttestor (M2)
    assert not hasattr(LocalQuiescenceAttestor, "from_environment")

    # 6. Try EVERY public callable on LocalQuiescenceAttestor
    public_callables = [
        attr for attr in dir(LocalQuiescenceAttestor)
        if not attr.startswith("_") and callable(getattr(LocalQuiescenceAttestor, attr))
    ]
    for name in public_callables:
        member = getattr(LocalQuiescenceAttestor, name)
        if callable(member):
            try:
                res = member(cp.keys)
                if res is not None:
                    assert res.is_production_provisioned() is False
            except (TypeError, PermissionError, ValueError, AttributeError):
                pass

    store.close()


def test_openat2_class_resolution_rejects_symlink(tmp_path):
    import os
    if not hasattr(os, "O_PATH") or sys.platform == "win32":
        pytest.skip("Linux O_PATH unavailable on Windows")
    b=LinuxExecutionBoundary(str(tmp_path),require_sandbox=False)
    (tmp_path/"safe.txt").write_text("safe")
    fd=b._secure_workspace_fd("safe.txt")
    try:
        resolved=Path(os.readlink(f"/proc/self/fd/{fd}"))
        assert resolved == (tmp_path/"safe.txt").resolve()
    finally:
        os.close(fd)
    (tmp_path/"link.txt").symlink_to(tmp_path/"safe.txt")
    with pytest.raises(OSError):
        b._secure_workspace_fd("link.txt")


def test_process_tree_monitor_rejects_unauthorized_descendant(monkeypatch,tmp_path):
    if not Path("/proc").exists() or sys.platform == "win32":
        pytest.skip("Linux /proc process monitor unavailable on Windows")
    from tests.helpers.test_boundary import TestOnlyUnsandboxedBoundary
    b=TestOnlyUnsandboxedBoundary(str(tmp_path))
    monkeypatch.setattr(b, "_file_digest", lambda p: Digest("sha256:"+"0"*64) if "python" in str(p).lower() else Digest("sha256:"+"1"*64))
    good=b._file_digest(b._executable_path("python"))
    code="import subprocess,time; subprocess.Popen(['sh','-c','sleep 1']); time.sleep(.5)"
    with pytest.raises(PermissionError):
        b._run_from_gate(b._gate_capability,("python","-c",code),expected_executable_digest=good,timeout_ms=2_000)


def test_process_tree_monitor_records_authorized_same_binary_child(monkeypatch,tmp_path):
    if not Path("/proc").exists() or sys.platform == "win32":
        pytest.skip("Linux /proc process monitor unavailable on Windows")
    from tests.helpers.test_boundary import TestOnlyUnsandboxedBoundary
    b=TestOnlyUnsandboxedBoundary(str(tmp_path))
    monkeypatch.setattr(b, "_file_digest", lambda p: Digest("sha256:"+"0"*64))
    good=b._file_digest(b._executable_path("python"))
    code="import subprocess,sys; p=subprocess.Popen([sys.executable,'-c','print(1)']); p.wait()"
    result=b._run_from_gate(b._gate_capability,("python","-c",code),expected_executable_digest=good,timeout_ms=2_000)
    assert result.returncode==0
    assert result.process_lineage
    assert all(entry.executable_digest==good for entry in result.process_lineage)


def _make_test_authorized_work_request(
    d_digest=None,
    fencing_token: int = 1,
):
    import sclass_runtime_v6_0_1 as R
    zero_dig = R.Digest("sha256:" + "0" * 64)
    z_budget = R.ResourceBudget(0, 0, 0, 30000, 0, 0, 0, 0, 0, 0, 0)
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


def test_execute_lifecycle_exit_0_effect_mismatch_rejects(monkeypatch, tmp_path):
    import sclass_runtime_v6_0_1 as R
    from tests.helpers.test_boundary import TestOnlyUnsandboxedBoundary, create_test_quiescence_attestor
    from types import SimpleNamespace
    import os

    boundary = TestOnlyUnsandboxedBoundary(str(tmp_path))
    store = R.SQLiteEventStore(str(tmp_path / "test.sqlite"))
    control_plane = R.SClassControlPlane(store)
    control_plane.boundary_attestor = create_test_quiescence_attestor(control_plane.keys)

    gate = R.ExecutionGate(boundary, control_plane)

    state = SimpleNamespace()
    state.workspace_id = "ws-1"
    state.workspace_snapshot_id = "ws-snap-1"
    state.policy_version = "policy-v1"
    state.event_sequence = 1
    state.causal_frontier = SimpleNamespace(authorization_epoch="epoch-1")
    state.event_head_hash = "head-hash"

    d_digest = R.Digest("sha256:" + "d" * 64)
    v_delta = SimpleNamespace(delta_digest=d_digest)
    state.verified_deltas = {"d1": v_delta}
    rev = SimpleNamespace(revision_id="rev-1")
    state.objective = SimpleNamespace(revisions=[rev])
    state.work_graph = SimpleNamespace(revision_id="wg-1")

    req = _make_test_authorized_work_request(d_digest=d_digest)

    lease_record = R.LeaseRecord(req.execution_lease, R.LeaseState.ACTIVE)
    state.leases = {"lease-1": lease_record}

    res_mock = R.BudgetReservation(
        "res-1", "ws-1", "req-1", R.BudgetLevel.ATTEMPT, None, "budget-1",
        R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.UtcInstant(0), R.BudgetReservationState.RESERVED,
        R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), 1
    )
    state.budget_reservations = {"res-1": res_mock}

    gate._preflight = lambda *args, **kwargs: (state, SimpleNamespace(), [], R.UtcInstant(0))
    gate._admit_request = lambda *args, **kwargs: (req, lease_record, SimpleNamespace(), state)
    gate._verify_budget_reservation = lambda *args, **kwargs: res_mock
    control_plane.nonces.verify_consumed_binding = lambda *args, **kwargs: True
    control_plane.store._load_canonical_state = lambda *args, **kwargs: state

    run_result = R.BoundaryRunResult(
        R.BoundaryIsolation.DENY, 0, b"out", b"err", False, 10,
        R.Digest("sha256:" + "1" * 64), None, 123, 1000, 3, 3, ()
    )
    boundary._run_from_gate = lambda *args, **kwargs: run_result
    boundary._executable_path = lambda argv0: Path("/bin/echo")

    monkeypatch.setattr(R, "apply_delta_observation_matches", lambda d, o: R.DeltaMatchVerdict.MISMATCH)

    submitted_events = []

    def mock_submit_internal(cmd):
        submitted_events.append((cmd.event_type, cmd.payload))
        return SimpleNamespace(disposition=R.RuntimeDisposition.APPLIED)

    monkeypatch.setattr(control_plane, "_submit_internal", mock_submit_internal)

    with monkeypatch.context() as m:
        m.setattr(R, "validate_execution_lease", lambda s, l: True)
        m.setattr(R, "canonical_current_state_binding", lambda s, g, b: SimpleNamespace())
        m.setattr(R, "state_binding_digest", lambda b: R.Digest("sha256:" + "2" * 64))
        m.setattr(R, "digest", lambda domain, obj: R.Digest("sha256:" + "5" * 64))
        def _mock_dead_proc(pid, sig):
            raise ProcessLookupError("No such process")
        if hasattr(os, "killpg"):
            m.setattr(os, "killpg", _mock_dead_proc)
        m.setattr(os, "kill", _mock_dead_proc)

        obs = SimpleNamespace(observation_id="obs-1")

        class DummyCollector:
            def __init__(self, *args, **kwargs):
                pass

            def capture_before(self, handle):
                return obs

            def capture_after(self, *args, **kwargs):
                return obs

        m.setattr(R, "LocalObservationCollector", DummyCollector)

        outcome = gate.execute_lifecycle(req, ["echo", "test"])

    # Assert REJECT
    assert outcome.gate_result is R.GateResult.DENIED_BINDING

    # Assert no OBLIGATION_SATISFIED
    assert not any(et == R.EventType.OBLIGATION_SATISFIED for et, _ in submitted_events)

    # Assessment should reflect REJECT
    assessment_payloads = [p for et, p in submitted_events if et == R.EventType.ASSESSMENT_CREATED]
    assert len(assessment_payloads) == 1
    assert assessment_payloads[0]["assessment"].verdict is R.AssessmentVerdict.REJECT
    store.close()


def test_execute_lifecycle_exit_0_effect_match_accepts(monkeypatch, tmp_path):
    import sclass_runtime_v6_0_1 as R
    from tests.helpers.test_boundary import TestOnlyUnsandboxedBoundary, create_test_quiescence_attestor
    from types import SimpleNamespace
    import os

    boundary = TestOnlyUnsandboxedBoundary(str(tmp_path))
    store = R.SQLiteEventStore(str(tmp_path / "test2.sqlite"))
    control_plane = R.SClassControlPlane(store)
    control_plane.boundary_attestor = create_test_quiescence_attestor(control_plane.keys)

    gate = R.ExecutionGate(boundary, control_plane)

    state = SimpleNamespace()
    state.workspace_id = "ws-1"
    state.workspace_snapshot_id = "ws-snap-1"
    state.policy_version = "policy-v1"
    state.event_sequence = 1
    state.causal_frontier = SimpleNamespace(authorization_epoch="epoch-1")
    state.event_head_hash = "head-hash"

    d_digest = R.Digest("sha256:" + "d" * 64)
    v_delta = SimpleNamespace(delta_digest=d_digest)
    state.verified_deltas = {"d1": v_delta}
    rev = SimpleNamespace(revision_id="rev-1")
    state.objective = SimpleNamespace(revisions=[rev])
    state.work_graph = SimpleNamespace(revision_id="wg-1")

    req = _make_test_authorized_work_request(d_digest=d_digest)

    lease_record = R.LeaseRecord(req.execution_lease, R.LeaseState.ACTIVE)
    state.leases = {"lease-1": lease_record}

    res_mock = R.BudgetReservation(
        "res-1", "ws-1", "req-1", R.BudgetLevel.ATTEMPT, None, "budget-1",
        R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.UtcInstant(0), R.BudgetReservationState.RESERVED,
        R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), R.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), 1
    )
    state.budget_reservations = {"res-1": res_mock}

    gate._preflight = lambda *args, **kwargs: (state, SimpleNamespace(), [], R.UtcInstant(0))
    gate._admit_request = lambda *args, **kwargs: (req, lease_record, SimpleNamespace(), state)
    gate._verify_budget_reservation = lambda *args, **kwargs: res_mock
    control_plane.nonces.verify_consumed_binding = lambda *args, **kwargs: True
    control_plane.store._load_canonical_state = lambda *args, **kwargs: state

    run_result = R.BoundaryRunResult(
        R.BoundaryIsolation.DENY, 0, b"out", b"err", False, 10,
        R.Digest("sha256:" + "1" * 64), None, 123, 1000, 3, 3, ()
    )
    boundary._run_from_gate = lambda *args, **kwargs: run_result
    boundary._executable_path = lambda argv0: Path("/bin/echo")

    monkeypatch.setattr(R, "apply_delta_observation_matches", lambda d, o: R.DeltaMatchVerdict.MATCH)

    submitted_events = []

    def mock_submit_internal(cmd):
        submitted_events.append((cmd.event_type, cmd.payload))
        return SimpleNamespace(disposition=R.RuntimeDisposition.APPLIED)

    monkeypatch.setattr(control_plane, "_submit_internal", mock_submit_internal)

    with monkeypatch.context() as m:
        m.setattr(R, "validate_execution_lease", lambda s, l: True)
        m.setattr(R, "canonical_current_state_binding", lambda s, g, b: SimpleNamespace())
        m.setattr(R, "state_binding_digest", lambda b: R.Digest("sha256:" + "2" * 64))
        m.setattr(R, "digest", lambda domain, obj: R.Digest("sha256:" + "5" * 64))
        def _mock_dead_proc(pid, sig):
            raise ProcessLookupError("No such process")
        if hasattr(os, "killpg"):
            m.setattr(os, "killpg", _mock_dead_proc)
        m.setattr(os, "kill", _mock_dead_proc)

        obs = SimpleNamespace(observation_id="obs-1")

        class DummyCollector:
            def __init__(self, *args, **kwargs):
                pass

            def capture_before(self, handle):
                return obs

            def capture_after(self, *args, **kwargs):
                return obs

        m.setattr(R, "LocalObservationCollector", DummyCollector)

        outcome = gate.execute_lifecycle(req, ["echo", "test"])

    # Assert ACCEPT
    assert outcome.gate_result is R.GateResult.EXECUTED

    # Assert valid evidence generated
    evidence_payloads = [p for et, p in submitted_events if et == R.EventType.EVIDENCE_ACCEPTED]
    assert len(evidence_payloads) == 1
    closure = evidence_payloads[0]["closure"]
    assert closure.verdict is R.ClosureVerdict.SATISFIED

    # Validate EvidenceReceipt identity and provenance
    receipt = closure.evidence_receipts[0]
    import sclass_semantics_v6_0_1 as Sem
    receipt_payload_digest = Sem.evidence_signed_payload_digest(receipt)
    assert receipt.signature is not None

    receipt_verification = evidence_payloads[0]["signature_verifications"][0]
    assert receipt_verification.signed_payload_digest == receipt_payload_digest
    assert receipt_verification.verification_result is Sem.SignatureVerificationResult.VALID

    state.signature_verification_records = {receipt.receipt_id: receipt_verification}
    assert Sem.signature_subject_is_verified(state, receipt.receipt_id, receipt_payload_digest, receipt.signature)

    # Assert valid assessment generated
    assessment_payloads = [p for et, p in submitted_events if et == R.EventType.ASSESSMENT_CREATED]
    assert len(assessment_payloads) == 1
    assessment = assessment_payloads[0]["assessment"]
    assert assessment.verdict is R.AssessmentVerdict.ACCEPT

    # Validate IndependentAssessment identity and provenance
    assessment_payload_digest = Sem.assessment_signed_payload_digest(assessment)
    assert assessment.signature is not None

    assessment_verification = assessment_payloads[0]["signature_verification"]
    assert assessment_verification.signed_payload_digest == assessment_payload_digest
    assert assessment_verification.verification_result is Sem.SignatureVerificationResult.VALID

    state.signature_verification_records[assessment.assessment_id] = assessment_verification
    assert Sem.signature_subject_is_verified(state, assessment.assessment_id, assessment_payload_digest, assessment.signature)

    # Assert OBLIGATION_SATISFIED
    assert any(et == R.EventType.OBLIGATION_SATISFIED for et, _ in submitted_events)
    store.close()


def test_concurrent_nonce_race(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import sqlite3
    db_path = str(tmp_path / "nonce_race.sqlite")
    store = SQLiteEventStore(db_path)
    cp = SClassControlPlane(store)
    reqd = Digest("sha256:" + "1"*64)
    exp = UtcInstant(time.time_ns() + 100_000_000_000)
    cp.issue_nonce("w", "worker", reqd, exp, "RACE_NONCE")
    store.close()

    def try_consume(worker_id):
        local_store = SQLiteEventStore(db_path)
        local_cp = SClassControlPlane(local_store)
        res = local_cp.nonces.consume_and_bind(
            "w:worker", "RACE_NONCE", reqd,
            f"auth-{worker_id}", f"exec-{worker_id}",
            UtcInstant(time.time_ns())
        )
        local_store.close()
        return res

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(try_consume, i) for i in range(8)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r == NonceConsumptionResult.SUCCESS]
    rejected = [r for r in results if r != NonceConsumptionResult.SUCCESS]
    assert len(successes) == 1
    assert len(rejected) == 7


def test_concurrent_budget_reservation_race(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    db_path = str(tmp_path / "budget_race.sqlite")
    store = SQLiteEventStore(db_path)
    cp = SClassControlPlane(store)
    lim = ResourceBudget(5, 5, 0, 100, 0, 5, 5, 0, 0, 100, 10)
    cp.budgets._set_workspace_limit_for_test("w", lim)
    store.close()

    amt = ResourceBudget(2, 2, 0, 10, 0, 2, 2, 0, 0, 10, 1)

    def try_reserve(i):
        local_store = SQLiteEventStore(db_path)
        local_cp = SClassControlPlane(local_store)
        try:
            local_cp.budgets._reserve_for_test(
                "w", f"req-{i}", "L1", amt,
                UtcInstant(time.time_ns() + 100_000_000_000),
                reservation_id=f"R-{i}"
            )
            local_store.close()
            return True
        except ValueError:
            local_store.close()
            return False

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(try_reserve, i) for i in range(8)]
        results = [f.result() for f in futures]

    successes = [r for r in results if r is True]
    assert len(successes) <= 2


def test_revoked_auth_rejected_before_dispatch(tmp_path):
    from types import SimpleNamespace
    gate = ExecutionGate(LinuxExecutionBoundary(str(tmp_path), require_sandbox=False))
    req = _make_test_authorized_work_request()
    claims = req.authorization_lease.claims
    dec = AuthorizationDecision(
        claims.decision_id, "prop-1", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        AuthorizationState.DENY, Authority.USER, "user", (), "reason",
        UtcInstant(1), UtcInstant(10),
        "obj", "worker-1", Digest("sha256:" + "3" * 64), "pol",
        EffectScope((), (), (), fmap(), ".", (), (), ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
        "snap", Digest("sha256:" + "4" * 64), "node-1"
    )
    state = SimpleNamespace(authorization_decisions={claims.decision_id: dec})
    with pytest.raises(PermissionError, match="canonical ALLOW authorization decision required"):
        gate._canonical_decision(req, state)


def test_lease_expiry_during_run_rejected(tmp_path):
    from types import SimpleNamespace
    gate = ExecutionGate(LinuxExecutionBoundary(str(tmp_path), require_sandbox=False))
    req = _make_test_authorized_work_request()
    claims = req.authorization_lease.claims
    scope = EffectScope((), (), (), fmap(), ".", (), (), ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    dec = AuthorizationDecision(
        claims.decision_id, "prop-1", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        AuthorizationState.ALLOW, Authority.USER, "user", (), "reason",
        UtcInstant(1), UtcInstant(10),
        "obj", "worker-1", Digest("sha256:" + "3" * 64), "pol",
        scope, "snap", Digest("sha256:" + "4" * 64), "node-1"
    )
    state = SimpleNamespace(authorization_decisions={claims.decision_id: dec})
    with pytest.raises(PermissionError, match="canonical authorization decision no longer validates"):
        gate._canonical_decision(req, state)

