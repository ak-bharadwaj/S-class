from target_module import HighRiskModule10, InvariantViolationError
import pytest

def test_h6_1_basic_10():
    m = HighRiskModule10()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
