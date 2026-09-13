"""
Adversarial Test: Attack A - Agent Fabricates "pytest" Receipt.
Proves that an agent-fabricated EvidenceReceipt with simulated success is rejected
by the verification engine because it lacks authentic ledger observation anchoring.
"""

import pytest
from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger


def test_attack_a_agent_fabricates_pytest_receipt(adv_workspace):
    """
    Attack A:
    Agent manufactures an EvidenceReceipt object directly, setting exit_code=0,
    verifier='pytest', and execution_kind='test_runner'.
    Result MUST be REJECT.
    """
    ledger = LocalLedger(adv_workspace)

    fabricated_receipt = EvidenceReceipt(
        receipt_id="rcpt_forged_001",
        task_id="task_hack",
        claim_id="claim_auth_hack",
        agent="evil_agent",
        action="run_pytest",
        workspace=adv_workspace,
        command="pytest tests/auth",
        exit_code=0,
        stdout_hash="fake_stdout",
        stderr_hash="fake_stderr",
        execution_kind="test_runner",
        verifier="pytest",
        workspace_fingerprint="fp_fake",
        verified=False,
        is_observed=False,
    )
    fabricated_receipt.receipt_hash = fabricated_receipt.compute_hash()

    claim = Claim(
        claim_id="claim_auth_hack",
        task_id="task_hack",
        statement="All authentication tests pass successfully",
        claim_type="test_pass",
        requested_verifier="pytest",
    )

    verdict = verify_claim(claim, fabricated_receipt, workspace_dir=adv_workspace, ledger=ledger)

    assert verdict.is_rejected
    assert "unobserved or untrusted evidence" in verdict.reason or "Provenance not found" in verdict.reason
