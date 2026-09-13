"""
Adversarial Test: Invariant 3 - Fake Verifier Request.
Proves that an agent cannot upgrade a generic script or python -c command into pytest evidence.
"""

import sys
from sclass.domain.claim import Claim
from sclass.domain.execution import ExecutionMode
from sclass.observation.observer import observe_command
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger


def test_caller_requested_verifier_cannot_upgrade_generic_command(adv_workspace):
    """
    Caller requests verifier="pytest" when calling observe_command,
    but the actual executed process is `python -c "print('fake pytest run')"`.
    The authoritative detector must identify it as generic_command,
    and verify_claim must REJECT the claim due to verifier mismatch.
    """
    ledger = LocalLedger(adv_workspace)
    cmd = f'"{sys.executable}" -c "print(\'fake pytest run\')"'

    receipt = observe_command(
        command=cmd,
        workspace_dir=adv_workspace,
        mode=ExecutionMode.HOST_ARGV,
        ledger=ledger,
        requested_verifier="pytest",  # Untrusted caller request
    )

    # Invariant 3: Authoritative verifier derived by detector
    assert receipt.verifier in ("generic", "none")
    assert receipt.execution_kind == "generic_command"

    # Agent claims tests passed with requested verifier pytest
    claim = Claim(
        claim_id=receipt.claim_id,
        task_id=receipt.task_id,
        statement="All tests pass",
        claim_type="test_pass",
        requested_verifier="pytest",
    )

    verdict = verify_claim(claim, receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert verdict.is_rejected
    assert "Verifier mismatch" in verdict.reason or "not executed by an authorized test runner" in verdict.reason
