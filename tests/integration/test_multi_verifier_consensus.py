"""
End-to-End integration test validating multi-verifier consensus gate (V7).
"""
import pytest

class ConsensusGate:
    def __init__(self, required_signals: int = 2):
        self.required_signals = required_signals

    def evaluate_claim(self, verdicts: list[bool]) -> bool:
        positive_count = sum(1 for v in verdicts if v is True)
        return positive_count >= self.required_signals

def test_consensus_requires_minimum_corroborating_verifiers():
    gate = ConsensusGate(required_signals=2)
    assert gate.evaluate_claim([True, False, False]) is False
    assert gate.evaluate_claim([True, True, False]) is True
    assert gate.evaluate_claim([True, True, True]) is True
