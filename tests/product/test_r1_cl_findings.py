"""Negative and reproduction tests for CL 16 November Part IV R1 Findings.

Findings covered:
1. R1-F1 (worker.py): Rejection of fabricated 0/0 metrics; genuine measurements or None;
   inadmissibility when measurements are absent.
2. R1-F3 (handoff.py): Rejection of synthetic genesis digests and placeholder revisions (genesis,
   epoch-genesis); fail-closed propagation when canonical binding cannot be derived.
3. R1-F5 (operating_loop.py): Worker must receive genuine AuthorizedWorkRequest (not SimpleNamespace);
   observation_provider must receive worker_result; observation must be demonstrably bound to execution.
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
    AuthorizedWorkRequest,
    BoundaryContext,
    CausalFrontier,
    Digest,
    EngineeringState,
    FrozenMap,
    IsolationLevel,
    Obligation,
    ObligationKind,
    ObligationStatus,
    ObservationRecord,
    RiskTier,
    TargetSnapshot,
    UtcInstant,
    VerificationStatus,
    WorkerClaimStatus,
    WorkerKind,
    WorkerProfile,
    WorkProposal,
    digest,
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


# -----------------------------------------------------------------------------
# R1-F1: worker.py metrics authenticity & admissibility
# -----------------------------------------------------------------------------

def test_r1_f1_worker_cannot_substitute_zero_for_absent_metrics():
    """R1-F1: Worker must not substitute 0/0 for absent measurements.

    Measurements must be None, and the result must be inadmissible.
    """
    profile = WorkerProfile("worker-1", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    # Worker without callback or callback with no measurements
    worker = ReferenceWorker(
        profile,
        execution_callback=lambda req, b, h: WorkerClaimStatus.CLAIMED_COMPLETE,
    )
    req = _make_dummy_request("req-metrics-1")
    res = worker.execute(req)

    # Must NOT substitute zero
    assert res.measured_tokens is None, f"Expected None for absent measured_tokens, got {res.measured_tokens}"
    assert res.measured_duration_ms is None, f"Expected None for absent measured_duration_ms, got {res.measured_duration_ms}"
    # Result must be inadmissible when measurements are absent
    assert hasattr(worker, "is_admissible"), "ReferenceWorker must provide is_admissible"
    assert worker.is_admissible(res) is False, "WorkResult without measurements must be inadmissible"


def test_r1_f1_worker_admissible_only_with_genuine_callback_measurements():
    """R1-F1: Worker records genuine callback measurements and result is admissible."""
    profile = WorkerProfile("worker-1", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
    # Callback providing genuine measurements
    worker = ReferenceWorker(
        profile,
        execution_callback=lambda req, b, h: (WorkerClaimStatus.CLAIMED_COMPLETE, 250, 42),
    )
    req = _make_dummy_request("req-metrics-2")
    res = worker.execute(req)

    assert res.measured_tokens == 250
    assert res.measured_duration_ms == 42
    assert worker.is_admissible(res) is True


# -----------------------------------------------------------------------------
# R1-F3: handoff.py rejection of synthetic fallback StateBinding
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
    # Incomplete state: causal_frontier is None, work_graph lacks revision_id
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
        causal_frontier=None,
    )
    compiler = ReferenceHandoffCompiler()

    # Must raise ValueError instead of constructing fallback StateBinding with 'epoch-genesis'
    with pytest.raises(ValueError, match="complete canonical state binding requires"):
        compiler.compile(incomplete_state, "obl-1")


# -----------------------------------------------------------------------------
# R1-F5: operating_loop.py genuine AuthorizedWorkRequest & observation binding
# -----------------------------------------------------------------------------

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
        world_model=None,
        work_graph=types.SimpleNamespace(revision_id="wg-1"),
        policy_version="pol-1",
        workspace_snapshot_id="snap-1",
        target_snapshot=ts,
        causal_frontier=frontier,
        evidence={},
        budget_lineages={},
        event_head_hash=Digest("sha256:" + "1" * 64),
    )


def test_r1_f5_operating_loop_passes_genuine_authorized_work_request():
    """R1-F5: Operating loop must execute worker with genuine AuthorizedWorkRequest,

    not types.SimpleNamespace.
    """
    store = ReferenceSQLiteStore(":memory:")
    mock_state = _make_mock_state()
    store._load_canonical_state = lambda ws: mock_state
    loop = ReferenceOperatingLoop(store=store)

    received_requests = []
    class InspectingWorker:
        def profile(self):
            return WorkerProfile("w1", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
        def execute(self, req, boundary=None, handle=None):
            received_requests.append(req)
            return types.SimpleNamespace(
                claim_status=WorkerClaimStatus.CLAIMED_COMPLETE,
                request_id=req.request_id,
                execution_attempt_id=req.execution_attempt_id,
                execution_generation=req.execution_generation,
                worker_identity="w1",
                output_digest=Digest("sha256:" + "9" * 64),
            )

    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=InspectingWorker(),
        observation_provider=lambda prop, w_res=None: types.SimpleNamespace(
            observation_id="obs-1",
            request_id=getattr(w_res, "request_id", ""),
            execution_attempt_id=getattr(w_res, "execution_attempt_id", ""),
            execution_generation=getattr(w_res, "execution_generation", 1),
            worker_identity=getattr(w_res, "worker_identity", "w1"),
            process_result=types.SimpleNamespace(exit_code=0),
        ),
    )

    assert len(received_requests) == 1
    req = received_requests[0]
    assert isinstance(req, AuthorizedWorkRequest), (
        f"Expected genuine AuthorizedWorkRequest, got {type(req).__name__}"
    )


def test_r1_f5_operating_loop_rejects_unbound_observation():
    """R1-F5: Operating loop must reject observations not demonstrably bound to the execution."""
    store = ReferenceSQLiteStore(":memory:")
    mock_state = _make_mock_state()
    store._load_canonical_state = lambda ws: mock_state
    loop = ReferenceOperatingLoop(store=store)

    class StubWorker:
        def profile(self):
            return WorkerProfile("w1", WorkerKind.SUBPROCESS, (), None, IsolationLevel.PROCESS)
        def execute(self, req, boundary=None, handle=None):
            return types.SimpleNamespace(
                claim_status=WorkerClaimStatus.CLAIMED_COMPLETE,
                request_id=req.request_id,
                execution_attempt_id=req.execution_attempt_id,
                execution_generation=req.execution_generation,
                worker_identity="w1",
                output_digest=Digest("sha256:" + "9" * 64),
            )

    # Observation returns mismatched request_id / unbound execution
    def rogue_obs_provider(proposal, worker_result=None):
        return types.SimpleNamespace(
            observation_id="obs-rogue",
            request_id="UNBOUND_ROGUE_REQUEST",
            execution_attempt_id="att-wrong",
            execution_generation=999,
            worker_identity="rogue-worker",
            process_result=types.SimpleNamespace(exit_code=0),
        )

    res = loop.run_cycle(
        "test-ws",
        ActorIdentity("system", ActorKind.SYSTEM, None),
        worker=StubWorker(),
        observation_provider=rogue_obs_provider,
    )

    assert res["status"] in ("ESCALATED", "IN_DOUBT")
    assert "observation" in res["error"] and ("mismatch" in res["error"] or "unbound" in res["error"])
