from target_module import HighRiskModule15, InvariantViolationError
import pytest

def test_h6_module_15():
    m = HighRiskModule15()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
