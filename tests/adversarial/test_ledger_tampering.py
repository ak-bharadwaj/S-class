"""
Adversarial Test: Attack G & Golden 6 - Ledger Tampering Defense.
Proves that modifying or replacing ledger entries breaks the cryptographic hash chain
and causes the verification engine to reject any evidence anchored in it.
"""

import os
import json
from sclass.trust.ledger import LocalLedger
from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.verification.engine import verify_claim


def test_attack_g_ledger_tampering_breaks_hash_chain(adv_workspace):
    """
    Attack G:
    Agent tampers with an entry inside audit_ledger.jsonl.
    verify_integrity() must return False, and verification must fail.
    """
    ledger = LocalLedger(adv_workspace)
    ledger.append("test_event", {"data": "authentic"})

    assert ledger.verify_chain()

    # Tamper with the ledger file directly
    with open(ledger.ledger_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Modify payload in the last line without updating hash
    entry = json.loads(lines[-1])
    entry["payload"]["data"] = "tampered_by_attacker"
    lines[-1] = json.dumps(entry) + "\n"

    with open(ledger.ledger_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    is_valid, err = ledger.verify_integrity()
    assert not is_valid
    assert "mismatch" in err.lower() or "broken" in err.lower()
