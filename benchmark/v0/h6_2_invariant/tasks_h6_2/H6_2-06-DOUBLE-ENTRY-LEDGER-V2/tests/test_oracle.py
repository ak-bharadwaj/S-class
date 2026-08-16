from target_module import DoubleEntryLedgerV2, LedgerError
import pytest
def test_ledger_l1():
    l = DoubleEntryLedgerV2()
    assert l.balance([100.0], [100.0]) is True
    with pytest.raises(LedgerError):
        l.balance([100.0], [50.0])
