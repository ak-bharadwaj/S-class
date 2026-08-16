from target_module import HighRiskModule23, InvariantViolationError
import pytest

def test_h6_module_23():
    m = HighRiskModule23()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
