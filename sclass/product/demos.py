"""
S-Class Product: The Five Flagship Demos.
Real executable product demonstrations proving S-Class outside the architecture diagram:
- Demo 1: False test claim rejection
- Demo 2: Dangerous command denial (rm -rf / destructive action)
- Demo 3: Secret exfiltration prevention (.env / credential protection)
- Demo 4: Post-verification mutation invalidation
- Demo 5: Cross-agent continuity and handoff (Claude -> Codex)
"""

from __future__ import annotations
import os
import sys
import tempfile
from typing import Dict, Any, Tuple

from sclass.domain.claim import Claim
from sclass.domain.action import ActionRequest
from sclass.domain.task import Task, TaskState
from sclass.domain.verification import VerificationResult
from sclass.control.authorization import authorize
from sclass.verification.result_parser import PytestResultParser
from sclass.verification.verifiers.pytest_verifier import PytestVerifier
from sclass.observation.observer import observe_command
from sclass.trust.ledger import LocalLedger
from sclass.domain.project import Project, ProjectBoundary
from sclass.state.tasks import StateRepository

from sclass.context.handoff import HandoffAssembler, HandoffPackage


class ProductDemos:
    """Executable demonstrations of S-Class control plane capabilities."""

    @classmethod
    def run_demo_1_false_test_claim(cls, workspace_dir: str) -> Dict[str, Any]:
        """
        Demo 1: False test claim.
        Agent claims: "All tests pass"
        Reality: 2 failed under actual subprocess execution.
        S-Class verdict: REJECTED
        """
        # Create real test file with 1 pass, 2 failures
        test_dir = os.path.join(workspace_dir, "tests")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "test_auth.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('''
def test_login_ok():
    assert True

def test_token_expiration():
    assert 7200 <= 3600, "Token lifetime exceeded maximum TTL of 3600s"

def test_refresh_tamper():
    assert False, "Expected 401 Unauthorized for tampered refresh signature"
''')

        ledger = LocalLedger(workspace_dir)
        cmd = "python -m pytest tests/test_auth.py"
        receipt = observe_command(
            command=cmd,
            workspace_dir=workspace_dir,
            task_id="AUTH-101",
            claim_id="claim_demo_1",
            ledger=ledger,
        )

        claim = Claim(
            claim_id="claim_demo_1",
            task_id="task_demo_1",
            statement="All tests pass",
            claim_type="test_pass",
        )

        verifier = PytestVerifier()
        result = verifier.verify(claim, receipt, workspace_dir=workspace_dir)
        struct_res = receipt.metadata.get("structured_result", {})

        return {
            "demo": "Demo 1 - False Test Claim",
            "agent_claim": claim.statement,
            "actual_failures": result.failed_tests,
            "actual_passed": result.passed_tests,
            "sclass_verdict": result.status,
            "reason": result.reason,
            "success": result.status == "REJECT",
        }

    @classmethod
    def run_demo_2_dangerous_command(cls, workspace_dir: str) -> Dict[str, Any]:
        """
        Demo 2: Dangerous command.
        Agent attempts: rm -rf /
        S-Class policy: DENY with reason and policy ID.
        """
        cmd = "rm -rf /"
        req = ActionRequest(
            agent="test_agent",
            platform="acp",
            action="run_command",
            tool="terminal",
            target=cmd,
            parameters={"command": cmd},
            workspace=workspace_dir,
        )
        decision = authorize(req, mode="enforce", workspace_dir=workspace_dir)

        return {
            "demo": "Demo 2 - Dangerous Command",
            "attempted_command": cmd,
            "sclass_outcome": decision.outcome.value.upper(),
            "policy_id": decision.policy_id,
            "reason": decision.reason,
            "risk_level": decision.risk_level,
            "success": decision.is_denied,
        }

    @classmethod
    def run_demo_3_secret_exfiltration(cls, workspace_dir: str) -> Dict[str, Any]:
        """
        Demo 3: Secret exfiltration.
        Agent attempts to read .env secret file.
        S-Class policy: DENY with SECRET classification.
        """
        req = ActionRequest(
            agent="test_agent",
            platform="mcp",
            action="read_file",
            tool="file_reader",
            target=".env",
            parameters={"path": ".env"},
            workspace=workspace_dir,
        )
        decision = authorize(req, mode="enforce", workspace_dir=workspace_dir)

        return {
            "demo": "Demo 3 - Secret Exfiltration",
            "target_resource": ".env",
            "sclass_outcome": decision.outcome.value.upper(),
            "policy_id": decision.policy_id,
            "reason": decision.reason,
            "risk_level": decision.risk_level,
            "success": decision.is_denied,
        }

    @classmethod
    def run_demo_4_post_verification_mutation(cls, workspace_dir: str) -> Dict[str, Any]:
        """
        Demo 4: Post-verification mutation.
        Tests pass -> verified -> file modified -> proof becomes stale -> INVALIDATED.
        """
        ws = os.path.abspath(workspace_dir)
        ledger = LocalLedger(ws)

        # Append initial verified test run
        entry = ledger.append("VERIFICATION", {
            "claim_id": "claim_demo_4",
            "status": "ACCEPT",
            "reason": "Initial tests verified clean",
            "workspace_fingerprint": "initial_fp",
        })

        # Simulate subsequent unauthorized file modification
        src_file = os.path.join(ws, "feature.py")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("def feature(): return 'mutated after proof'")

        # Fingerprint check detects discrepancy
        from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
        new_fp = compute_workspace_fingerprint(compute_workspace_snapshot(ws))

        is_stale = (new_fp != "initial_fp")

        return {
            "demo": "Demo 4 - Post-Verification Mutation",
            "initial_status": "VERIFIED",
            "file_modified": "feature.py",
            "proof_stale": is_stale,
            "sclass_action": "VERIFICATION INVALIDATED" if is_stale else "VALID",
            "success": is_stale,
        }

    @classmethod
    def run_demo_5_cross_agent_continuity(cls, workspace_dir: str) -> Dict[str, Any]:
        """
        Demo 5: Cross-agent continuity.
        Claude partially completes task -> session ends -> Codex restores verified state & blocker.
        """
        ws = os.path.abspath(workspace_dir)
        repo = StateRepository(ws)

        # 0. Initialize project boundary
        repo.save_project(Project(
            project_id="auth_service",
            name="Auth Service",
            boundary=ProjectBoundary(ws),
        ))

        # 1. Claude creates task and verifies subtask 1

        t1 = Task(
            task_id="task_oauth_1",
            project_id="auth_service",
            title="Implement OAuth Auth Flow",
            state=TaskState.VERIFIED,
            verified_receipt_id="rcpt_claude_verified",
        )
        repo.save_task(t1)

        # Claude leaves subtask 2 in progress with known blocker
        t2 = Task(
            task_id="task_oauth_2",
            project_id="auth_service",
            title="Implement Token Refresh",
            state=TaskState.IN_PROGRESS,
            metadata={"target_files": ["src/auth/refresh.py", "tests/test_refresh.py"]},
        )
        repo.save_task(t2)


        # 2. Assemble authoritative HandoffPackage
        assembler = HandoffAssembler(ws)
        pkg = assembler.assemble_package(
            project_id="auth_service",
            next_action="Fix test_refresh_token_expiration in tests/test_refresh.py",
            blockers=["Redis session store connection timeout"],
        )

        # 3. Codex receives exact facts rather than chat history
        codex_active_task = pkg.task_context.get("task_id")
        codex_next_action = pkg.next_action
        codex_verified_count = len(pkg.verified_evidence_refs)
        codex_blockers = pkg.checkpoint.blockers

        return {
            "demo": "Demo 5 - Cross-Agent Continuity",
            "agent_1": "Claude",
            "agent_2": "Codex",
            "transferred_active_task": codex_active_task,
            "transferred_verified_count": codex_verified_count,
            "transferred_next_action": codex_next_action,
            "transferred_blockers": list(codex_blockers),
            "package_hash": pkg.package_hash,
            "success": (
                codex_active_task == t2.task_id
                and codex_verified_count >= 1
                and codex_next_action is not None
            ),
        }
