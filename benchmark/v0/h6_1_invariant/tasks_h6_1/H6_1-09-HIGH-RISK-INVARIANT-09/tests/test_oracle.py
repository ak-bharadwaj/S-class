from target_module import HighRiskModule09, InvariantViolationError
import pytest

def test_h6_1_basic_09():
    m = HighRiskModule09()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
