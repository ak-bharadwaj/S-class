"""E2E Test Suite Helpers and Canonical Builders.

Authoritative source of sample data, canonical state initialization, and
contract verification fixtures across Tiers 1-4.
"""
from __future__ import annotations

import sys
from dataclasses import fields, replace
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
for _subdir in ("10-CONFORMANCE", "20-RUNTIME", "src"):
    _path_str = str(_repo_root / _subdir)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sclass_semantics_v6_0_1 import (
    GENESIS_EVENT_HASH,
    AcceptanceContract,
    AcceptanceSnapshot,
    AcceptedRiskWaiver,
    ActionType,
    ActorIdentity,
    ActorKind,
    ApprovalKind,
    ApprovalRecord,
    AssessmentMethod,
    AssessmentVerdict,
    Authority,
    AuthorizationMode,
    AuthorizationRules,
    BoundaryViolationRecord,
    BudgetLevel,
    BudgetReservation,
    BudgetReservationState,
    BudgetRules,
    CanonicalEvent,
    CanonicalObjective,
    CausalFrontier,
    CheckpointRef,
    ClosureVerdict,
    CommitRecord,
    CommitState,
    CompositionMode,
    ContentManifestState,
    ControlProfile,
    DataClassification,
    DataClassificationPolicy,
    Decision,
    DecisionOption,
    DecisionOutcome,
    DependencyRules,
    Digest,
    DiscoveryMethod,
    EffectScope,
    EngineeringSnapshot,
    EngineeringState,
    EnvironmentFingerprint,
    EventType,
    EvidenceClosure,
    EvidenceComposition,
    EvidenceDependencySet,
    EvidenceKind,
    EvidenceRules,
    ExecutionIdentity,
    ExecutionLease,
    ExternalEffect,
    FrozenMap,
    GitState,
    Idempotency,
    IndependenceLevel,
    IndependenceProfile,
    IndependentAssessment,
    InDoubtRecord,
    InvalidationSet,
    IsolationLevel,
    LeaseRecord,
    LeaseState,
    MutationDigest,
    ObjectiveRevision,
    Obligation,
    ObligationGraph,
    ObligationKind,
    ObligationStatus,
    ObservationRecord,
    Policy,
    ProviderEgressPolicy,
    QuiescenceProof,
    RedactionPolicy,
    ReleaseEvaluation,
    ReleaseRules,
    ReleaseState,
    ReleaseVerdict,
    RepairObligation,
    RepairPlan,
    RepairStrategy,
    RequestedEffect,
    RequiredEvidence,
    Requirement,
    ResourceBudget,
    RetentionPolicy,
    RetryBudget,
    RetryRules,
    RiskMapping,
    RiskTier,
    SemanticGraph,
    SideEffectReceipt,
    SideEffectStatus,
    SignatureBlock,
    SourceType,
    StructuredIntent,
    TargetSnapshot,
    TelemetryPrivacyPolicy,
    UtcInstant,
    VerificationPlan,
    VerificationStep,
    VerifiedWorkspaceDelta,
    WaiverRules,
    WorkGraph,
    WorkNode,
    WorkNodeStatus,
    commit_record_digest,
    digest,
    quiescence_proof_digest,
)


def fmap(items=()):
    return FrozenMap.from_items(items)


def z_budget(tokens: int = 1000, duration_ms: int = 5000) -> ResourceBudget:
    return ResourceBudget(10, 10, 10, tokens, 10, 10, 10, 10, 10, duration_ms, 10)


def empty_scope(**kw) -> EffectScope:
    return EffectScope(
        kw.get("fs_rules", ()),
        kw.get("process_rules", ()),
        kw.get("network_rules", ()),
        kw.get("allowed_env", fmap()),
        kw.get("working_directory", "."),
        kw.get("credential_grants", ()),
        kw.get("external_effect_rules", ()),
        kw.get("resource_budget", z_budget()),
    )


def req_effect(fs=(), process=(), network=(), environment=None, budget=None) -> RequestedEffect:
    return RequestedEffect(
        tuple(fs),
        tuple(process),
        tuple(network),
        fmap(tuple((environment or {}).items())),
        (),
        (),
        budget or z_budget(),
    )


def make_actor(kind: ActorKind = ActorKind.SYSTEM, aid: str = "system") -> ActorIdentity:
    exec_id = None
    if kind is ActorKind.WORKER:
        exec_id = ExecutionIdentity(
            "/bin/worker", "/bin/worker", Digest("sha256:" + "1" * 64),
            "1.0", "python", Digest("sha256:" + "2" * 64),
            Digest("sha256:" + "3" * 64), 1000, ()
        )
    return ActorIdentity(aid, kind, exec_id)


def sample_keypair():
    priv = Ed25519PrivateKey.generate()
    pub_raw = priv.public_key().public_bytes_raw()
    return priv, pub_raw


def make_signature(priv: Ed25519PrivateKey, message: bytes, key_id: str = "key-1") -> SignatureBlock:
    sig_bytes = priv.sign(message)
    return SignatureBlock("ed25519", key_id, "root", "c1", sig_bytes)


def make_minimal_policy(policy_id: str = "policy-test", version: str = "pol-1") -> Policy:
    profiles = fmap(
        (tier, ControlProfile(
            AuthorizationMode.AUTO,
            IsolationLevel.PROCESS,
            (),
            IndependenceProfile(
                IndependenceLevel.NONE, IndependenceLevel.NONE,
                IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE
            ),
            3,
            True,
        ))
        for tier in RiskTier
    )
    risk = RiskMapping("risk-test", (), profiles)
    auth = AuthorizationRules(1000, 1000, ("worker",), False, ())
    evidence = EvidenceRules((), False, 1024)
    retry = RetryRules(3, 1)
    budget = BudgetRules(z_budget(), 5000)
    rel = ReleaseRules(("test",), (), True, 1000)
    waiver = WaiverRules(("sec-admin", "policy-admin"), 1000, False)
    dep = DependencyRules(False, True)
    dc = DataClassificationPolicy(DataClassification.PUBLIC, ())
    red = RedactionPolicy((), "[REDACTED]", False)
    egress = ProviderEgressPolicy((), DataClassification.SECRET, (), False, True)
    retention = RetentionPolicy(1, 1, 1)
    telemetry = TelemetryPrivacyPolicy((), True, True)
    return Policy(
        policy_id, version, risk, auth, evidence, retry, budget,
        egress, rel, waiver, dep, dc, red, retention, telemetry,
        1, "floor-1", Digest("sha256:" + "f" * 64),
    )


def sample_target_snapshot(snap_id: str = "snap-target-1", workspace: str = "w") -> TargetSnapshot:
    return TargetSnapshot(
        snap_id, workspace,
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        None, None,
        Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64), (), fmap(), "pol-1", UtcInstant(1)
    )


def sample_structured_intent(goal: str = "Implement test feature") -> StructuredIntent:
    return StructuredIntent(1, goal, ("scope-a",), (), ("src/mod.py",), ("tests pass",))


def sample_objective(workspace: str = "w", obj_id: str = "obj-1") -> CanonicalObjective:
    snap = EngineeringSnapshot(
        "es-1", 1, Digest("sha256:" + "6" * 64),
        ContentManifestState(Digest("sha256:" + "7" * 64), 0),
        "wm-1", "pol-1", "risk-test", "sdk-1", "toolchain-1", Digest("sha256:" + "8" * 64)
    )
    rev = ObjectiveRevision(
        "rev-1", 1, sample_structured_intent(), (), (), (), snap, None
    )
    return CanonicalObjective(obj_id, workspace, (rev,))


def sample_requirement(req_id: str = "rq-1", obj_rev: str = "rev-1") -> Requirement:
    return Requirement(
        req_id, "Authorize and verify tests", Authority.USER,
        SourceType.USER_INPUT, Digest("sha256:" + "1" * 64),
        DiscoveryMethod.USER_STATED, 10000, obj_rev, None, ()
    )


def sample_decision(dec_id: str = "dec-1", pol_version: str = "pol-1") -> Decision:
    opt1 = DecisionOption("opt-1", "Option A", 10, 9000)
    opt2 = DecisionOption("opt-2", "Option B", 20, 9500)
    return Decision(
        dec_id, "Which architecture pattern to use?", (opt1, opt2),
        "opt-1", "Simpler and compliant", (), (), pol_version,
        "architecture", (), None, "architect"
    )


def sample_decision_outcome(dec_id: str = "dec-1") -> DecisionOutcome:
    return DecisionOutcome(dec_id, "SUCCESS", 10, 9000, UtcInstant(10))


def sample_obligation(obl_id: str = "obl-1", obj_id: str = "obj-1", contract_id: str = "contract-1") -> Obligation:
    return Obligation(
        obl_id, obj_id, 1, "Verify module functionality",
        ObligationKind.FUNCTIONAL, RiskTier.LOW, ObligationStatus.PENDING,
        frozenset(), contract_id, None, "plan-1"
    )


def sample_acceptance_contract(contract_id: str = "contract-1", obl_id: str = "obl-1") -> AcceptanceContract:
    ind = IndependenceProfile(IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE)
    req = RequiredEvidence("req-key-1", EvidenceKind.BEHAVIORAL, "verifier-1", ind, (), True, 1)
    comp = EvidenceComposition(CompositionMode.ALL_OF, 0)
    return AcceptanceContract(
        contract_id, obl_id, 1, (req,), comp, WaiverRules((), 1000, False), Authority.USER
    )


def sample_verification_plan(plan_id: str = "plan-1", obl_id: str = "obl-1", contract_rev: int = 1) -> VerificationPlan:
    step = VerificationStep("step-1", EvidenceKind.BEHAVIORAL, "verifier-1", "1.0", Digest("sha256:" + "c" * 64), 5000, z_budget())
    return VerificationPlan(plan_id, obl_id, 1, contract_rev, (step,))


def sample_work_graph(wg_id: str = "wg-1", node_id: str = "n-1", obl_id: str = "obl-1") -> WorkGraph:
    node = WorkNode(
        node_id, obl_id, frozenset({obl_id}), "Execute step", ActionType.CODE_READ,
        req_effect(), empty_scope(), 100, 50, WorkNodeStatus.READY,
        Idempotency.IDEMPOTENT, None, "retry-1", RiskTier.LOW, 1, "lineage-1"
    )
    sem_graph = SemanticGraph((node_id,), ())
    return WorkGraph(wg_id, "rev-1", "og-1", "pol-1", "wm-1", sem_graph, fmap(((node_id, node),)))


def sample_lease(lease_id: str = "lease-1", workspace: str = "w", node_id: str = "n-1", token: int = 1) -> LeaseRecord:
    ex_id = ExecutionIdentity(
        "/bin/worker", "/bin/worker", Digest("sha256:" + "4" * 64),
        "1.0", "python", Digest("sha256:" + "5" * 64),
        Digest("sha256:" + "6" * 64), 1000, ()
    )
    lease = ExecutionLease(
        lease_id, workspace, node_id, Digest("sha256:" + "1" * 64),
        1, "attempt-1", Digest("sha256:" + "2" * 64), "lineage-1",
        "res-1", "snap-target-1", Digest("sha256:" + "3" * 64), "auth-lease-1",
        "rev-1", "pol-1", "worker-1", ex_id, Digest("sha256:" + "7" * 64),
        "rev-state-1", token, UtcInstant(1), UtcInstant(1000)
    )
    return LeaseRecord(lease, LeaseState.ACTIVE)


def sample_budget_reservation(res_id: str = "res-1", workspace: str = "w") -> BudgetReservation:
    return BudgetReservation(
        res_id, workspace, "req-1", BudgetLevel.WORK_NODE, None,
        "lineage-1", z_budget(), UtcInstant(5000), BudgetReservationState.RESERVED
    )


def sample_approval_record(app_id: str = "app-1", workspace: str = "w") -> ApprovalRecord:
    priv, _ = sample_keypair()
    sig = make_signature(priv, b"dummy approval signature")
    return ApprovalRecord(
        app_id, ApprovalKind.DUAL_AUTHORIZATION, "principal-1", "admin",
        workspace, Digest("sha256:" + "t" * 64), "pol-1",
        Digest("sha256:" + "s" * 64), UtcInstant(1), UtcInstant(1000), sig
    )


def sample_quiescence_proof(proof_id: str = "proof-1", lease_id: str = "lease-1") -> QuiescenceProof:
    priv, _ = sample_keypair()
    dummy_sig = make_signature(priv, b"quiescence", key_id="attest-key-1")
    exec_id_dig = Digest("sha256:" + "e" * 64)
    # Proof digest preimage
    temp = QuiescenceProof(
        proof_id, "boundary-1", "process_tree_drain",
        exec_id_dig, lease_id, 1, "attempt-1",
        "worker-1", 12345, 1000, UtcInstant(50),
        Digest("sha256:" + "0" * 64), "attest-key-1", dummy_sig
    )
    p_dig = quiescence_proof_digest(temp)
    return replace(temp, proof_digest=p_dig)


def sample_observation(obs_id: str = "obs-1", proof: QuiescenceProof | None = None) -> ObservationRecord:
    git_st = GitState("commit-sha", "main", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64))
    env_fp = EnvironmentFingerprint("linux", "x86_64", Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64), None)
    return ObservationRecord(
        obs_id, "req-1", "n-1", 1, "attempt-1",
        Digest("sha256:" + "t" * 64), "lineage-1", "worker-1",
        MutationDigest(Digest("sha256:" + "m" * 64)), (), git_st, env_fp,
        make_actor(ActorKind.WORKER, "worker-1"), (), UtcInstant(60), "filesystem", (),
        None, "snap-before", "snap-after", Digest("sha256:" + "a" * 64),
        proof, False
    )


def sample_side_effect_receipt(eff_id: str = "eff-1", workspace: str = "w") -> SideEffectReceipt:
    eff_obj = ExternalEffect("database", "row_insert", 1)
    eff_dig = digest("sclass/external-effect/v1", eff_obj)
    return SideEffectReceipt(
        eff_id, "req-1", workspace, "row_insert", "database",
        make_actor(ActorKind.SYSTEM), Digest("sha256:" + "b" * 64),
        Digest("sha256:" + "a" * 64), eff_dig, UtcInstant(100),
        SideEffectStatus.OBSERVED, None, 1
    )


def sample_in_doubt_record(node_id: str = "n-1", seq: int = 1) -> InDoubtRecord:
    return InDoubtRecord(node_id, "Quiescence proof lost during power failure", ("eff-1",), seq)


def sample_repair_plan(plan_id: str = "repair-plan-1") -> RepairPlan:
    rep = RepairObligation(
        "fail-1", None, "network_partition", "rev-1", "snap-target-1",
        frozenset({"obl-1"}), "wg-1", RepairStrategy.RETRY_SAME,
        (EvidenceKind.BEHAVIORAL,), 1, z_budget()
    )
    return RepairPlan(plan_id, Digest("sha256:" + "f" * 64), (rep,), RepairStrategy.RETRY_SAME)


def sample_retry_budget(b_id: str = "retry-1", node_id: str = "n-1", consumed: int = 0) -> RetryBudget:
    fp = Digest("sha256:" + "f" * 64) if consumed > 0 else None
    return RetryBudget(b_id, node_id, 3, consumed, consumed, fp, consumed + 1)


def sample_verified_delta(delta_id: str = "delta-1") -> VerifiedWorkspaceDelta:
    return VerifiedWorkspaceDelta(
        delta_id, "snap-before", Digest("sha256:" + "b" * 64),
        Digest("sha256:" + "t" * 64), Digest("sha256:" + "a" * 64),
        (), "ev-1", "verifier-1", Digest("sha256:" + "v" * 64),
        Digest("sha256:" + "d" * 64)
    )


def sample_checkpoint_ref(chk_id: str = "chk-1", seq: int = 1) -> CheckpointRef:
    return CheckpointRef(chk_id, seq, Digest("sha256:" + "s" * 64), "commit-chk-1")


def sample_evidence_closure(ev_id: str = "ev-1", obl_id: str = "obl-1") -> EvidenceClosure:
    dep_set = EvidenceDependencySet((), (), True)
    comp = EvidenceComposition(CompositionMode.ALL_OF, 0)
    return EvidenceClosure(
        ev_id, obl_id, (), "snap-target-1",
        Digest("sha256:" + "t" * 64), Digest("sha256:" + "w" * 64),
        1, "pol-1", "rev-1", "wm-1", 1, 1,
        Digest("sha256:" + "c" * 64), Digest("sha256:" + "e" * 64),
        dep_set, (), (), comp, ClosureVerdict.SATISFIED
    )


def sample_invalidation_set(evidence_ids=(), obl_ids=(), node_ids=()) -> InvalidationSet:
    return InvalidationSet(frozenset(evidence_ids), frozenset(obl_ids), frozenset(node_ids))


def sample_acceptance_snapshot(snap_id: str = "acc-snap-1", workspace: str = "w") -> AcceptanceSnapshot:
    return AcceptanceSnapshot(
        snap_id, workspace, Digest("sha256:" + "t" * 64),
        "rev-1", "pol-1", fmap(), fmap(), fmap(), (), UtcInstant(100), 1
    )


def sample_independent_assessment(assessment_id: str = "assess-1", ev_id: str = "ev-1") -> IndependentAssessment:
    priv, _ = sample_keypair()
    sig = make_signature(priv, b"dummy assessment")
    ind = IndependenceProfile(IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE, IndependenceLevel.NONE)
    return IndependentAssessment(
        assessment_id, ev_id, "pol-1", "snap-target-1", "1.0",
        make_actor(ActorKind.VERIFIER, "verifier-1"), ind,
        Digest("sha256:" + "v" * 64), AssessmentMethod.AUTOMATED_RULE,
        Digest("sha256:" + "i" * 64), Digest("sha256:" + "t" * 64),
        Digest("sha256:" + "a" * 64), "policy-test",
        AssessmentVerdict.ACCEPT, "Fully conforms", UtcInstant(150), sig
    )


def sample_waiver(waiver_id: str = "waiver-1", obl_id: str = "obl-1", workspace: str = "w") -> AcceptedRiskWaiver:
    priv, _ = sample_keypair()
    sig = make_signature(priv, b"waiver signature")
    return AcceptedRiskWaiver(
        waiver_id, obl_id, (EvidenceKind.PERFORMANCE,), req_effect(),
        "pol-1", "rev-1", workspace, "sec-admin", "approval-set-1",
        "Accepted non-critical benchmark waiver", UtcInstant(100), UtcInstant(2000), sig
    )


def sample_release(rel_id: str = "rel-1") -> ReleaseState:
    snap = EngineeringSnapshot(
        "es-1", 1, Digest("sha256:" + "6" * 64),
        ContentManifestState(Digest("sha256:" + "7" * 64), 0),
        "wm-1", "pol-1", "risk-test", "sdk-1", "toolchain-1", Digest("sha256:" + "8" * 64)
    )
    return ReleaseState(
        rel_id, "pol-1", Digest("sha256:" + "a" * 64), "production",
        (), (), (), (), snap, "acc-snap-1", Digest("sha256:" + "s" * 64)
    )


def sample_release_evaluation(rel_id: str = "rel-1") -> ReleaseEvaluation:
    ev_digest = digest("sclass/release-evaluation/v3", (
        rel_id, Digest("sha256:" + "s" * 64), (), (), (),
        Digest("sha256:" + "0" * 64), ReleaseVerdict.READY, None, UtcInstant(200)
    ))
    return ReleaseEvaluation(
        rel_id, Digest("sha256:" + "s" * 64), fmap(), fmap(), fmap(),
        Digest("sha256:" + "0" * 64), ev_digest, ReleaseVerdict.READY, UtcInstant(200)
    )


def sample_boundary_violation(v_id: str = "viol-1") -> BoundaryViolationRecord:
    return BoundaryViolationRecord(
        v_id, "SYMLINK_ESCAPE", "filesystem", "req-1",
        Digest("sha256:" + "e" * 64), Digest("sha256:" + "o" * 64),
        UtcInstant(100), "worker-1", "CONTAINED"
    )


def make_minimal_state(workspace: str = "w") -> EngineeringState:
    vals = {f.name: None for f in fields(EngineeringState)}
    node = WorkNode(
        "n", "ob", frozenset({"ob"}), "test", ActionType.CODE_READ,
        req_effect(), empty_scope(), 0, 0, WorkNodeStatus.READY,
        Idempotency.IDEMPOTENT, None, "retry", RiskTier.LOW, 1, "lineage"
    )
    wg = WorkGraph("wg", "o", "og", "pol", "wm", SemanticGraph(("n",), ()), fmap((("n", node),)))
    target = sample_target_snapshot("s", workspace)
    objective = sample_objective(workspace, "obj")
    policy = make_minimal_policy()
    frontier = CausalFrontier(
        "cf-1", "cp-1", "pol", "rev-1", "og-1", "wg",
        Digest("sha256:" + "0" * 64), Digest("sha256:" + "1" * 64),
        "epoch-1", Digest("sha256:" + "a" * 64), Digest("sha256:" + "b" * 64),
        (), ("TEST",)
    )
    obl_graph = ObligationGraph(SemanticGraph((), ()), fmap())
    vals.update(
        workspace_id=workspace, state_schema_version=1, reducer_version="6.0.1",
        state_revision=Digest("sha256:" + "0" * 64), event_sequence=0,
        event_head_hash=GENESIS_EVENT_HASH, work_graph=wg, obligations=obl_graph,
        requirements=fmap(), objective=objective, workspace_snapshot_id="s",
        target_snapshot=target, causal_frontier=frontier, policy_version="pol",
        policy_digest=digest("sclass/policy/v1", policy), active_policy=policy,
        world_model_revision="wm",
        reducer_facts=fmap((
            ("WorkNodeStatus", fmap((("n", "READY"),))),
            ("ObligationStatus", fmap()),
            ("RequirementStatus", fmap()),
            ("LeaseState", fmap()),
        )),
    )
    for name in (
        "acceptance_contracts", "verification_plans", "evidence", "assessments",
        "assignments", "leases", "retry_budgets", "budget_reservations",
        "repair_plans", "waivers", "in_doubt", "releases", "verified_deltas",
        "break_glass_consumption", "approval_records", "approval_sets",
        "signature_verification_facts", "signature_verification_records",
        "causal_frontiers", "target_snapshots", "acceptance_snapshots",
        "execution_generations", "governing_budget_lineages", "authorization_decisions",
        "execution_outcomes", "checkpoints", "retry_consumptions", "verification_results",
        "observations", "quiescence_proofs", "execution_intents", "boundary_violations",
        "external_effect_receipts", "release_evaluations", "evidence_invalidations",
        "decision_outcomes", "decisions"
    ):
        vals[name] = fmap()
    return EngineeringState(**vals)


def make_event(
    seq: int,
    prev_hash: Digest,
    event_type: EventType,
    aggregate: str = "n",
    payload: dict | None = None,
    workspace: str = "w",
    commit: str = "c-1",
    actor: ActorIdentity | None = None,
    time_offset: int = 0
) -> CanonicalEvent:
    if actor is None:
        actor = make_actor(ActorKind.SYSTEM, "sys")
    f_payload = fmap((payload or {}).items())
    return CanonicalEvent.create(
        f"evt-{seq}", commit, workspace, seq, event_type, 1,
        aggregate, actor, f"caus-{seq}", f"corr-{seq}",
        f_payload, prev_hash, "pol", "sdk", UtcInstant(seq * 1000 + time_offset)
    )


def make_commit_record(
    commit_id: str,
    prev_head: Digest,
    resulting_head: Digest,
    seq_start: int,
    seq_end: int,
    workspace: str = "w"
) -> CommitRecord:
    rec_unsigned = CommitRecord(
        commit_id=commit_id,
        workspace_id=workspace,
        participant_ids=("p1",),
        participant_hashes=(Digest("sha256:" + "1" * 64),),
        participant_types=("CanonicalEvent",),
        previous_head=prev_head,
        resulting_head=resulting_head,
        resulting_state_revision="rev-1",
        event_sequence_start=seq_start,
        event_sequence_end=seq_end,
        schema_version=2,
        commit_digest=Digest("sha256:" + "0" * 64),
        state=CommitState.COMMITTED,
        prepared_at_epoch_ns=1000,
        committed_at_epoch_ns=2000,
        resulting_state_digest=None,
    )
    rec_digest = commit_record_digest(rec_unsigned)
    return replace(rec_unsigned, commit_digest=rec_digest)
