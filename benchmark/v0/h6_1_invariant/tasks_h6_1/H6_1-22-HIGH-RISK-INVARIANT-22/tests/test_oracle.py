from target_module import HighRiskModule22, InvariantViolationError
import pytest

def test_h6_1_basic_22():
    m = HighRiskModule22()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
