from target_module import HighRiskModule11, InvariantViolationError
import pytest

def test_h6_module_11():
    m = HighRiskModule11()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
