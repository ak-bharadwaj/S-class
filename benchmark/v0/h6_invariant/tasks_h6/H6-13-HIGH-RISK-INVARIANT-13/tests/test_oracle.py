from target_module import HighRiskModule13, InvariantViolationError
import pytest

def test_h6_module_13():
    m = HighRiskModule13()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
