import types
import base64,json,re,sys,types
from pathlib import Path
from dataclasses import fields
import pytest
from sclass_kernel_v6_0_1 import *
import sclass_kernel_v6_0_1 as kernel
import sclass_semantics_v6_0_1 as semantics

def z(): return ResourceBudget(0,0,0,0,0,0,0,0,0,0,0)
def fmap(items=()): return FrozenMap.from_items(items)
def empty_scope(**kw): return EffectScope(kw.get("fs_rules",()),kw.get("process_rules",()),kw.get("network_rules",()),kw.get("allowed_env",fmap()),kw.get("working_directory","."),kw.get("credential_grants",()),kw.get("external_effect_rules",()),kw.get("resource_budget",z()))
def req(fs=(),process=(),network=(),environment=None,budget=None): return RequestedEffect(tuple(fs),tuple(process),tuple(network),fmap(tuple((environment or {}).items())),(),(),budget or z())

def test_strong_canonical_construction_and_schema_registry_are_complete():
    import dataclasses
    classes=[]
    module=sys.modules[semantics.__name__]
    for name,obj in vars(module).items():
        if isinstance(obj,type) and dataclasses.is_dataclass(obj) and getattr(obj,"__module__",None)==module.__name__:
            classes.append(obj)
    assert classes
    assert all(getattr(cls,"__c1_canonical__",False) for cls in classes)
    assert set(EVENT_PAYLOAD_SCHEMA)==set(EventType)
    assert all(EVENT_PAYLOAD_SCHEMA[e] is not None for e in EventType)


def test_c1_profile_bounds_and_mutability():
    assert canonical_c1(ActionType.CODE_EDIT)!=canonical_c1("CODE_EDIT")
    assert canonical_c1(b"\x01")==b'{"$bytes":"AQ=="}'
    for x in (2**63,-2**63-1):
        with pytest.raises(TypeError): canonical_c1(x)
    with pytest.raises(TypeError): canonical_c1("e\u0301")
    with pytest.raises(TypeError): canonical_c1([1,2])
    with pytest.raises(TypeError): canonical_c1({"a":1})

def test_c1_depth_and_frozen_map():
    x=1
    for _ in range(C1_MAX_DEPTH+2): x=(x,)
    with pytest.raises(TypeError): canonical_c1(x)
    m=fmap((("a",1),)); assert hash(m)
    with pytest.raises(TypeError): m._m["a"]=2

def test_root_specificity_and_order_independence():
    a=empty_scope(fs_rules=(FsRule(".",frozenset({FsMode.READ,FsMode.WRITE})),FsRule("a",frozenset({FsMode.READ}))))
    b=empty_scope(fs_rules=tuple(reversed(a.fs_rules))); r=req((FsAccess("a/x",FsMode.WRITE),))
    assert authorized(r,a) is not ScopeAuthorizationResult.AUTHORIZED
    assert authorized(r,b) is not ScopeAuthorizationResult.AUTHORIZED

def test_direct_authority_conjunction():
    allow=empty_scope(fs_rules=(FsRule("a/secret",frozenset({FsMode.WRITE})),)); deny=empty_scope(fs_rules=(FsRule("a/secret",frozenset({FsMode.READ})),))
    assert authorize_with_authorities(req((FsAccess("a/secret/x",FsMode.WRITE),)),allow,deny,allow) is not ScopeAuthorizationResult.AUTHORIZED

def test_process_child_argv_is_constrained():
    parent=(b"p",b"a"); child=(b"c",b"ca"); s=empty_scope(process_rules=(ProcessRule(parent[0],parent[1],True,(child,)),))
    good=ProcessSpec(parent[0],parent[1],".",(child,),True); bad=ProcessSpec(parent[0],parent[1],".",((b"c",b"evil"),),True)
    assert authorized(req(process=(good,)),s) is ScopeAuthorizationResult.AUTHORIZED
    assert authorized(req(process=(bad,)),s) is not ScopeAuthorizationResult.AUTHORIZED

def test_environment_values_are_authorized():
    s=empty_scope(allowed_env=fmap((("MODE","digest:prod"),)))
    assert authorized(req(environment={"MODE":"digest:prod"}),s) is ScopeAuthorizationResult.AUTHORIZED
    assert authorized(req(environment={"MODE":"digest:evil"}),s) is not ScopeAuthorizationResult.AUTHORIZED

def test_network_wildcard_ip_boundary_and_redirect():
    rule=NetRule("*.example.com",("192.0.2.0/24",),frozenset({443}),"tcp",True,True); s=empty_scope(network_rules=(rule,))
    n=NetAccess("api.example.com",("192.0.2.1",),443,"tcp",True)
    assert authorized(req(network=(n,)),s,{"api.example.com":("192.0.2.1",)}) is ScopeAuthorizationResult.AUTHORIZED
    ip=NetAccess("192.0.2.1",("192.0.2.1",),443,"tcp",True)
    assert authorized(req(network=(ip,)),s,{"192.0.2.1":("192.0.2.1",)}) is not ScopeAuthorizationResult.AUTHORIZED
    with pytest.raises(ValueError): NetRule("*",("192.0.2.0/24",),frozenset({443}),"tcp",True,False)

def test_redirect_reauthorization():
    s=empty_scope(network_rules=(NetRule("example.com",("192.0.2.0/24",),frozenset({443}),"tcp",True,True),NetRule("redirect.example.com",("198.51.100.0/24",),frozenset({443}),"tcp",True,False)))
    n=NetAccess("example.com",("192.0.2.10",),443,"tcp",True,(NetworkDestination("redirect.example.com",443,"tcp",True,("198.51.100.10",)),))
    assert authorized(req(network=(n,)),s,{"example.com":("192.0.2.10",),"redirect.example.com":("198.51.100.10",)}) is ScopeAuthorizationResult.AUTHORIZED

def gen(status=ExecutionGenerationStatus.ACTIVE,objective="o2",workgraph="w2"):
    return ExecutionGeneration("n",2,"a2","epoch","worker",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),"b",objective,workgraph,status)
def result(objective="o2",workgraph="w2"):
    return WorkResult("r","q","rq","env",2,"a2",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),"b",objective,workgraph,"worker",WorkerClaimStatus.CLAIMED_COMPLETE,0,0,"out","diag",())

def test_generation_fencing_status_and_revisions():
    c=gen(); r=result(); assert admit_work_result(c,r) is GateResult.ACCEPTED
    for st in (ExecutionGenerationStatus.SUPERSEDED,ExecutionGenerationStatus.RECONCILED): assert admit_work_result(gen(st),r) is GateResult.DENIED_STALE_GENERATION
    assert admit_work_result(c,result("bad")) is GateResult.DENIED_BINDING
    assert admit_work_result(c,result(workgraph="bad")) is GateResult.DENIED_BINDING

def test_capability_action_and_window_are_authoritative():
    cap=Capability(ActionType.CODE_READ,empty_scope(),(),UtcInstant(0),UtcInstant(10))
    assert capability_authorizes((cap,),ActionType.CODE_READ,UtcInstant(5),req(),empty_scope(),empty_scope(),{})
    assert not capability_authorizes((cap,),ActionType.CODE_EDIT,UtcInstant(5),req(),empty_scope(),empty_scope(),{})

def actor(): return ActorIdentity("system",ActorKind.SYSTEM,None)
def event(): return CanonicalEvent.create("e","c","w",1,EventType.SHUTDOWN_REQUESTED,1,"system",actor(),"caus","corr",fmap((("reason","test"),)),GENESIS_EVENT_HASH,"pol","sdk",UtcInstant(10))

def test_event_hash_binds_security_fields():
    e=event()
    for field,value in (("actor",ActorIdentity("other",ActorKind.SYSTEM,None)),("causation_id","other"),("correlation_id","other"),("schema_version",2),("commit_id","c2")):
        d={f.name:getattr(e,f.name) for f in fields(e)}; d[field]=value
        with pytest.raises(ValueError): CanonicalEvent(**d)

def test_reducer_handlers_are_callable_and_fail_closed():
    assert set(REFERENCE_REDUCER_HANDLERS)==set(EventType); assert all(callable(x) for x in REFERENCE_REDUCER_HANDLERS.values())
    assert REFERENCE_REDUCER_HANDLERS[EventType.APPROVAL_RECORDED] is not REFERENCE_REDUCER_HANDLERS[EventType.WORK_FAILED]

def test_spec_blocks_are_kernel_source():
    spec=Path(__file__).parents[1]/"00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md"; blocks=re.findall(r"```python\n(.*?)\n```",spec.read_text(),re.S); module=types.ModuleType("independent_spec_exec"); sys.modules[module.__name__]=module; ns=module.__dict__; ns["__file__"]=str(spec); exec(compile("\n\n".join(blocks),str(spec),"exec"),ns,ns)
    assert ns["canonical_c1"](("x",1,True))==canonical_c1(("x",1,True)); assert ns["digest"]("sclass/test/v1",("x",1,True))==digest("sclass/test/v1",("x",1,True))

def test_c1_vectors():
    vectors=json.loads((Path(__file__).with_name("c1-vectors.v6.0.1.json")).read_text())["vectors"]
    objs={"enum":ActionType.CODE_EDIT,"bytes":b"\x00\xff","tuple":("a",1,True),"set":frozenset({"z","a"}),"null":None,"bool":False,"int_zero":0,"int_max":C1_MAX_INT,"int_min":C1_MIN_INT,"nfc_string":"é","nested":("x",(1,2),frozenset({3,4})),"map":FrozenMap.from_items((("a",1),(2,"b")))}
    for v in vectors:
        o=objs[v["name"]]; assert base64.b64encode(canonical_c1(o)).decode()==v["canonical_c1_base64"]; assert digest("sclass/vector/v1",o)==v["digest"]

# --- C17-C28 lifecycle conformance ---
def _minimal_policy():
    profiles=fmap((
        (tier, ControlProfile(AuthorizationMode.AUTO, IsolationLevel.PROCESS, (), IndependenceProfile(IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE), 3, True))
        for tier in RiskTier
    ))
    risk=RiskMapping("risk-test",(),profiles)
    auth=AuthorizationRules(1000,1000,("worker",),False,())
    evidence=EvidenceRules((),False,1024)
    retry=RetryRules(3,1)
    budget=BudgetRules(ResourceBudget(10,10,10,1000,10,10,10,10,10,100,10),5000)
    rel=ReleaseRules(("test",),(),True,1000)
    waiver=WaiverRules((),1000,False)
    dep=DependencyRules(False,True)
    dc=DataClassificationPolicy(DataClassification.PUBLIC,())
    red=RedactionPolicy((),"[REDACTED]",False)
    egress=ProviderEgressPolicy((),DataClassification.SECRET,(),False,True)
    retention=RetentionPolicy(1,1,1)
    telemetry=TelemetryPrivacyPolicy((),True,True)
    return Policy("policy-test","pol",risk,auth,evidence,retry,budget,egress,rel,waiver,dep,dc,red,retention,telemetry,1,"floor",Digest("sha256:"+"f"*64))


def _minimal_state(workspace="w"):
    vals={f.name:None for f in fields(EngineeringState)}
    node=WorkNode("n","ob",frozenset({"ob"}),"test",ActionType.CODE_READ,req(),empty_scope(),0,0,WorkNodeStatus.READY,Idempotency.IDEMPOTENT,None,"retry",RiskTier.LOW,1,"lineage")
    wg=WorkGraph("wg","o","og","pol","wm",SemanticGraph(("n",),()),fmap((("n",node),)))
    target=TargetSnapshot("s",workspace,Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),None,None,Digest("sha256:"+"3"*64),Digest("sha256:"+"4"*64),Digest("sha256:"+"5"*64),(),fmap(),"pol",UtcInstant(1))
    snap=EngineeringSnapshot("es",1,Digest("sha256:"+"6"*64),ContentManifestState(Digest("sha256:"+"7"*64),0),"wm","pol","risk-test","sdk","toolchain",Digest("sha256:"+"8"*64))
    intent=StructuredIntent(1,"test",(),(),(),())
    rev=ObjectiveRevision("o",1,intent,(),(),(),snap,None)
    objective=CanonicalObjective("obj",workspace,(rev,))
    policy=_minimal_policy()
    vals.update(workspace_id=workspace, state_schema_version=1, reducer_version="6.0.1",
                state_revision=Digest("sha256:"+"0"*64), event_sequence=0,
                event_head_hash=GENESIS_EVENT_HASH, work_graph=wg, requirements=fmap(),
                objective=objective, workspace_snapshot_id="s", target_snapshot=target, policy_version="pol",
                policy_digest=digest("sclass/policy/v1",policy), active_policy=policy,
                world_model_revision="wm",
                reducer_facts=fmap((("WorkNodeStatus", fmap((("n","READY"),))), ("ObligationStatus",fmap()), ("RequirementStatus",fmap()), ("LeaseState",fmap()))))
    for name in ("acceptance_contracts","verification_plans","evidence","assessments","assignments","leases","retry_budgets","budget_reservations","repair_plans","waivers","in_doubt","releases","verified_deltas","break_glass_consumption","approval_records","approval_sets","signature_verification_facts","signature_verification_records","causal_frontiers","target_snapshots","acceptance_snapshots","execution_generations","governing_budget_lineages","authorization_decisions","execution_outcomes","checkpoints","retry_consumptions"):
        vals[name]=fmap()
    return EngineeringState(**vals)

def _canonical_genesis(workspace="w"):
    return genesis_engineering_state(workspace)

def _shutdown_event(seq, prev, commit):
    return _reducer_event(seq,prev,EventType.SHUTDOWN_REQUESTED,aggregate="system",payload={"reason":"test"},commit=commit)

def _reducer_event(seq, prev, et, aggregate="n", payload=None, commit="c"):
    payload=fmap((payload or {}).items())
    return CanonicalEvent.create("e"+str(seq),commit,"w",seq,et,1,aggregate,actor(),"caus","corr",payload,prev,"pol","sdk",UtcInstant(seq))

def test_reference_reducer_replay_and_illegal_transition():
    initial=_minimal_state()
    e1=_reducer_event(1,GENESIS_EVENT_HASH,EventType.WORK_ASSIGNED,payload={"worker_id":"worker-1"})
    s0=ReferenceReducer().reduce(initial,e1)
    ad=AuthorizationDecision("d","n",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),AuthorizationState.ALLOW,Authority.USER,"system",(),"test",UtcInstant(1),UtcInstant(10),"o","worker-1",Digest("sha256:"+"3"*64),"pol",empty_scope(),"s",control_profile_digest=digest("sclass/control-profile/v1",_minimal_policy().risk_mapping.control_profiles[RiskTier.LOW]),work_node_id="n")
    lineage=canonical_governing_budget_lineage(s0,"n"); frontier=canonical_causal_frontier(s0,ad,lineage,RiskTier.LOW)
    e_auth=_reducer_event(2,e1.event_hash,EventType.AUTHORIZATION_GRANTED,payload={"authorization_decision":ad,"governing_budget_lineage":lineage,"causal_frontier":frontier})
    eg=ExecutionGeneration("n",1,"a",frontier.authorization_epoch,"worker-1",target_snapshot_digest(ReferenceReducer().reduce(s0,e_auth).target_snapshot),state_binding_digest(canonical_current_state_binding(ReferenceReducer().reduce(s0,e_auth),1,lineage.lineage_id)),"lineage","o","wg",ExecutionGenerationStatus.ACTIVE)
    e2=_reducer_event(3,e_auth.event_hash,EventType.EXECUTION_STARTED,payload={"execution_generation":eg})
    r=ReferenceReducer(); s1=r.replay(initial,(e1,e_auth,e2)); s2=r.replay(initial,(e1,e_auth,e2))
    assert s1.event_sequence==3 and s1.reducer_facts["WorkNodeStatus"]["n"]=="EXECUTING"
    assert digest("sclass/state/v1",s1.reducer_facts)==digest("sclass/state/v1",s2.reducer_facts)
    bad=_reducer_event(4,e2.event_hash,EventType.WORK_ASSIGNED,payload={"worker_id":"worker-2"})
    with pytest.raises(ValueError): r.reduce(s1,bad)

def test_reference_reducer_all_handlers_are_real():
    assert set(REFERENCE_REDUCER_HANDLERS)==set(EventType)
    assert all(callable(h) for h in REFERENCE_REDUCER_HANDLERS.values())
    assert REFERENCE_REDUCER_HANDLERS[EventType.WORK_ASSIGNED] is not REFERENCE_REDUCER_HANDLERS[EventType.WORK_FAILED]


def _tightening_policy_like(allow_waivers=False, waived=False):
    from types import SimpleNamespace as N
    prof=N(authorization_mode=AuthorizationMode.AUTO,min_isolation=0,required_evidence_kinds=frozenset(),
           required_independence=N(model=0,context=0,execution=0,verifier=0,configuration=0),max_retries=3,external_effects_allowed=True)
    risk=N(classifier_version="v",floor_rules=(),control_profiles={t:prof for t in RiskTier})
    auth=N(lease_ttl_ms=100,max_execution_ms=100,allowed_audiences=(),require_attestation=False,denied_action_types=())
    ev=N(default_freshness=(),receipts_must_be_signed=False,max_excerpt_bytes=100)
    retry=N(max_same_failure=3,backoff_ms=1)
    budget=N(default_objective_budget=ResourceBudget(10,10,10,10,10,10,10,10,10,10,10),reservation_ttl_ms=100)
    eg=N(allowed_providers=(),max_classification=DataClassification.SECRET,denied_path_globs=(),require_redaction=False,allow_remote_workers=True)
    rel=N(target_environments=("prod",),required_evidence_kinds=(),allow_waivers=allow_waivers,max_waiver_ttl_ms=100)
    wa=N(approver_authorities=(),max_ttl_ms=100,require_signature=True)
    dep=N(waived_satisfies_dependents=waived,superseded_requires_replacement_satisfied=True)
    dc=N(default=DataClassification.PUBLIC,path_rules=())
    red=N(secret_detector_ids=(),replacement="x",redact_registered_credentials=False)
    ret=N(evidence_days=1,model_io_days=1,telemetry_days=1)
    tel=N(allowed_fields=(),forbid_content=True,hash_paths=True)
    return N(floor_id="f",floor_digest=Digest("sha256:"+"1"*64),risk_mapping=risk,authorization_rules=auth,evidence_rules=ev,
             retry_rules=retry,budget_rules=budget,egress_rules=eg,release_rules=rel,waiver_rules=wa,dependency_rules=dep,
             data_classification=dc,redaction=red,retention=ret,telemetry=tel,clock_skew_tolerance_ms=1)

def test_policy_tightening_boolean_directions():
    old=_tightening_policy_like(False,False)
    assert kernel._is_tightening(old,_tightening_policy_like(False,False))
    assert not kernel._is_tightening(old,_tightening_policy_like(True,False))
    assert not kernel._is_tightening(old,_tightening_policy_like(False,True))
    old2=_tightening_policy_like(True,True)
    assert kernel._is_tightening(old2,_tightening_policy_like(False,False))


def test_external_effect_rule_is_exact_and_order_independent():
    a=empty_scope(external_effect_rules=(ExternalEffectRule("github",frozenset({"read"}),1),ExternalEffectRule("github",frozenset({"write"}),100)))
    r=req(); r=RequestedEffect((),(),(),fmap(),(),(ExternalEffect("github","write",50),),z())
    assert authorized(r,a) is ScopeAuthorizationResult.AUTHORIZED
    b=empty_scope(external_effect_rules=tuple(reversed(a.external_effect_rules)))
    assert authorized(r,b) is ScopeAuthorizationResult.AUTHORIZED
    c=empty_scope(external_effect_rules=(ExternalEffectRule("github",frozenset({"write"}),1),ExternalEffectRule("github",frozenset({"write"}),100)))
    with pytest.raises(ValueError): kernel._validate_scope_rules(c)


def test_target_snapshot_digest_binds_all_components_and_dependencies():
    ts=TargetSnapshot("s","w",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),None,None,Digest("sha256:"+"3"*64),Digest("sha256:"+"4"*64),Digest("sha256:"+"5"*64),(),fmap((("pkg",Digest("sha256:"+"6"*64)),)),"p",UtcInstant(1))
    d=target_snapshot_digest(ts)
    ts2=TargetSnapshot(ts.snapshot_id,ts.workspace_id,ts.repository_identity_digest,Digest("sha256:"+"7"*64),ts.dependency_lock_digest,ts.generated_state_digest,ts.untracked_manifest_digest,ts.environment_digest,ts.toolchain_digest,ts.external_state_reference_digests,ts.dependency_digests,ts.target_policy_version,ts.created_at)
    assert d != target_snapshot_digest(ts2)


def test_dependency_freshness_requires_authoritative_current_map():
    ctx=FreshnessContext("s",Digest("sha256:"+"1"*64),"o","p",1,1,Digest("sha256:"+"2"*64),Digest("sha256:"+"3"*64),fmap((("pkg",Digest("sha256:"+"4"*64)),)),Digest("sha256:"+"5"*64),frozenset())
    dep=EvidenceDependencySet((('pkg',Digest("sha256:"+"4"*64)),),(),False)
    c=type("C",(),{})(); c.target_snapshot_digest=ctx.target_snapshot_digest;c.workspace_snapshot_id="s";c.evidence_id="e";c.objective_revision="o";c.policy_version="p";c.acceptance_contract_revision=1;c.verification_plan_revision=1;c.verifier_config_digest=ctx.verifier_config_digest;c.environment_digest=ctx.environment_digest;c.dependency_set=dep
    assert is_fresh(c,FRESHNESS_FLOOR,ctx).state is FreshnessState.FRESH
    missing=FreshnessContext(ctx.snapshot_id,ctx.target_snapshot_digest,ctx.objective_revision,ctx.policy_version,ctx.contract_revision,ctx.plan_revision,ctx.verifier_config_digest,ctx.environment_digest,fmap(),ctx.dependency_set_digest_now,frozenset())
    assert is_fresh(c,FRESHNESS_FLOOR,missing).state is FreshnessState.UNKNOWN


def _receipt(reqkey="r",kind=EvidenceKind.BEHAVIORAL,signer="v",status=VerificationStatus.PASS):
    p=SignedEvidencePayload("c1",signer,"step",kind,"ob",reqkey,"obs",Digest("sha256:"+"1"*64),"o",1,1,Digest("sha256:"+"2"*64),status,Digest("sha256:"+"3"*64),Digest("sha256:"+"4"*64),Digest("sha256:"+"5"*64),Digest("sha256:"+"3"*64),"tool","1",UtcInstant(1))
    sig=SignatureBlock("ed25519","k","root","c1",b"sig")
    temp=EvidenceReceipt("",kind,p,sig)
    return EvidenceReceipt(str(evidence_receipt_identity(temp)),kind,p,sig)

def test_evidence_composition_all_any_k_of_n():
    reqs=(RequiredEvidence("a",EvidenceKind.BEHAVIORAL,"v",IndependenceProfile(IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE),(),True,1),
          RequiredEvidence("b",EvidenceKind.STATIC,"v",IndependenceProfile(IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE),(),False,1),
          RequiredEvidence("c",EvidenceKind.DYNAMIC,"v",IndependenceProfile(IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE),(),False,1))
    base=dict(target_snapshot_digest=Digest("sha256:"+"1"*64),objective_revision="o",policy_version="p",contract_revision=1,plan_revision=1,verifier_config_digest=Digest("sha256:"+"2"*64),environment_digest=Digest("sha256:"+"3"*64),dependency_set_digest_now=None)
    ctx=FreshnessContext("s",dependency_digests_now=fmap((("pkg",Digest("sha256:"+"4"*64)),)),**base)
    profiles={"v":IndependenceProfile(IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE,IndependenceLevel.NONE)}
    rs=(_receipt("a",EvidenceKind.BEHAVIORAL),_receipt("b",EvidenceKind.STATIC),_receipt("c",EvidenceKind.DYNAMIC))
    for mode,k,expected in ((CompositionMode.ALL_OF,0,True),(CompositionMode.ANY_OF,0,True),(CompositionMode.K_OF_N,2,True)):
        comp=EvidenceComposition(mode,k); contract=AcceptanceContract("c","ob",1,reqs,comp,WaiverRules((),1,True),Authority.USER)
        ev=evaluate_evidence_composition(contract,rs,ctx,profiles,frozenset(r.receipt_id for r in rs))
        assert (ev.verdict is ClosureVerdict.SATISFIED)==expected
    with pytest.raises(ValueError): AcceptanceContract("c","ob",1,reqs,EvidenceComposition(CompositionMode.K_OF_N,3),WaiverRules((),1,True),Authority.USER)
    with pytest.raises(ValueError): evaluate_evidence_composition(contract,rs+(rs[0],),ctx,profiles,frozenset(r.receipt_id for r in rs))


def _commit_record(cid="c", ws="w"):
    base=CommitRecord(cid,ws,("e1","state1"),(Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64)),("event","state"),Digest("sha256:"+"3"*64),Digest("sha256:"+"4"*64),"rev",1,2,1,Digest("sha256:"+"0"*64),CommitState.PROPOSED,1,None)
    return CommitRecord(base.commit_id,base.workspace_id,base.participant_ids,base.participant_hashes,base.participant_types,base.previous_head,base.resulting_head,base.resulting_state_revision,base.event_sequence_start,base.event_sequence_end,base.schema_version,commit_record_digest(base),base.state,base.prepared_at_epoch_ns,None)

def test_eventstore_is_the_only_durable_commit_authority():
    import sclass_semantics_v6_0_1 as sem
    assert not hasattr(sem, "SQLiteCommitStore")
    assert not hasattr(sem, "DurableCommitStore")
    assert SQLiteEventStore.STORE_SCHEMA_VERSION >= 2


def test_approval_separation_of_duties_and_authority_identity():
    sig=SignatureBlock("ed25519","k","root","c1",b"s")
    r=ApprovalRecord("a",ApprovalKind.RELEASE,"approver","APPROVER","w",Digest("sha256:"+"1"*64),"p",Digest("sha256:"+"2"*64),UtcInstant(0),UtcInstant(10),sig)
    a=ApprovalSet("s",ApprovalKind.RELEASE,"w",r.target_digest,"p",r.scope_digest,1,(r,),"requester")
    assert validate_approval_set(a,frozenset({"a"}),UtcInstant(1),{"approver":"APPROVER"},1,{"approver":"human-1"}) is ApprovalSetResult.VALID
    same=ApprovalRecord("a2",r.kind,"approver2","APPROVER","w",r.target_digest,"p",r.scope_digest,UtcInstant(0),UtcInstant(10),sig)
    a2=ApprovalSet("s2",r.kind,"w",r.target_digest,"p",r.scope_digest,2,(r,same),"requester")
    assert validate_approval_set(a2,frozenset({"a","a2"}),UtcInstant(1),{"approver":"APPROVER","approver2":"APPROVER"},2,{"approver":"human-1","approver2":"human-1"}) is ApprovalSetResult.DUPLICATE_PRINCIPAL


def test_netaccess_redirects_bind_complete_destination():
    n=NetAccess("example.com",("192.0.2.10",),443,"tcp",True,(NetworkDestination("other.example",8443,"tcp",False,("198.51.100.10",)),))
    assert n.redirect_chain[0].port==8443 and n.redirect_chain[0].protocol=="tcp" and n.resolution_binding_digest is not None

def test_state_machine_json_is_authoritative_source():
    assert kernel.STATE_MACHINE_SOURCE["generated_from"] == "10-CONFORMANCE/state-machines.v6.0.1.json"
    assert kernel.STATE_MACHINE_SOURCE["machines"]["WorkNodeStatus"]["ASSIGNED"] == ["AUTHORIZED","READY","CANCELLED"]
    assert kernel.STATE_MACHINE_SOURCE["machines"]["WorkNodeStatus"]["EXECUTING"] == ["OBSERVING","FAILED","IN_DOUBT","CANCELLED"]
    assert set(kernel.STATE_MACHINE_SOURCE["event_transitions"]) == {e.name for e in EventType}
    assert kernel.STATE_MACHINE_SOURCE["event_transitions"]["WORK_ASSIGNED"]["target"] == "ASSIGNED"


def test_release_evaluation_is_canonical_and_digest_bound():
    from types import SimpleNamespace as N
    ts=TargetSnapshot("s","w",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),None,None,Digest("sha256:"+"3"*64),Digest("sha256:"+"4"*64),Digest("sha256:"+"5"*64),(),fmap(),"p",UtcInstant(1))
    policy=N(policy_version="p",release_rules=N(target_environments=("prod",),allow_waivers=False))
    acc=AcceptanceSnapshot("as","w",Digest("sha256:"+"6"*64),target_snapshot_digest(ts),"o", "og", "wg", Digest("sha256:"+"7"*64),Digest("sha256:"+"8"*64),Digest("sha256:"+"9"*64),Digest("sha256:"+"a"*64),Digest("sha256:"+"b"*64),1,GENESIS_EVENT_HASH)
    state=N(obligations=N(_obligations={}),target_snapshot=ts,workspace_snapshot_id="s",objective=N(revisions=(N(revision_id="o"),)),policy_version="p",acceptance_contracts=fmap(),evidence=fmap(),assessments=fmap(),waivers=fmap(),acceptance_snapshots=fmap((("as",acc),)),state_revision=Digest("sha256:"+"b"*64),state_digest=Digest("sha256:"+"b"*64))
    snap=EngineeringSnapshot("es",1,state.state_revision,GitCommitState("git","tree",Digest("sha256:"+"b"*64)),"wm","p","risk","sdk","tool",Digest("sha256:"+"c"*64))
    rel=ReleaseState("r","p",Digest("sha256:"+"d"*64),"prod",(),(),(),(),snap,"as",acceptance_snapshot_digest(acc))
    e1=evaluate_release(state,rel,policy,UtcInstant(100)); e2=evaluate_release(state,rel,policy,UtcInstant(100))
    assert isinstance(e1,ReleaseEvaluation) and e1.verdict is ReleaseVerdict.READY and e1.evaluation_digest==e2.evaluation_digest
    rel2=ReleaseState(rel.release_id,rel.release_policy_version,Digest("sha256:"+"f"*64),rel.target_environment,rel.blocking_obligations,rel.waivers,rel.final_assessments,rel.provenance,rel.engineering_snapshot,rel.acceptance_snapshot_id,rel.acceptance_snapshot_digest)
    assert e1.evaluation_digest != evaluate_release(state,rel2,policy,UtcInstant(100)).evaluation_digest


def test_eventstore_reopen_preserves_committed_visibility(tmp_path):
    path=str(tmp_path/"eventstore-reopen.db")
    store=SQLiteEventStore(path); e=_shutdown_event(1,GENESIS_EVENT_HASH,"reopen")
    derived=REFERENCE_REDUCER.reduce(_canonical_genesis(),e); commit=_commit_for(e,derived,"reopen")
    assert store.append(e,commit,GENESIS_EVENT_HASH)[0] is AppendResult.APPENDED
    store.close()
    reopened=SQLiteEventStore(path)
    assert reopened.head("w").sequence==1
    assert reopened.verify_chain("w",1,1) is ChainStatus.VALID
    reopened.close()


def test_redirect_authorization_uses_redirect_destination_fields():
    scope=empty_scope(network_rules=(NetRule("example.com",("192.0.2.0/24",),frozenset({443}),"tcp",True,True),
        NetRule("other.example",("198.51.100.0/24",),frozenset({8443}),"tcp",False,False)))
    n=NetAccess("example.com",("192.0.2.10",),443,"tcp",True,(NetworkDestination("other.example",8443,"tcp",False,("198.51.100.10",)),))
    boundary={"example.com":("192.0.2.10",),"other.example":("198.51.100.10",)}
    assert authorized(req(network=(n,)),scope,boundary) is ScopeAuthorizationResult.AUTHORIZED
    wrong=NetAccess("example.com",("192.0.2.10",),443,"tcp",True,(NetworkDestination("other.example",443,"tcp",False,("198.51.100.10",)),))
    assert authorized(req(network=(wrong,)),scope,boundary) is not ScopeAuthorizationResult.AUTHORIZED

def test_every_event_handler_is_real_and_malformed_payload_fails_closed():
    for i, et in enumerate(EventType, 1):
        try:
            e=_reducer_event(1,GENESIS_EVENT_HASH,et,aggregate=f"a{i}",payload={},commit=f"c{i}")
        except (ValueError,TypeError):
            continue
        handler=REFERENCE_REDUCER_HANDLERS[et]
        with pytest.raises((ValueError,TypeError)):
            handler(_minimal_state(),e)


def test_release_wrong_acceptance_snapshot_is_not_evaluable():
    from types import SimpleNamespace as N
    ts=TargetSnapshot("s","w",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),None,None,Digest("sha256:"+"3"*64),Digest("sha256:"+"4"*64),Digest("sha256:"+"5"*64),(),fmap(),"p",UtcInstant(1))
    acc=AcceptanceSnapshot("as","w",Digest("sha256:"+"6"*64),target_snapshot_digest(ts),"o","og","wg",Digest("sha256:"+"7"*64),Digest("sha256:"+"8"*64),Digest("sha256:"+"9"*64),Digest("sha256:"+"a"*64),Digest("sha256:"+"b"*64),1,GENESIS_EVENT_HASH)
    state=N(obligations=N(_obligations={}),target_snapshot=ts,workspace_snapshot_id="s",objective=N(revisions=(N(revision_id="o"),)),policy_version="p",acceptance_contracts=fmap(),evidence=fmap(),assessments=fmap(),waivers=fmap(),acceptance_snapshots=fmap((("as",acc),)),state_revision=Digest("sha256:"+"c"*64))
    snap=EngineeringSnapshot("es",1,state.state_revision,GitCommitState("git","tree",Digest("sha256:"+"b"*64)),"wm","p","risk","sdk","tool",Digest("sha256:"+"d"*64))
    rel=ReleaseState("r","p",Digest("sha256:"+"e"*64),"prod",(),(),(),(),snap,"as",Digest("sha256:"+"f"*64))
    policy=N(policy_version="p",release_rules=N(target_environments=("prod",),allow_waivers=False))
    assert evaluate_release(state,rel,policy,UtcInstant(100)).verdict is ReleaseVerdict.NOT_EVALUABLE

def test_event_payload_tamper_is_rejected_at_reducer_boundary():
    e=_reducer_event(1,GENESIS_EVENT_HASH,EventType.WORK_ASSIGNED,payload={"worker_id":"worker-1"})
    object.__setattr__(e,"payload",fmap((("worker_id","attacker"),)))
    with pytest.raises(ValueError, match="payload digest"):
        REFERENCE_REDUCER.reduce(_minimal_state(),e)


def test_reducer_materializes_authorization_and_execution_state():
    initial=_minimal_state()
    e1=_reducer_event(1,GENESIS_EVENT_HASH,EventType.WORK_ASSIGNED,payload={"worker_id":"worker-1"})
    s0=ReferenceReducer().reduce(initial,e1)
    ad=AuthorizationDecision("d","n",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),AuthorizationState.ALLOW,Authority.USER,"system",(),"test",UtcInstant(1),UtcInstant(10),"o","worker-1",Digest("sha256:"+"3"*64),"pol",empty_scope(),"s",control_profile_digest=digest("sclass/control-profile/v1",_minimal_policy().risk_mapping.control_profiles[RiskTier.LOW]),work_node_id="n")
    lineage=canonical_governing_budget_lineage(s0,"n"); frontier=canonical_causal_frontier(s0,ad,lineage,RiskTier.LOW)
    e2=_reducer_event(2,e1.event_hash,EventType.AUTHORIZATION_GRANTED,payload={"authorization_decision":ad,"governing_budget_lineage":lineage,"causal_frontier":frontier})
    state2=ReferenceReducer().reduce(s0,e2)
    eg=ExecutionGeneration("n",1,"a",frontier.authorization_epoch,"worker-1",target_snapshot_digest(state2.target_snapshot),state_binding_digest(canonical_current_state_binding(state2,1,lineage.lineage_id)),"lineage","o","wg",ExecutionGenerationStatus.ACTIVE)
    e3=_reducer_event(3,e2.event_hash,EventType.EXECUTION_STARTED,payload={"execution_generation":eg})
    state=REFERENCE_REDUCER.replay(initial,(e1,e2,e3))
    assert state.authorization_decisions["d"] == ad
    assert state.execution_generations["n"] == eg


def test_atomic_event_projection_commit_boundary(tmp_path):
    initial=_canonical_genesis()
    e=_shutdown_event(1,GENESIS_EVENT_HASH,"atomic")
    state=REFERENCE_REDUCER.reduce(initial,e)
    commit=_commit_for(e,state,"atomic")
    store=SQLiteCanonicalStore(str(tmp_path/"canonical.db"))
    store.append_atomic(e,commit)
    assert store.visible_head("w") == (1,e.event_hash,state.state_digest)


def _assessment_release_fixture(obligation_count=2, assessment_count=2):
    from types import SimpleNamespace as N
    ts=TargetSnapshot("s","w",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),None,None,Digest("sha256:"+"3"*64),Digest("sha256:"+"4"*64),Digest("sha256:"+"5"*64),(),fmap(),"p",UtcInstant(1))
    policy=N(policy_version="p",release_rules=N(target_environments=("prod",),allow_waivers=False))
    objs={}
    evid={}
    ass={}
    for i in range(obligation_count):
        oid=f"o{i}"; eid=f"e{i}"; aid=f"a{i}"
        objs[oid]=N(status=ObligationStatus.SATISFIED,satisfied_by=eid,acceptance_contract_id="ac")
        evid[eid]=N(evidence_id=eid,obligation_id=oid,verdict=ClosureVerdict.SATISFIED,evidence_receipts=(),verification_plan_revision=1,verifier_config_digest=Digest("sha256:"+"6"*64),policy_version="p",world_model_revision="wm",target_snapshot_digest=target_snapshot_digest(ts),workspace_snapshot_id="s",objective_revision="o",acceptance_contract_revision=1,environment_digest=ts.environment_digest,dependency_digests=ts.dependency_digests,dependency_set=EvidenceDependencySet((),(),True))
        if i < assessment_count:
            ass[aid]=N(assessment_id=aid,evidence_id=eid,policy_version="p",workspace_snapshot_id="s",target_snapshot_digest=target_snapshot_digest(ts),artifact_digest=Digest("sha256:"+"d"*64),verdict=AssessmentVerdict.ACCEPT)
    acc=AcceptanceSnapshot("as","w",Digest("sha256:"+"7"*64),target_snapshot_digest(ts),"o","og","wg",Digest("sha256:"+"8"*64),Digest("sha256:"+"9"*64),Digest("sha256:"+"a"*64),Digest("sha256:"+"b"*64),Digest("sha256:"+"c"*64),1,GENESIS_EVENT_HASH)
    state=N(obligations=N(_obligations=objs),target_snapshot=ts,workspace_snapshot_id="s",objective=N(revisions=(N(revision_id="o"),)),policy_version="p",acceptance_contracts=fmap((("ac",N(revision=1)),)),evidence=fmap(evid.items()),assessments=fmap(ass.items()),waivers=fmap(),acceptance_snapshots=fmap((("as",acc),)),state_revision=Digest("sha256:"+"b"*64),state_digest=Digest("sha256:"+"b"*64),signature_verification_facts=fmap(((f"a{i}","VERIFIED") for i in range(assessment_count))),target_snapshots=fmap(),reducer_facts=fmap(),target_environment="prod")
    snap=EngineeringSnapshot("es",1,state.state_revision,GitCommitState("git","tree",Digest("sha256:"+"b"*64)),"wm","p","risk","sdk","tool",Digest("sha256:"+"c"*64))
    ids=tuple(f"o{i}" for i in range(obligation_count))
    aids=tuple(f"a{i}" for i in range(assessment_count))
    rel=ReleaseState("r","p",Digest("sha256:"+"d"*64),"prod",ids,(),aids,(),snap,"as",acceptance_snapshot_digest(acc))
    return state,rel,policy


def test_release_rejects_missing_assessment_per_nonwaived_obligation(monkeypatch):
    monkeypatch.setattr("sclass_semantics_v6_0_1.evaluate_evidence_composition", lambda *a, **k: types.SimpleNamespace(verdict=ClosureVerdict.SATISFIED))
    state,rel,policy=_assessment_release_fixture(2,1)
    out=evaluate_release(state,rel,policy,UtcInstant(100))
    assert out.verdict is not ReleaseVerdict.READY
    assert out.evaluation_digest is not None


def test_release_rejects_extra_assessment(monkeypatch):
    monkeypatch.setattr("sclass_semantics_v6_0_1.evaluate_evidence_composition", lambda *a, **k: types.SimpleNamespace(verdict=ClosureVerdict.SATISFIED))
    state,rel,policy=_assessment_release_fixture(2,3)
    out=evaluate_release(state,rel,policy,UtcInstant(100))
    assert out.verdict is not ReleaseVerdict.READY


def test_release_rejects_duplicate_assessments_for_same_obligation(monkeypatch):
    monkeypatch.setattr("sclass_semantics_v6_0_1.evaluate_evidence_composition", lambda *a, **k: types.SimpleNamespace(verdict=ClosureVerdict.SATISFIED))
    state,rel,policy=_assessment_release_fixture(1,1)
    a=state.assessments["a0"]
    state.assessments=state.assessments
    # Two supplied references to the same assessment are rejected before cardinality evaluation.
    rel2=ReleaseState(rel.release_id,rel.release_policy_version,rel.artifact_digest,rel.target_environment,rel.blocking_obligations,rel.waivers,("a0","a0"),rel.provenance,rel.engineering_snapshot,rel.acceptance_snapshot_id,rel.acceptance_snapshot_digest)
    out=evaluate_release(state,rel2,policy,UtcInstant(100))
    assert out.verdict is not ReleaseVerdict.READY

# --- V6 adversarial S0/S1 gates ---
def _commit_for(event, state, commit_id):
    sd=engineering_state_digest(state)
    provisional=CommitRecord(commit_id,"w",(event.event_id,"state:w"),(event.event_hash,sd),("event","state"),
        event.previous_event_hash,event.event_hash,state.state_revision,event.event_sequence,event.event_sequence,COMMIT_SCHEMA_VERSION,
        Digest("sha256:"+"0"*64),CommitState.COMMITTED,1,1000000000,sd)
    return replace(provisional,commit_digest=commit_record_digest(provisional))

def test_v6_eventstore_cas_rejects_stale_writer(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"cas.db")); state0=_canonical_genesis()
    e1=_shutdown_event(1,GENESIS_EVENT_HASH,"c1")
    s1=REFERENCE_REDUCER.reduce(state0,e1); c1=_commit_for(e1,s1,"c1")
    assert store.append(e1,c1,GENESIS_EVENT_HASH)[0] is AppendResult.APPENDED
    e2=_shutdown_event(2,e1.event_hash,"c2")
    s2=REFERENCE_REDUCER.reduce(s1,e2); c2=_commit_for(e2,s2,"c2")
    stale=store.append(e2,c2,GENESIS_EVENT_HASH)
    assert stale[0] is AppendResult.HEAD_MISMATCH
    assert store.head("w").sequence==1

def test_v6_state_digest_binds_unchanged_and_derived_state():
    state=_minimal_state(); d1=engineering_state_digest(state)
    altered=replace(state,reducer_facts=fmap((("tampered",True),)))
    assert engineering_state_digest(altered)!=d1

def test_strong_canonical_event_constructor_enforces_schema_before_persistence():
    with pytest.raises(TypeError):
        CanonicalEvent.create("bad","c","w",1,EventType.WORK_ASSIGNED,1,"n",actor(),"caus","corr",fmap((("worker_id",123),)),GENESIS_EVENT_HASH,"pol","sdk",UtcInstant(1))
    with pytest.raises(ValueError):
        CanonicalEvent.create("bad2","c","w",1,EventType.WORK_ASSIGNED,2,"n",actor(),"caus","corr",fmap((("worker_id","w"),)),GENESIS_EVENT_HASH,"pol","sdk",UtcInstant(1))
    with pytest.raises(ValueError):
        CanonicalEvent.create("bad3","c","w",1,EventType.WORK_ASSIGNED,1,"n",actor(),"caus","corr",fmap((("worker_id","w"),("unexpected",True))),GENESIS_EVENT_HASH,"pol","sdk",UtcInstant(1))


def test_v6_event_schema_is_rejected_before_persistence(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"schema.db")); state=_canonical_genesis()
    with pytest.raises(TypeError):
        CanonicalEvent.create("bad","bad","w",1,EventType.WORK_ASSIGNED,1,"n",actor(),"caus","corr",fmap((("worker_id",123),)),GENESIS_EVENT_HASH,"pol","sdk",UtcInstant(1))
    e=_shutdown_event(1,GENESIS_EVENT_HASH,"bad")
    tampered=object.__new__(CanonicalEvent)
    for f in fields(CanonicalEvent):
        object.__setattr__(tampered,f.name,getattr(e,f.name))
    object.__setattr__(tampered,"payload",fmap((("reason",123),)))
    derived=REFERENCE_REDUCER.reduce(state,e)
    commit=_commit_for(e,derived,"bad")
    with pytest.raises((ValueError,TypeError)): store.append(tampered,commit,GENESIS_EVENT_HASH)
    assert store.head("w").sequence==0
    store.close()

def test_v6_checkpoint_restore_and_corruption_detection(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"checkpoint.db")); state=_canonical_genesis()
    e=_shutdown_event(1,GENESIS_EVENT_HASH,"cp")
    state=REFERENCE_REDUCER.reduce(state,e); c=_commit_for(e,state,"cp")
    assert store.append(e,c,GENESIS_EVENT_HASH)[0] is AppendResult.APPENDED
    ref=CheckpointRef("cp1",state.event_sequence,state.state_digest,"cp")
    store.checkpoint(ref,state)
    restored=store.restore("cp1")
    assert engineering_state_digest(restored)==state.state_digest
    store._db.execute("UPDATE checkpoints SET state_digest=? WHERE checkpoint_id=?",("sha256:"+"f"*64,"cp1"))
    with pytest.raises(ValueError): store.restore("cp1")

def test_v6_multi_event_atomic_transaction(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"batch.db")); state0=_canonical_genesis()
    e1=_shutdown_event(1,GENESIS_EVENT_HASH,"batch")
    e2=_shutdown_event(2,e1.event_hash,"batch")
    state=REFERENCE_REDUCER.replay(state0,(e1,e2))
    sd=engineering_state_digest(state)
    c0=CommitRecord("batch","w",(e1.event_id,e2.event_id,"state:w"),(e1.event_hash,e2.event_hash,sd),("event","event","state"),GENESIS_EVENT_HASH,e2.event_hash,state.state_revision,1,2,COMMIT_SCHEMA_VERSION,Digest("sha256:"+"0"*64),CommitState.COMMITTED,1,1000000000,sd)
    c=replace(c0,commit_digest=commit_record_digest(c0))
    result,head=store.append_batch((e1,e2),c,GENESIS_EVENT_HASH)
    assert result is AppendResult.APPENDED and head.sequence==2
    assert store.verify_chain("w",1,2) is ChainStatus.VALID
    assert tuple(e.event_sequence for e in store.read("w",1,2))==(1,2)



# --- STRONG CANDIDATE gates: adversarial canonical-state / provenance / durability ---

def test_strong_store_cannot_accept_caller_selected_projection(tmp_path):
    import inspect
    store=SQLiteEventStore(str(tmp_path/"projection.db")); genesis=_canonical_genesis()
    e=_shutdown_event(1,GENESIS_EVENT_HASH,"p1")
    derived=REFERENCE_REDUCER.reduce(genesis,e); commit=_commit_for(e,derived,"p1")
    assert "state" not in inspect.signature(store.append).parameters
    with pytest.raises(TypeError):
        store.append(e,derived,commit,GENESIS_EVENT_HASH)
    # Canonical append has no projection argument; the store derives it internally.
    assert store.append(e,commit,GENESIS_EVENT_HASH)[0] is AppendResult.APPENDED


def test_strong_store_rejects_prepared_visibility(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"prepared.db")); genesis=_canonical_genesis()
    e=_shutdown_event(1,GENESIS_EVENT_HASH,"prep")
    derived=REFERENCE_REDUCER.reduce(genesis,e)
    committed=_commit_for(e,derived,"prep")
    prepared=replace(committed,state=CommitState.PREPARED,committed_at_epoch_ns=None,commit_digest=Digest("sha256:"+"0"*64))
    prepared=replace(prepared,commit_digest=commit_record_digest(prepared))
    with pytest.raises(ValueError, match="COMMITTED"):
        store.append(e,prepared,GENESIS_EVENT_HASH)
    assert store.head("w").sequence==0


def test_strong_store_rejects_mixed_commit_ids_before_mutation(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"mixed.db")); genesis=_canonical_genesis()
    e1=_shutdown_event(1,GENESIS_EVENT_HASH,"c1")
    e2=_shutdown_event(2,e1.event_hash,"c2")
    derived=REFERENCE_REDUCER.replay(genesis,(e1,e2))
    sd=engineering_state_digest(derived)
    bad=CommitRecord("c1","w",(e1.event_id,e2.event_id,"state:w"),(e1.event_hash,e2.event_hash,sd),("event","event","state"),GENESIS_EVENT_HASH,e2.event_hash,derived.state_revision,1,2,COMMIT_SCHEMA_VERSION,Digest("sha256:"+"0"*64),CommitState.COMMITTED,1,1000000000,sd)
    bad=replace(bad,commit_digest=commit_record_digest(bad))
    with pytest.raises(ValueError, match="commit ID"):
        store.append_batch((e1,e2),bad,GENESIS_EVENT_HASH)
    assert store.head("w").sequence==0


def test_strong_head_fails_when_projection_is_corrupted(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"corrupt-projection.db")); genesis=_canonical_genesis()
    e=_shutdown_event(1,GENESIS_EVENT_HASH,"cp")
    derived=REFERENCE_REDUCER.reduce(genesis,e); commit=_commit_for(e,derived,"cp")
    store.append(e,commit,GENESIS_EVENT_HASH)
    store._db.execute("UPDATE canonical_projection SET state_digest=? WHERE workspace_id=?",("sha256:"+"e"*64,"w"))
    with pytest.raises(ValueError, match="projection"):
        store.head("w")


def test_strong_history_fails_when_commit_record_is_corrupted(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"corrupt-commit.db")); genesis=_canonical_genesis()
    e=_shutdown_event(1,GENESIS_EVENT_HASH,"cc")
    derived=REFERENCE_REDUCER.reduce(genesis,e); commit=_commit_for(e,derived,"cc")
    store.append(e,commit,GENESIS_EVENT_HASH)
    row=store._db.execute("SELECT record_blob FROM canonical_commits WHERE commit_id='cc'").fetchone()
    blob=bytearray(row[0]); blob[-1] ^= 1
    store._db.execute("UPDATE canonical_commits SET record_blob=? WHERE commit_id='cc'",(bytes(blob),))
    with pytest.raises(Exception):
        store.read("w",1,1)


def test_strong_store_supports_multiple_sequential_commits(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"sequential.db")); genesis=_canonical_genesis()
    e1=_shutdown_event(1,GENESIS_EVENT_HASH,"seq1")
    s1=REFERENCE_REDUCER.reduce(genesis,e1); c1=_commit_for(e1,s1,"seq1")
    assert store.append(e1,c1,GENESIS_EVENT_HASH)[0] is AppendResult.APPENDED
    e2=_shutdown_event(2,e1.event_hash,"seq2")
    s2=REFERENCE_REDUCER.reduce(s1,e2); c2=_commit_for(e2,s2,"seq2")
    assert store.append(e2,c2,e1.event_hash)[0] is AppendResult.APPENDED
    assert store.head("w").sequence==2
    assert engineering_state_digest(store.replay("w"))==s2.state_digest


def test_strong_genesis_replay_equals_checkpoint_replay(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"replay.db")); genesis=_canonical_genesis()
    e1=_shutdown_event(1,GENESIS_EVENT_HASH,"rp2")
    e2=_shutdown_event(2,e1.event_hash,"rp2")
    derived=REFERENCE_REDUCER.replay(genesis,(e1,e2))
    sd=engineering_state_digest(derived)
    commit=CommitRecord("rp2","w",(e1.event_id,e2.event_id,"state:w"),(e1.event_hash,e2.event_hash,sd),("event","event","state"),GENESIS_EVENT_HASH,e2.event_hash,derived.state_revision,1,2,COMMIT_SCHEMA_VERSION,Digest("sha256:"+"0"*64),CommitState.COMMITTED,1,1000000000,sd)
    commit=replace(commit,commit_digest=commit_record_digest(commit))
    store.append_batch((e1,e2),commit,GENESIS_EVENT_HASH)
    ref=CheckpointRef("r2",2,derived.state_digest,"rp2")
    store.checkpoint(ref,derived)
    from_genesis=store.replay("w")
    from_checkpoint=store.replay("w",ref)
    assert engineering_state_digest(from_genesis)==engineering_state_digest(from_checkpoint)==derived.state_digest


def test_strong_duplicate_canonical_identity_rejects_replacement():
    initial=_minimal_state()
    e0=_reducer_event(1,GENESIS_EVENT_HASH,EventType.WORK_ASSIGNED,payload={"worker_id":"worker-1"},commit="dup")
    s0=REFERENCE_REDUCER.reduce(initial,e0)
    ad1=AuthorizationDecision("d","n",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64),AuthorizationState.ALLOW,Authority.USER,"system",(),"one",UtcInstant(1),UtcInstant(10),"o","worker-1",Digest("sha256:"+"3"*64),"pol",empty_scope(),"s",control_profile_digest=digest("sclass/control-profile/v1",_minimal_policy().risk_mapping.control_profiles[RiskTier.LOW]),work_node_id="n")
    lineage=canonical_governing_budget_lineage(s0,"n"); frontier=canonical_causal_frontier(s0,ad1,lineage,RiskTier.LOW)
    e1=_reducer_event(2,e0.event_hash,EventType.AUTHORIZATION_GRANTED,payload={"authorization_decision":ad1,"governing_budget_lineage":lineage,"causal_frontier":frontier},commit="dup")
    s1=REFERENCE_REDUCER.reduce(s0,e1)
    ad2=replace(ad1,rationale="different")
    lineage2=canonical_governing_budget_lineage(s1,"n"); frontier2=canonical_causal_frontier(s1,ad2,lineage2,RiskTier.LOW)
    e2=_reducer_event(3,e1.event_hash,EventType.AUTHORIZATION_GRANTED,payload={"authorization_decision":ad2,"governing_budget_lineage":lineage2,"causal_frontier":frontier2},commit="dup")
    with pytest.raises(ValueError, match="duplicate authorization decision identity"):
        REFERENCE_REDUCER.reduce(s1,e2)


def test_strong_commit_separates_revision_from_state_digest(tmp_path):
    store=SQLiteEventStore(str(tmp_path/"identity.db")); genesis=_canonical_genesis()
    e=_shutdown_event(1,GENESIS_EVENT_HASH,"id")
    derived=REFERENCE_REDUCER.reduce(genesis,e); commit=_commit_for(e,derived,"id")
    assert commit.resulting_state_revision == derived.state_revision
    assert commit.resulting_state_digest == derived.state_digest
    assert str(commit.resulting_state_revision) != str(commit.resulting_state_digest)


def test_strong_safe_unpickler_blocks_global_code_execution():
    # Protocol 0 GLOBAL reference to builtins.eval; no callable from DB bytes is permitted.
    malicious=b"cbuiltins\neval\n(S'1+1'\ntR."
    with pytest.raises(ValueError, match="unsafe pickle global blocked"):
        semantics._safe_pickle_loads(malicious)


def test_strong_s1_crash_matrix_is_atomic(tmp_path):
    import os, subprocess, sys, textwrap
    module_dir=Path(__file__).parent
    db=tmp_path/"crash.db"
    script=textwrap.dedent(f"""
        import os, sys
        sys.path.insert(0, {str(module_dir)!r})
        from sclass_semantics_v6_0_1 import *
        stage=os.environ.get("SCLASS_KILL_STAGE")
        def hook(s):
            if s == stage:
                os._exit(137)
        def actor(): return ActorIdentity("system",ActorKind.SYSTEM,None)
        store=SQLiteEventStore({str(db)!r}, fault_injector=hook)
        e=CanonicalEvent.create("e1","crash","w",1,EventType.SHUTDOWN_REQUESTED,1,"system",actor(),"caus","corr",FrozenMap.from_items((("reason","test"),)),GENESIS_EVENT_HASH,"pol","sdk",UtcInstant(1))
        state=genesis_engineering_state("w")
        derived=REFERENCE_REDUCER.reduce(state,e)
        c=CommitRecord("crash","w",(e.event_id,"state:w"),(e.event_hash,engineering_state_digest(derived)),("event","state"),GENESIS_EVENT_HASH,e.event_hash,derived.state_revision,1,1,COMMIT_SCHEMA_VERSION,Digest("sha256:"+"0"*64),CommitState.COMMITTED,1,1,engineering_state_digest(derived))
        c=replace(c,commit_digest=commit_record_digest(c))
        store.append(e,c,GENESIS_EVENT_HASH)
        os._exit(0)
    """)
    stages=[
        ("K1_BEFORE_DURABLE_INTENT",0),
        ("K2_AFTER_COMMIT_RECORD",0),
        ("K3_AFTER_EVENT_ROWS",0),
        ("K4_AFTER_PROJECTION",0),
        ("K5_BEFORE_COMMIT",0),
        ("K6_AFTER_COMMIT",1),
    ]
    for stage,expected_sequence in stages:
        if db.exists(): db.unlink()
        env=os.environ.copy(); env["SCLASS_KILL_STAGE"]=stage
        proc=subprocess.run([sys.executable,"-c",script],env=env,cwd=str(module_dir),capture_output=True)
        assert proc.returncode == 137, (stage,proc.stdout,proc.stderr)
        reopened=SQLiteEventStore(str(db))
        assert reopened.head("w").sequence==expected_sequence
        if expected_sequence:
            assert reopened.verify_chain("w",1,1) is ChainStatus.VALID
            assert reopened.replay("w").event_sequence==1
        else:
            assert reopened.head("w").hash==GENESIS_EVENT_HASH
        reopened.close()


def test_strong_requirement_lifecycle_index_is_domain_derived():
    r=Requirement("rq","description",Authority.USER,SourceType.USER_INPUT,Digest("sha256:"+"1"*64),DiscoveryMethod.USER_STATED,10000,"o",None,())
    e1=_reducer_event(1,GENESIS_EVENT_HASH,EventType.REQUIREMENT_DISCOVERED,aggregate="rq",payload={"requirement":r},commit="req")
    s1=REFERENCE_REDUCER.reduce(_minimal_state(),e1)
    assert s1.requirements["rq"].status is RequirementStatus.PROPOSED
    assert s1.reducer_facts["RequirementStatus"]["rq"]==RequirementStatus.PROPOSED.value
    e2=_reducer_event(2,e1.event_hash,EventType.REQUIREMENT_CONFIRMED,aggregate="rq",payload={"requirement_id":"rq"},commit="req")
    s2=REFERENCE_REDUCER.reduce(s1,e2)
    assert s2.requirements["rq"].status is RequirementStatus.CONFIRMED
    assert s2.reducer_facts["RequirementStatus"]["rq"]==RequirementStatus.CONFIRMED.value


def test_causal_frontier_is_fresh_per_authorization_decision():
    initial=_minimal_state()
    e1=_reducer_event(1,GENESIS_EVENT_HASH,EventType.WORK_ASSIGNED,payload={"worker_id":"worker-1"})
    state=ReferenceReducer().reduce(initial,e1)
    scope=empty_scope()
    base=("node-1",Digest("sha256:"+"1"*64),Digest("sha256:"+"2"*64))
    d1=AuthorizationDecision("decision-1","n",base[1],base[2],AuthorizationState.ALLOW,Authority.USER,"principal",(),"r",UtcInstant(1),UtcInstant(100),"o","worker-1",Digest("sha256:"+"3"*64),"pol",scope,"s",control_profile_digest=digest("sclass/control-profile/v1",_minimal_policy().risk_mapping.control_profiles[RiskTier.LOW]),work_node_id="n")
    d2=replace(d1,decision_id="decision-2",decided_at=UtcInstant(2))
    lineage1=canonical_governing_budget_lineage(state,"n")
    lineage2=canonical_governing_budget_lineage(state,"n")
    f1=canonical_causal_frontier(state,d1,lineage1,RiskTier.LOW)
    f2=canonical_causal_frontier(state,d2,lineage2,RiskTier.LOW)
    assert f1.frontier_id != f2.frontier_id
    assert f1.authorization_epoch != f2.authorization_epoch


def test_lease_revoke_is_materialized_and_not_only_machine_state():
    initial=_minimal_state()
    lease=ExecutionLease("lease-1","w","n",Digest("sha256:"+"1"*64),1,"attempt-1",Digest("sha256:"+"2"*64),"lineage","reservation-1","s",Digest("sha256:"+"3"*64),"auth","o", "pol", "worker",ExecutionIdentity("/bin/true","/bin/true",Digest("sha256:"+"4"*64),"v","",Digest("sha256:"+"5"*64),Digest("sha256:"+"6"*64),1,()),Digest("sha256:"+"7"*64),"rev",1,UtcInstant(1),UtcInstant(100))
    facts=dict(initial.reducer_facts.items()); facts["LeaseState"]=fmap((("lease-1",LeaseState.ACTIVE.value),)); state=replace(initial,leases=fmap((("lease-1",LeaseRecord(lease,LeaseState.ACTIVE)),)),reducer_facts=fmap(facts.items()))
    e=_reducer_event(1,GENESIS_EVENT_HASH,EventType.LEASE_REVOKED,aggregate="lease-1",payload={"lease_id":"lease-1"})
    state2=ReferenceReducer().reduce(state,e)
    assert state2.leases["lease-1"].state is LeaseState.REVOKED
