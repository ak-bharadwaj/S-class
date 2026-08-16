from target_module import HighRiskModule21, InvariantViolationError
import pytest

def test_h6_1_adversarial_probes_21():
    m = HighRiskModule21()
    # Probe 1: None payload
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({})
    # Probe 2: Obfuscated false payload
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': 'false'})
