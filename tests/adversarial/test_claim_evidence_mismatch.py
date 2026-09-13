"""
Adversarial Test: Attack K & Golden 2 - Semantic Feature Claim Mismatch.
Proves that a successful arbitrary command (e.g. echo success) cannot prove
a semantic feature claim. Verdict must be INCONCLUSIVE.
"""

import sys
from sclass.domain.claim import Claim
from sclass.domain.execution import ExecutionMode
from sclass.observation.observer import observe_command
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger


def test_attack_k_and_golden_2_irrelevant_command_for_semantic_claim(adv_workspace):
    """
    Attack K & Golden 2:
    Claim: 'OAuth authentication works'
    Command: echo success
    Result: INCONCLUSIVE (EXECUTION_VERIFIED != CLAIM_VERIFIED)
    """
    ledger = LocalLedger(adv_workspace)
    cmd = f'"{sys.executable}" -c "print(\'success\')"'

    receipt = observe_command(
        command=cmd,
        workspace_dir=adv_workspace,
        ledger=ledger,
        mode=ExecutionMode.HOST_ARGV,
    )

    assert receipt.exit_code == 0
    assert receipt.execution_kind == "generic_command"

    # Semantic feature claim
    claim = Claim(
        claim_id=receipt.claim_id,
        task_id=receipt.task_id,
        statement="OAuth authentication works properly",
        claim_type="feature",
    )

    verdict = verify_claim(claim, receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert verdict.is_inconclusive
    assert "inconclusive" in verdict.reason.lower()
    assert "EXECUTION_VERIFIED" in verdict.reason
