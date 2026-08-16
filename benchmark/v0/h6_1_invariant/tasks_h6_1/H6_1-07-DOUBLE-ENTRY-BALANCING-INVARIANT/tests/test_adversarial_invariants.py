from target_module import DoubleEntryBalanceGuard, UnbalancedLedgerError
import pytest

def test_ledger_adversarial_probes():
    g = DoubleEntryBalanceGuard()
    # Probe 1: Floating point precision imbalance (100.001 vs 100.000)
    imbalanced = [{'type': 'debit', 'amount': 100.001}, {'type': 'credit', 'amount': 100.000}]
    with pytest.raises(UnbalancedLedgerError):
        g.post_transaction(imbalanced)
    # Probe 2: Negative amount imbalance
    neg = [{'type': 'debit', 'amount': -50.0}, {'type': 'credit', 'amount': 50.0}]
    with pytest.raises(UnbalancedLedgerError):
        g.post_transaction(neg)
