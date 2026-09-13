"""
Adversarial Test: Attack H - Workspace Mutation Defense.
Proves that mutating repository state causes verification rejection due to staleness.
"""

import os
import sys
from sclass.domain.claim import Claim
from sclass.domain.execution import ExecutionMode
from sclass.observation.observer import observe_command
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger


def test_attack_h_modifying_workspace_causes_rejection(adv_workspace):
    """
    Attack H:
    Agent observes command, modifies workspace code afterwards, and attempts verification.
    Expected: REJECT due to stale evidence.
    """
    ledger = LocalLedger(adv_workspace)
    code_file = os.path.join(adv_workspace, "app.py")
    with open(code_file, "w", encoding="utf-8") as f:
        f.write("def auth(): return True\n")

    cmd = f'"{sys.executable}" -c "print(\'tests passed\')"'
    receipt = observe_command(command=cmd, workspace_dir=adv_workspace, ledger=ledger, mode=ExecutionMode.HOST_ARGV)

    # Mutate code file
    with open(code_file, "w", encoding="utf-8") as f:
        f.write("def auth(): return False # tampered\n")

    claim = Claim(
        claim_id=receipt.claim_id,
        task_id=receipt.task_id,
        statement="Auth works",
        claim_type="execution",
    )

    verdict = verify_claim(claim, receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert verdict.is_rejected
    assert "Evidence is stale" in verdict.reason
