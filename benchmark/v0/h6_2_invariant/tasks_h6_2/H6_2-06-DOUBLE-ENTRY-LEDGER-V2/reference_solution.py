class LedgerError(Exception): pass
class DoubleEntryLedgerV2:
    def balance(self, debits: list, credits: list) -> bool:
        if any(d < 0 for d in debits) or any(c < 0 for c in credits):
            raise LedgerError('Negative amount')
        if round(sum(debits), 4) != round(sum(credits), 4):
            raise LedgerError('Unbalanced')
        return True
