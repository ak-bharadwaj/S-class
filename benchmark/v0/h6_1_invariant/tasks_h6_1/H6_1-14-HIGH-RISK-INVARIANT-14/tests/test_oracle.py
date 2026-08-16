from target_module import HighRiskModule14, InvariantViolationError
import pytest

def test_h6_1_basic_14():
    m = HighRiskModule14()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
