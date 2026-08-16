from target_module import HighRiskModule17, InvariantViolationError
import pytest

def test_h6_1_basic_17():
    m = HighRiskModule17()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
