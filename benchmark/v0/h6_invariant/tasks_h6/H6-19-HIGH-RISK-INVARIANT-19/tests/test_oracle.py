from target_module import HighRiskModule19, InvariantViolationError
import pytest

def test_h6_module_19():
    m = HighRiskModule19()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
