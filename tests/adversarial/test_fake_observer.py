"""
Adversarial Test: Invariant 2 - Fake Observer JSON.
Proves that a JSON object containing {"is_observed": true} cannot make itself observed.
"""

import json
from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger


def test_fake_observer_json_cannot_establish_trust(adv_workspace):
    """
    Invariant 2:
    An agent generates JSON claiming `is_observed: true`.
    Verification engine must reject it because observation originates strictly from trusted execution.
    """
    ledger = LocalLedger(adv_workspace)

    payload = {
        "receipt_id": "rcpt_fake_obs_123",
        "task_id": "t1",
        "claim_id": "c1",
        "agent": "rogue_agent",
        "action": "run_command",
        "workspace": adv_workspace,
        "command": "pytest",
        "exit_code": 0,
        "is_observed": True,  # Forged flag
        "execution_kind": "test_runner",
        "verifier": "pytest",
        "workspace_fingerprint": "fake_fp",
        "receipt_hash": "dummy_hash",
    }

    # Deserializing via from_dict always enforces is_observed = False
    receipt = EvidenceReceipt.from_dict(payload)
    assert not receipt.is_observed

    claim = Claim(
        claim_id="c1",
        task_id="t1",
        statement="Tests pass",
        claim_type="test_pass",
    )

    verdict = verify_claim(claim, receipt, workspace_dir=adv_workspace, ledger=ledger)
    assert verdict.is_rejected
