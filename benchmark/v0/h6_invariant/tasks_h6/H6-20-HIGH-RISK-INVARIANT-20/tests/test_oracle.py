from target_module import HighRiskModule20, InvariantViolationError
import pytest

def test_h6_module_20():
    m = HighRiskModule20()
    assert m.validate_invariant({'valid': True}) is True
    with pytest.raises(InvariantViolationError):
        m.validate_invariant({'valid': False})
