"""
D8 Read-Only Analytical Fabric & Ephemeral Worker Test Suite (Phase C).
Verifies structural object-capability isolation, context binding,
runtime-owned execution lifecycle, ResourceTracker atomic reservations,
digest verification, candidate plan critique verification, analytical lineage,
and the mandatory architectural contracts & C51-C85 adversarial properties.
"""

import copy
import hashlib
import hmac
import os
import sys
import threading
import time
import pytest
from dataclasses import FrozenInstanceError
from concurrent.futures import ThreadPoolExecutor

from planner.analysis import (
    AnalysisArtifact,
    AnalystType,
    Observation,
    Hypothesis,
    Inference,
    Uncertainty,
    Contradiction,
    Implication,
    ToolProvenance,
    ModelProvenance,
    DigestVerificationError,
    compute_analysis_artifact_digest,
    compute_analysis_artifact_canonical_bytes,
)
from planner.fabric import (
    WorkerIdentity,
    IssuedAnalysisIdentity,
    WorkerExecutionHandle,
    WorkerRuntime,
    WorkerContext,
    CandidatePlanView,
    ReadOnlyFabricContext,
    CapabilityScope,
    WorkerResourceBudget,
    WorkerRegistry,
    WorkerRunner,
    ArtifactEmitter,
    WorkerTerminationReason,
    WorkerExecutionResult,
    ResourceTracker,
    ResourceExhaustionError,
    StaleContextError,
    ReadOnlyRepositoryAccessor,
    ReadOnlyEventLogAccessor,
    ReadOnlyEvidenceAccessor,
    EphemeralAnalyst,
    RepositoryAnalyst,
    EvidenceAnalyst,
    ArchitectureAnalyst,
    DependencyAnalyst,
    RiskRegressionAnalyst,
    PlanCriticAnalyst,
)


@pytest.fixture
def mock_repo(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "core.py").write_text("class CoreEngine:\n    def run(self): pass\n", encoding="utf-8")
    (repo_dir / "src" / "utils.py").write_text("import sys\ndef helper(): pass\n", encoding="utf-8")
    (repo_dir / "tests").mkdir()
    (repo_dir / "tests" / "test_core.py").write_text("from src.core import CoreEngine\ndef test_ok(): pass\n", encoding="utf-8")
    (repo_dir / "docs").mkdir()
    (repo_dir / "docs" / "readme.md").write_text("# Project Docs\n", encoding="utf-8")
    return str(repo_dir)


@pytest.fixture
def runtime():
    return WorkerRuntime(initial_epoch=1)


@pytest.fixture
def default_identity(runtime):
    return runtime.issue_identity(AnalystType.REPOSITORY)


@pytest.fixture
def default_context(default_identity):
    return WorkerContext(
        identity=default_identity,
        task_id="TASK-001",
        repository_id="repo-main",
        source_sha="a" * 40,
        planner_state_digest="b" * 64,
        capability_scope=CapabilityScope(),
        resource_budget=WorkerResourceBudget(
            max_tool_calls=20,
            max_wall_time_seconds=10.0,
            max_output_bytes=100_000,
            max_output_artifacts=1,
            max_model_tokens=5_000,
        ),
    )


@pytest.fixture
def default_execution_handle(runtime, default_context):
    return runtime.issue_execution(default_context)


@pytest.fixture
def default_issued_identity(runtime, default_execution_handle):
    return runtime.issue_analysis_identity(default_execution_handle)


# ============================================================================
# 10 MANDATORY PHASE C ARCHITECTURAL CONTRACTS
# ============================================================================

def test_contract_1_event_log_accessor_immutable_snapshots():
    """Contract 1: ReadOnlyEventLogAccessor returns deep-copied snapshots; mutating return does not mutate source."""
    class MutableEvent:
        def __init__(self, seq, data):
            self.sequence_number = seq
            self.payload = {"status": data}

    original_event = MutableEvent(1, "ORIGINAL")
    source_events = [original_event]

    tracker = ResourceTracker(WorkerResourceBudget())
    accessor = ReadOnlyEventLogAccessor(
        events_provider=lambda: source_events,
        state_digest_provider=lambda: "0" * 64,
        tracker=tracker,
    )

    events = accessor.get_events()
    assert len(events) == 1
    events[0].payload["status"] = "TAMPERED"
    assert original_event.payload["status"] == "ORIGINAL"


def test_contract_2_evidence_accessor_deep_copy_no_mutable_leaks():
    """Contract 2: ReadOnlyEvidenceAccessor cannot leak mutable D4 objects; mutations do not affect internal state."""
    class MutableClaim:
        def __init__(self, cid, status):
            self.claim_id = cid
            self.status = status
            self.metadata = {"reviewed": False}

    original_claim = MutableClaim("CLM-001", "UNSUPPORTED")
    claims = {"CLM-001": original_claim}

    tracker = ResourceTracker(WorkerResourceBudget())
    accessor = ReadOnlyEvidenceAccessor(
        claims=claims,
        evidence={},
        assessments=None,
        scope=CapabilityScope(),
        tracker=tracker,
    )

    retrieved = accessor.get_claim("CLM-001")
    assert retrieved is not None
    retrieved.status = "VERIFIED_TRUE"
    retrieved.metadata["reviewed"] = True

    assert original_claim.status == "UNSUPPORTED"
    assert original_claim.metadata["reviewed"] is False


def test_contract_3_repository_path_containment_comprehensive(mock_repo, tmp_path):
    """Contract 3: Path containment strictly handles .., absolute paths, symlinks, drive changes, and UNC paths."""
    tracker = ResourceTracker(WorkerResourceBudget())
    repo = ReadOnlyRepositoryAccessor(mock_repo, "a" * 40, CapabilityScope(), tracker)

    # 1. Parent traversal
    with pytest.raises(PermissionError, match="Path containment violation"):
        repo.read_file("../../outside.txt")

    # 2. Absolute path outside repository
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")
    with pytest.raises(PermissionError, match="Path containment violation"):
        repo.read_file(str(outside_file))

    # 3. Symlink pointing outside repo
    link_outside = os.path.join(mock_repo, "src", "link_out")
    try:
        os.symlink(str(outside_file), link_outside)
        with pytest.raises(PermissionError, match="Path containment violation"):
            repo.read_file("src/link_out")
    except (OSError, NotImplementedError):
        pass

    # 4. Windows drive changes (e.g. Z:\some\path)
    with pytest.raises(PermissionError, match="Path containment violation"):
        repo.read_file("Z:\\nonexistent\\drive\\path.txt")

    # 5. UNC / extended paths outside repo
    with pytest.raises(PermissionError, match="Path containment violation"):
        repo.read_file("\\\\server\\share\\file.txt")


def test_contract_4_capability_scope_cannot_be_widened_by_worker():
    """Contract 4: CapabilityScope is frozen; worker cannot widen permissions."""
    scope = CapabilityScope(allowed_file_patterns=("src/*.py",), allow_ast_parsing=False)
    with pytest.raises(FrozenInstanceError):
        scope.allow_ast_parsing = True  # type: ignore
    with pytest.raises(FrozenInstanceError):
        scope.allowed_file_patterns = ("*",)  # type: ignore


def test_contract_5_worker_epoch_is_runtime_issued_never_worker_controlled(runtime, default_context, default_issued_identity):
    """Contract 5: worker_epoch is immutable in context; emitter rejects artifacts with forged epoch."""
    tracker = ResourceTracker(default_context.resource_budget)
    emitter = ArtifactEmitter(default_context, default_issued_identity, tracker, runtime=runtime)

    art_forged = AnalysisArtifact(
        analysis_id=default_issued_identity.analysis_id,
        execution_id=default_issued_identity.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
        worker_epoch=99,
    )
    with pytest.raises(ValueError, match="Artifact worker_epoch 99 does not match"):
        emitter.emit(art_forged)


def test_contract_6_budget_exhaustion_stops_further_calls(default_context, mock_repo):
    """Contract 6: Once budget is exhausted, any subsequent tool call or output immediately raises ResourceExhaustionError."""
    budget = WorkerResourceBudget(max_tool_calls=1)
    tracker = ResourceTracker(budget)
    repo = ReadOnlyRepositoryAccessor(mock_repo, default_context.source_sha, default_context.capability_scope, tracker)

    repo.file_exists("src/core.py")

    with pytest.raises(ResourceExhaustionError):
        repo.file_exists("src/core.py")

    with pytest.raises(ResourceExhaustionError, match="resource budget already exhausted"):
        repo.read_file("src/core.py")


def test_contract_7_concurrent_workers_cannot_cross_use_state(runtime, default_context, mock_repo):
    """Contract 7: Concurrent workers have distinct isolated contexts, budgets, and epochs."""
    def run_worker_thread(epoch_id):
        rt = WorkerRuntime(initial_epoch=epoch_id)
        ident = rt.issue_identity(AnalystType.REPOSITORY)
        ctx = WorkerContext(
            identity=ident,
            task_id=f"TASK-{epoch_id}",
            repository_id=default_context.repository_id,
            source_sha=default_context.source_sha,
            planner_state_digest=default_context.planner_state_digest,
        )
        exec_handle = rt.issue_execution(ctx)
        return WorkerRunner.run_worker(
            worker=RepositoryAnalyst(),
            context=ctx,
            execution=exec_handle,
            runtime=rt,
            repo_root=mock_repo,
            active_repo_sha=ctx.source_sha,
            events_provider=lambda: (),
            state_digest_provider=lambda: ctx.planner_state_digest,
            claims={},
            evidence={},
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(run_worker_thread, i) for i in range(1, 6)]
        results = [f.result() for f in futures]

    for i, res in enumerate(results, 1):
        assert res.termination_reason == WorkerTerminationReason.COMPLETED
        assert res.artifact is not None
        assert res.artifact.worker_epoch == i
        assert res.artifact.task_id == f"TASK-{i}"


def test_contract_8_analysts_lack_authority_methods():
    """Contract 8: Analysts structurally lack methods to authorize, select plans, close claims, mint tokens, or execute."""
    analysts = [
        RepositoryAnalyst(),
        EvidenceAnalyst(),
        ArchitectureAnalyst(),
        DependencyAnalyst(),
        RiskRegressionAnalyst(),
        PlanCriticAnalyst(),
    ]
    forbidden_methods = [
        "authorize",
        "select_plan",
        "close_claim",
        "mutate_claim",
        "mint_token",
        "execute",
        "execute_proposal",
        "mutate_policy",
        "acquire_lease",
    ]
    for analyst in analysts:
        for method in forbidden_methods:
            assert not hasattr(analyst, method), f"{analyst.__class__.__name__} must not have {method}"


def test_contract_9_plan_critic_is_advisory_not_hidden_planner(runtime, default_context, mock_repo):
    """Contract 9: PlanCriticAnalyst emits only advisory AnalysisArtifact; records INSUFFICIENT_INPUT when no plan given."""
    critic = PlanCriticAnalyst()
    assert not hasattr(critic, "generate_plan")
    assert not hasattr(critic, "select_plan")
    assert not hasattr(critic, "emit_proposal")

    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.PLAN_CRITIC),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    exec_handle = runtime.issue_execution(ctx)
    result = WorkerRunner.run_worker(
        worker=critic,
        context=ctx,
        execution=exec_handle,
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
        candidate_plan=None,  # No candidate plan supplied
    )
    assert result.termination_reason == WorkerTerminationReason.COMPLETED
    assert isinstance(result.artifact, AnalysisArtifact)
    assert result.artifact.analyst_type == AnalystType.PLAN_CRITIC
    # Epistemic honesty: uncertainty recorded because no plan was supplied
    assert len(result.artifact.uncertainties) == 1
    assert "INSUFFICIENT_INPUT" in result.artifact.observations[0].description


def test_contract_10_phase_c_does_not_add_d2_events_or_persistence():
    """Contract 10: Phase C creates zero new D2 event types and instantiates zero event stores."""
    import events.store
    from domain.types import EventType
    assert hasattr(events.store, "InMemoryEventStore")
    assert hasattr(events.store, "FileAppendEventStore")
    assert not hasattr(events.store, "WorkerEventStore")
    assert not hasattr(events.store, "AnalyticalEventStore")
    for member in EventType:
        assert "ANALYTICAL" not in member.name
        assert "WORKER" not in member.name


# ============================================================================
# C51 - C85 ADVERSARIAL & INVARIANT PROPERTIES
# ============================================================================

def test_c51_worker_execution_without_handle_impossible(default_context, mock_repo):
    """C51: Worker execution without a WorkerExecutionHandle and WorkerRuntime is type-rejected."""
    with pytest.raises(TypeError, match="execution must be a WorkerExecutionHandle instance"):
        WorkerRunner.run_worker(
            worker=RepositoryAnalyst(),
            context=default_context,
            execution="NOT_A_HANDLE",  # type: ignore
            runtime=WorkerRuntime(),
            repo_root=mock_repo,
            active_repo_sha=default_context.source_sha,
            events_provider=lambda: (),
            state_digest_provider=lambda: default_context.planner_state_digest,
            claims={},
            evidence={},
        )


def test_c52_same_handle_concurrent_claim_exactly_one_winner(runtime, default_context, mock_repo):
    """C52: When multiple concurrent threads attempt to claim the exact same WorkerExecutionHandle, exactly one wins."""
    exec_handle = runtime.issue_execution(default_context)

    winners = 0
    consumed_errors = 0
    lock = threading.Lock()

    def try_execute():
        nonlocal winners, consumed_errors
        res = WorkerRunner.run_worker(
            worker=RepositoryAnalyst(),
            context=default_context,
            execution=exec_handle,
            runtime=runtime,
            repo_root=mock_repo,
            active_repo_sha=default_context.source_sha,
            events_provider=lambda: (),
            state_digest_provider=lambda: default_context.planner_state_digest,
            claims={},
            evidence={},
        )
        with lock:
            if res.termination_reason == WorkerTerminationReason.COMPLETED:
                winners += 1
            elif res.termination_reason in (WorkerTerminationReason.CONTEXT_ALREADY_CONSUMED, WorkerTerminationReason.UNAUTHORIZED_EXECUTION_HANDLE):
                consumed_errors += 1

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(try_execute) for _ in range(10)]
        for f in futures:
            f.result()

    assert winners == 1
    assert consumed_errors == 9


def test_c53_forged_artifact_digest_rejected(runtime, default_context, default_issued_identity):
    """C53: Forged artifact digest rejected by constant-time SHA recomputation in ArtifactEmitter."""
    tracker = ResourceTracker(default_context.resource_budget)
    emitter = ArtifactEmitter(default_context, default_issued_identity, tracker, runtime=runtime)

    # Subclass with forged digest property
    class ForgedArtifact(AnalysisArtifact):
        @property
        def artifact_digest(self) -> str:
            return "0" * 64

    art_forged = ForgedArtifact(
        analysis_id=default_issued_identity.analysis_id,
        execution_id=default_issued_identity.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
    )

    with pytest.raises(DigestVerificationError, match="does not match recomputed digest"):
        emitter.emit(art_forged)


def test_c54_modified_provenance_with_stale_digest_rejected(runtime, default_context, default_issued_identity):
    """C54: Altering tool_provenance or model_provenance changes canonical digest; stale digest is rejected."""
    art_clean = AnalysisArtifact(
        analysis_id=default_issued_identity.analysis_id,
        execution_id=default_issued_identity.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
        tool_provenance=ToolProvenance(call_count=1),
    )
    original_digest = art_clean.artifact_digest

    class TamperedProvenanceArtifact(AnalysisArtifact):
        @property
        def artifact_digest(self) -> str:
            return original_digest

    art_tampered = TamperedProvenanceArtifact(
        analysis_id=default_issued_identity.analysis_id,
        execution_id=default_issued_identity.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
        tool_provenance=ToolProvenance(call_count=999),  # Tampered provenance
    )

    tracker = ResourceTracker(default_context.resource_budget)
    emitter = ArtifactEmitter(default_context, default_issued_identity, tracker, runtime=runtime)
    with pytest.raises(DigestVerificationError):
        emitter.emit(art_tampered)


def test_c55_caller_cannot_provide_worker_epoch(runtime):
    """C55: WorkerRuntime authoritatively controls worker_epoch; caller only supplies analyst_type."""
    ident = runtime.issue_identity(AnalystType.REPOSITORY)
    assert ident.worker_epoch == 1


def test_c56_caller_cannot_provide_worker_timestamp(runtime):
    """C56: WorkerRuntime supplies authoritative timestamp from clock, ignoring caller."""
    ident = runtime.issue_identity(AnalystType.REPOSITORY)
    assert ident.spawned_at != ""
    assert "T" in ident.spawned_at and ident.spawned_at.endswith("Z")


def test_c57_candidate_plan_view_mutation_impossible():
    """C57: CandidatePlanView is an immutable frozen dataclass; mutations raise FrozenInstanceError."""
    plan_view = CandidatePlanView(
        plan_id="PLAN-001",
        source_sha="a" * 40,
        planner_state_digest="b" * 64,
        node_ids=("N1", "N2"),
    )
    with pytest.raises(FrozenInstanceError):
        plan_view.plan_id = "TAMPERED"  # type: ignore
    with pytest.raises(FrozenInstanceError):
        plan_view.node_ids = ("N1",)  # type: ignore


def test_c58_plan_from_wrong_sha_rejected(runtime, default_context, mock_repo):
    """C58: CandidatePlanView with mismatched source_sha is caught by PlanCritic."""
    mismatched_plan = CandidatePlanView(
        plan_id="PLAN-001",
        source_sha="f" * 40,
        planner_state_digest=default_context.planner_state_digest,
        node_ids=("N1",),
    )
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.PLAN_CRITIC),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    res = WorkerRunner.run_worker(
        worker=PlanCriticAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
        candidate_plan=mismatched_plan,
    )
    assert res.termination_reason == WorkerTerminationReason.COMPLETED
    assert any(c.contradiction_id == "CON-CRIT-SHA-MISMATCH" for c in res.artifact.contradictions)


def test_c59_plan_from_wrong_planner_state_digest_rejected(runtime, default_context, mock_repo):
    """C59: CandidatePlanView with mismatched planner_state_digest is caught by PlanCritic."""
    mismatched_plan = CandidatePlanView(
        plan_id="PLAN-001",
        source_sha=default_context.source_sha,
        planner_state_digest="f" * 64,
        node_ids=("N1",),
    )
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.PLAN_CRITIC),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    res = WorkerRunner.run_worker(
        worker=PlanCriticAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
        candidate_plan=mismatched_plan,
    )
    assert res.termination_reason == WorkerTerminationReason.COMPLETED
    assert any(c.contradiction_id == "CON-CRIT-STATE-MISMATCH" for c in res.artifact.contradictions)


def test_c60_critic_without_candidate_records_insufficient_input(runtime, default_context, mock_repo):
    """C60: PlanCritic without CandidatePlanView truthfully records INSUFFICIENT_INPUT."""
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.PLAN_CRITIC),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    res = WorkerRunner.run_worker(
        worker=PlanCriticAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
        candidate_plan=None,
    )
    assert res.termination_reason == WorkerTerminationReason.COMPLETED
    assert "INSUFFICIENT_INPUT" in res.artifact.observations[0].description
    assert len(res.artifact.uncertainties) == 1


def test_c61_critic_cyclic_graph_records_cycle_contradiction(runtime, default_context, mock_repo):
    """C61: PlanCritic runs Kahn's algorithm and records CON-CRIT-TOPOLOGY-CYCLE on cyclic graphs."""
    cyclic_plan = CandidatePlanView(
        plan_id="PLAN-CYCLE-001",
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
        node_ids=("A", "B", "C"),
        dependency_edges=(("A", "B"), ("B", "C"), ("C", "A")),
    )
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.PLAN_CRITIC),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    res = WorkerRunner.run_worker(
        worker=PlanCriticAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
        candidate_plan=cyclic_plan,
    )
    assert res.termination_reason == WorkerTerminationReason.COMPLETED
    assert any(c.contradiction_id == "CON-CRIT-TOPOLOGY-CYCLE" for c in res.artifact.contradictions)


def test_c62_critic_missing_dependency_records_contradiction(runtime, default_context, mock_repo):
    """C62: PlanCritic catches dependency edges pointing to non-existent nodes."""
    broken_plan = CandidatePlanView(
        plan_id="PLAN-BROKEN-001",
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
        node_ids=("A", "B"),
        dependency_edges=(("A", "NON_EXISTENT_NODE"),),
    )
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.PLAN_CRITIC),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    res = WorkerRunner.run_worker(
        worker=PlanCriticAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
        candidate_plan=broken_plan,
    )
    assert res.termination_reason == WorkerTerminationReason.COMPLETED
    assert any(c.contradiction_id == "CON-CRIT-MISSING-DEPENDENCY" for c in res.artifact.contradictions)


def test_c63_critic_cannot_emit_d3_policy_verdict():
    """C63: PlanCriticAnalyst structurally lacks policy decision capabilities."""
    critic = PlanCriticAnalyst()
    assert not hasattr(critic, "evaluate_policy")
    assert not hasattr(critic, "policy_verdict")
    assert not hasattr(critic, "admit_proposal")


def test_c64_critic_cannot_emit_d4_truth_verdict():
    """C64: PlanCriticAnalyst structurally lacks D4 evidence/truth mutation capabilities."""
    critic = PlanCriticAnalyst()
    assert not hasattr(critic, "commit_truth")
    assert not hasattr(critic, "mutate_claim")
    assert not hasattr(critic, "claim_verdict")


def test_c65_analysis_id_tied_to_worker_execution_id(runtime, default_context, mock_repo):
    """C65: Analysis ID is issued by runtime tied to worker execution lineage."""
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.REPOSITORY),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    exec_handle = runtime.issue_execution(ctx)
    res = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=ctx,
        execution=exec_handle,
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
    )
    exec_core = exec_handle.execution_id.replace("EXEC-", "")
    assert res.artifact.analysis_id.startswith(f"ANA-{exec_core}-REPOSITORY-")
    assert res.artifact.execution_id == exec_handle.execution_id


def test_c66_two_executions_have_distinct_analysis_lineage(runtime, default_context, mock_repo):
    """C66: Successive executions produce distinct, non-colliding analysis IDs."""
    ctx1 = WorkerContext(
        identity=runtime.issue_identity(AnalystType.REPOSITORY),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    res1 = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=ctx1,
        execution=runtime.issue_execution(ctx1),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx1.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx1.planner_state_digest,
        claims={},
        evidence={},
    )

    ctx2 = WorkerContext(
        identity=runtime.issue_identity(AnalystType.REPOSITORY),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    res2 = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=ctx2,
        execution=runtime.issue_execution(ctx2),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx2.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx2.planner_state_digest,
        claims={},
        evidence={},
    )
    assert res1.artifact.analysis_id != res2.artifact.analysis_id
    assert res1.artifact.execution_id != res2.artifact.execution_id


def test_c67_emitter_reservation_failure_leaves_no_emitted_artifact(runtime, default_context, default_issued_identity):
    """C67: If resource budget reservation fails during emit, no artifact is stored in emitter."""
    budget = WorkerResourceBudget(max_output_bytes=100)
    tracker = ResourceTracker(budget)
    emitter = ArtifactEmitter(default_context, default_issued_identity, tracker, runtime=runtime)

    art = AnalysisArtifact(
        analysis_id=default_issued_identity.analysis_id,
        execution_id=default_issued_identity.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
    )

    with pytest.raises(ResourceExhaustionError):
        emitter.emit(art)

    assert emitter.emitted_artifact is None


def test_c68_forged_execution_handle_rejected(runtime, default_context, mock_repo):
    """C68: WorkerExecutionHandle with forged HMAC tag is rejected with UNAUTHORIZED_EXECUTION_HANDLE."""
    forged_handle = WorkerExecutionHandle(
        execution_id="EXEC-FORGED-001",
        worker_id=default_context.identity.worker_id,
        worker_epoch=default_context.identity.worker_epoch,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
        analyst_type=default_context.analyst_type,
        auth_tag="0" * 64,  # Forged fake HMAC tag
    )

    res = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=default_context,
        execution=forged_handle,
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=default_context.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: default_context.planner_state_digest,
        claims={},
        evidence={},
    )
    assert res.termination_reason == WorkerTerminationReason.UNAUTHORIZED_EXECUTION_HANDLE
    assert "HMAC authentication failed or was not issued by runtime" in res.error_message


def test_c69_tampered_coordinates_handle_rejected(runtime, default_context, mock_repo):
    """C69: WorkerExecutionHandle with tampered coordinates is rejected."""
    legit_handle = runtime.issue_execution(default_context)

    # Construct context with mismatched source_sha
    tampered_context = WorkerContext(
        identity=default_context.identity,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha="f" * 40,  # Tampered SHA
        planner_state_digest=default_context.planner_state_digest,
    )

    res = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=tampered_context,
        execution=legit_handle,
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha="f" * 40,
        events_provider=lambda: (),
        state_digest_provider=lambda: default_context.planner_state_digest,
        claims={},
        evidence={},
    )
    assert res.termination_reason == WorkerTerminationReason.CONTEXT_MISMATCH


def test_c70_handle_from_runtime_a_rejected_by_runtime_b(default_context, mock_repo):
    """C70: WorkerExecutionHandle issued by Runtime A is rejected when submitted to Runtime B."""
    runtime_a = WorkerRuntime()
    runtime_b = WorkerRuntime()

    handle_a = runtime_a.issue_execution(default_context)

    res = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=default_context,
        execution=handle_a,
        runtime=runtime_b,  # Different runtime instance with different secret
        repo_root=mock_repo,
        active_repo_sha=default_context.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: default_context.planner_state_digest,
        claims={},
        evidence={},
    )
    assert res.termination_reason == WorkerTerminationReason.UNAUTHORIZED_EXECUTION_HANDLE


def test_c71_identity_issuers_not_exposed_publicly(runtime):
    """C71: WorkerRuntime encapsulates issuer internals; does not expose issuer objects publicly."""
    assert not hasattr(runtime, "identity_issuer")
    assert not hasattr(runtime, "analysis_identity_issuer")
    import planner
    assert "WorkerIdentityIssuer" not in planner.__all__
    assert "AnalysisIdentityIssuer" not in planner.__all__


def test_c72_advance_epoch_not_caller_accessible(runtime):
    """C72: advance_epoch() is not caller-accessible on WorkerRuntime."""
    assert not hasattr(runtime, "advance_epoch")


def test_c73_runtime_directly_issues_identities_and_analysis_ids(runtime, default_context):
    """C73: WorkerRuntime provides direct, authoritative issuance methods."""
    ident = runtime.issue_identity(AnalystType.ARCHITECTURE)
    assert isinstance(ident, WorkerIdentity)
    assert ident.analyst_type == AnalystType.ARCHITECTURE

    handle = runtime.issue_execution(default_context)
    ana_id = runtime.issue_analysis_id(handle)
    exec_core = handle.execution_id.replace("EXEC-", "")
    assert ana_id.startswith(f"ANA-{exec_core}-{default_context.analyst_type.value}-")


def test_c74_artifact_without_execution_id_rejected():
    """C74: AnalysisArtifact without execution_id raises TypeError (mandatory field)."""
    with pytest.raises(TypeError):
        AnalysisArtifact(  # type: ignore
            analysis_id="ANA-001",
            analyst_type=AnalystType.REPOSITORY,
            task_id="TASK-001",
            repository_id="repo-main",
            source_sha="a" * 40,
            input_state_digest="b" * 64,
        )


def test_c75_sentinel_execution_id_rejected():
    """C75: Sentinel execution_id 'EXEC-000000000000' is rejected fail-closed."""
    with pytest.raises(ValueError, match="Invalid or sentinel execution_id rejected"):
        AnalysisArtifact(
            analysis_id="ANA-001",
            execution_id="EXEC-000000000000",
            analyst_type=AnalystType.REPOSITORY,
            task_id="TASK-001",
            repository_id="repo-main",
            source_sha="a" * 40,
            input_state_digest="b" * 64,
        )


def test_c76_analysis_id_from_execution_a_cannot_validate_as_execution_b(runtime, default_context):
    """C76: analysis_id issued for execution A fails lineage verification when emitted under execution B."""
    tracker = ResourceTracker(default_context.resource_budget)
    handle_b = runtime.issue_execution(default_context)
    issued_id_b = runtime.issue_analysis_identity(handle_b)
    emitter_b = ArtifactEmitter(default_context, issued_id_b, tracker, runtime=runtime)

    art_from_a = AnalysisArtifact(
        analysis_id="ANA-A00000000001-REPOSITORY-001",  # Lineage bound to EXEC-A00000000001
        execution_id=issued_id_b.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
    )

    with pytest.raises(StaleContextError, match="does not match runtime-issued analysis_id"):
        emitter_b.emit(art_from_a)


def test_c77_two_analyses_under_same_execution_have_distinct_sequence_identities(runtime, default_context):
    """C77: Successive analysis ID requests under the same execution have incrementing sequence identities."""
    handle = runtime.issue_execution(default_context)
    id1 = runtime.issue_analysis_identity(handle)
    id2 = runtime.issue_analysis_identity(handle)

    assert id1.analysis_id != id2.analysis_id
    assert id1.sequence == 1
    assert id2.sequence == 2
    assert id1.analysis_id.endswith("-001")
    assert id2.analysis_id.endswith("-002")


def test_c78_forged_analysis_id_with_valid_execution_prefix_rejected(runtime, default_context, default_issued_identity):
    """C78: Forged analysis_id with valid execution prefix is rejected by ArtifactEmitter."""
    tracker = ResourceTracker(default_context.resource_budget)
    emitter = ArtifactEmitter(default_context, default_issued_identity, tracker, runtime=runtime)

    # Forged ID that shares the execution prefix but differs in suffix
    forged_art = AnalysisArtifact(
        analysis_id=f"{default_issued_identity.analysis_id}-FORGED",
        execution_id=default_issued_identity.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
    )
    with pytest.raises(StaleContextError, match="does not match runtime-issued analysis_id"):
        emitter.emit(forged_art)


def test_c79_unissued_sequence_number_rejected(runtime, default_context, default_issued_identity):
    """C79: AnalysisArtifact with an unissued sequence number is rejected by ArtifactEmitter."""
    tracker = ResourceTracker(default_context.resource_budget)
    emitter = ArtifactEmitter(default_context, default_issued_identity, tracker, runtime=runtime)

    # Modify sequence number in analysis_id
    base_id = default_issued_identity.analysis_id[:-3] + "099"
    unissued_seq_art = AnalysisArtifact(
        analysis_id=base_id,
        execution_id=default_issued_identity.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
    )
    with pytest.raises(StaleContextError, match="does not match runtime-issued analysis_id"):
        emitter.emit(unissued_seq_art)


def test_c80_analysis_identity_from_execution_a_plus_artifact_execution_b_rejected(runtime, default_context):
    """C80: Artifact carrying execution_id B against an IssuedAnalysisIdentity issued for execution A is rejected."""
    tracker = ResourceTracker(default_context.resource_budget)
    handle_a = runtime.issue_execution(default_context)
    identity_a = runtime.issue_analysis_identity(handle_a)
    emitter = ArtifactEmitter(default_context, identity_a, tracker, runtime=runtime)

    art = AnalysisArtifact(
        analysis_id=identity_a.analysis_id,
        execution_id="EXEC-B00000000002",  # Mismatched execution_id
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
    )
    with pytest.raises(StaleContextError, match="does not match issued identity execution_id"):
        emitter.emit(art)


def test_c81_reused_duplicate_analysis_identity_rejected(runtime, default_context, default_issued_identity):
    """C81: Attempting to reuse an ArtifactEmitter for a duplicate emission fails closed."""
    tracker = ResourceTracker(default_context.resource_budget)
    emitter = ArtifactEmitter(default_context, default_issued_identity, tracker, runtime=runtime)

    art = AnalysisArtifact(
        analysis_id=default_issued_identity.analysis_id,
        execution_id=default_issued_identity.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
    )
    emitter.emit(art)

    # Second emit on the same emitter must fail
    with pytest.raises(ResourceExhaustionError, match="has already emitted an artifact and cannot be reused"):
        emitter.emit(art)


def test_c82_format_valid_but_unissued_execution_id_rejected(runtime, default_context, mock_repo):
    """C82: A format-valid but unissued/unauthenticated execution_id is rejected by WorkerRunner."""
    unissued_handle = WorkerExecutionHandle(
        execution_id="EXEC-UNISSUED-001",
        worker_id=default_context.identity.worker_id,
        worker_epoch=default_context.identity.worker_epoch,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
        analyst_type=default_context.analyst_type,
        auth_tag="f" * 64,  # Arbitrary unissued HMAC auth tag
    )

    res = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=default_context,
        execution=unissued_handle,
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=default_context.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: default_context.planner_state_digest,
        claims={},
        evidence={},
    )
    assert res.termination_reason == WorkerTerminationReason.UNAUTHORIZED_EXECUTION_HANDLE


def test_c83_public_api_cannot_construct_or_expose_issued_analysis_identity():
    """C83: Public planner package API does not export IssuedAnalysisIdentity."""
    import planner
    assert not hasattr(planner, "IssuedAnalysisIdentity")
    assert "IssuedAnalysisIdentity" not in planner.__all__


def test_c84_forged_identity_object_rejected_by_artifact_emitter(runtime, default_context):
    """C84: Hand-crafted IssuedAnalysisIdentity object with forged auth_tag is rejected by ArtifactEmitter."""
    tracker = ResourceTracker(default_context.resource_budget)
    forged_identity = IssuedAnalysisIdentity(
        analysis_id="ANA-FORGED-001-REPOSITORY-001",
        execution_id="EXEC-FORGED-001",
        analyst_type=default_context.analyst_type,
        sequence=1,
        auth_tag="0" * 64,  # Forged HMAC tag
    )
    emitter = ArtifactEmitter(default_context, forged_identity, tracker, runtime=runtime)

    art = AnalysisArtifact(
        analysis_id=forged_identity.analysis_id,
        execution_id=forged_identity.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
    )
    with pytest.raises(StaleContextError, match="failed runtime HMAC provenance verification"):
        emitter.emit(art)


def test_c85_identity_from_runtime_a_cannot_be_transplanted_into_runtime_b_emitter(default_context):
    """C85: IssuedAnalysisIdentity from Runtime A is rejected when evaluated by ArtifactEmitter under Runtime B."""
    runtime_a = WorkerRuntime()
    runtime_b = WorkerRuntime()

    handle_a = runtime_a.issue_execution(default_context)
    identity_a = runtime_a.issue_analysis_identity(handle_a)

    tracker = ResourceTracker(default_context.resource_budget)
    emitter_b = ArtifactEmitter(default_context, identity_a, tracker, runtime=runtime_b)

    art = AnalysisArtifact(
        analysis_id=identity_a.analysis_id,
        execution_id=identity_a.execution_id,
        analyst_type=default_context.analyst_type,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        input_state_digest=default_context.planner_state_digest,
    )
    with pytest.raises(StaleContextError, match="failed runtime HMAC provenance verification"):
        emitter_b.emit(art)


# ============================================================================
# EXTENDED OBJECT CAPABILITY & ISOLATION TESTS
# ============================================================================

def test_v01_fabric_context_lacks_private_key_access(default_context, mock_repo, default_issued_identity):
    tracker = ResourceTracker(default_context.resource_budget)
    repo_acc = ReadOnlyRepositoryAccessor(mock_repo, default_context.source_sha, default_context.capability_scope, tracker)
    event_acc = ReadOnlyEventLogAccessor(lambda: (), lambda: default_context.planner_state_digest, tracker)
    evid_acc = ReadOnlyEvidenceAccessor({}, {}, None, default_context.capability_scope, tracker)
    fabric_ctx = ReadOnlyFabricContext(
        default_context.task_id,
        default_context.repository_id,
        default_context.source_sha,
        default_context.planner_state_digest,
        default_context.analyst_type,
        default_context.worker_epoch,
        default_context.spawned_at,
        default_issued_identity,
        repo_acc,
        event_acc,
        evid_acc,
        tracker,
    )

    assert not hasattr(fabric_ctx, "private_key")
    assert not hasattr(fabric_ctx, "signing_key")
    assert not hasattr(fabric_ctx, "sign_payload")
    assert not hasattr(fabric_ctx, "authority_signer")
    assert not hasattr(fabric_ctx, "keystore")


def test_v02_fabric_context_lacks_d5_token_minting(default_context, mock_repo, default_issued_identity):
    tracker = ResourceTracker(default_context.resource_budget)
    fabric_ctx = ReadOnlyFabricContext(
        default_context.task_id,
        default_context.repository_id,
        default_context.source_sha,
        default_context.planner_state_digest,
        default_context.analyst_type,
        default_context.worker_epoch,
        default_context.spawned_at,
        default_issued_identity,
        ReadOnlyRepositoryAccessor(mock_repo, default_context.source_sha, default_context.capability_scope, tracker),
        ReadOnlyEventLogAccessor(lambda: (), lambda: default_context.planner_state_digest, tracker),
        ReadOnlyEvidenceAccessor({}, {}, None, default_context.capability_scope, tracker),
        tracker,
    )
    assert not hasattr(fabric_ctx, "mint_execution_token")
    assert not hasattr(fabric_ctx, "_mint_execution_token")
    assert not hasattr(fabric_ctx, "mint_token")


def test_v03_fabric_context_lacks_d5_admission(default_context, mock_repo, default_issued_identity):
    tracker = ResourceTracker(default_context.resource_budget)
    fabric_ctx = ReadOnlyFabricContext(
        default_context.task_id,
        default_context.repository_id,
        default_context.source_sha,
        default_context.planner_state_digest,
        default_context.analyst_type,
        default_context.worker_epoch,
        default_context.spawned_at,
        default_issued_identity,
        ReadOnlyRepositoryAccessor(mock_repo, default_context.source_sha, default_context.capability_scope, tracker),
        ReadOnlyEventLogAccessor(lambda: (), lambda: default_context.planner_state_digest, tracker),
        ReadOnlyEvidenceAccessor({}, {}, None, default_context.capability_scope, tracker),
        tracker,
    )
    assert not hasattr(fabric_ctx, "admit_execution")
    assert not hasattr(fabric_ctx, "commit_admission")
    assert not hasattr(fabric_ctx, "admission_engine")


def test_v04_fabric_context_lacks_d6_execution(default_context, mock_repo, default_issued_identity):
    tracker = ResourceTracker(default_context.resource_budget)
    fabric_ctx = ReadOnlyFabricContext(
        default_context.task_id,
        default_context.repository_id,
        default_context.source_sha,
        default_context.planner_state_digest,
        default_context.analyst_type,
        default_context.worker_epoch,
        default_context.spawned_at,
        default_issued_identity,
        ReadOnlyRepositoryAccessor(mock_repo, default_context.source_sha, default_context.capability_scope, tracker),
        ReadOnlyEventLogAccessor(lambda: (), lambda: default_context.planner_state_digest, tracker),
        ReadOnlyEvidenceAccessor({}, {}, None, default_context.capability_scope, tracker),
        tracker,
    )
    assert not hasattr(fabric_ctx, "execute")
    assert not hasattr(fabric_ctx, "execute_envelope")
    assert not hasattr(fabric_ctx, "execution_gateway")
    assert not hasattr(fabric_ctx, "sandbox_runner")


def test_v05_fabric_context_lacks_d2_nonce_reservation(default_context, mock_repo, default_issued_identity):
    tracker = ResourceTracker(default_context.resource_budget)
    fabric_ctx = ReadOnlyFabricContext(
        default_context.task_id,
        default_context.repository_id,
        default_context.source_sha,
        default_context.planner_state_digest,
        default_context.analyst_type,
        default_context.worker_epoch,
        default_context.spawned_at,
        default_issued_identity,
        ReadOnlyRepositoryAccessor(mock_repo, default_context.source_sha, default_context.capability_scope, tracker),
        ReadOnlyEventLogAccessor(lambda: (), lambda: default_context.planner_state_digest, tracker),
        ReadOnlyEvidenceAccessor({}, {}, None, default_context.capability_scope, tracker),
        tracker,
    )
    assert not hasattr(fabric_ctx, "reserve_nonce")
    assert not hasattr(fabric_ctx, "consume_nonce")
    assert not hasattr(fabric_ctx, "nonce_store")


def test_v06_fabric_context_lacks_d3_policy_mutation(default_context, mock_repo, default_issued_identity):
    tracker = ResourceTracker(default_context.resource_budget)
    fabric_ctx = ReadOnlyFabricContext(
        default_context.task_id,
        default_context.repository_id,
        default_context.source_sha,
        default_context.planner_state_digest,
        default_context.analyst_type,
        default_context.worker_epoch,
        default_context.spawned_at,
        default_issued_identity,
        ReadOnlyRepositoryAccessor(mock_repo, default_context.source_sha, default_context.capability_scope, tracker),
        ReadOnlyEventLogAccessor(lambda: (), lambda: default_context.planner_state_digest, tracker),
        ReadOnlyEvidenceAccessor({}, {}, None, default_context.capability_scope, tracker),
        tracker,
    )
    assert not hasattr(fabric_ctx, "register_policy")
    assert not hasattr(fabric_ctx, "mutate_policy")
    assert not hasattr(fabric_ctx, "override_policy")


def test_v07_fabric_context_lacks_lease_mutation(default_context, mock_repo, default_issued_identity):
    tracker = ResourceTracker(default_context.resource_budget)
    fabric_ctx = ReadOnlyFabricContext(
        default_context.task_id,
        default_context.repository_id,
        default_context.source_sha,
        default_context.planner_state_digest,
        default_context.analyst_type,
        default_context.worker_epoch,
        default_context.spawned_at,
        default_issued_identity,
        ReadOnlyRepositoryAccessor(mock_repo, default_context.source_sha, default_context.capability_scope, tracker),
        ReadOnlyEventLogAccessor(lambda: (), lambda: default_context.planner_state_digest, tracker),
        ReadOnlyEvidenceAccessor({}, {}, None, default_context.capability_scope, tracker),
        tracker,
    )
    assert not hasattr(fabric_ctx, "acquire_lease")
    assert not hasattr(fabric_ctx, "renew_lease")
    assert not hasattr(fabric_ctx, "release_lease")
    assert not hasattr(fabric_ctx, "lease_manager")


def test_v09_file_pattern_scope_enforcement(mock_repo):
    scope = CapabilityScope(allowed_file_patterns=("src/*.py",))
    tracker = ResourceTracker(WorkerResourceBudget())
    repo = ReadOnlyRepositoryAccessor(mock_repo, "a" * 40, scope, tracker)

    assert repo.read_file("src/core.py") is not None
    with pytest.raises(PermissionError, match="does not match permitted capability scope"):
        repo.read_file("tests/test_core.py")


def test_v10_ast_parsing_scope_permission(mock_repo):
    scope = CapabilityScope(allow_ast_parsing=False)
    tracker = ResourceTracker(WorkerResourceBudget())
    repo = ReadOnlyRepositoryAccessor(mock_repo, "a" * 40, scope, tracker)
    with pytest.raises(PermissionError, match="AST parsing is not permitted"):
        repo.parse_ast("src/core.py")


def test_v11_evidence_inspection_scope_permission():
    scope = CapabilityScope(allow_evidence_inspection=False)
    tracker = ResourceTracker(WorkerResourceBudget())
    evid = ReadOnlyEvidenceAccessor(
        claims={"CLM-1": "claim"},
        evidence={"EV-1": "evidence"},
        assessments=None,
        scope=scope,
        tracker=tracker,
    )
    with pytest.raises(PermissionError, match="Evidence inspection is not permitted"):
        evid.get_claim("CLM-1")
    with pytest.raises(PermissionError, match="Evidence inspection is not permitted"):
        evid.list_claim_ids()


def test_v12_stale_source_sha_mismatch_fails_closed(runtime, default_context, mock_repo):
    result = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=default_context,
        execution=runtime.issue_execution(default_context),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha="f" * 40,
        events_provider=lambda: (),
        state_digest_provider=lambda: default_context.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.STALE_CONTEXT
    assert result.artifact is None
    assert "Context SHA" in result.error_message


def test_v13_stale_planner_state_digest_mismatch_fails_closed(runtime, default_context, mock_repo):
    result = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=default_context,
        execution=runtime.issue_execution(default_context),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=default_context.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: "f" * 64,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.CONTEXT_MISMATCH
    assert result.artifact is None
    assert "Context state digest" in result.error_message


def test_v20_resource_budget_exhaustion_max_tool_calls(runtime, default_context, mock_repo):
    budget = WorkerResourceBudget(max_tool_calls=2)
    ctx = WorkerContext(
        identity=default_context.identity,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
        resource_budget=budget,
    )

    class GreedyAnalyst(EphemeralAnalyst):
        @property
        def analyst_type(self) -> AnalystType:
            return AnalystType.REPOSITORY

        def analyze(self, fc, em):
            fc.repository.file_exists("src/core.py")
            fc.repository.file_exists("src/core.py")
            fc.repository.file_exists("src/core.py")

    result = WorkerRunner.run_worker(
        worker=GreedyAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.BUDGET_EXHAUSTED_CALLS
    assert result.artifact is None


def test_v21_resource_budget_exhaustion_max_wall_time(runtime, default_context, mock_repo):
    budget = WorkerResourceBudget(max_wall_time_seconds=0.01)
    ctx = WorkerContext(
        identity=default_context.identity,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
        resource_budget=budget,
    )

    class SlowAnalyst(EphemeralAnalyst):
        @property
        def analyst_type(self) -> AnalystType:
            return AnalystType.REPOSITORY

        def analyze(self, fc, em):
            time.sleep(0.05)
            fc.repository.file_exists("src/core.py")

    result = WorkerRunner.run_worker(
        worker=SlowAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.TIMEOUT
    assert result.artifact is None


def test_v22_resource_budget_exhaustion_max_output_artifacts(runtime, default_context, mock_repo):
    class MultiArtifactAnalyst(EphemeralAnalyst):
        @property
        def analyst_type(self) -> AnalystType:
            return AnalystType.REPOSITORY

        def analyze(self, fc, em):
            art1 = AnalysisArtifact(
                analysis_id=fc.analysis_id,
                execution_id=fc.execution_id,
                analyst_type=fc.analyst_type,
                task_id=fc.task_id,
                repository_id=fc.repository_id,
                source_sha=fc.source_sha,
                input_state_digest=fc.planner_state_digest,
                worker_epoch=fc.worker_epoch,
                created_at=fc.spawned_at,
            )
            em.emit(art1)
            art2 = AnalysisArtifact(
                analysis_id=fc.analysis_id,
                execution_id=fc.execution_id,
                analyst_type=fc.analyst_type,
                task_id=fc.task_id,
                repository_id=fc.repository_id,
                source_sha=fc.source_sha,
                input_state_digest=fc.planner_state_digest,
                worker_epoch=fc.worker_epoch,
                created_at=fc.spawned_at,
            )
            em.emit(art2)

    result = WorkerRunner.run_worker(
        worker=MultiArtifactAnalyst(),
        context=default_context,
        execution=runtime.issue_execution(default_context),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=default_context.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: default_context.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.BUDGET_EXHAUSTED_ARTIFACTS


def test_v24_resource_budget_exhaustion_max_model_tokens(runtime, default_context, mock_repo):
    budget = WorkerResourceBudget(max_model_tokens=500)
    ctx = WorkerContext(
        identity=default_context.identity,
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
        resource_budget=budget,
    )

    class TokenHeavyAnalyst(EphemeralAnalyst):
        @property
        def analyst_type(self) -> AnalystType:
            return AnalystType.REPOSITORY

        def analyze(self, fc, em):
            fc.tracker.reserve_tokens(1000)

    result = WorkerRunner.run_worker(
        worker=TokenHeavyAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.BUDGET_EXHAUSTED_TOKENS


def test_v26_worker_registry_registration_and_types():
    reg = WorkerRegistry()
    types = reg.list_analyst_types()
    assert len(types) == 6
    assert AnalystType.REPOSITORY in types
    assert AnalystType.EVIDENCE in types
    assert AnalystType.ARCHITECTURE in types
    assert AnalystType.DEPENDENCY in types
    assert AnalystType.RISK_REGRESSION in types
    assert AnalystType.PLAN_CRITIC in types


def test_v27_repository_analyst_execution(runtime, default_context, mock_repo):
    result = WorkerRunner.run_worker(
        worker=RepositoryAnalyst(),
        context=default_context,
        execution=runtime.issue_execution(default_context),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=default_context.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: default_context.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.COMPLETED
    assert result.artifact is not None
    assert result.artifact.analyst_type == AnalystType.REPOSITORY
    assert len(result.artifact.observations) > 0


def test_v28_evidence_analyst_execution(runtime, default_context, mock_repo):
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.EVIDENCE),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    claims = {"CLM-001": type("Claim", (), {"status": "UNSUPPORTED"})()}
    evidence = {"EV-001": type("Evidence", (), {})()}

    result = WorkerRunner.run_worker(
        worker=EvidenceAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims=claims,
        evidence=evidence,
    )
    assert result.termination_reason == WorkerTerminationReason.COMPLETED
    assert result.artifact is not None
    assert result.artifact.analyst_type == AnalystType.EVIDENCE
    assert len(result.artifact.uncertainties) == 1
    assert "CLM-001" in result.artifact.referenced_claim_ids


def test_v29_architecture_analyst_execution(runtime, default_context, mock_repo):
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.ARCHITECTURE),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    result = WorkerRunner.run_worker(
        worker=ArchitectureAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.COMPLETED
    assert result.artifact is not None
    assert result.artifact.analyst_type == AnalystType.ARCHITECTURE
    assert any("CoreEngine" in o.description for o in result.artifact.observations)
    assert len(result.artifact.inferences) == 1


def test_v30_dependency_analyst_execution(runtime, default_context, mock_repo):
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.DEPENDENCY),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    result = WorkerRunner.run_worker(
        worker=DependencyAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.COMPLETED
    assert result.artifact is not None
    assert result.artifact.analyst_type == AnalystType.DEPENDENCY


def test_v31_risk_regression_analyst_execution(runtime, default_context, mock_repo):
    ctx = WorkerContext(
        identity=runtime.issue_identity(AnalystType.RISK_REGRESSION),
        task_id=default_context.task_id,
        repository_id=default_context.repository_id,
        source_sha=default_context.source_sha,
        planner_state_digest=default_context.planner_state_digest,
    )
    result = WorkerRunner.run_worker(
        worker=RiskRegressionAnalyst(),
        context=ctx,
        execution=runtime.issue_execution(ctx),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=ctx.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: ctx.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.COMPLETED
    assert result.artifact is not None
    assert result.artifact.analyst_type == AnalystType.RISK_REGRESSION
    assert len(result.artifact.implications) == 1


# ============================================================================
# EXTENDED VALIDATION & BOUNDS TESTS
# ============================================================================

def test_v35_worker_identity_validation_bounds():
    with pytest.raises(ValueError, match="Invalid worker_id format"):
        WorkerIdentity(worker_id="BAD_ID", analyst_type=AnalystType.REPOSITORY)
    with pytest.raises(TypeError, match="analyst_type must be an AnalystType enum member"):
        WorkerIdentity(worker_id="WKR-1", analyst_type="NOT_AN_ENUM")  # type: ignore
    with pytest.raises(ValueError, match="worker_epoch must be >= 1"):
        WorkerIdentity(worker_id="WKR-1", analyst_type=AnalystType.REPOSITORY, worker_epoch=0)


def test_v36_capability_scope_validation_bounds():
    with pytest.raises(ValueError, match="max_search_depth must be >= 1"):
        CapabilityScope(max_search_depth=0)
    scope = CapabilityScope(allowed_file_patterns=["*.py"])
    assert isinstance(scope.allowed_file_patterns, tuple)


def test_v37_resource_budget_validation_bounds():
    with pytest.raises(ValueError, match="max_tool_calls must be >= 1"):
        WorkerResourceBudget(max_tool_calls=0)
    with pytest.raises(ValueError, match="max_wall_time_seconds must be > 0"):
        WorkerResourceBudget(max_wall_time_seconds=0)
    with pytest.raises(ValueError, match="max_output_bytes must be >= 100"):
        WorkerResourceBudget(max_output_bytes=50)
    with pytest.raises(ValueError, match="max_output_artifacts must be >= 1"):
        WorkerResourceBudget(max_output_artifacts=0)
    with pytest.raises(ValueError, match="max_model_tokens must be >= 100"):
        WorkerResourceBudget(max_model_tokens=50)


def test_v38_candidate_plan_view_validation_bounds():
    with pytest.raises(ValueError, match="plan_id must be non-empty"):
        CandidatePlanView(plan_id="", source_sha="0"*40, planner_state_digest="0"*64)
    with pytest.raises(ValueError, match="Invalid source_sha hex format"):
        CandidatePlanView(plan_id="P1", source_sha="invalid", planner_state_digest="0"*64)
    with pytest.raises(ValueError, match="Invalid planner_state_digest hex format"):
        CandidatePlanView(plan_id="P1", source_sha="0"*40, planner_state_digest="invalid")


def test_v39_worker_execution_handle_validation_bounds():
    with pytest.raises(ValueError, match="Invalid execution_id format"):
        WorkerExecutionHandle(
            execution_id="BAD_EXEC",
            worker_id="WKR-1",
            worker_epoch=1,
            task_id="T",
            repository_id="R",
            source_sha="0"*40,
            planner_state_digest="0"*64,
            analyst_type=AnalystType.REPOSITORY,
            auth_tag="0"*64,
        )
    with pytest.raises(ValueError, match="Invalid worker_id format"):
        WorkerExecutionHandle(
            execution_id="EXEC-1",
            worker_id="BAD_WORKER",
            worker_epoch=1,
            task_id="T",
            repository_id="R",
            source_sha="0"*40,
            planner_state_digest="0"*64,
            analyst_type=AnalystType.REPOSITORY,
            auth_tag="0"*64,
        )


def test_v40_worker_context_validation_bounds(default_identity):
    with pytest.raises(ValueError, match="task_id and repository_id must be non-empty"):
        WorkerContext(identity=default_identity, task_id="", repository_id="R", source_sha="0"*40, planner_state_digest="0"*64)
    with pytest.raises(ValueError, match="task_id and repository_id must be non-empty"):
        WorkerContext(identity=default_identity, task_id="T", repository_id="", source_sha="0"*40, planner_state_digest="0"*64)
    with pytest.raises(ValueError, match="Invalid source_sha hex format"):
        WorkerContext(identity=default_identity, task_id="T", repository_id="R", source_sha="not-hex", planner_state_digest="0"*64)
    with pytest.raises(ValueError, match="Invalid planner_state_digest hex format"):
        WorkerContext(identity=default_identity, task_id="T", repository_id="R", source_sha="0"*40, planner_state_digest="not-hex")
    with pytest.raises(TypeError, match="identity must be a WorkerIdentity instance"):
        WorkerContext(identity="NOT_AN_IDENTITY", task_id="T", repository_id="R", source_sha="0"*40, planner_state_digest="0"*64)  # type: ignore
    with pytest.raises(TypeError, match="capability_scope must be a CapabilityScope instance"):
        WorkerContext(identity=default_identity, task_id="T", repository_id="R", source_sha="0"*40, planner_state_digest="0"*64, capability_scope="BAD")  # type: ignore
    with pytest.raises(TypeError, match="resource_budget must be a WorkerResourceBudget instance"):
        WorkerContext(identity=default_identity, task_id="T", repository_id="R", source_sha="0"*40, planner_state_digest="0"*64, resource_budget="BAD")  # type: ignore


def test_v41_resource_tracker_and_accessors_edge_cases(mock_repo):
    tracker = ResourceTracker(WorkerResourceBudget())
    with pytest.raises(ValueError, match="Token count must be non-negative"):
        tracker.reserve_tokens(-10)
    with pytest.raises(ValueError, match="byte_count and artifact_count must be non-negative"):
        tracker.reserve_output(-10, 1)

    repo_acc = ReadOnlyRepositoryAccessor(mock_repo, "0"*40, CapabilityScope(), tracker)
    with pytest.raises(FileNotFoundError, match="File not found"):
        repo_acc.read_file("nonexistent.txt")

    event_acc = ReadOnlyEventLogAccessor(
        events_provider=lambda: (type("Evt", (), {"sequence_number": 1})(), type("Evt", (), {"sequence_number": 5})()),
        state_digest_provider=lambda: "0"*64,
        tracker=tracker,
    )
    evts = event_acc.get_events(after_sequence=2)
    assert len(evts) == 1

    evid_acc = ReadOnlyEvidenceAccessor(
        claims={},
        evidence={},
        assessments={"REC-1": "assessment"},
        scope=CapabilityScope(),
        tracker=tracker,
    )
    assert evid_acc.get_assessment("REC-1") == "assessment"
    assert evid_acc.list_evidence_ids() == ()


def test_v42_worker_registry_and_emitter_edge_cases(runtime, default_context, default_issued_identity, mock_repo):
    reg = WorkerRegistry()
    with pytest.raises(TypeError, match="analyst must inherit from EphemeralAnalyst"):
        reg.register_analyst("NOT_AN_ANALYST")  # type: ignore

    tracker = ResourceTracker(default_context.resource_budget)
    emitter = ArtifactEmitter(default_context, default_issued_identity, tracker, runtime=runtime)
    with pytest.raises(TypeError, match="Emitted output must be an instance of AnalysisArtifact"):
        emitter.emit("NOT_AN_ARTIFACT")  # type: ignore

    # Context binding mismatch tests in emitter
    with pytest.raises(StaleContextError, match="Artifact task_id"):
        emitter.emit(AnalysisArtifact(
            analysis_id=default_issued_identity.analysis_id,
            execution_id=default_issued_identity.execution_id,
            analyst_type=default_context.analyst_type,
            task_id="WRONG-TASK",
            repository_id=default_context.repository_id,
            source_sha=default_context.source_sha,
            input_state_digest=default_context.planner_state_digest,
        ))

    with pytest.raises(StaleContextError, match="Artifact repository_id"):
        emitter.emit(AnalysisArtifact(
            analysis_id=default_issued_identity.analysis_id,
            execution_id=default_issued_identity.execution_id,
            analyst_type=default_context.analyst_type,
            task_id=default_context.task_id,
            repository_id="WRONG-REPO",
            source_sha=default_context.source_sha,
            input_state_digest=default_context.planner_state_digest,
        ))

    with pytest.raises(StaleContextError, match="Artifact source_sha"):
        emitter.emit(AnalysisArtifact(
            analysis_id=default_issued_identity.analysis_id,
            execution_id=default_issued_identity.execution_id,
            analyst_type=default_context.analyst_type,
            task_id=default_context.task_id,
            repository_id=default_context.repository_id,
            source_sha="0"*40,
            input_state_digest=default_context.planner_state_digest,
        ))

    with pytest.raises(StaleContextError, match="Artifact input_state_digest"):
        emitter.emit(AnalysisArtifact(
            analysis_id=default_issued_identity.analysis_id,
            execution_id=default_issued_identity.execution_id,
            analyst_type=default_context.analyst_type,
            task_id=default_context.task_id,
            repository_id=default_context.repository_id,
            source_sha=default_context.source_sha,
            input_state_digest="0"*64,
        ))

    class SilentAnalyst(EphemeralAnalyst):
        @property
        def analyst_type(self) -> AnalystType:
            return AnalystType.REPOSITORY

        def analyze(self, fc, em):
            pass

    result = WorkerRunner.run_worker(
        worker=SilentAnalyst(),
        context=default_context,
        execution=runtime.issue_execution(default_context),
        runtime=runtime,
        repo_root=mock_repo,
        active_repo_sha=default_context.source_sha,
        events_provider=lambda: (),
        state_digest_provider=lambda: default_context.planner_state_digest,
        claims={},
        evidence={},
    )
    assert result.termination_reason == WorkerTerminationReason.ERROR
    assert "Worker terminated without emitting" in result.error_message
