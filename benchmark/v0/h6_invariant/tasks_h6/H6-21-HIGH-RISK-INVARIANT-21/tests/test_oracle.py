from target_module import HighRiskModule21, InvariantViolationError
import pytest

def test_h6_module_21():
    m = HighRiskModule21()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
