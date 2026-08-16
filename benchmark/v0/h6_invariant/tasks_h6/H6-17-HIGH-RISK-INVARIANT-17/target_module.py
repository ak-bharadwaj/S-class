class InvariantViolationError(Exception): pass

class HighRiskModule17:
    def __init__(self):
        self.enabled = True

    def validate_invariant(self, payload: dict) -> bool:
        pass
