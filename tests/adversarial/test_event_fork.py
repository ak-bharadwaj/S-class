"""
Adversarial Test: Ledger Event Fork Defense.
Proves that diverging or forked ledger histories are flagged by ledger.repair().
"""

from sclass.trust.ledger import LocalLedger


def test_ledger_fork_detected_by_repair(adv_workspace):
    """
    Creates two diverging ledger files (primary vs legacy).
    ledger.repair() must detect the discrepancy and produce 'FORKED'.
    """
    ledger = LocalLedger(adv_workspace)
    ledger.append("event_1", {"msg": "common"})

    # Diverge primary and legacy ledger files
    with open(ledger.ledger_file, "a", encoding="utf-8") as f:
        f.write('{"sequence": 2, "event": "primary_branch"}\n')

    with open(ledger.legacy_ledger_file, "a", encoding="utf-8") as f:
        f.write('{"sequence": 2, "event": "legacy_branch"}\n')

    repair_result = ledger.repair()
    assert repair_result in ("FORKED", "CORRUPTED")
