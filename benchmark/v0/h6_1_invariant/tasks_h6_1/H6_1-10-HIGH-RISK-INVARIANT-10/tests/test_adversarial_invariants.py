from target_module import HighRiskModule10, InvariantViolationError
import pytest

def test_h6_1_adversarial_probes_10():
    m = HighRiskModule10()
    # Probe 1: None payload
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({})
    # Probe 2: Obfuscated false payload
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': 'false'})
