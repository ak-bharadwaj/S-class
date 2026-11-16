"""Negative and reproduction tests for CL 16 November Part IV R1 Findings.

Findings covered:
1. R1-F1 (worker.py / operating_loop.py):
   - Rejection of fabricated 0/0 metrics; genuine measurements or None.
   - Enforcing admissibility at operating-loop boundary before accepting CLAIMED_COMPLETE.
   - A result with absent measurements (None) must not progress to observation or verification.
2. R1-F3 (handoff.py):
   - Rejection of synthetic genesis digests and placeholder revisions (genesis, wm-0, epoch-genesis).
   - Missing canonical objective or world-model revision data must propagate as an error fail-closed.
3. R1-F5 (operating_loop.py):
   - Operating loop must NOT manufacture AuthorizationLeaseClaims, AuthorizationLease, ExecutionLease, or SignatureBlock.
   - Loop requires genuine caller-supplied AuthorizedWorkRequest; fails closed when omitted.
   - Observation provider must receive (proposal, worker_result) with no 1-argument fallback.
   - Observation must contain and match request ID, attempt ID, generation, worker identity, and worker-result output digest.
   - Missing fields must fail closed just like mismatched fields.
   - Positive test uses genuine AuthorizedWorkRequest, genuine WorkResult, and bound observation.
"""
from __future__ import annotations

import types
import pytest

from sclass.reference_impl import (
    ReferenceWorker,
    ReferenceHandoffCompiler,
    ReferenceOperatingLoop,
    ReferenceSQLiteStore,
    ReferenceVerificationProvider,
)
from sclass_semantics_v6_0_1 import (
    ActionType,
    ActorIdentity,
    ActorKind,
    AuthorizationLease,
    AuthorizationLeaseClaims,
    AuthorizedWorkRequest,
    BoundaryContext,
    CausalFrontier,
    ContextItem,
    ContextItemKind,
    ContextPackage,
    DataClassification,
    Digest,
    EffectScope,
    EngineeringState,
    ExecutionIdentity,
    ExecutionLease,
    FileMutation,
    FrozenMap,
    GitState,
    EnvironmentFingerprint,
    IsolationLevel,
    Obligation,
    ObligationKind,
    ObligationStatus,
    ObservationRecord,
    ProcessExecutionResult,
    RedactionReport,
    RequestedEffect,
    ResourceBudget,
    RiskTier,
    SignatureBlock,
    StateBinding,
    TargetSnapshot,
    TerminationKind,
    TokenUsage,
    TrustLevel,
    UtcInstant,
    VerificationStatus,
    WorkerClaimStatus,
    WorkerKind,
    WorkerProfile,
    WorkProposal,
    WorkResult,
    digest,
    state_binding_digest,
    target_snapshot_digest,
)


def _make_dummy_request(req_id: str = "req-test-1") -> types.SimpleNamespace:
    return types.SimpleNamespace(
        request_id=req_id,
        state_binding_digest=Digest("sha256:" + "1" * 64),
        envelope_digest=Digest("sha256:" + "2" * 64),
        execution_generation=1,
        execution_attempt_id="att-1",
        governing_budget_lineage_id="lineage-1",
        request_content_digest=Digest("sha256:" + "3" * 64),
        target_snapshot_digest=Digest("sha256:" + "4" * 64),
        proposal=types.SimpleNamespace(
            state_binding=types.SimpleNamespace(
                objective_revision="obj-rev-real",
                workgraph_revision="wg-rev-real",
            )
        ),
    )


def _make_genuine_authorized_work_request(
    obl_id: str = "obl-unsatisfied",
    req_id: str = "req-1",
    generation: int = 1,
    attempt_id: str = "attempt-1",
    worker_identity: str = "ref-worker",
) -> AuthorizedWorkRequest:
    sb = StateBinding(
        "test-ws",
        "rev-1",
        "wg-1",
        "pol-1",
        "snap-1",
        Digest("sha256:" + "1" * 64),
        Digest("sha256:" + "2" * 64),
        "lineage-1",
        generation,
        "epoch-1",
        Digest("sha256:" + "3" * 64),
    )
    sb_digest = state_binding_digest(sb)
    req_budget = ResourceBudget(1, 1, 0, 100, 0, 1, 1, 0, 0, 10, 1)
    effect = RequestedEffect(
        filesystem=(),
        subprocess=(),
        network=(),
        environment=FrozenMap.from_items(()),
        credentials=(),
        external_side_effects=(),
        requested_budget=req_budget,
    )
    req_content_digest = digest("sclass/request-content/v1", (obl_id, "req-1"))
    ctx_digest = digest("sclass/context/v1", ("test-ws", "rev-1", obl_id))
    prop = WorkProposal(
        f"prop-{obl_id}",
        obl_id,
        req_content_digest,
        sb,
        ctx_digest,
        effect,
    )
    scope = EffectScope(
        fs_rules=(),
        process_rules=(),
        network_rules=(),
        allowed_env=FrozenMap.from_items(()),
        working_directory="test-ws",
        credential_grants=(),
        external_effect_rules=(),
        resource_budget=req_budget,
    )
    claims = AuthorizationLeaseClaims(
        lease_id=f"lease-{obl_id}",
        decision_id=f"dec-{obl_id}",
        request_content_digest=req_content_digest,
        state_binding_digest=sb_digest,
        policy_version="pol-1",
        allowed_effects=scope,
        workspace_id="test-ws",
        workspace_snapshot_id="snap-1",
        audience="worker",
        nonce="nonce-1",
        issuer_identity="system",
        issued_at=UtcInstant(0),
        expires_at=UtcInstant(3600),
    )
    sig = SignatureBlock(
        algorithm="ed25519",
        key_id="system",
        trust_root="root",
        canonicalization_version="c1",
        signature=digest("sclass/lease-sig/v1", claims.lease_id).encode(),
    )
    auth_lease = AuthorizationLease(claims, sig)
    ex_identity = ExecutionIdentity(
        path="/bin/worker",
        resolved_identity=worker_identity,
        digest=digest("sclass/worker-identity/v1", worker_identity),
        version="1.0",
        interpreter="python",
        parent_executable_digest=digest("sclass/parent-exec/v1", "sclass"),
        environment_digest=digest("sclass/env/v1", "test-ws"),
        process_start_time_ns=0,
        child_lineage=(),
    )
    ex_lease = ExecutionLease(
        lease_id=f"ex-lease-{obl_id}",
        workspace_id="test-ws",
        node_id=obl_id,
        request_content_digest=req_content_digest,
        execution_generation=generation,
        execution_attempt_id=attempt_id,
        state_binding_digest=sb_digest,
        governing_budget_lineage_id="lineage-1",
        budget_reservation_id="res-1",
        workspace_snapshot_id="snap-1",
        target_snapshot_digest=sb.target_snapshot_digest,
        authorization_lease_id=auth_lease.claims.lease_id,
        objective_revision="rev-1",
        policy_version="pol-1",
        worker_identity=worker_identity,
        executable_identity=ex_identity,
        execution_environment_digest=digest("sclass/env/v1", "test-ws"),
        state_revision="rev-1",
        fencing_token=1,
        issued_at=UtcInstant(0),
        expires_at=UtcInstant(3600),
    )
    ctx_item = ContextItem(
        item_id="repo-map",
        kind=ContextItemKind.REPO_MAP,
        source_snapshot_id="snap-1",
        path=None,
        range=None,
        symbol=None,
        content_digest=ctx_digest,
        classification=DataClassification.INTERNAL,
        trust=TrustLevel.TRUSTED,
        rank=1,
        token_estimate=10,
    )
    ctx_pkg = ContextPackage(
        budget=4000,
        repo_map=ctx_item,
        items=(),
        obligation_context=obl_id,
        constraints=(),
        prior_evidence=(),
        token_accounting=TokenUsage(0, 0, 0, 0, 10, 10, 0),
        redaction=RedactionReport("pol-1", (), 0, ctx_digest),
        ranking_policy_version="ranking-v1",
    )
    env_digest = digest("sclass/envelope/v1", (req_id, sb_digest, req_content_digest))
    return AuthorizedWorkRequest(
        request_id=req_id,
        node_id=obl_id,
        execution_generation=generation,
        execution_attempt_id=attempt_id,
        governing_budget_lineage_id="lineage-1",
        budget_reservation_id="res-1",
        state_binding_digest=sb_digest,
        primary_obligation_id=obl_id,
        satisfies_obligation_ids=frozenset({obl_id}),
        action_description=f"Execute {obl_id}",
        action_type=ActionType.CODE_EDIT,
        requested_effect=effect,
        effect_scope=scope,
        context=ctx_pkg,
        constraints=(),
        proposal=prop,
        authorization_lease=auth_lease,
        execution_lease=ex_lease,
        authorization_binding_digest=digest("sclass/auth-binding/v1", (auth_lease.claims.lease_id, sb_digest)),
        envelope_digest=env_digest,
    )


def _make_mock_state():
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
        "snap-1", "test-ws", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        None, None, Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64), (), FrozenMap.from_items(()), "pol-1", UtcInstant(1)
    )
    frontier = CausalFrontier(
        "f-1", "p-1", "1.0", "rev-1", "og-1", "wg-1",
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64), "epoch-1",
        Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64), (), ("reason-1",)
    )
    return types.SimpleNamespace(
        workspace_id="test-ws",
        obligations=types.SimpleNamespace(_obligations={"obl-unsatisfied": obl}),
        objective=types.SimpleNamespace(revisions=(types.SimpleNamespace(revision_id="rev-1"),)),
        world_model=types.SimpleNamespace(revision_id="wm-rev-1"),
        world_model_revision="wm-rev-1",
        work_graph=types.SimpleNamespace(revision_id="wg-1"),
        policy_version="pol-1",
        workspace_snapshot_id="snap-1",
        target_snapshot=ts,
        causal_frontier=frontier,
        evidence={},
        budget_lineages={},
        event_head_hash=Digest("sha256:" + "1" * 64),
    )


# -----------------------------------------------------------------------------
# R1-F1: worker.py metrics authenticity & operating-loop admissibility
# -----------------------------------------------------------------------------

def test_r1_f1_worker_cannot_substitute_zero_for_absent_metrics():
    """R1-F1: Worker must not substitute 0/0 for absent measurements.

    Measurements must be None, and the result must be inadmissible.
    """
    profile = WorkerProfile("worker-1", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    worker = ReferenceWorker(
        profile,
        execution_callback=lambda req, b, h: WorkerClaimStatus.CLAIMED_COMPLETE,
    )
    req = _make_dummy_request("req-metrics-1")
    res = worker.execute(req)

    assert res.measured_tokens is None, f"Expected None for absent measured_tokens, got {res.measured_tokens}"
    assert res.measured_duration_ms is None, f"Expected None for absent measured_duration_ms, got {res.measured_duration_ms}"
    assert hasattr(worker, "is_admissible"), "ReferenceWorker must provide is_admissible"
    assert worker.is_admissible(res) is False, "WorkResult without measurements must be inadmissible"


def test_r1_f1_worker_admissible_only_with_genuine_callback_measurements():
    """R1-F1: Worker records genuine callback measurements and result is admissible."""
    profile = WorkerProfile("worker-1", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    worker = ReferenceWorker(
        profile,
        execution_callback=lambda req, b, h: (WorkerClaimStatus.CLAIMED_COMPLETE, 250, 42),
    )
    req = _make_dummy_request("req-metrics-2")
    res = worker.execute(req)

    assert res.measured_tokens == 250
    assert res.measured_duration_ms == 42
    assert worker.is_admissible(res) is True


def test_r1_f1_operating_loop_rejects_claimed_complete_with_absent_measurements():
    """R1-F1: Before accepting CLAIMED_COMPLETE, operating loop must require

    admissibility check. A result with absent measurements (None) must NOT
    progress to observation or verification.
    """
    store = ReferenceSQLiteStore(":memory:")
    mock_state = _make_mock_state()
    store._load_canonical_state = lambda ws: mock_state
    loop = ReferenceOperatingLoop(store=store)
    auth_req = _make_genuine_authorized_work_request()

    obs_called = []
    class WorkerWithAbsentMetrics:
        def profile(self):
            return WorkerProfile("w1", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
        def execute(self, req, boundary=None, handle=None):
            # Worker claims COMPLETE but has absent (None) measurements
            return WorkResult(
                result_id="wr-absent",
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
                worker_identity="w1",
                claim_status=WorkerClaimStatus.CLAIMED_COMPLETE,
                measured_tokens=None,
                measured_duration_ms=None,
                output_digest=Digest("sha256:" + "9" * 64),
                diagnostics_digest=Digest("sha256:" + "8" * 64),
                produced_artifacts=(),
            )

    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=WorkerWithAbsentMetrics(),
        observation_provider=lambda prop, w_res=None: obs_called.append((prop, w_res)),
        authorized_request=auth_req,
    )

    # Must fail closed with ESCALATED
    assert res["status"] == "ESCALATED", f"Expected ESCALATED for inadmissible metrics, got {res['status']}"
    assert "inadmissible" in res["error"] or "metrics" in res["error"]
    # Observation provider must NEVER have been called
    assert len(obs_called) == 0, "Observation provider was called for inadmissible result with absent measurements!"


# -----------------------------------------------------------------------------
# R1-F3: handoff.py rejection of synthetic fallback StateBinding & fallback revisions
# -----------------------------------------------------------------------------

def test_r1_f3_handoff_compiler_rejects_incomplete_state_without_fallback_binding():
    """R1-F3: Incomplete canonical state must NOT fabricate synthetic StateBinding

    with placeholder revisions ('genesis', 'epoch-genesis') or genesis digests.
    It must fail closed and propagate the failure.
    """
    ts = TargetSnapshot(
        "s", "w", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        None, None, Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64), (), FrozenMap.from_items(()), "p", UtcInstant(1)
    )
    incomplete_state = types.SimpleNamespace(
        workspace_id="w",
        workspace_snapshot_id="s",
        target_snapshot=ts,
        policy_version="p",
        obligations=types.SimpleNamespace(_obligations={"obl-1": types.SimpleNamespace(obligation_id="obl-1")}),
        evidence={},
        work_graph=types.SimpleNamespace(_frontier=("node-1",)),
        authorization_decisions={},
        constraints={},
        objective=types.SimpleNamespace(revisions=(types.SimpleNamespace(revision_id="obj-rev-1"),)),
        world_model=types.SimpleNamespace(revision_id="wm-rev-1"),
        causal_frontier=None,
    )
    compiler = ReferenceHandoffCompiler()

    with pytest.raises(ValueError, match="complete canonical state binding requires"):
        compiler.compile(incomplete_state, "obl-1")


def test_r1_f3_handoff_compiler_rejects_missing_objective_revision():
    """R1-F3: Handoff compiler must NOT substitute 'genesis' when objective revision is missing.

    Missing objective revisions must fail closed immediately.
    """
    ts = TargetSnapshot(
        "s", "w", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        None, None, Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64), (), FrozenMap.from_items(()), "p", UtcInstant(1)
    )
    frontier = CausalFrontier(
        "f-1", "p-1", "1.0", "rev-1", "og-1", "wg-1",
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64), "epoch-1",
        Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64), (), ("reason-1",)
    )
    state_no_obj = types.SimpleNamespace(
        workspace_id="w",
        workspace_snapshot_id="s",
        target_snapshot=ts,
        policy_version="p",
        obligations=types.SimpleNamespace(_obligations={"obl-1": types.SimpleNamespace(obligation_id="obl-1")}),
        evidence={},
        work_graph=types.SimpleNamespace(_frontier=("node-1",), revision_id="wg-1"),
        authorization_decisions={},
        constraints={},
        objective=None,
        world_model=types.SimpleNamespace(revision_id="wm-rev-1"),
        world_model_revision="wm-rev-1",
        causal_frontier=frontier,
    )
    compiler = ReferenceHandoffCompiler()

    with pytest.raises(ValueError, match="objective"):
        compiler.compile(state_no_obj, "obl-1")


def test_r1_f3_handoff_compiler_rejects_missing_world_model_revision():
    """R1-F3: Handoff compiler must NOT substitute 'wm-0' when world-model revision is missing.

    Missing world-model revision must fail closed immediately.
    """
    ts = TargetSnapshot(
        "s", "w", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        None, None, Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64), (), FrozenMap.from_items(()), "p", UtcInstant(1)
    )
    frontier = CausalFrontier(
        "f-1", "p-1", "1.0", "rev-1", "og-1", "wg-1",
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64), "epoch-1",
        Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64), (), ("reason-1",)
    )
    state_no_wm = types.SimpleNamespace(
        workspace_id="w",
        workspace_snapshot_id="s",
        target_snapshot=ts,
        policy_version="p",
        obligations=types.SimpleNamespace(_obligations={"obl-1": types.SimpleNamespace(obligation_id="obl-1")}),
        evidence={},
        work_graph=types.SimpleNamespace(_frontier=("node-1",), revision_id="wg-1"),
        authorization_decisions={},
        constraints={},
        objective=types.SimpleNamespace(revisions=(types.SimpleNamespace(revision_id="obj-rev-1"),)),
        world_model=None,
        world_model_revision="",
        causal_frontier=frontier,
    )
    compiler = ReferenceHandoffCompiler()

    with pytest.raises(ValueError, match="world-model"):
        compiler.compile(state_no_wm, "obl-1")


# -----------------------------------------------------------------------------
# R1-F5: operating_loop.py caller-supplied authorization & mandatory observation binding
# -----------------------------------------------------------------------------

def test_r1_f5_operating_loop_fails_closed_when_caller_omits_authorized_request():
    """R1-F5: Operating loop must NOT manufacture AuthorizationLeaseClaims,

    AuthorizationLease, ExecutionLease, or SignatureBlock internally.
    When caller does not supply an AuthorizedWorkRequest, loop must fail closed with IN_DOUBT.
    """
    store = ReferenceSQLiteStore(":memory:")
    mock_state = _make_mock_state()
    store._load_canonical_state = lambda ws: mock_state
    loop = ReferenceOperatingLoop(store=store)

    class AnyWorker:
        def profile(self):
            return WorkerProfile("w1", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
        def execute(self, req, boundary=None, handle=None):
            return types.SimpleNamespace(claim_status=WorkerClaimStatus.CLAIMED_COMPLETE)

    # Caller passes NO authorized_request
    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=AnyWorker(),
        observation_provider=lambda prop, w_res=None: None,
    )

    assert res["status"] == "IN_DOUBT"
    assert res["error"] == "missing_authorized_work_request"


def test_r1_f5_operating_loop_fails_closed_when_caller_supplies_invalid_authorized_request_type():
    """R1-F5: Operating loop must reject invalid authorized_request types fail-closed."""
    store = ReferenceSQLiteStore(":memory:")
    mock_state = _make_mock_state()
    store._load_canonical_state = lambda ws: mock_state
    loop = ReferenceOperatingLoop(store=store)

    class AnyWorker:
        def profile(self):
            return WorkerProfile("w1", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
        def execute(self, req, boundary=None, handle=None):
            return types.SimpleNamespace(claim_status=WorkerClaimStatus.CLAIMED_COMPLETE)

    # Caller passes a fake object instead of AuthorizedWorkRequest
    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=AnyWorker(),
        observation_provider=lambda prop, w_res=None: None,
        authorized_request=types.SimpleNamespace(fake=True),  # type: ignore
    )

    assert res["status"] == "ESCALATED"
    assert res["error"] == "invalid_authorized_work_request_type"


def test_r1_f5_operating_loop_rejects_one_argument_observation_provider():
    """R1-F5: Do not allow the one-argument observation-provider path for an execution

    that requires provenance binding.
    """
    store = ReferenceSQLiteStore(":memory:")
    mock_state = _make_mock_state()
    store._load_canonical_state = lambda ws: mock_state
    loop = ReferenceOperatingLoop(store=store)
    auth_req = _make_genuine_authorized_work_request()

    profile = WorkerProfile("ref-worker", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    worker = ReferenceWorker(
        profile,
        execution_callback=lambda req, b, h: (WorkerClaimStatus.CLAIMED_COMPLETE, 100, 20),
    )

    # 1-argument observation provider
    def one_arg_provider(proposal):
        return types.SimpleNamespace(observation_id="obs-1")

    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=worker,
        observation_provider=one_arg_provider,
        authorized_request=auth_req,
    )

    assert res["status"] == "ESCALATED"
    assert "observation_provider" in res["error"]


@pytest.mark.parametrize("missing_field", [
    "request_id",
    "execution_attempt_id",
    "execution_generation",
    "worker_identity",
    "worker_result_digest",
])
def test_r1_f5_operating_loop_rejects_observation_missing_fields(missing_field: str):
    """R1-F5: Observation must contain and match request ID, attempt ID, generation,

    worker identity, and worker-result output digest. Missing fields must fail closed
    just like mismatched fields.
    """
    store = ReferenceSQLiteStore(":memory:")
    mock_state = _make_mock_state()
    store._load_canonical_state = lambda ws: mock_state
    loop = ReferenceOperatingLoop(store=store)
    auth_req = _make_genuine_authorized_work_request()

    profile = WorkerProfile("ref-worker", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    worker = ReferenceWorker(
        profile,
        execution_callback=lambda req, b, h: (WorkerClaimStatus.CLAIMED_COMPLETE, 100, 20),
    )

    def flawed_obs_provider(proposal, worker_result):
        fields = {
            "observation_id": "obs-flawed",
            "request_id": auth_req.request_id,
            "execution_attempt_id": auth_req.execution_attempt_id,
            "execution_generation": auth_req.execution_generation,
            "worker_identity": worker_result.worker_identity,
            "worker_result_digest": worker_result.output_digest,
            "process_result": types.SimpleNamespace(exit_code=0),
        }
        # Delete or set to None the targeted missing field
        fields[missing_field] = None
        return types.SimpleNamespace(**fields)

    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=worker,
        observation_provider=flawed_obs_provider,
        authorized_request=auth_req,
    )

    assert res["status"] == "ESCALATED"
    assert "observation_binding_missing_field" in res["error"]
    assert missing_field in res["error"]


def test_r1_f5_operating_loop_rejects_observation_mismatched_worker_result_digest():
    """R1-F5: Observation must fail closed when worker_result_digest is mismatched."""
    store = ReferenceSQLiteStore(":memory:")
    mock_state = _make_mock_state()
    store._load_canonical_state = lambda ws: mock_state
    loop = ReferenceOperatingLoop(store=store)
    auth_req = _make_genuine_authorized_work_request()

    profile = WorkerProfile("ref-worker", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    worker = ReferenceWorker(
        profile,
        execution_callback=lambda req, b, h: (WorkerClaimStatus.CLAIMED_COMPLETE, 100, 20),
    )

    def mismatched_obs_provider(proposal, worker_result):
        return types.SimpleNamespace(
            observation_id="obs-mismatched",
            request_id=auth_req.request_id,
            execution_attempt_id=auth_req.execution_attempt_id,
            execution_generation=auth_req.execution_generation,
            worker_identity=worker_result.worker_identity,
            worker_result_digest=Digest("sha256:" + "e" * 64),  # Mismatched!
            process_result=types.SimpleNamespace(exit_code=0),
        )

    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=worker,
        observation_provider=mismatched_obs_provider,
        authorized_request=auth_req,
    )

    assert res["status"] == "ESCALATED"
    assert "observation_binding_mismatch" in res["error"]
    assert "worker_result_digest mismatch" in res["error"]


def test_r1_f5_operating_loop_succeeds_with_genuine_request_result_and_bound_observation():
    """R1-F5 Positive Test: Operating loop succeeds using genuine AuthorizedWorkRequest,

    genuine WorkResult from ReferenceWorker, and bound observation with no SimpleNamespace stubs.
    """
    store = ReferenceSQLiteStore(":memory:")
    mock_state = _make_mock_state()
    store._load_canonical_state = lambda ws: mock_state
    loop = ReferenceOperatingLoop(store=store)
    auth_req = _make_genuine_authorized_work_request()

    profile = WorkerProfile("ref-worker", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    worker = ReferenceWorker(
        profile,
        execution_callback=lambda req, b, h: (WorkerClaimStatus.CLAIMED_COMPLETE, 150, 45),
    )

    def bound_obs_provider(proposal, worker_result):
        # Genuine ObservationRecord with authentic fields and bound digests
        obs = ObservationRecord(
            observation_id="obs-bound-1",
            request_id=auth_req.request_id,
            work_node_id=auth_req.node_id,
            execution_generation=auth_req.execution_generation,
            execution_attempt_id=auth_req.execution_attempt_id,
            target_snapshot_digest=auth_req.execution_lease.target_snapshot_digest,
            governing_budget_lineage_id=auth_req.governing_budget_lineage_id,
            worker_identity=worker_result.worker_identity,
            mutation_digest=Digest("sha256:" + "0" * 64),
            mutations=(),
            git_state=GitState(
                "main",
                "c1",
                Digest("sha256:" + "0" * 64),
                Digest("sha256:" + "0" * 64),
            ),
            environment=EnvironmentFingerprint(
                "linux",
                "x86_64",
                Digest("sha256:" + "0" * 64),
                Digest("sha256:" + "0" * 64),
                None,
            ),
            actor=ActorIdentity("system", ActorKind.SYSTEM, None),
            attribution=(),
            observed_at=UtcInstant(1),
            target_system="local",
            receipts=(),
            process_result=ProcessExecutionResult(
                termination=TerminationKind.EXITED,
                exit_code=0,
                signal=None,
                identity=auth_req.execution_lease.executable_identity,
                started_at=UtcInstant(0),
                ended_at=UtcInstant(45),
                wall_time_ms=45,
                cpu_time_ms=40,
                args_digest=Digest("sha256:" + "0" * 64),
                env_digest=Digest("sha256:" + "0" * 64),
                stdout_digest=Digest("sha256:" + "0" * 64),
                stderr_digest=Digest("sha256:" + "0" * 64),
                stdout_bytes=0,
                stderr_bytes=0,
                stdout_excerpt="",
                stderr_excerpt="",
                output_truncated=False,
                workspace_mutation_count=0,
                process_id=1234,
            ),
            before_snapshot_id="snap-1",
            after_snapshot_id="snap-1",
            after_workspace_digest=Digest("sha256:" + "1" * 64),
            quiescence_proof=None,
            post_expiry=False,
        )
        object.__setattr__(obs, "worker_result_digest", worker_result.output_digest)
        return obs

    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=worker,
        observation_provider=bound_obs_provider,
        authorized_request=auth_req,
    )

    assert res["status"] == "PROGRESSING", f"Error was: {res.get('error')}"
    assert "obl-unsatisfied" in res["satisfied"]
