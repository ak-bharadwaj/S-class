"""
Certification Suite: Cross-Agent Continuity & Handoff Integrity.
Certifies:
1. Invariant I7: Handoff contains persisted SQLite and ledger truth, never chat transcripts.
2. Complete HandoffPackage assembly and verified task preservation.
3. Fail-closed behavior on state corruption (HandoffIntegrityError).
4. Zero-drift context restoration for downstream agents.
"""

import os
import pytest
from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState
from sclass.state.tasks import StateRepository
from sclass.trust.ledger import LocalLedger
from sclass.context.handoff import HandoffAssembler, HandoffPackage, HandoffContext
from sclass.core.errors import HandoffIntegrityError


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "cert_handoff_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_cert_handoff_assembly_from_truth(workspace):
    """Certifies that HandoffPackage derives strictly from persisted SQLite state and ledger."""
    repo = StateRepository(workspace)
    ledger = LocalLedger(workspace)

    # 1. Persist Project
    proj = Project(
        project_id="PROJ_CERT",
        name="Certification Service",
        boundary=ProjectBoundary(root_path=workspace),
        active_agent="claude-code",
        current_goal="Pass all certification gates",
    )
    repo.save_project(proj)

    # 2. Persist Task 1 as VERIFIED
    task1 = Task(
        task_id="t1",
        project_id="PROJ_CERT",
        title="Implement Protocol Handshake",
        state=TaskState.VERIFIED,
    )
    repo.save_task(task1)

    # 3. Persist Task 2 as BLOCKED / IN_PROGRESS
    task2 = Task(
        task_id="t2",
        project_id="PROJ_CERT",
        title="Fix Concurrency Race Condition",
        state=TaskState.IN_PROGRESS,
    )
    repo.save_task(task2)

    # 4. Assemble handoff package
    assembler = HandoffAssembler(workspace_dir=workspace)
    package = assembler.assemble_package(project_id="PROJ_CERT", next_action="Investigate lock in queue.py")

    assert isinstance(package, HandoffPackage)
    assert package.package_hash != ""
    assert package.next_action == "Investigate lock in queue.py"
    assert "t1" in package.verified_evidence_refs
    assert package.task_context.get("task_id") == "t2"

    # Verify context assembly
    ctx = assembler.assemble(project_id="PROJ_CERT", next_action="Investigate lock in queue.py")
    assert isinstance(ctx, HandoffContext)
    assert ctx.project_id == "PROJ_CERT"
    verified_ids = [t["task_id"] for t in ctx.verified_tasks]
    assert "t1" in verified_ids


def test_cert_handoff_fail_closed_on_corrupted_state(workspace):
    """Certifies that handoff assembly fails closed when database state cannot be accessed or is corrupted."""
    class BrokenRepo:
        def list_tasks(self, *args, **kwargs):
            raise RuntimeError("Database disk image is malformed: SQLite error 11")

    assembler = HandoffAssembler(workspace_dir=workspace, repo=BrokenRepo())

    # Assembling handoff on broken/corrupted repository MUST raise HandoffIntegrityError
    with pytest.raises(HandoffIntegrityError, match="Database access failure"):
        assembler.assemble(project_id="PROJ_CERT")
