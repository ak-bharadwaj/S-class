from target_module import CircuitBreakerStateMachine
import pytest

def test_circuit_breaker_closed_to_open():
    cb = CircuitBreakerStateMachine(failure_threshold=2)
    def failing_fn(): raise ValueError('err')
    assert cb.get_state() == 'CLOSED'
    with pytest.raises(ValueError): cb.call(failing_fn)
    with pytest.raises(ValueError): cb.call(failing_fn)
    assert cb.get_state() == 'OPEN'
