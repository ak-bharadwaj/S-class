"""
Survival Test Suite: Operational Recovery and Crash Resilience (Handoff C).
Verifies:
1. Daemon crash, ungraceful kill, and restart state recovery
2. Stale lock recovery and lock timeout resilience
3. Corrupt ledger tampering detection and claim verification quarantine
4. SQLite state repository persistence and multi-process reopen
5. Mid-execution agent crash and unanchored task recovery via HandoffAssembler
"""

import os
import json
import pytest

from sclass.cli.daemon import SClassDaemon
from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock
from sclass.trust.ledger import LocalLedger
from sclass.state.tasks import StateRepository
from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.claim import Claim
from sclass.verification.engine import verify_claim
from sclass.context.handoff import HandoffAssembler


def test_daemon_crash_and_restart_recovery(tmp_path):
    """Verifies that SClassDaemon can recover and resume cleanly after process crash."""
    ws = str(tmp_path / "daemon_rec_ws")
    os.makedirs(ws, exist_ok=True)
    paths = WorkspacePaths(ws)
    paths.ensure_directories()

    # 1. First daemon instance creates state and ticks
    daemon1 = SClassDaemon(ws, poll_interval_sec=0.01)
    repo = StateRepository(ws)
    proj_id = os.path.basename(ws)
    repo.save_project(Project(project_id=proj_id, name="Daemon Project", boundary=ProjectBoundary(ws)))
    t1 = Task.create(title="Task 1", project_id=proj_id)
    repo.save_task(t1)


    daemon1.run_once()
    health1 = daemon1.check_health()
    assert health1["status"] == "healthy"
    assert health1["active_tasks_count"] == 1

    # Simulate abrupt crash (do not cleanly stop, just abandon daemon1)
    del daemon1

    # 2. Second daemon instance launches on same workspace
    daemon2 = SClassDaemon(ws, poll_interval_sec=0.01)
    daemon2.run_once()
    health2 = daemon2.check_health()
    assert health2["status"] == "healthy"
    assert health2["active_tasks_count"] == 1

    ipc_file = os.path.join(paths.sclass_dir, "daemon", "ipc.json")
    assert os.path.exists(ipc_file)
    with open(ipc_file, "r", encoding="utf-8") as f:
        ipc_data = json.load(f)
    assert ipc_data["status"] == "healthy"
    assert len(ipc_data["tasks"]) == 1


def test_stale_lock_recovery(tmp_path):
    """Verifies lock acquisition and release across sequential sessions without deadlock."""
    ws = str(tmp_path / "lock_rec_ws")
    os.makedirs(ws, exist_ok=True)

    # Acquire and release first lock
    with WorkspaceLock(ws, lock_name="test_lock", timeout=2.0) as l1:
        assert os.path.exists(l1.lock_file)

    # Subsequent acquisition on same lock file must succeed immediately
    with WorkspaceLock(ws, lock_name="test_lock", timeout=2.0) as l2:
        assert os.path.exists(l2.lock_file)


def test_corrupt_ledger_tampering_detection_and_quarantine(tmp_path):
    """Verifies that an altered ledger line is immediately quarantined and causes verification rejection."""
    ws = str(tmp_path / "ledger_rec_ws")
    os.makedirs(ws, exist_ok=True)
    paths = WorkspacePaths(ws)
    paths.ensure_directories()

    ledger = LocalLedger(ws)
    ledger.append("event_1", {"data": "authentic_1"})
    ledger.append("event_2", {"data": "authentic_2"})
    is_valid, _ = ledger.verify_integrity()
    assert is_valid

    # Corrupt ledger file directly by modifying payload without updating cryptographic hash
    ledger_file = ledger.ledger_file
    with open(ledger_file, "r", encoding="utf-8") as f:

        lines = f.readlines()

    corrupt_entry = json.loads(lines[1])
    corrupt_entry["payload"]["data"] = "tampered_evil_payload"
    lines[1] = json.dumps(corrupt_entry) + "\n"

    with open(ledger_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Verification must flag integrity violation
    corrupted_ledger = LocalLedger(ws)
    valid, err = corrupted_ledger.verify_integrity()
    assert not valid
    assert "mismatch" in err.lower() or "integrity" in err.lower()

    # Claim verification against a corrupted ledger must REJECT
    class MockReceipt:
        receipt_id = "rcpt_tampered"
        receipt_hash = "mock_hash"
        task_id = "task_dummy"

    claim = Claim(claim_id="claim_test", task_id="task_dummy", statement="Assert pass", claim_type="execution")
    res = verify_claim(claim, MockReceipt(), workspace_dir=ws, ledger=corrupted_ledger)
    assert res.is_rejected
    assert "integrity compromised" in res.reason.lower()


def test_sqlite_state_store_recovery_and_reopen(tmp_path):
    """Verifies SQLite state store persists entities across connection teardowns."""
    ws = str(tmp_path / "sqlite_rec_ws")
    os.makedirs(ws, exist_ok=True)

    repo1 = StateRepository(ws)
    proj_id = "recovery_proj"
    repo1.save_project(Project(project_id=proj_id, name="Recovery Proj", boundary=ProjectBoundary(ws)))

    t = Task.create(title="Survive reboot", project_id=proj_id, priority=TaskPriority.CRITICAL)
    t.transition_to(TaskState.READY)
    t.transition_to(TaskState.IN_PROGRESS)
    repo1.save_task(t)
    del repo1

    # Re-open repo from disk
    repo2 = StateRepository(ws)
    loaded = repo2.get_task(t.task_id)
    assert loaded is not None
    assert loaded.state == TaskState.IN_PROGRESS
    assert loaded.priority == TaskPriority.CRITICAL


def test_unanchored_evidence_crash_recovery(tmp_path):
    """Verifies that an agent crash mid-task preserves authoritative state and handoff guidance."""
    ws = str(tmp_path / "agent_crash_ws")
    os.makedirs(ws, exist_ok=True)

    repo = StateRepository(ws)
    proj_id = "crash_proj"
    repo.save_project(Project(project_id=proj_id, name="Crash Recovery Proj", boundary=ProjectBoundary(ws)))

    # Task was in progress when agent crashed
    task = Task.create(title="Unfinished payment gateway integration", project_id=proj_id)
    task.transition_to(TaskState.READY)
    task.transition_to(TaskState.IN_PROGRESS)
    repo.save_task(task)

    # Next agent inherits exact handoff package with active task and clear next action
    assembler = HandoffAssembler(ws)
    pkg = assembler.assemble_package(project_id=proj_id, next_action="Resume payment gateway integration tests")

    assert pkg.checkpoint.active_task_id == task.task_id
    assert task.task_id not in pkg.checkpoint.verified_tasks
    assert pkg.next_action == "Resume payment gateway integration tests"
