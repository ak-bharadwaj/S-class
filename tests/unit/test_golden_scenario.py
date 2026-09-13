"""
S-Class Golden End-to-End Test (Section 38).
Implements the exact end-to-end verification scenario without mocks or special-case logic:
1. Agent attempts action -> S-Class policy authorizes
2. Agent executes test suite under independent observation -> 48 pass, 2 fail
3. Agent asserts claim "All authentication tests pass"
4. S-Class verification engine evaluates claim vs observed receipt -> CLAIM REJECTED
5. Project state transitions task to REJECTED
6. HandoffAssembler generates verified handoff context recording failure & next action
7. Next agent inherits exact verified project state without transcript bloat.
"""

import os
import sys
import json
import pytest

from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.action import ActionRequest
from sclass.domain.claim import Claim
from sclass.control.authorization import authorize
from sclass.trust.ledger import LocalLedger
from sclass.observation.observer import observe_command
from sclass.verification.engine import verify_claim
from sclass.state.tasks import StateRepository
from sclass.context.handoff import HandoffAssembler


def test_golden_end_to_end_scenario(tmp_path):
    ws = tmp_path / "golden_auth_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    workspace = str(ws)

    # 1. Initialize Authoritative Workspace State
    repo = StateRepository(workspace)
    ledger = LocalLedger(workspace)
    proj_id = "golden_auth_proj"
    proj = Project(
        project_id=proj_id,
        name="Authentication Service",
        boundary=ProjectBoundary(workspace),
    )
    repo.save_project(proj)

    task = Task.create(title="Implement Authentication", project_id=proj_id, priority=TaskPriority.HIGH)
    task.transition_to(TaskState.READY)
    task.transition_to(TaskState.IN_PROGRESS)
    repo.save_task(task)

    # 2. Agent requests file edit: policy permits operation
    edit_req = ActionRequest(
        agent="claude",
        platform="claude_code",
        action="file_edit",
        tool="Edit",
        target="src/auth.py",
        parameters={"content": "def authenticate(): return False"},
        workspace=workspace,
        task_id=task.task_id,
    )
    auth_decision = authorize(edit_req, mode="enforce", workspace_dir=workspace)
    assert auth_decision.is_allowed is True

    # 3. Create real test file with 48 passing tests and 2 failing tests
    test_dir = ws / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_auth.py"
    test_code = (
        "import pytest\n\n"
        "@pytest.mark.parametrize('i', range(48))\n"
        "def test_pass(i):\n"
        "    assert True\n\n"
        "def test_auth_token_expiration():\n"
        "    assert False, 'Token expired unexpectedly'\n\n"
        "def test_auth_signature_verification():\n"
        "    assert False, 'Signature mismatch'\n"
    )
    test_file.write_text(test_code, encoding="utf-8")

    # 4. S-Class independently observes test execution
    cmd = f'"{sys.executable}" -m pytest "{str(test_file)}" -q'
    receipt = observe_command(cmd, workspace_dir=workspace, ledger=ledger, task_id=task.task_id)

    assert receipt.exit_code == 1
    assert receipt.execution_kind == "test_runner"
    assert receipt.verifier == "pytest"
    assert receipt.is_observed is True

    # 5. Agent untruthfully claims: "All authentication tests pass"
    claim = Claim(
        claim_id=f"claim_{task.task_id}",
        task_id=task.task_id,
        statement="All authentication tests pass",
        claim_type="test_pass",
    )
    task.transition_to(TaskState.CLAIMED)
    task.transition_to(TaskState.VERIFYING)
    repo.save_task(task)

    # 6. S-Class verification engine evaluates claim against observed evidence
    verdict = verify_claim(claim, receipt, workspace_dir=workspace, ledger=ledger)
    assert verdict.is_accepted is False
    assert verdict.status == "REJECT"
    assert "exit code 1" in verdict.reason

    # 7. Project state deterministically transitions to REJECTED
    task.transition_to(TaskState.REJECTED)
    repo.save_task(task)
    loaded_task = repo.get_task(task.task_id)
    assert loaded_task is not None
    assert loaded_task.state == TaskState.REJECTED

    # 8. Handoff context captures exact failure & next action for next agent
    assembler = HandoffAssembler(workspace)
    handoff = assembler.assemble(
        project_id=proj_id,
        next_action="Resolve token expiration and signature mismatch failures in test_auth.py",
    )
    md = handoff.to_markdown()

    assert "S-Class Project Handoff" in md
    assert "Resolve token expiration and signature mismatch" in md
    assert handoff.next_action is not None
