class LedgerError(Exception): pass
class DoubleEntryLedgerV2:
    def balance(self, debits: list, credits: list) -> bool:
        return sum(debits) == sum(credits) # Flawed: float precision mismatch
