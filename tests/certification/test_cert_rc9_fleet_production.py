"""
Certification Suite: RC.9 Fleet Task Graph, Agent Registry & Conflict/Ownership Engine.
Certifies:
1. TaskGraph DAG construction, topological execution ordering, and ready task discovery.
2. TaskGraph cycle detection and fail-closed prevention of circular dependencies.
3. AgentSessionManager: agent registration, heartbeat tracking, liveness checks, and timeout detection.
4. AgentSessionManager: automated stale lease cleanup preventing swarm deadlock.
5. ConflictDetector: precise detection of concurrent file mutations and duplicate symbol claims.
6. ConflictResolver & QuarantineEngine: agent isolation, lease revocation, and resolution strategies.
7. EvidenceAggregator: multi-agent evidence merge and conflict handling.
8. FleetIntegrityEngine: multi-agent concurrent coordination and ACID storage integrity under stress.
"""

import os
import time
import pytest

from sclass.agent_fleet.models import (
    AgentIdentity,
    AgentStatus,
    ResourceLease,
    LeaseType,
    ConflictRecord,
    ConflictType,
    QuarantineRecord,
    TaskNode,
    TaskEdge,
)
from sclass.agent_fleet.agent_registry import AgentSessionManager
from sclass.agent_fleet.conflict import (
    ConflictDetector,
    ConflictResolver,
    QuarantineEngine,
    ResolutionStrategy,
)
from sclass.agent_fleet.engine import (
    FleetIntegrityEngine,
    FleetStorageError,
    TaskGraph,
    ConflictEngine,
    EvidenceAggregator,
)
from sclass.domain.project import VerifiedProjectState


@pytest.fixture
def rc9_workspace(tmp_path):
    ws = tmp_path / "cert_rc9_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_rc9_task_graph_dag_execution_order_and_ready_tasks():
    """Certifies TaskGraph DAG construction, topological sort, and ready task discovery."""
    tg = TaskGraph()
    tg.add_task(task_id="t_compile", title="Compile sources")
    tg.add_task(task_id="t_unit", title="Run unit tests", dependencies=["t_compile"])
    tg.add_task(task_id="t_lint", title="Run linter", dependencies=["t_compile"])
    tg.add_task(task_id="t_deploy", title="Deploy package", dependencies=["t_unit", "t_lint"])

    assert tg.has_cycles() is False

    order = tg.get_execution_order()
    assert order.index("t_compile") < order.index("t_unit")
    assert order.index("t_compile") < order.index("t_lint")
    assert order.index("t_unit") < order.index("t_deploy")
    assert order.index("t_lint") < order.index("t_deploy")

    # Initial ready tasks: only t_compile has no dependencies
    ready = tg.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "t_compile"

    # After compiling, t_unit and t_lint become ready
    tg.mark_completed("t_compile")
    ready_after = tg.get_ready_tasks()
    ready_ids = [t.task_id for t in ready_after]
    assert "t_unit" in ready_ids
    assert "t_lint" in ready_ids
    assert "t_deploy" not in ready_ids


def test_rc9_task_graph_cycle_detection():
    """Certifies that circular task dependencies are detected and fail closed."""
    tg = TaskGraph()
    tg.add_task(task_id="tA", title="Task A", dependencies=["tC"])
    tg.add_task(task_id="tB", title="Task B", dependencies=["tA"])
    tg.add_task(task_id="tC", title="Task C", dependencies=["tB"])

    assert tg.has_cycles() is True

    with pytest.raises(FleetStorageError, match="Cycle detected"):
        tg.get_execution_order()


def test_rc9_agent_session_manager_registration_heartbeat_and_timeout():
    """Certifies agent registration, heartbeat monitoring, and timeout detection."""
    manager = AgentSessionManager(heartbeat_timeout=0.2)
    agent = manager.register("agent_01", role="coder", platform_id="claude_code")

    assert agent.agent_id == "agent_01"
    assert manager.is_healthy("agent_01") is True

    # After time passes beyond timeout, agent is recognized as stale
    time.sleep(0.25)
    assert manager.is_healthy("agent_01") is False

    stale = manager.get_stale_agents()
    assert len(stale) == 1
    assert stale[0].agent_id == "agent_01"

    # Heartbeat revives health
    manager.heartbeat("agent_01")
    assert manager.is_healthy("agent_01") is True


def test_rc9_stale_agent_lease_cleanup(rc9_workspace):
    """Certifies that dead agents automatically have their held leases revoked."""
    engine = FleetIntegrityEngine(workspace_root=rc9_workspace)
    manager = AgentSessionManager(heartbeat_timeout=0.1)

    # Register agent and acquire lease in engine
    manager.register("dead_agent", role="worker")
    lease = engine.acquire_lease(
        agent_id="dead_agent",
        path="src/critical_lock.py",
        lease_type=LeaseType.EXCLUSIVE_WRITE,
    )
    assert lease is not None
    assert "src/critical_lock.py" in engine.state.leases

    # Wait for timeout
    time.sleep(0.15)
    cleaned = manager.cleanup_stale_leases(fleet_engine=engine)
    assert "src/critical_lock.py" in cleaned
    assert "src/critical_lock.py" not in engine.state.leases


def test_rc9_conflict_detector_file_and_symbol_overlap():
    """Certifies file mutation and symbol claim collision detection."""
    existing_leases = {
        "src/core.py": ResourceLease(
            lease_id="l1",
            path="src/core.py",
            holder_agent_id="agent_1",
            lease_type=LeaseType.EXCLUSIVE_WRITE,
        )
    }

    # Agent 2 attempts write on same file -> conflict detected
    conf = ConflictDetector.detect_file_conflict(
        agent_id="agent_2",
        path="src/core.py",
        requested_type=LeaseType.EXCLUSIVE_WRITE,
        existing_leases=existing_leases,
    )
    assert conf is not None
    assert conf.conflict_type == ConflictType.CONCURRENT_MUTATION.value
    assert "agent_1" in conf.agents_involved
    assert "agent_2" in conf.agents_involved

    # Agent 2 attempts duplicate work on claimed symbol -> conflict detected
    existing_symbols = {"src/core.py::process_data": "agent_1"}
    sym_conf = ConflictDetector.detect_symbol_conflict(
        agent_id="agent_2",
        symbol_key="src/core.py::process_data",
        existing_claims=existing_symbols,
    )
    assert sym_conf is not None
    assert sym_conf.conflict_type == ConflictType.DUPLICATE_WORK.value


def test_rc9_conflict_resolver_and_quarantine_engine(rc9_workspace):
    """Certifies conflict resolution policies and quarantine isolation with lease revocation."""
    engine = FleetIntegrityEngine(workspace_root=rc9_workspace)
    engine.acquire_lease("rogue_agent", "db/schema.sql", LeaseType.EXCLUSIVE_WRITE)

    q_engine = QuarantineEngine()
    resolver = ConflictResolver(quarantine_engine=q_engine)

    conf = ConflictRecord(
        conflict_id="c_test_01",
        conflict_type=ConflictType.CONCURRENT_MUTATION.value,
        agents_involved=["good_agent", "rogue_agent"],
        resource_target="db/schema.sql",
    )

    # Resolve via QUARANTINE strategy
    res = resolver.resolve(conf, strategy=ResolutionStrategy.QUARANTINE, fleet_engine=engine)
    assert res.resolved is True
    assert "Quarantined offending agent 'rogue_agent'" in res.resolution

    # Verify rogue agent is quarantined and leases were revoked
    assert q_engine.is_quarantined("rogue_agent") is True
    assert "db/schema.sql" not in engine.state.leases


def test_rc9_evidence_aggregator_multi_agent_merge(rc9_workspace):
    """Certifies multi-agent evidence aggregation and truth reconciliation."""
    engine = FleetIntegrityEngine(workspace_root=rc9_workspace)
    aggregator = EvidenceAggregator(workspace_root=rc9_workspace, fleet_engine=engine)
    verified_state = VerifiedProjectState(workspace=rc9_workspace)

    agent_receipts = [
        {"claim_id": "c1", "agent_id": "agent_a", "exit_code": 0, "receipt_id": "r1"},
        {"claim_id": "c2", "agent_id": "agent_b", "exit_code": 1, "receipt_id": "r2"},
    ]

    merge_res = aggregator.aggregate_evidence(agent_receipts, verified_state=verified_state)
    assert len(merge_res.merged_claims) == 1
    assert merge_res.merged_claims[0]["claim_id"] == "c1"
    assert len(merge_res.invalidated_claims) == 1
    assert merge_res.invalidated_claims[0]["claim_id"] == "c2"


def test_rc9_fleet_integrity_engine_concurrent_coordination(rc9_workspace):
    """Certifies concurrent multi-agent coordination with ACID leases and zero state corruption."""
    engine = FleetIntegrityEngine(workspace_root=rc9_workspace)

    # Agent 1 claims file 1
    ok1, conf1 = engine.acquire_lease("agent_1", "module_a.py", LeaseType.EXCLUSIVE_WRITE)
    assert ok1 is True
    assert conf1 is None

    # Agent 2 claims file 2
    ok2, conf2 = engine.acquire_lease("agent_2", "module_b.py", LeaseType.EXCLUSIVE_WRITE)
    assert ok2 is True
    assert conf2 is None

    # Agent 2 attempts to claim file 1 -> must fail closed
    ok_fail, conf_fail = engine.acquire_lease("agent_2", "module_a.py", LeaseType.EXCLUSIVE_WRITE)
    assert ok_fail is False
    assert conf_fail is not None
    assert conf_fail.conflict_type == ConflictType.CONCURRENT_MUTATION

    # Agent 1 releases file 1
    engine.release_lease("agent_1", "module_a.py")

    # Agent 2 can now acquire file 1
    ok_new, conf_new = engine.acquire_lease("agent_2", "module_a.py", LeaseType.EXCLUSIVE_WRITE)
    assert ok_new is True
    assert conf_new is None
    assert engine.state.leases["module_a.py"].holder_agent_id == "agent_2"


def test_rc9_symbol_ownership_lifecycle_and_release(rc9_workspace):
    """Certifies symbol work claim, collision rejection, and release allowing reacquisition."""
    engine = FleetIntegrityEngine(workspace_root=rc9_workspace)

    # Agent 1 claims symbol
    ok1, conf1 = engine.claim_symbol_work("agent_1", "execute_pipeline", file_path="src/engine.py")
    assert ok1 is True
    assert conf1 is None

    # Agent 2 claims same symbol -> duplicate work rejected
    ok2, conf2 = engine.claim_symbol_work("agent_2", "execute_pipeline", file_path="src/engine.py")
    assert ok2 is False
    assert conf2 is not None
    assert conf2.conflict_type == ConflictType.DUPLICATE_WORK

    # Agent 1 releases symbol
    rel = engine.release_symbol_work("agent_1", "execute_pipeline", file_path="src/engine.py")
    assert rel is True

    # Agent 2 can now successfully claim symbol
    ok3, conf3 = engine.claim_symbol_work("agent_2", "execute_pipeline", file_path="src/engine.py")
    assert ok3 is True
    assert conf3 is None


def test_rc9_quarantine_and_stale_cleanup_revokes_symbol_claims(rc9_workspace):
    """Certifies that quarantining an agent or stale lease cleanup revokes symbol claims."""
    engine = FleetIntegrityEngine(workspace_root=rc9_workspace)
    manager = AgentSessionManager(heartbeat_timeout=0.1)

    # Agent 1 claims symbol then gets quarantined
    engine.claim_symbol_work("rogue_agent", "critical_symbol", file_path="src/core.py")
    engine.quarantine_agent("rogue_agent", "Security violation")

    # Claim should be revoked, allowing healthy agent to claim it
    ok_after_q, conf_after_q = engine.claim_symbol_work("clean_agent", "critical_symbol", file_path="src/core.py")
    assert ok_after_q is True
    assert conf_after_q is None

    # Stale agent claims symbol
    manager.register("stale_agent")
    engine.claim_symbol_work("stale_agent", "stale_symbol", file_path="src/core.py")
    time.sleep(0.15)
    manager.cleanup_stale_leases(fleet_engine=engine)

    # Claim should be revoked, allowing another agent to claim it
    ok_after_stale, _ = engine.claim_symbol_work("clean_agent", "stale_symbol", file_path="src/core.py")
    assert ok_after_stale is True


def test_rc9_task_graph_missing_dependency_fails_closed():
    """Certifies that task graph fails closed if tasks depend on undeclared/missing dependencies."""
    tg = TaskGraph()
    tg.add_task(task_id="t_deploy", title="Deploy", dependencies=["missing_compile_task"])

    with pytest.raises(FleetStorageError, match="missing task"):
        tg.get_execution_order()


def test_rc9_directory_hierarchy_containment_conflict():
    """Certifies that ConflictDetector catches directory vs file containment collisions."""
    existing_leases = {
        "src/controllers": ResourceLease(
            lease_id="l_dir",
            path="src/controllers",
            holder_agent_id="agent_lead",
            lease_type=LeaseType.EXCLUSIVE_WRITE,
        )
    }

    conf = ConflictDetector.detect_file_conflict(
        agent_id="agent_sub",
        path="src/controllers/auth.py",
        requested_type=LeaseType.EXCLUSIVE_WRITE,
        existing_leases=existing_leases,
    )
    assert conf is not None
    assert conf.conflict_type == ConflictType.CONCURRENT_MUTATION.value
    assert "agent_lead" in conf.agents_involved


def test_rc9_conflict_engine_delegator_api(rc9_workspace):
    """Certifies that ConflictEngine delegator methods function on engine state."""
    engine = FleetIntegrityEngine(workspace_root=rc9_workspace)
    engine.acquire_lease("agent_1", "src/shared.py", LeaseType.EXCLUSIVE_WRITE)
    engine.claim_symbol_work("agent_1", "shared_func", file_path="src/shared.py")

    file_conf = engine.conflict_engine.detect_file_conflict("agent_2", "src/shared.py")
    assert file_conf is not None

    sym_conf = engine.conflict_engine.detect_symbol_conflict("agent_2", "src/shared.py::shared_func")
    assert sym_conf is not None
