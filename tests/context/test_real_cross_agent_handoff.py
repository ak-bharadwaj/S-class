"""
Cross-Agent Continuity & Handoff Test:
Validates real end-to-end handoff lifecycle:
Claude-style session state
        ↓
Persisted SQLite state + LocalLedger
        ↓
Cryptographic HandoffPackage & Checkpoint
        ↓
Codex-style consumer
"""

import os
import sys
import tempfile
import pytest

from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult
from sclass.state.tasks import StateRepository
from sclass.trust.ledger import LocalLedger
from sclass.context.handoff import HandoffAssembler, HandoffPackage
from sclass.integrations.claude.adapter import ClaudeAdapter
from sclass.integrations.codex.adapter import CodexAdapter


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "cross_agent_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    # Create sample project files
    src_dir = ws / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "auth.py").write_text("def generate_token(): pass\n", encoding="utf-8")
    (src_dir / "refresh.py").write_text("def refresh_token(): pass\n", encoding="utf-8")
    return str(ws)


def test_real_claude_to_codex_handoff(workspace):
    """
    Simulates real cross-agent handoff:
    1. Claude works on AUTH-PROJECT, verifies Task 1, fails Task 2.
    2. S-Class persists truth into StateRepository and LocalLedger.
    3. HandoffAssembler derives authoritative HandoffPackage.
    4. Codex consumes HandoffPackage and resumes with zero context drift.
    """
    repo = StateRepository(workspace)
    ledger = LocalLedger(workspace)

    # Setup Project
    project = Project(
        project_id="AUTH-PROJ",
        name="Authentication Service",
        boundary=ProjectBoundary(root_path=workspace),
        active_agent="claude-code",
        current_goal="Build OAuth2 tokens and refresh flow",
    )
    repo.save_project(project)

    # --------------------------------------------------------------------
    # Phase 1: Claude Session
    # --------------------------------------------------------------------
    claude_adapter = ClaudeAdapter(workspace_dir=workspace)

    # Claude completes Task 1: Verified
    task1 = Task(
        task_id="AUTH-101",
        project_id="AUTH-PROJ",
        title="Create OAuth2 Token Endpoint",
        state=TaskState.VERIFIED,
        priority=TaskPriority.CRITICAL,
        assigned_agent="claude-code",
        verified_receipt_id="rcpt_auth_101_verified",
        metadata={"target_files": ["src/auth.py"]},
    )
    repo.save_task(task1)
    ledger.append("VERIFICATION", {
        "task_id": "AUTH-101",
        "status": "ACCEPT",
        "receipt_id": "rcpt_auth_101_verified",
        "passed_tests": 12,
        "failed_tests": 0,
    })

    # Claude attempts Task 2: Fails with replay bug
    task2 = Task(
        task_id="AUTH-102",
        project_id="AUTH-PROJ",
        title="Implement JWT Refresh Flow",
        state=TaskState.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        assigned_agent="claude-code",
        metadata={"target_files": ["src/refresh.py"]},
    )
    repo.save_task(task2)

    claim2 = Claim(
        claim_id="claim_refresh_tamper",
        task_id="AUTH-102",
        statement="Token refresh prevents replay attacks",
        claim_type="test_pass",
    )
    repo.save_claim(claim2)

    # Record rejected verification result into SQLite
    verif_fail = VerificationResult(
        status="REJECT",
        claim_id="claim_refresh_tamper",
        reason="Token refresh replay attack succeeded (exit code 1)",
        observed_exit_code=1,
        passed_tests=5,
        failed_tests=1,
        receipt_id="rcpt_refresh_fail_002",
        metadata={"test_target": "tests/test_refresh.py:test_replay"},
    )
    repo.save_verification(verif_fail)
    ledger.append("VERIFICATION", {
        "claim_id": "claim_refresh_tamper",
        "status": "REJECT",
        "reason": "Token refresh replay attack succeeded (exit code 1)",
        "receipt_id": "rcpt_refresh_fail_002",
    })

    # Claude session terminates (e.g. rate limit, context exhaust)

    # --------------------------------------------------------------------
    # Phase 2: S-Class Handoff Assembly (Derivation from State)
    # --------------------------------------------------------------------
    assembler = HandoffAssembler(workspace)
    pkg = assembler.assemble_package(
        project_id="AUTH-PROJ",
        next_action="Fix tests/test_refresh.py line 42: token refresh replay attack",
    )

    # Verify that HandoffPackage authoritatively derived all historical facts
    assert pkg.task_context.get("task_id") == "AUTH-102"
    assert "rcpt_auth_101_verified" in pkg.verified_evidence_refs

    # Authoritative rejected claims derived from SQLite verifications table
    assert len(pkg.rejected_claims) >= 1
    rejected_match = next((r for r in pkg.rejected_claims if r.get("claim_id") == "claim_refresh_tamper"), None)
    assert rejected_match is not None
    assert rejected_match["status"] == "REJECT"
    assert "replay attack succeeded" in rejected_match["reason"]
    assert rejected_match["observed_exit_code"] == 1
    assert rejected_match["failed_tests"] == 1

    # Authoritative ledger head and checkpoint
    assert pkg.ledger_head
    assert pkg.checkpoint.checkpoint_hash
    assert "src/refresh.py" in pkg.relevant_files
    assert pkg.next_action == "Fix tests/test_refresh.py line 42: token refresh replay attack"

    # --------------------------------------------------------------------
    # Phase 3: Codex Session Consumption
    # --------------------------------------------------------------------
    codex_adapter = CodexAdapter(workspace_dir=workspace)

    # Codex consumes the handoff package
    handoff_dict = pkg.to_dict()
    assert handoff_dict["package_hash"] == pkg.package_hash
    assert handoff_dict["ledger_head"] == pkg.ledger_head

    # Codex extracts facts directly
    codex_active_focus = handoff_dict["task_context"]["title"]
    codex_verified_refs = handoff_dict["verified_evidence_refs"]
    codex_known_failures = handoff_dict["rejected_claims"]
    codex_next_step = handoff_dict["next_action"]

    assert codex_active_focus == "Implement JWT Refresh Flow"
    assert "rcpt_auth_101_verified" in codex_verified_refs
    assert codex_known_failures[0]["failed_tests"] == 1
    assert "replay attack" in codex_next_step
