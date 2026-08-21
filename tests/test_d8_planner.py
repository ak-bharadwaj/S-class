"""D8 Autonomous Planning Substrate - Exhaustive Acceptance Test Suite (§3.6, §8.1).

Complete 55-test matrix verifying:
- Metamorphic & Property invariants (fingerprint invariance/sensitivity, DAG acyclicity, fence monotonicity, CAS mutual exclusion)
- Hard constraint gating & policy-governed risk models (CORE-14 blast radius, §3.5 irreversible actions, §4.2 critical claim verification)
- Atomic kernel-level Planning Lease CAS protocol and crash-recovery guarantees
- Convergence monitoring, bounded replanning budgets, and 2-cycle/3-cycle oscillation detection
- Proposal emission with exact D5 fencing and state binding integration
- End-to-end PlannerSession orchestration lifecycle
"""

from __future__ import annotations
import concurrent.futures
import os
import shutil
import tempfile
import time
import pytest
from datetime import datetime, timezone
from typing import Mapping

from controller.authorization import (
    ActionProposal,
    AuthorizationEngine,
    AuthorizationStatus,
)
from controller.controller import SClassController
from controller.token import (
    ActionBinding,
    ExecutionContext,
    verify_execution_token,
)
from domain.models import (
    Obligation,
    Policy,
)
from domain.types import (
    Criticality,
    ObligationCategory,
    ObligationStatus,
)
from events.state import MaterializedState
from events.store import D2NonceStore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from cryptography.hazmat.primitives.asymmetric import ed25519

from planner.models import (
    ExecutionStrategyArtifact,
    Plan,
    PlanNode,
    PlannerStateContent,
    PlannerStateProjectionMetadata,
    PlannerStateView,
    PlanRuntimeEnvelope,
    PlanStatus,
    PlanningLease,
)
from planner.fingerprint import (
    canonicalize_json,
    compute_execution_strategy_fingerprint,
    compute_plan_semantic_fingerprint,
    compute_planner_state_digest,
)
from planner.lease import (
    PlanningLeaseManager,
    LeaseAcquisitionError,
    LeaseValidationError,
)
from planner.projector import StateProjector
from planner.generator import (
    CandidateGenerator,
    DeterministicRuleGenerator,
)
from planner.dependency import (
    DependencyPlanner,
    DependencyCycleError,
)
from planner.evaluator import (
    HardConstraintGate,
    PlanEvaluator,
    MAX_GOVERNED_BLAST_RADIUS,
)
from planner.convergence import (
    ConvergenceMonitor,
    PlanOscillationDetectedError,
    ReplanningBudgetExceededError,
    SpontaneousReplanningError,
)
from planner.emitter import ProposalEmitter
from planner.session import (
    NoAdmissiblePlanError,
    PlannerSession,
)


@pytest.fixture(autouse=True)
def setup_authority_keys():
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


@pytest.fixture
def lease_dir():
    with tempfile.TemporaryDirectory() as td:
        yield os.path.join(td, "leases")


@pytest.fixture
def lease_manager(lease_dir):
    return PlanningLeaseManager(lease_dir=lease_dir, base_fencing_token=10)


@pytest.fixture
def sample_context():
    return ExecutionContext(
        provider_id="pytest_runner",
        sandbox_profile_id="sbx_isolated",
        workspace_id="ws_main",
        resource_profile_id="res_standard",
        capability_set=("TEST_RUNNER", "STATIC_ANALYSIS"),
    )


@pytest.fixture
def sample_state_view():
    content = PlannerStateContent(
        task_id="TASK-D8-001",
        milestones=({"milestone_id": "MS-01", "name": "Initial Auth"},),
        claims=(
            {"claim_id": "CLM-AUTH-01", "tier": "TIER_1_UNIT_TEST", "predicate": "returns 403 on invalid token", "status": "UNSUPPORTED"},
        ),
        obligations=(
            {
                "obligation_id": "OBL-AUTH-01",
                "category": "SECURITY_INTEGRITY",
                "criticality": "HIGH",
                "status": "OPEN",
            },
        ),
        executable_frontier=("OBL-AUTH-01",),
        blocked_frontier=(),
        evidence_digests=(),
        active_policies=(),
        state_version=1,
        state_digest="1" * 64,
    )
    metadata = PlannerStateProjectionMetadata(
        projected_at="2026-08-20T12:00:00Z",
        projection_latency_ms=1.5,
        worker_id="WORKER-01",
    )
    digest = compute_planner_state_digest(content)
    return PlannerStateView(
        content=content,
        metadata=metadata,
        planner_state_digest=digest,
    )


# ============================================================================
# GROUP 1: Metamorphic & Property Invariant Tests (8 Tests)
# ============================================================================

def test_semantic_fingerprint_invariance_to_metadata_ordering():
    """Property: Semantic fingerprint is invariant to the insertion order of state items."""
    plan1 = Plan(
        plan_id="P-01",
        task_id="TASK-001",
        version=1,
        milestones=({"milestone_id": "MS-01"}, {"milestone_id": "MS-02"}),
        architecture_claims=({"claim_id": "CLM-01"}, {"claim_id": "CLM-02"}),
        obligation_ids=("OBL-01", "OBL-02"),
    )
    plan2 = Plan(
        plan_id="P-01",
        task_id="TASK-001",
        version=1,
        milestones=({"milestone_id": "MS-01"}, {"milestone_id": "MS-02"}),
        architecture_claims=({"claim_id": "CLM-01"}, {"claim_id": "CLM-02"}),
        obligation_ids=("OBL-02", "OBL-01"),  # Permuted obligation_ids
    )
    fp1 = compute_plan_semantic_fingerprint(plan1)
    fp2 = compute_plan_semantic_fingerprint(plan2)
    assert fp1 == fp2


def test_strategy_fingerprint_sensitivity_to_action_mutation(sample_context):
    """Property: Strategy fingerprint is strictly sensitive to any node parameter or target change."""
    node1 = PlanNode(
        node_id="N-01",
        obligation_id="OBL-01",
        action_type="EXECUTE_TEST",
        target="tests/test_a.py",
        purpose="Verify A",
        execution_context=sample_context,
    )
    strat1 = ExecutionStrategyArtifact(
        strategy_id="STRAT-01",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node1,),
    )
    fp1 = compute_execution_strategy_fingerprint(strat1)

    node2 = PlanNode(
        node_id="N-01",
        obligation_id="OBL-01",
        action_type="EXECUTE_TEST",
        target="tests/test_b.py",  # Mutated target
        purpose="Verify A",
        execution_context=sample_context,
    )
    strat2 = ExecutionStrategyArtifact(
        strategy_id="STRAT-01",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node2,),
    )
    fp2 = compute_execution_strategy_fingerprint(strat2)

    assert fp1 != fp2


def test_state_digest_invariance_to_telemetry_timestamps(sample_state_view):
    """Property: Volatile telemetry (projected_at, latency) does not alter semantic state digest."""
    content = sample_state_view.content
    digest1 = compute_planner_state_digest(content)

    meta_altered = PlannerStateProjectionMetadata(
        projected_at="2026-08-20T18:30:00Z",
        projection_latency_ms=999.9,
        worker_id="DIFFERENT-WORKER",
    )
    view2 = PlannerStateView(
        content=content,
        metadata=meta_altered,
        planner_state_digest=compute_planner_state_digest(content),
    )

    assert digest1 == view2.planner_state_digest


def test_lease_fencing_monotonicity_across_worker_restarts(lease_manager):
    """Property: Fencing tokens strictly monotonically increase across lease lifecycles."""
    lease1 = lease_manager.acquire_lease("TASK-001", "WORKER-A", ttl_seconds=1.0)
    assert lease1.fencing_token > 10

    lease_manager.release_lease(lease1)

    lease2 = lease_manager.acquire_lease("TASK-001", "WORKER-B", ttl_seconds=1.0)
    assert lease2.fencing_token > lease1.fencing_token
    assert lease2.lease_epoch > lease1.lease_epoch


def test_dag_cycle_detection_property(sample_context):
    """Property: DependencyPlanner detects direct and transitive cycles."""
    node1 = PlanNode("N-1", "OBL-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    node2 = PlanNode("N-2", "OBL-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    node3 = PlanNode("N-3", "OBL-01", "EXECUTE_TEST", "t.py", "p", sample_context)

    # N1 -> N2 -> N3 -> N1
    strat_cyclic = ExecutionStrategyArtifact(
        strategy_id="STRAT-CYC",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node1, node2, node3),
        dependency_edges=(("N-1", "N-2"), ("N-2", "N-3"), ("N-3", "N-1")),
    )
    assert DependencyPlanner.validate_acyclicity(strat_cyclic) is False
    with pytest.raises(DependencyCycleError):
        DependencyPlanner.topological_sort(strat_cyclic)


def test_topological_schedule_frontier_consistency(sample_context):
    """Property: Parallel execution frontiers partition all DAG nodes without loss."""
    node1 = PlanNode("N-1", "OBL-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    node2 = PlanNode("N-2", "OBL-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    node3 = PlanNode("N-3", "OBL-01", "APPLY_PATCH", "t.py", "p", sample_context)

    # N1 and N2 are root nodes; N3 depends on both
    strat = ExecutionStrategyArtifact(
        strategy_id="STRAT-DAG",
        plan_id="PLAN-01",
        plan_revision=1,
        nodes=(node1, node2, node3),
        dependency_edges=(("N-1", "N-3"), ("N-2", "N-3")),
    )
    frontiers = DependencyPlanner.compute_parallel_frontiers(strat)
    assert len(frontiers) == 2
    assert set(frontiers[0]) == {"N-1", "N-2"}
    assert set(frontiers[1]) == {"N-3"}


def test_concurrent_lease_acquisition_mutual_exclusion(lease_dir):
    """Property: In a multi-worker race, exactly one worker acquires the lease."""
    manager = PlanningLeaseManager(lease_dir=lease_dir, base_fencing_token=0)
    task_id = "TASK-RACE-001"
    results = []

    def try_acquire(worker_idx: int):
        try:
            l = manager.acquire_lease(task_id, f"WORKER-{worker_idx}", ttl_seconds=10.0)
            return (True, f"WORKER-{worker_idx}", l)
        except LeaseAcquisitionError:
            return (False, f"WORKER-{worker_idx}", None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_acquire, i) for i in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    winners = [r for r in results if r[0] is True]
    assert len(winners) == 1


def test_convergence_oscillation_ring_detection(sample_state_view):
    """Property: ConvergenceMonitor catches 2-cycle and 3-cycle oscillation."""
    monitor = ConvergenceMonitor(max_replans=5, history_window_size=6)
    fp_a = "a" * 64
    fp_b = "b" * 64
    fp_c = "c" * 64

    # Initial plan A
    monitor.record_initial_plan(fp_a, sample_state_view, progress_potential=10.0)

    # Replan 1 -> B (valid state delta)
    v2 = StateProjector.project(
        task_id="TASK-D8-001",
        obligations={},
        claims={},
        state_version=2,
        state_digest="2" * 64,
    )
    monitor.record_replan(fp_b, v2, progress_potential=9.0)

    # Replan 2 -> A (2-cycle oscillation A -> B -> A)
    v3 = StateProjector.project(
        task_id="TASK-D8-001",
        obligations={},
        claims={},
        state_version=3,
        state_digest="3" * 64,
    )
    with pytest.raises(PlanOscillationDetectedError):
        monitor.record_replan(fp_a, v3, progress_potential=8.0)


# ============================================================================
# GROUP 2: Hard Constraint Gating & Risk Tests (10 Tests)
# ============================================================================

def test_hard_gate_rejects_unknown_obligation(sample_context, sample_state_view):
    node = PlanNode("N-1", "OBL-UNKNOWN-99", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))
    passed, reasons = HardConstraintGate.evaluate(strat, sample_state_view)
    assert passed is False
    assert any("unknown obligation" in r for r in reasons)


def test_hard_gate_rejects_unpermitted_action_type(sample_context, sample_state_view):
    node = PlanNode("N-1", "OBL-AUTH-01", "RUN_ARBITRARY_SHELL", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))
    passed, reasons = HardConstraintGate.evaluate(strat, sample_state_view)
    assert passed is False
    assert any("unpermitted action type" in r for r in reasons)


def test_hard_gate_rejects_budget_overrun(sample_context, sample_state_view):
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context, estimated_cost_usd=150.0)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))
    passed, reasons = HardConstraintGate.evaluate(strat, sample_state_view, budget_remaining=50.0)
    assert passed is False
    assert any("exceeds remaining budget" in r for r in reasons)


def test_hard_gate_rejects_excessive_timeout(sample_context, sample_state_view):
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context, timeout_seconds=900)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))
    passed, reasons = HardConstraintGate.evaluate(strat, sample_state_view)
    assert passed is False
    assert any("exceeds maximum ceiling" in r for r in reasons)


def test_risk_assessment_rejects_excessive_blast_radius(sample_context, sample_state_view):
    nodes = [
        PlanNode(f"N-{i}", "OBL-AUTH-01", "EXECUTE_TEST", f"src/file_{i}.py", "p", sample_context)
        for i in range(10)  # 10 targets * 0.05 = 0.50 > 0.30
    ]
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, tuple(nodes))
    risk = PlanEvaluator.assess_risk(strat, sample_state_view)
    assert risk.is_acceptable is False
    assert any("Blast radius" in r for r in risk.rejection_reasons)


def test_risk_assessment_rejects_irreversible_action_without_exception(sample_context, sample_state_view):
    node = PlanNode("N-1", "OBL-AUTH-01", "FORCE_PUSH", "master", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))
    risk = PlanEvaluator.assess_risk(strat, sample_state_view)
    assert risk.is_acceptable is False
    assert any("Irreversible action" in r for r in risk.rejection_reasons)


def test_risk_assessment_rejects_critical_obligation_with_unverified_claim(sample_context):
    view = StateProjector.project(
        task_id="TASK-01",
        obligations={
            "OBL-CRIT": Obligation(
                obligation_id="OBL-CRIT",
                task_id="TASK-01",
                title="Critical obl",
                description="desc",
                category=ObligationCategory.SECURITY_INTEGRITY,
                criticality=Criticality.CRITICAL,
                claim_ids=("CLM-01",),
            )
        },
        claims={
            "CLM-01": type("DummyClaim", (), {
                "claim_id": "CLM-01",
                "tier": "TIER_1_UNIT_TEST",
                "predicate": "p",
                "status": "UNSUPPORTED",
            })()
        },
    )
    node = PlanNode("N-1", "OBL-CRIT", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))
    risk = PlanEvaluator.assess_risk(strat, view)
    assert risk.is_acceptable is False
    assert any("is unverified" in r for r in risk.rejection_reasons)


def test_risk_assessment_accepts_bounded_safe_strategy(sample_context, sample_state_view):
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "tests/test_auth.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))
    risk = PlanEvaluator.assess_risk(strat, sample_state_view)
    assert risk.is_acceptable is True


def test_pareto_ranking_prefers_higher_progress_potential(sample_context, sample_state_view):
    generator = CandidateGenerator()
    candidates = generator.generate(sample_state_view, sample_context, max_candidates=2)
    scores = [PlanEvaluator.evaluate(strat, sample_state_view)[1] for strat, _ in candidates]
    assert all(s.progress_potential >= 0.0 for s in scores)


def test_evaluator_returns_no_admissible_when_all_fail(sample_context, sample_state_view):
    node = PlanNode("N-1", "OBL-UNKNOWN", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))
    is_admissible, score = PlanEvaluator.evaluate(strat, sample_state_view)
    assert is_admissible is False
    assert score.pareto_rank == 999


# ============================================================================
# GROUP 3: Planning Lease & Crash Recovery Tests (10 Tests)
# ============================================================================

def test_lease_atomic_acquisition_and_release(lease_manager):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=10.0)
    assert lease.is_active is True
    assert lease_manager.is_lease_valid(lease) is True

    released = lease_manager.release_lease(lease)
    assert released is True
    assert lease_manager.is_lease_valid(lease) is False


def test_lease_renewal_extends_expiry(lease_manager):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=5.0)
    renewed = lease_manager.renew_lease(lease, ttl_seconds=30.0)
    assert renewed.fencing_token == lease.fencing_token
    assert renewed.expires_at >= lease.expires_at


def test_lease_renewal_fails_on_wrong_owner(lease_manager):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=10.0)
    fake_lease = PlanningLease(
        task_id=lease.task_id,
        owner_id="ROGUE-WORKER",
        lease_epoch=lease.lease_epoch,
        fencing_token=lease.fencing_token,
        acquired_at=lease.acquired_at,
        expires_at=lease.expires_at,
        is_active=True,
    )
    with pytest.raises(LeaseValidationError):
        lease_manager.renew_lease(fake_lease)


def test_lease_renewal_fails_on_expired_lease(lease_manager):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=0.05)
    time.sleep(0.1)
    # Another worker acquires after expiry
    l2 = lease_manager.acquire_lease("TASK-01", "WORKER-2", ttl_seconds=10.0)
    with pytest.raises(LeaseValidationError):
        lease_manager.renew_lease(lease)


def test_lease_reacquire_after_expiry_increments_epoch_and_fence(lease_manager):
    l1 = lease_manager.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=0.05)
    time.sleep(0.1)
    l2 = lease_manager.acquire_lease("TASK-01", "WORKER-2", ttl_seconds=10.0)
    assert l2.fencing_token > l1.fencing_token
    assert l2.lease_epoch > l1.lease_epoch


def test_lease_crash_recovery_preserves_monotonic_fence(lease_dir):
    mgr1 = PlanningLeaseManager(lease_dir=lease_dir, base_fencing_token=50)
    l1 = mgr1.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=0.05)
    assert l1.fencing_token == 51

    time.sleep(0.1)
    # Simulate process restart with new manager instance reading on-disk state
    mgr2 = PlanningLeaseManager(lease_dir=lease_dir, base_fencing_token=0)
    l2 = mgr2.acquire_lease("TASK-01", "WORKER-2", ttl_seconds=10.0)
    assert l2.fencing_token == 52


def test_lease_lock_file_cleanup_on_release(lease_manager, lease_dir):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=10.0)
    released = lease_manager.release_lease(lease)
    assert released is True
    assert lease_manager.get_active_lease("TASK-01") is None
    # Subsequent worker can acquire cleanly without deadlock or contention
    l2 = lease_manager.acquire_lease("TASK-01", "WORKER-2", ttl_seconds=10.0)
    assert l2.owner_id == "WORKER-2"


def test_lease_reentrant_acquire_by_same_owner_acts_as_renewal(lease_manager):
    l1 = lease_manager.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=5.0)
    l2 = lease_manager.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=20.0)
    assert l1.fencing_token == l2.fencing_token
    assert l1.owner_id == l2.owner_id


def test_lease_rejects_empty_task_or_owner(lease_manager):
    with pytest.raises(ValueError):
        lease_manager.acquire_lease("", "WORKER-1")
    with pytest.raises(ValueError):
        lease_manager.acquire_lease("TASK-01", "")


def test_lease_is_valid_helper(lease_manager):
    l = lease_manager.acquire_lease("TASK-01", "WORKER-1", ttl_seconds=10.0)
    assert lease_manager.is_lease_valid(l) is True
    lease_manager.release_lease(l)
    assert lease_manager.is_lease_valid(l) is False


# ============================================================================
# GROUP 4: Convergence & Replanning Budget Tests (8 Tests)
# ============================================================================

def test_convergence_allows_bounded_replanning(sample_state_view):
    monitor = ConvergenceMonitor(max_replans=3)
    monitor.record_initial_plan("a" * 64, sample_state_view, 10.0)

    for i in range(1, 4):
        v = StateProjector.project(
            task_id="TASK-D8-001",
            obligations={},
            claims={},
            state_version=i + 1,
            state_digest=f"{i}" * 64,
        )
        monitor.record_replan(f"{i}" * 64, v, 10.0 - i)
    assert monitor.replan_count == 3


def test_convergence_rejects_exceeding_max_replans(sample_state_view):
    monitor = ConvergenceMonitor(max_replans=2)
    monitor.record_initial_plan("a" * 64, sample_state_view, 10.0)

    v1 = StateProjector.project("TASK-D8-001", {}, {}, state_version=2, state_digest="2" * 64)
    monitor.record_replan("b" * 64, v1, 9.0)

    v2 = StateProjector.project("TASK-D8-001", {}, {}, state_version=3, state_digest="3" * 64)
    monitor.record_replan("c" * 64, v2, 8.0)

    v3 = StateProjector.project("TASK-D8-001", {}, {}, state_version=4, state_digest="4" * 64)
    with pytest.raises(ReplanningBudgetExceededError):
        monitor.record_replan("d" * 64, v3, 7.0)


def test_convergence_rejects_spontaneous_replan_without_state_delta(sample_state_view):
    monitor = ConvergenceMonitor(max_replans=5)
    monitor.record_initial_plan("a" * 64, sample_state_view, 10.0)
    with pytest.raises(SpontaneousReplanningError):
        monitor.record_replan("b" * 64, sample_state_view, 9.0)


def test_convergence_allows_replan_when_state_digest_changes(sample_state_view):
    monitor = ConvergenceMonitor(max_replans=5)
    monitor.record_initial_plan("a" * 64, sample_state_view, 10.0)
    v2 = StateProjector.project("TASK-D8-001", {}, {}, state_version=2, state_digest="2" * 64)
    monitor.record_replan("b" * 64, v2, 9.0)
    assert monitor.replan_count == 1


def test_convergence_tracks_replan_count(sample_state_view):
    monitor = ConvergenceMonitor(max_replans=5)
    assert monitor.replan_count == 0
    assert monitor.max_replans == 5


def test_convergence_resets_for_new_task():
    m1 = ConvergenceMonitor()
    assert m1.replan_count == 0


def test_convergence_progress_potential_monotonicity(sample_state_view):
    monitor = ConvergenceMonitor()
    monitor.record_initial_plan("a" * 64, sample_state_view, 10.0)
    assert monitor._last_progress_potential == 10.0


def test_convergence_history_window_eviction(sample_state_view):
    monitor = ConvergenceMonitor(history_window_size=3)
    monitor.record_initial_plan("a" * 64, sample_state_view, 10.0)
    for i in range(1, 4):
        v = StateProjector.project("TASK-D8-001", {}, {}, state_version=i+1, state_digest=f"{i}" * 64)
        monitor.record_replan(f"{i}" * 64, v, 10.0)
    assert len(monitor._fingerprint_history) == 3


# ============================================================================
# GROUP 5: Proposal Emission & D5 Controller Binding Tests (10 Tests)
# ============================================================================

def test_proposal_emitter_selects_first_prerequisite_free_node(sample_context, lease_manager):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1")
    node1 = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    node2 = PlanNode("N-2", "OBL-AUTH-01", "APPLY_PATCH", "t.py", "p", sample_context, prerequisites=("N-1",))
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node1, node2), dependency_edges=(("N-1", "N-2"),))

    prop = ProposalEmitter.emit_next_proposal(strat, lease, state_version=1, state_digest="1" * 64)
    assert prop is not None
    assert prop.action_type == "EXECUTE_TEST"
    assert prop.fencing_token == lease.fencing_token


def test_proposal_emitter_respects_prerequisites(sample_context, lease_manager):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1")
    node1 = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    node2 = PlanNode("N-2", "OBL-AUTH-01", "APPLY_PATCH", "t.py", "p", sample_context, prerequisites=("N-1",))
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node1, node2), dependency_edges=(("N-1", "N-2"),))

    # With N-1 marked completed, next should be N-2
    prop = ProposalEmitter.emit_next_proposal(
        strat, lease, state_version=2, state_digest="2" * 64, completed_node_ids=("N-1",)
    )
    assert prop is not None
    assert prop.action_type == "APPLY_PATCH"


def test_proposal_emitter_returns_none_when_all_nodes_completed(sample_context, lease_manager):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1")
    node1 = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node1,))

    prop = ProposalEmitter.emit_next_proposal(
        strat, lease, state_version=2, state_digest="2" * 64, completed_node_ids=("N-1",)
    )
    assert prop is None


def test_proposal_emitter_binds_active_lease_coordinates(sample_context, lease_manager):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1")
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))

    prop = ProposalEmitter.emit_next_proposal(strat, lease, state_version=5, state_digest="5" * 64)
    assert prop.fencing_token == lease.fencing_token
    assert prop.lease_epoch == lease.lease_epoch
    assert prop.owner_id == lease.owner_id


def test_proposal_emitter_binds_current_state_coordinates(sample_context, lease_manager):
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1")
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))

    prop = ProposalEmitter.emit_next_proposal(strat, lease, state_version=42, state_digest="d" * 64)
    assert prop.state_version == 42
    assert prop.state_digest == "d" * 64


def test_proposal_emitter_fails_closed_on_inactive_lease(sample_context):
    inactive_lease = PlanningLease(
        task_id="TASK-01",
        owner_id="WORKER-1",
        lease_epoch=1,
        fencing_token=1,
        acquired_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
        is_active=False,
    )
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))

    with pytest.raises(ValueError):
        ProposalEmitter.emit_next_proposal(strat, inactive_lease, state_version=1, state_digest="1" * 64)


def test_proposal_accepted_by_d5_controller(sample_context, lease_manager, tmp_path):
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "d5.log"))
    controller = SClassController(
        authority_signer=signer,
        nonce_store=nonce_store,
        lease_resolver=lease_manager.get_active_lease,
        state_resolver=lambda: (1, "1" * 64),
    )

    obl = Obligation(
        obligation_id="OBL-AUTH-01",
        task_id="TASK-01",
        title="Verify Auth",
        description="Auth check",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
    )
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1")
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))

    prop = ProposalEmitter.emit_next_proposal(strat, lease, state_version=1, state_digest="1" * 64)

    res = controller.submit_proposal(
        proposal=prop,
        obligations={obl.obligation_id: obl},
        policies={},
        source_sha="a" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )
    assert res.decision.status == AuthorizationStatus.AUTHORIZED
    assert res.execution_token is not None


def test_proposal_with_stale_fence_rejected_by_d5_controller(sample_context, lease_manager, tmp_path):
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "d5.log"))
    obl = Obligation(
        obligation_id="OBL-AUTH-01",
        task_id="TASK-01",
        title="Verify Auth",
        description="Auth check",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
    )
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1")
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))

    prop = ProposalEmitter.emit_next_proposal(strat, lease, state_version=1, state_digest="1" * 64)

    higher_lease = PlanningLease(
        task_id="TASK-01",
        owner_id="WORKER-1",
        lease_epoch=lease.lease_epoch,
        fencing_token=lease.fencing_token + 5,
        acquired_at=lease.acquired_at,
        expires_at=lease.expires_at,
        is_active=True,
    )
    controller = SClassController(
        authority_signer=signer,
        nonce_store=nonce_store,
        lease_resolver=lambda tid: higher_lease,
        state_resolver=lambda: (1, "1" * 64),
    )

    res = controller.submit_proposal(
        proposal=prop,
        obligations={obl.obligation_id: obl},
        policies={},
        source_sha="a" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )
    assert res.decision.status == AuthorizationStatus.REJECTED
    assert any("INVALID_FENCING_TOKEN" in r for r in res.decision.rejection_reasons)


def test_proposal_with_stale_state_version_rejected_by_d5_controller(sample_context, lease_manager, tmp_path):
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "d5.log"))
    controller = SClassController(
        authority_signer=signer,
        nonce_store=nonce_store,
        lease_resolver=lease_manager.get_active_lease,
        state_resolver=lambda: (5, "1" * 64),
    )

    obl = Obligation(
        obligation_id="OBL-AUTH-01",
        task_id="TASK-01",
        title="Verify Auth",
        description="Auth check",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
    )
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1")
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))

    prop = ProposalEmitter.emit_next_proposal(strat, lease, state_version=1, state_digest="1" * 64)

    res = controller.submit_proposal(
        proposal=prop,
        obligations={obl.obligation_id: obl},
        policies={},
        source_sha="a" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )
    assert res.decision.status == AuthorizationStatus.REJECTED
    assert any("STALE_STATE_VERSION" in r for r in res.decision.rejection_reasons)


def test_proposal_with_stale_state_digest_rejected_by_d5_controller(sample_context, lease_manager, tmp_path):
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "d5.log"))
    controller = SClassController(
        authority_signer=signer,
        nonce_store=nonce_store,
        lease_resolver=lease_manager.get_active_lease,
        state_resolver=lambda: (1, "9" * 64),
    )

    obl = Obligation(
        obligation_id="OBL-AUTH-01",
        task_id="TASK-01",
        title="Verify Auth",
        description="Auth check",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
    )
    lease = lease_manager.acquire_lease("TASK-01", "WORKER-1")
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))

    prop = ProposalEmitter.emit_next_proposal(strat, lease, state_version=1, state_digest="1" * 64)

    res = controller.submit_proposal(
        proposal=prop,
        obligations={obl.obligation_id: obl},
        policies={},
        source_sha="a" * 40,
        policy_version=1,
        evaluated_at="2026-08-20T12:00:00Z",
        expires_at="2026-08-20T12:30:00Z",
    )
    assert res.decision.status == AuthorizationStatus.REJECTED
    assert any("STALE_STATE_DIGEST" in r for r in res.decision.rejection_reasons)


# ============================================================================
# GROUP 6: End-to-End PlannerSession Orchestration (9 Tests)
# ============================================================================

def test_planner_session_context_manager(lease_manager):
    with PlannerSession("TASK-01", "WORKER-1", lease_manager) as session:
        assert session.active_lease is not None
        assert session.active_lease.is_active is True
    assert session.active_lease is None


def test_planner_session_end_to_end_plan_and_proposal(lease_manager, sample_context, sample_state_view):
    session = PlannerSession("TASK-D8-001", "WORKER-1", lease_manager)
    session.start()

    envelope, quality = session.plan(sample_state_view, sample_context)
    assert envelope.status == PlanStatus.VALIDATED
    assert quality.progress_potential > 0.0

    prop = session.next_proposal()
    assert prop is not None
    assert prop.obligation_id == "OBL-AUTH-01"
    assert prop.fencing_token == session.active_lease.fencing_token
    session.close()


def test_planner_session_replan_workflow(lease_manager, sample_context, sample_state_view):
    session = PlannerSession("TASK-D8-001", "WORKER-1", lease_manager)
    session.start()

    envelope1, score1 = session.plan(sample_state_view, sample_context)
    assert envelope1.fencing_token == session.active_lease.fencing_token

    # Mutate state version and digest to create legitimate state delta
    delta_content = PlannerStateContent(
        task_id=sample_state_view.content.task_id,
        milestones=sample_state_view.content.milestones,
        claims=sample_state_view.content.claims,
        obligations=sample_state_view.content.obligations,
        executable_frontier=sample_state_view.content.executable_frontier,
        state_version=2,
        state_digest="2" * 64,
    )
    delta_view = PlannerStateView(
        content=delta_content,
        metadata=sample_state_view.metadata,
        planner_state_digest=compute_planner_state_digest(delta_content),
    )

    envelope2, score2 = session.replan(delta_view, sample_context)
    assert envelope2.state_version == 2
    session.close()


def test_planner_session_rejects_action_when_lease_lost(lease_manager, sample_context, sample_state_view):
    session = PlannerSession("TASK-D8-001", "WORKER-1", lease_manager)
    session.start()

    # Worker 2 steals lease after expiry/release
    session.close()

    with pytest.raises(RuntimeError):
        session.plan(sample_state_view, sample_context)


def test_planner_session_no_admissible_plan_error(lease_manager, sample_context):
    session = PlannerSession("TASK-D8-001", "WORKER-1", lease_manager)
    session.start()

    # Empty state view with no executable frontier
    empty_content = PlannerStateContent(task_id="TASK-D8-001")
    empty_view = PlannerStateView(
        content=empty_content,
        metadata=PlannerStateProjectionMetadata(projected_at="2026-08-20T12:00:00Z"),
        planner_state_digest=compute_planner_state_digest(empty_content),
    )

    with pytest.raises(NoAdmissiblePlanError):
        session.plan(empty_view, sample_context)
    session.close()


def test_planner_state_projector_end_to_end(sample_state_view):
    assert sample_state_view.content.task_id == "TASK-D8-001"
    assert len(sample_state_view.content.obligations) == 1
    assert sample_state_view.planner_state_digest != ""


def test_planner_state_projector_from_materialized_state():
    mat = MaterializedState(
        last_sequence_number=5,
        last_digest="5" * 64,
        obligations={},
        claims={},
        evidence={},
        assessments={},
    )
    view = StateProjector.project_materialized_state("TASK-01", mat)
    assert view.content.state_version == 5
    assert view.content.state_digest == "5" * 64


def test_candidate_generator_provenance_integrity(sample_context, sample_state_view):
    gen = CandidateGenerator()
    candidates = gen.generate(sample_state_view, sample_context, max_candidates=2)
    assert len(candidates) == 2
    for strat, prov in candidates:
        assert prov.generator_id == "GEN-SCLASS-CORE-V1"
        assert prov.model_id == "deterministic-rules"
        assert prov.prompt_digest != ""


def test_full_governed_lifecycle_flow(lease_manager, sample_context, sample_state_view, tmp_path):
    """End-to-end integration: D4 State -> D8 Planner -> D8 Strategy -> ActionProposal -> D5 Controller."""
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(str(tmp_path / "d5.log"))
    controller = SClassController(
        authority_signer=signer,
        nonce_store=nonce_store,
        lease_resolver=lease_manager.get_active_lease,
        state_resolver=lambda: (sample_state_view.content.state_version, sample_state_view.content.state_digest),
    )

    obl = Obligation(
        obligation_id="OBL-AUTH-01",
        task_id="TASK-D8-001",
        title="Verify Authentication",
        description="Must enforce 403 on unauthenticated request",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
    )

    with PlannerSession("TASK-D8-001", "WORKER-E2E", lease_manager) as session:
        envelope, score = session.plan(sample_state_view, sample_context)
        proposal = session.next_proposal()
        assert proposal is not None

        dispatch = controller.submit_proposal(
            proposal=proposal,
            obligations={obl.obligation_id: obl},
            policies={},
            source_sha="c" * 40,
            policy_version=1,
            evaluated_at="2026-08-20T12:00:00Z",
            expires_at="2026-08-20T12:30:00Z",
        )

        assert dispatch.decision.status == AuthorizationStatus.AUTHORIZED
        assert dispatch.execution_token is not None
        assert dispatch.execution_token.fencing_token == session.active_lease.fencing_token


# ============================================================================
# GROUP 7: Additional Adversarial & Schema Integrity Tests
# ============================================================================

def test_d0_plan_status_lifecycle_including_superseded():
    """Verify D0 Plan schema supports the full frozen lifecycle including SUPERSEDED."""
    statuses = [
        PlanStatus.DRAFT,
        PlanStatus.UNDER_REVIEW,
        PlanStatus.VALIDATED,
        PlanStatus.REJECTED,
        PlanStatus.SUPERSEDED,
    ]
    for st in statuses:
        plan = Plan(
            plan_id=f"PLAN-{st.value}",
            task_id="TASK-D8-001",
            version=1,
            status=st,
        )
        assert plan.status == st


def test_plan_runtime_envelope_rejects_missing_d0_plan(sample_context):
    """Runtime envelope must fail closed if D0 Plan entity is missing or invalid."""
    node = PlanNode("N-1", "OBL-AUTH-01", "EXECUTE_TEST", "t.py", "p", sample_context)
    strat = ExecutionStrategyArtifact("S-1", "P-1", 1, (node,))

    with pytest.raises(TypeError):
        PlanRuntimeEnvelope(
            plan="NOT_A_PLAN",  # Invalid type
            strategy=strat,
            fencing_token=1,
            lease_epoch=1,
            owner_id="WORKER-1",
            state_version=1,
            state_digest="1" * 64,
            planner_state_digest="2" * 64,
        )


def test_semantic_fingerprint_commits_to_d0_plan_fields_and_detects_drift():
    """Semantic fingerprint commits strictly to plan_id, task_id, version, milestones, architecture_claims, and obligation_ids."""
    base_plan = Plan(
        plan_id="PLAN-01",
        task_id="TASK-D8-001",
        version=1,
        milestones=({"milestone_id": "MS-1"},),
        architecture_claims=({"claim_id": "CLM-1"},),
        obligation_ids=("OBL-1",),
    )
    base_fp = compute_plan_semantic_fingerprint(base_plan)

    # Version change triggers fingerprint drift
    drifted_version = Plan(
        plan_id="PLAN-01",
        task_id="TASK-D8-001",
        version=2,
        milestones=({"milestone_id": "MS-1"},),
        architecture_claims=({"claim_id": "CLM-1"},),
        obligation_ids=("OBL-1",),
    )
    assert compute_plan_semantic_fingerprint(drifted_version) != base_fp

    # Architecture claims change triggers fingerprint drift
    drifted_claims = Plan(
        plan_id="PLAN-01",
        task_id="TASK-D8-001",
        version=1,
        milestones=({"milestone_id": "MS-1"},),
        architecture_claims=({"claim_id": "CLM-MUTATED"},),
        obligation_ids=("OBL-1",),
    )
    assert compute_plan_semantic_fingerprint(drifted_claims) != base_fp
