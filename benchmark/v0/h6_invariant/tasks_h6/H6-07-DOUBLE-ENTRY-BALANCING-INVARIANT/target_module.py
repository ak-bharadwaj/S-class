class UnbalancedLedgerError(Exception): pass

class DoubleEntryBalanceGuard:
    def post_transaction(self, entries: list) -> bool:
        pass
