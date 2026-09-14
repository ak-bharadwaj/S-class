"""
Certification Suite: RC.8 Handoff/Continuity Engine & Durable Cross-Agent State.
Certifies:
1. Checkpoint creation and cryptographic hash integrity binding.
2. Durable SQLite checkpoint persistence, listing, and direct retrieval.
3. Incremental checkpointing with delta computation and recursive state reconstruction.
4. RecoveryEngine: resume from verified checkpoint, reconciling abandoned tasks and restoring truth.
5. RecoveryEngine: crash detection for uncompleted in-flight tasks.
6. RollbackEngine: revert workspace to last known-good verified state, invalidating unverified claims.
7. Cross-agent handoff transfer under Law L9: strict exclusion of chat transcripts and conversational fluff.
8. Fail-closed rejection on corrupted checkpoint integrity or workspace divergence.
"""

import os
import json
import pytest

from sclass.domain.task import Task, TaskState
from sclass.domain.project import VerifiedProjectState, Project, ProjectBoundary
from sclass.domain.truth import ProjectTruth
from sclass.state.tasks import StateRepository
from sclass.trust.ledger import LocalLedger
from sclass.core.errors import HandoffIntegrityError
from sclass.context.checkpoint import ProjectCheckpoint, CheckpointManager, DurableCheckpointStore
from sclass.context.handoff import (
    HandoffAssembler,
    HandoffPackage,
    RecoveryEngine,
    RecoveryResult,
    RollbackEngine,
    RollbackResult,
)
from sclass.context.continuity import CrossPlatformContinuityEngine, ContinuityTransferResult
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint


@pytest.fixture
def rc8_workspace(tmp_path):
    ws = tmp_path / "cert_rc8_ws"
    ws.mkdir(parents=True, exist_ok=True)
    # Seed sample file
    (ws / "app.py").write_text("def run():\n    return 42\n", encoding="utf-8")
    
    # Save default project p1 so tasks foreign keys pass
    repo = StateRepository(str(ws))
    proj = Project(
        project_id="p1",
        name="Test Project",
        boundary=ProjectBoundary(root_path=str(ws)),
    )
    repo.save_project(proj)

    return str(ws)


def test_rc8_checkpoint_creation_and_cryptographic_integrity(rc8_workspace):
    """Certifies that ProjectCheckpoint binds all critical fields cryptographically."""
    chk = CheckpointManager.create_checkpoint(
        workspace_dir=rc8_workspace,
        checkpoint_id="chk_001",
        active_task_id="task_build",
        blockers=["blocker_dep"],
        relevant_files=["app.py"],
        next_action="Run test suite",
        persist=True,
    )

    assert isinstance(chk, ProjectCheckpoint)
    assert chk.checkpoint_id == "chk_001"
    assert chk.active_task_id == "task_build"
    assert "app.py" in chk.relevant_files
    assert chk.checkpoint_hash != ""
    assert chk.verify_integrity() is True


def test_rc8_durable_sqlite_checkpoint_persistence_and_restore(rc8_workspace):
    """Certifies durable ACID SQLite persistence and retrieval of checkpoints."""
    pt = ProjectTruth(rc8_workspace)
    pt.verify("claim_core_algo", receipt=None, files=["app.py"])

    chk = CheckpointManager.create_checkpoint(
        workspace_dir=rc8_workspace,
        checkpoint_id="chk_sqlite_001",
        active_task_id="task_sqlite",
        blockers=[],
        relevant_files=["app.py"],
        next_action="Deploy",
        project_truth=pt,
        persist=True,
    )

    # Retrieve from SQLite store
    loaded = CheckpointManager.get_checkpoint(rc8_workspace, "chk_sqlite_001")
    assert loaded is not None
    assert loaded.checkpoint_id == "chk_sqlite_001"
    assert loaded.active_task_id == "task_sqlite"
    assert loaded.project_truth is not None
    assert "claim_core_algo" in loaded.project_truth["records"]
    assert loaded.verify_integrity() is True

    # List all checkpoints
    all_chks = CheckpointManager.list_checkpoints(rc8_workspace)
    assert len(all_chks) >= 1
    assert any(c.checkpoint_id == "chk_sqlite_001" for c in all_chks)


def test_rc8_incremental_checkpoint_and_reconstruction(rc8_workspace):
    """Certifies incremental checkpointing and recursive reconstruction from delta chain."""
    # 1. Base checkpoint
    repo = StateRepository(rc8_workspace)
    t1 = Task(task_id="t1", project_id="p1", title="Task 1", state=TaskState.VERIFIED)
    repo.save_task(t1)

    base_chk = CheckpointManager.create_checkpoint(
        workspace_dir=rc8_workspace,
        checkpoint_id="chk_base",
        active_task_id=None,
        blockers=[],
        relevant_files=["app.py"],
        next_action="Start task 2",
        persist=True,
    )

    # 2. Mutate state: add new verified task and new file
    (os.path.join(rc8_workspace, "utils.py"))
    with open(os.path.join(rc8_workspace, "utils.py"), "w", encoding="utf-8") as f:
        f.write("def helper(): pass\n")

    t2 = Task(task_id="t2", project_id="p1", title="Task 2", state=TaskState.VERIFIED)
    repo.save_task(t2)

    # 3. Create incremental checkpoint
    inc_chk = CheckpointManager.create_incremental_checkpoint(
        workspace_dir=rc8_workspace,
        base_checkpoint_id="chk_base",
        checkpoint_id="chk_inc_01",
        relevant_files=["app.py", "utils.py"],
        next_action="Continue work",
    )

    assert inc_chk.is_incremental is True
    assert inc_chk.parent_checkpoint_id == "chk_base"
    assert "t2" in inc_chk.delta.get("new_verified_tasks", [])

    # 4. Resolve incremental checkpoint to full reconstruction
    assert inc_chk.verify_integrity() is True
    resolved = CheckpointManager.resolve_checkpoint(rc8_workspace, "chk_inc_01")
    assert resolved.verify_integrity() is True
    assert "t1" in resolved.verified_tasks
    assert "t2" in resolved.verified_tasks
    assert "app.py" in resolved.relevant_files
    assert "utils.py" in resolved.relevant_files

    # 5. RecoveryEngine resumes cleanly from incremental checkpoint
    rec_result = RecoveryEngine.resume_from_checkpoint(rc8_workspace, "chk_inc_01")
    assert rec_result.success is True
    assert rec_result.checkpoint_id == "chk_inc_01"


def test_rc8_incremental_checkpoint_cycle_detection(rc8_workspace):
    """Certifies that cyclic parent pointers in incremental checkpoints fail closed."""
    # Create chk_a pointing to chk_b, and chk_b pointing to chk_a
    store = DurableCheckpointStore(rc8_workspace)
    chk_a = ProjectCheckpoint(
        checkpoint_id="chk_loop_a",
        repo_head="HEAD",
        working_tree_fingerprint="fp",
        ledger_head="lh",
        active_task_id=None,
        verified_tasks=(),
        failed_claims=(),
        blockers=(),
        relevant_files=(),
        next_action=None,
        constraints=(),
        checkpoint_hash="hash_a",
        parent_checkpoint_id="chk_loop_b",
        is_incremental=True,
    )
    chk_b = ProjectCheckpoint(
        checkpoint_id="chk_loop_b",
        repo_head="HEAD",
        working_tree_fingerprint="fp",
        ledger_head="lh",
        active_task_id=None,
        verified_tasks=(),
        failed_claims=(),
        blockers=(),
        relevant_files=(),
        next_action=None,
        constraints=(),
        checkpoint_hash="hash_b",
        parent_checkpoint_id="chk_loop_a",
        is_incremental=True,
    )
    store.save(chk_a)
    store.save(chk_b)

    with pytest.raises(HandoffIntegrityError):
        CheckpointManager.resolve_checkpoint(rc8_workspace, "chk_loop_a")


def test_rc8_recovery_engine_resume_from_checkpoint(rc8_workspace):
    """Certifies that RecoveryEngine restores workspace from checkpoint after session crash."""
    repo = StateRepository(rc8_workspace)
    t_done = Task(task_id="t_done", project_id="p1", title="Finished task", state=TaskState.VERIFIED)
    repo.save_task(t_done)

    # Save checkpoint
    chk = CheckpointManager.create_checkpoint(
        workspace_dir=rc8_workspace,
        checkpoint_id="chk_recov",
        active_task_id="t_inflight",
        relevant_files=["app.py"],
        next_action="Complete inflight task",
        persist=True,
    )

    # Simulate crash: task left in IN_PROGRESS state
    t_inflight = Task(task_id="t_inflight", project_id="p1", title="Crashed task", state=TaskState.IN_PROGRESS)
    repo.save_task(t_inflight)

    # Run recovery
    result = RecoveryEngine.resume_from_checkpoint(
        workspace_dir=rc8_workspace,
        checkpoint_id="chk_recov",
        strict_fingerprint=True,
    )

    assert isinstance(result, RecoveryResult)
    assert result.success is True
    assert result.checkpoint_id == "chk_recov"
    assert result.restored_tasks_count >= 1

    # In-flight task is reset to READY so it can be cleanly resumed
    recovered_t = repo.get_task("t_inflight")
    assert recovered_t.state == TaskState.READY


def test_rc8_recovery_engine_crash_detection(rc8_workspace):
    """Certifies detection of abandoned / crashed tasks in the workspace."""
    repo = StateRepository(rc8_workspace)
    t_active = Task(task_id="t_crashed", project_id="p1", title="Unfinished job", state=TaskState.CLAIMED)
    repo.save_task(t_active)

    crash_info = RecoveryEngine.detect_crash(rc8_workspace)
    assert crash_info["crash_detected"] is True
    assert "t_crashed" in crash_info["abandoned_tasks"]


def test_rc8_rollback_engine_revert_to_known_good(rc8_workspace):
    """Certifies that RollbackEngine reverts workspace to target checkpoint and invalidates subsequent state."""
    repo = StateRepository(rc8_workspace)
    t1 = Task(task_id="t_verified", project_id="p1", title="Task 1", state=TaskState.VERIFIED)
    repo.save_task(t1)

    chk_good = CheckpointManager.create_checkpoint(
        workspace_dir=rc8_workspace,
        checkpoint_id="chk_good_001",
        active_task_id=None,
        relevant_files=["app.py"],
        next_action="Proceed",
        persist=True,
    )

    # Later unverified task was added
    t2 = Task(task_id="t_bad", project_id="p1", title="Failed Task", state=TaskState.VERIFIED)
    repo.save_task(t2)

    # Roll back to chk_good_001
    res = RollbackEngine.rollback_to_checkpoint(
        workspace_dir=rc8_workspace,
        target_checkpoint_id="chk_good_001",
    )

    assert isinstance(res, RollbackResult)
    assert res.success is True
    assert res.target_checkpoint_id == "chk_good_001"

    # t_bad should no longer be VERIFIED
    reverted_t2 = repo.get_task("t_bad")
    assert reverted_t2.state == TaskState.READY

    # Check LocalLedger event recorded
    ledger = LocalLedger(rc8_workspace)
    last_entry = ledger.get_last_entry()
    assert last_entry is not None
    assert last_entry.get("event") == "ROLLBACK"


def test_rc8_cross_agent_state_transfer_law_l9_transcript_exclusion(rc8_workspace):
    """Certifies cross-agent state transfer strictly excludes chat transcripts under Law L9."""
    snap = compute_workspace_snapshot(rc8_workspace)
    fp = compute_workspace_fingerprint(snap)

    state = VerifiedProjectState(
        workspace=rc8_workspace,
        current_revision=fp,
        active_task="task_handoff",
        next_action="Continue next step",
    )
    state.record_verified_claim(
        {"claim_id": "c_truth", "statement": "Algorithm verified with proof"},
        receipt={"receipt_id": "rcpt_proof_01", "exit_code": 0},
    )

    # Execute handoff
    transfer_res = CrossPlatformContinuityEngine.execute_agent_handoff(
        workspace_dir=rc8_workspace,
        source_agent_id="agent_alpha",
        target_agent_id="agent_beta",
        source_platform="claude_code",
        target_platform="antigravity",
        next_action="Continue next step",
        project_state=state,
    )

    assert isinstance(transfer_res, ContinuityTransferResult)
    assert transfer_res.success is True
    assert transfer_res.verified_work_count == 1

    # Law L9: Ensure no chat transcripts in handoff package
    assert CrossPlatformContinuityEngine.validate_law_l9_compliance(transfer_res.handoff_package) is True

    # Test violation of Law L9 raises error
    corrupted_pkg = HandoffPackage(
        checkpoint=transfer_res.handoff_package.checkpoint,
        task_context={"task_id": "t1", "chat_transcript": "User: do this. Agent: ok."},
        verified_evidence_refs=(),
        rejected_claims=(),
        relevant_files=(),
        next_action="next",
        package_hash="hash",
    )
    with pytest.raises(HandoffIntegrityError, match="Law L9 Violation"):
        CrossPlatformContinuityEngine.validate_law_l9_compliance(corrupted_pkg)


def test_rc8_fail_closed_on_corrupted_checkpoint(rc8_workspace):
    """Certifies fail-closed behavior when checkpoint hash or integrity is tampered with."""
    chk = CheckpointManager.create_checkpoint(
        workspace_dir=rc8_workspace,
        checkpoint_id="chk_tamper",
        active_task_id="t1",
        relevant_files=["app.py"],
        persist=False,
    )

    # Tamper with checkpoint_hash
    tampered = ProjectCheckpoint(
        checkpoint_id=chk.checkpoint_id,
        repo_head=chk.repo_head,
        working_tree_fingerprint=chk.working_tree_fingerprint,
        ledger_head=chk.ledger_head,
        active_task_id=chk.active_task_id,
        verified_tasks=chk.verified_tasks,
        failed_claims=chk.failed_claims,
        blockers=chk.blockers,
        relevant_files=chk.relevant_files,
        next_action=chk.next_action,
        constraints=chk.constraints,
        checkpoint_hash="corrupted_hash_value_12345",
    )
    assert tampered.verify_integrity() is False

    # Persist tampered checkpoint and attempt recovery
    CheckpointManager.save_checkpoint(rc8_workspace, tampered)
    with pytest.raises(HandoffIntegrityError, match="Integrity check failed"):
        RecoveryEngine.resume_from_checkpoint(rc8_workspace, "chk_tamper")
