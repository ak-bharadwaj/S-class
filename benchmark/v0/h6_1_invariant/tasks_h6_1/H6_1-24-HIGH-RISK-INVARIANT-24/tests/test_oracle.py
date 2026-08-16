from target_module import HighRiskModule24, InvariantViolationError
import pytest

def test_h6_1_basic_24():
    m = HighRiskModule24()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
