"""
Adversarial Test: Golden 4 - Post-Verification Mutation.
Proves that when tests pass and claim is verified, subsequent file changes
invalidate previous evidence and cause verification rejection.
"""

import os
import sys
from sclass.domain.claim import Claim
from sclass.domain.execution import ExecutionMode
from sclass.observation.observer import observe_command
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger


def test_golden_4_post_verification_mutation_invalidates_evidence(adv_workspace):
    """
    Golden 4:
    1. Tests pass -> verification accepts.
    2. File changed.
    3. Previous evidence is now stale -> verification rejects.
    """
    ledger = LocalLedger(adv_workspace)
    mod_file = os.path.join(adv_workspace, "service.py")
    with open(mod_file, "w", encoding="utf-8") as f:
        f.write("def service(): return 1\n")

    cmd = f'"{sys.executable}" -c "print(\'tests clean\')"'
    receipt = observe_command(command=cmd, workspace_dir=adv_workspace, ledger=ledger, mode=ExecutionMode.HOST_ARGV)

    claim = Claim(
        claim_id=receipt.claim_id,
        task_id=receipt.task_id,
        statement="Executed test runner",
        claim_type="execution",
    )

    # Initial verification: succeeds
    v1 = verify_claim(claim, receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert v1.is_accepted

    # Post-verification file mutation
    with open(mod_file, "a", encoding="utf-8") as f:
        f.write("# mutation\n")

    # Second verification with same evidence: must REJECT
    v2 = verify_claim(claim, receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert v2.is_rejected
    assert "stale" in v2.reason.lower()
