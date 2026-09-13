"""
S-Class Demo 5: Cross-Agent Continuity (Claude -> Codex)
Flow:
1. Claude works on task, partially completes, records blockers and verified subtasks.
2. Credits/session ends.
3. S-Class assembles authoritative HandoffPackage.
4. Codex loads exact verified state and resumes directly from blockers.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState
from sclass.state.tasks import StateRepository
from sclass.trust.ledger import LocalLedger
from sclass.context.handoff import HandoffAssembler
from sclass.integrations.codex.adapter import CodexAdapter


def run():
    print("=" * 70)
    print("DEMO 5: CROSS-AGENT CONTINUITY (CLAUDE -> CODEX)")
    print("=" * 70)
    print("Scenario: Seamless handoff of verified state from Claude to Codex.")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        repo = StateRepository(tmp_dir)
        ledger = LocalLedger(tmp_dir)
        proj_name = "auth-service"
        proj = Project(project_id=proj_name, name="Auth Service", boundary=ProjectBoundary(tmp_dir))
        repo.save_project(proj)

        # 1. Claude verifies subtask 1
        t1 = Task.create(title="Create OAuth2 Token Endpoint", project_id=proj_name)
        t1.state = TaskState.VERIFIED
        t1.verified_receipt_id = "rcpt_claude_verified_01"
        repo.save_task(t1)

        # 2. Claude works on subtask 2, encounters blocker, session ends
        t2 = Task.create(title="Implement JWT Refresh Flow", project_id=proj_name)
        t2.state = TaskState.IN_PROGRESS
        repo.save_task(t2)

        print("[1] Session 1 (Claude Code):")
        print(f"    Verified: `{t1.task_id}` ({t1.title})")
        print(f"    Blocked:  `{t2.task_id}` ({t2.title})")
        print("    --> Claude session ends (rate limit / credit expiry).")

        # 3. Assemble Handoff Package
        print("\n[2] S-Class Assembles Cryptographic Handoff Package:")
        assembler = HandoffAssembler(tmp_dir)
        package = assembler.assemble_package(
            project_id=proj_name,
            next_action="Fix tests/auth/test_refresh.py line 42: token refresh replay attack",
            blockers=["Replay attack vulnerable in refresh token rotation"],
        )
        print(f"    Package ID:            {package.package_id[:16]}...")
        print(f"    Working Tree Hash:     {package.checkpoint.working_tree_fingerprint[:16]}...")
        print(f"    Verified Tasks Count:  {len(package.checkpoint.verified_tasks)}")
        print(f"    Next Preserved Action: {package.checkpoint.next_action}")

        # 4. Codex loads handoff package
        print("\n[3] Session 2 (OpenAI Codex):")
        codex_adapter = CodexAdapter(tmp_dir)
        print("    Codex connects to S-Class control plane.")
        resumed_context = assembler.assemble(proj_name, next_action=package.checkpoint.next_action)
        print("    Codex received verified facts without prompt drift:")
        print(f"    - Active Focus:  {resumed_context.active_task.get('title')}")
        print(f"    - Verified Work: {len(resumed_context.verified_tasks)} task(s)")
        print(f"    - Resumed From:  {resumed_context.next_action}")

        assert len(resumed_context.verified_tasks) == 1
        assert "test_refresh.py" in resumed_context.next_action
        print("\n[SUCCESS] Zero-drift continuity across disparate agents demonstrated!")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    run()
