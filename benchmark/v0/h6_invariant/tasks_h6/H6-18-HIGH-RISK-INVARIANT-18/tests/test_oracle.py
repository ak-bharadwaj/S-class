from target_module import HighRiskModule18, InvariantViolationError
import pytest

def test_h6_module_18():
    m = HighRiskModule18()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
