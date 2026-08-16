from target_module import HighRiskModule16, InvariantViolationError
import pytest

def test_h6_module_16():
    m = HighRiskModule16()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
