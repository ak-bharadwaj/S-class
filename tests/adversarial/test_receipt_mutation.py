"""
Adversarial Test: Attacks E & F - Receipt Mutation and Hash Recomputation.
Proves that mutating an observed receipt is blocked by immutability, and that
modifying a receipt on disk and recomputing its hash causes rejection via ledger mismatch.
"""

import os
import sys
import json
import pytest
from sclass.domain.claim import Claim
from sclass.domain.execution import ExecutionMode
from sclass.observation.observer import observe_command
from sclass.observation.receipt import save_receipt
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger


def test_attack_e_mutate_receipt_in_memory_blocked(adv_workspace):
    """
    Attack E:
    Agent attempts to modify attributes of an ObservedReceipt after issuance.
    Expected: AttributeError due to post-issuance immutability sealing.
    """
    cmd = f'"{sys.executable}" -c "print(100)"'
    receipt = observe_command(
        command=cmd,
        workspace_dir=adv_workspace,
        mode=ExecutionMode.HOST_ARGV,
    )

    # Attempt in-memory mutation
    with pytest.raises(AttributeError, match="immutable"):
        receipt.exit_code = 999

    with pytest.raises(AttributeError, match="immutable"):
        receipt.verifier = "pytest"


def test_attack_f_modify_receipt_and_recompute_hash_rejected(adv_workspace):
    """
    Attack F:
    Agent loads a valid serialized receipt, tampers with exit_code, recomputes receipt_hash,
    and submits for verification.
    Expected: REJECT due to mismatch between evidence receipt and ledger OBSERVATION entry.
    """
    ledger = LocalLedger(adv_workspace)
    cmd = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
    receipt = observe_command(
        command=cmd,
        workspace_dir=adv_workspace,
        mode=ExecutionMode.HOST_ARGV,
        ledger=ledger,
    )

    # Load serialized receipt dictionary and tamper with it
    data = receipt.to_dict()
    data["exit_code"] = 0  # Tamper failure into success

    from sclass.domain.evidence import EvidenceReceipt
    tampered_receipt = EvidenceReceipt.from_dict(data)
    # Recompute receipt hash to match tampered fields
    tampered_receipt.receipt_hash = tampered_receipt.compute_hash()

    claim = Claim(
        claim_id=receipt.claim_id,
        task_id=receipt.task_id,
        statement="Command succeeded",
        claim_type="execution",
    )

    verdict = verify_claim(claim, tampered_receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert verdict.is_rejected
    assert "Receipt hash mismatch" in verdict.reason or "Tampering detected" in verdict.reason
