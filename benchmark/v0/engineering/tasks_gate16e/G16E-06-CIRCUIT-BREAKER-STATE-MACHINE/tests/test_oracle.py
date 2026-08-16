from target_module import CircuitBreakerStateMachine
import pytest

def test_cb():
    cb = CircuitBreakerStateMachine(failure_threshold=2)
    assert cb.get_state() == 'CLOSED'
    def fail(): raise ValueError('err')
    with pytest.raises(ValueError): cb.call(fail)
    with pytest.raises(ValueError): cb.call(fail)
    assert cb.get_state() == 'OPEN'
