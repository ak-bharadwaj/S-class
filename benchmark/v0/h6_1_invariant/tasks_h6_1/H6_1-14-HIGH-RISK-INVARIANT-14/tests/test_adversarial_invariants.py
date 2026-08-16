from target_module import HighRiskModule14, InvariantViolationError
import pytest

def test_h6_1_adversarial_probes_14():
    m = HighRiskModule14()
    # Probe 1: None payload
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({})
    # Probe 2: Obfuscated false payload
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': 'false'})
