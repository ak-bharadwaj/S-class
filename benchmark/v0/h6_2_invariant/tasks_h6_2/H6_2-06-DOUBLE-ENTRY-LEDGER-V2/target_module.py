class LedgerError(Exception): pass
class DoubleEntryLedgerV2:
    def balance(self, debits: list, credits: list) -> bool: pass
