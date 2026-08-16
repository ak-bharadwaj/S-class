from target_module import DoubleEntryLedgerV2, LedgerError
import pytest
def test_ledger_l2():
    l = DoubleEntryLedgerV2()
    with pytest.raises(LedgerError):
        l.balance([-50.0], [50.0]) # Negative debit
