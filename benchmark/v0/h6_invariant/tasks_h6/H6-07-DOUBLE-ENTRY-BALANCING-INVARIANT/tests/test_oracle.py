from target_module import DoubleEntryBalanceGuard, UnbalancedLedgerError
import pytest

def test_ledger_balance():
    g = DoubleEntryBalanceGuard()
    valid = [{'type': 'debit', 'amount': 100.0}, {'type': 'credit', 'amount': 100.0}]
    assert g.post_transaction(valid) is True
    invalid = [{'type': 'debit', 'amount': 100.0}, {'type': 'credit', 'amount': 50.0}]
    with pytest.raises(UnbalancedLedgerError):
        g.post_transaction(invalid)
