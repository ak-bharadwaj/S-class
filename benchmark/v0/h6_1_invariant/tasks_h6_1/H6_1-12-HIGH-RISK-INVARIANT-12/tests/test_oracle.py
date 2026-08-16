from target_module import HighRiskModule12, InvariantViolationError
import pytest

def test_h6_1_basic_12():
    m = HighRiskModule12()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
