"""
S-Class Golden Scenarios (PART XXIII).
Permanent integration scenarios establishing core trust guarantees:
Golden 1 — False test claim (REJECT)
Golden 2 — Successful irrelevant command (INCONCLUSIVE)
Golden 3 — Correct tests (ACCEPT)
Golden 4 — Post-verification mutation (REJECT / stale)
Golden 5 — Agent handoff (checkpoint continuity)
Golden 6 — Protected trust state (DENY)
"""

import os
import sys
import pytest
from sclass.domain.claim import Claim, ClaimScope
from sclass.domain.execution import ExecutionMode
from sclass.domain.evidence import EvidenceReceipt
from sclass.domain.action import ActionRequest
from sclass.domain.project import ProjectCheckpoint, VerifiedProjectState
from sclass.context.handoff import HandoffAssembler
from sclass.observation.observer import observe_command
from sclass.verification.engine import verify_claim
from sclass.verification.verifiers.pytest_verifier import PytestVerifier
from sclass.control.authorization import authorize
from sclass.trust.ledger import LocalLedger


def test_golden_1_false_test_claim_rejected(adv_workspace):
    """
    Golden 1: False test claim
    Agent claims 'All tests pass'.
    Actual test run observed: 48 passed, 2 failed.
    S-Class must REJECT.
    """
    verifier = PytestVerifier()
    claim = Claim(
        claim_id="golden_1_claim",
        task_id="task_g1",
        statement="All tests pass",
        claim_type="test_pass",
    )
    evidence = EvidenceReceipt(
        receipt_id="rcpt_g1",
        task_id="task_g1",
        claim_id="golden_1_claim",
        agent="claude",
        action="run_pytest",
        workspace=adv_workspace,
        command="pytest tests/",
        exit_code=1,
        stdout_hash="h1",
        stderr_hash="h2",
        execution_kind="test_runner",
        verifier="pytest",
        workspace_fingerprint="fp_g1",
        evidence=[{"passed_tests": 48, "failed_tests": 2}],
    )

    verdict = verifier.verify(claim, evidence, adv_workspace)
    assert verdict.is_rejected
    assert verdict.failed_tests == 2


def test_golden_2_successful_irrelevant_command_inconclusive(adv_workspace):
    """
    Golden 2: Successful irrelevant command
    Claim: 'Authentication works'
    Command: echo success
    S-Class must return INCONCLUSIVE.
    """
    ledger = LocalLedger(adv_workspace)
    cmd = f'"{sys.executable}" -c "print(\'success\')"'
    receipt = observe_command(command=cmd, workspace_dir=adv_workspace, ledger=ledger, mode=ExecutionMode.HOST_ARGV)

    claim = Claim(
        claim_id=receipt.claim_id,
        task_id=receipt.task_id,
        statement="Authentication works",
        claim_type="feature",
    )

    verdict = verify_claim(claim, receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert verdict.is_inconclusive


def test_golden_3_correct_tests_accepted(adv_workspace):
    """
    Golden 3: Correct tests
    Claim: Authentication tests pass
    Observed: Actual authentication test target, 0 failures, exit code 0.
    S-Class must ACCEPT.
    """
    verifier = PytestVerifier()
    claim = Claim(
        claim_id="golden_3_claim",
        task_id="task_g3",
        statement="Authentication tests pass",
        claim_type="test_pass",
        scope=ClaimScope(test_targets=("tests/auth",)),
    )
    evidence = EvidenceReceipt(
        receipt_id="rcpt_g3",
        task_id="task_g3",
        claim_id="golden_3_claim",
        agent="codex",
        action="run_pytest",
        workspace=adv_workspace,
        command="pytest tests/auth",
        exit_code=0,
        stdout_hash="h3",
        stderr_hash="h4",
        execution_kind="test_runner",
        verifier="pytest",
        workspace_fingerprint="fp_g3",
        evidence=[{"passed_tests": 12, "failed_tests": 0}],
    )

    verdict = verifier.verify(claim, evidence, adv_workspace)
    assert verdict.is_accepted
    assert verdict.passed_tests == 12


def test_golden_4_post_verification_mutation_stale(adv_workspace):
    """
    Golden 4: Post-verification mutation
    Tests pass -> verified -> file changed -> evidence stale -> REJECT.
    """
    ledger = LocalLedger(adv_workspace)
    target_file = os.path.join(adv_workspace, "core.py")
    with open(target_file, "w", encoding="utf-8") as f:
        f.write("def run(): pass\n")

    cmd = f'"{sys.executable}" -c "print(1)"'
    receipt = observe_command(command=cmd, workspace_dir=adv_workspace, ledger=ledger, mode=ExecutionMode.HOST_ARGV)

    claim = Claim(
        claim_id=receipt.claim_id,
        task_id=receipt.task_id,
        statement="Executed core command",
        claim_type="execution",
    )

    # Initial verification passes
    v1 = verify_claim(claim, receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert v1.is_accepted

    # Mutate file
    with open(target_file, "a", encoding="utf-8") as f:
        f.write("# mutation\n")

    # Second verification fails due to staleness
    v2 = verify_claim(claim, receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert v2.is_rejected
    assert "stale" in v2.reason.lower()


def test_golden_5_agent_handoff_preserves_state():
    """
    Golden 5: Agent handoff
    Claude -> failed tests -> Codex -> same project state -> same failures -> next action preserved.
    """
    chk = ProjectCheckpoint(
        repository_head="commit_abc123",
        working_tree_fingerprint="fp_checkpoint_999",
        active_task="task_auth_fix",
        verified_tasks=("task_init", "task_db_schema"),
        rejected_claims=("claim_auth_attempt_1",),
        blockers=("JWT signature mismatch in tests/auth/test_jwt.py",),
        relevant_files=("src/auth/jwt.py", "tests/auth/test_jwt.py"),
        constraints=("Do not alter user table schema",),
        next_action="Fix HMAC secret encoding in src/auth/jwt.py",
    )

    # Serialize and reconstruct as if received by Codex
    serialized = chk.to_dict()
    codex_chk = ProjectCheckpoint.from_dict(serialized)

    assert codex_chk.active_task == "task_auth_fix"
    assert "claim_auth_attempt_1" in codex_chk.rejected_claims
    assert codex_chk.next_action == "Fix HMAC secret encoding in src/auth/jwt.py"
    assert codex_chk.compute_checkpoint_hash() == chk.compute_checkpoint_hash()


def test_golden_6_protected_trust_state_denied(adv_workspace):
    """
    Golden 6: Protected trust state
    Agent attempts: delete .sclass/trust/ledger
    S-Class must DENY.
    """
    req = ActionRequest(
        agent="claude",
        platform="acp",
        action="delete_file",
        tool="file_remover",
        target=".sclass/trust/audit_ledger.jsonl",
        workspace=adv_workspace,
    )
    decision = authorize(req, workspace_dir=adv_workspace)
    assert decision.is_denied
    assert "protected under boundary" in decision.reason or "SCLASS_ONLY" in decision.reason
