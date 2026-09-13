"""
Unit Tests for S-Class Open-Source-First Core Architecture.
Covers Batches A, B, C, D:
- Domain Models & ProjectBoundary
- Deterministic Task State Machine
- SQLite StateStore & StateRepository
- CloudEvents EventJournal
- ExecutionIdentity & SecretScanner
- PathAuthority Protection Boundaries
- Pluggable Verifiers & Verification Engine
- Cross-Agent Handoff Context
"""

import os
import sys
import pytest
from datetime import datetime, timezone

from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.execution import ExecutionIdentity
from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt, ObservedReceipt, _OBSERVATION_TOKEN
from sclass.core.errors import StateTransitionError, SecurityViolationError
from sclass.state.tasks import StateRepository
from sclass.state.events import EventJournal, CloudEvent
from sclass.storage.paths import WorkspacePaths
from sclass.control.authority import get_path_authority, PathAuthorityLevel, PathAuthority
from sclass.control.secret_scanner import SecretScanner
from sclass.control.authorization import authorize
from sclass.verification.engine import verify_claim
from sclass.verification.registry import get_verifier_registry
from sclass.trust.ledger import LocalLedger
from sclass.observation.observer import observe_command
from sclass.context.handoff import HandoffAssembler


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "test_oss_workspace"
    ws.mkdir()
    return str(ws)


def test_project_boundary_containment(workspace):
    boundary = ProjectBoundary(workspace)
    assert boundary.contains(os.path.join(workspace, "src", "main.py")) is True
    assert boundary.contains(os.path.join(workspace, ".sclass", "state")) is True
    # Path traversal outside boundary must return False
    assert boundary.contains(os.path.join(workspace, "..", "external.py")) is False
    assert boundary.contains("C:\\Windows\\System32\\cmd.exe") is False


def test_task_lifecycle_fsm():
    task = Task.create(title="Implement Auth", project_id="proj_01")
    assert task.state == TaskState.PLANNED

    # Legal transitions: PLANNED -> READY -> IN_PROGRESS -> CLAIMED -> VERIFYING -> VERIFIED
    task.transition_to(TaskState.READY)
    assert task.state == TaskState.READY

    task.transition_to(TaskState.IN_PROGRESS)
    assert task.state == TaskState.IN_PROGRESS

    task.transition_to(TaskState.CLAIMED)
    assert task.state == TaskState.CLAIMED

    task.transition_to(TaskState.VERIFYING)
    assert task.state == TaskState.VERIFYING

    task.transition_to(TaskState.VERIFIED)
    assert task.state == TaskState.VERIFIED
    assert task.completed_at is not None

    # Illegal transition from terminal state VERIFIED
    with pytest.raises(StateTransitionError):
        task.transition_to(TaskState.IN_PROGRESS)


def test_sqlite_state_store_and_repository(workspace):
    repo = StateRepository(workspace)

    proj = Project(
        project_id="proj_alpha",
        name="Alpha",
        boundary=ProjectBoundary(workspace),
    )
    repo.save_project(proj)
    loaded_proj = repo.get_project("proj_alpha")
    assert loaded_proj is not None
    assert loaded_proj.name == "Alpha"

    task = Task.create(title="Create DB Schema", project_id="proj_alpha", priority=TaskPriority.HIGH)
    repo.save_task(task)

    loaded_task = repo.get_task(task.task_id)
    assert loaded_task is not None
    assert loaded_task.title == "Create DB Schema"
    assert loaded_task.priority == TaskPriority.HIGH

    # Update state and verify persistence
    loaded_task.transition_to(TaskState.READY)
    repo.save_task(loaded_task)

    tasks_list = repo.list_tasks(project_id="proj_alpha", state=TaskState.READY)
    assert len(tasks_list) == 1
    assert tasks_list[0].task_id == task.task_id


def test_cloudevents_event_journal(workspace):
    journal = EventJournal(workspace)
    event = journal.append(
        event_type="sclass.task.created",
        subject="task:task_001",
        data={"title": "Test Task", "priority": "high"},
    )
    assert isinstance(event, CloudEvent)
    assert event.specversion == "1.0.2"
    assert event.type == "sclass.task.created"

    all_events = journal.read_all()
    assert len(all_events) == 1
    assert all_events[0].id == event.id
    assert all_events[0].subject == "task:task_001"


def test_path_authority_and_sclass_protection(workspace):
    paths = WorkspacePaths(workspace)
    paths.ensure_directories()

    # .sclass/trust/ is SCLASS_ONLY
    trust_file = os.path.join(paths.trust_dir, "ledger", "audit_ledger.jsonl")
    assert get_path_authority(trust_file, workspace) == PathAuthorityLevel.SCLASS_ONLY

    # .sclass/agent/ is AGENT_WRITABLE
    agent_scratch = os.path.join(paths.agent_dir, "scratch.txt")
    assert get_path_authority(agent_scratch, workspace) == PathAuthorityLevel.AGENT_WRITABLE

    # Workspace user source file is AGENT_WRITABLE
    src_file = os.path.join(workspace, "src", "app.py")
    assert get_path_authority(src_file, workspace) == PathAuthorityLevel.AGENT_WRITABLE

    # PathAuthority check_write_access raises on SCLASS_ONLY
    auth = PathAuthority(workspace)
    with pytest.raises(SecurityViolationError):
        auth.check_write_access(trust_file, agent="claude")


def test_secret_scanner_redaction():
    clean_text = "def connect(): return True"
    has_sec, red, findings = SecretScanner.scan(clean_text)
    assert has_sec is False
    assert len(findings) == 0

    secret_text = "export GITHUB_TOKEN='ghp_123456789012345678901234567890123456'"
    has_sec2, red2, findings2 = SecretScanner.scan(secret_text)
    assert has_sec2 is True
    assert any(f["confidence"] == "HIGH_CONFIDENCE" for f in findings2)
    assert any(f["type"] == "api_token" for f in findings2)
    assert "ghp_123456789012345678901234567890123456" not in red2
    assert "[REDACTED:api_token:" in red2


def test_authorization_enforcement(workspace):
    req_deny = ActionRequest(
        agent="claude",
        platform="claude_code",
        action="file_edit",
        tool="Edit",
        target=".sclass/trust/ledger/audit_ledger.jsonl",
        parameters={"content": "tamper"},
        workspace=workspace,
    )
    decision = authorize(req_deny, mode="enforce", workspace_dir=workspace)
    assert decision.is_denied is True
    assert decision.policy_id == "SCLASS-EVID-001"

    req_allow = ActionRequest(
        agent="claude",
        platform="claude_code",
        action="file_edit",
        tool="Edit",
        target="src/feature.py",
        parameters={"content": "def run(): pass"},
        workspace=workspace,
    )
    decision2 = authorize(req_allow, mode="enforce", workspace_dir=workspace)
    assert decision2.is_allowed is True


def test_pluggable_verifier_and_observation(workspace):
    ledger = LocalLedger(workspace)
    cmd = f'"{sys.executable}" -m pytest --version'
    receipt = observe_command(cmd, workspace_dir=workspace, ledger=ledger)
    assert receipt.exit_code == 0
    assert receipt.execution_kind == "test_runner"

    claim = Claim(
        claim_id="claim_verif_01",
        task_id=receipt.task_id,
        statement="All tests pass",
        claim_type="test_pass",
    )

    verdict = verify_claim(claim, receipt, workspace_dir=workspace, ledger=ledger)
    assert verdict.is_accepted is True
    assert verdict.verification_event is not None
    assert verdict.verification_event.result == "CLAIM_VERIFIED"


def test_cross_agent_handoff(workspace):
    repo = StateRepository(workspace)
    proj_id = "test_proj"
    proj = Project(
        project_id=proj_id,
        name="Test Handoff Project",
        boundary=ProjectBoundary(str(workspace)),
    )
    repo.save_project(proj)

    t1 = Task.create(title="Build API", project_id=proj_id)
    t1.transition_to(TaskState.READY)
    t1.transition_to(TaskState.IN_PROGRESS)
    t1.transition_to(TaskState.CLAIMED)
    t1.transition_to(TaskState.VERIFYING)
    t1.verified_receipt_id = "rcpt_verified_123"
    t1.transition_to(TaskState.VERIFIED)
    repo.save_task(t1)

    t2 = Task.create(title="Add Rate Limiting", project_id=proj_id)
    t2.transition_to(TaskState.READY)
    t2.transition_to(TaskState.IN_PROGRESS)
    repo.save_task(t2)

    assembler = HandoffAssembler(workspace)
    handoff = assembler.assemble(project_id=proj_id, next_action="Complete token bucket algorithm")

    assert handoff.project_id == proj_id
    assert len(handoff.verified_tasks) == 1
    assert handoff.active_task is not None
    assert handoff.active_task["title"] == "Add Rate Limiting"
    assert handoff.next_action == "Complete token bucket algorithm"

    md = handoff.to_markdown()
    assert "Verified Prior Work" in md
    assert "Add Rate Limiting" in md
    assert "Complete token bucket algorithm" in md
