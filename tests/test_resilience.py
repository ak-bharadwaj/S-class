"""
Comprehensive test suite for resilience.py (Action Fingerprinting & Circuit Breaker Engine).
"""

import pytest
from error_recovery import ErrorPath
from resilience import ActionResilienceEngine, CircuitBreakerOpenException


def test_action_resilience_fingerprint_deterministic_and_canonical():
    """Verifies fingerprint computation is deterministic and RFC 8785 key-order invariant."""
    payload1 = {"path": "src/app.py", "action": "update", "priority": 1}
    payload2 = {"priority": 1, "action": "update", "path": "src/app.py"}

    fp1 = ActionResilienceEngine.fingerprint("file_edit", payload1)
    fp2 = ActionResilienceEngine.fingerprint("file_edit", payload2)

    assert isinstance(fp1, str)
    assert len(fp1) == 64
    assert fp1 == fp2  # Key order invariance via canonical JSON


def test_action_resilience_loop_stagnation_trips_breaker():
    """Verifies repeating the identical action reaches loop_threshold and trips circuit breaker."""
    engine = ActionResilienceEngine(loop_threshold=3)
    action = "run_command"
    payload = {"cmd": "pytest tests/"}

    r1 = engine.record_action(action, payload)
    assert r1["consecutive_repetitions"] == 1
    assert r1["loop_detected"] is False
    assert r1["circuit_state"] == "CLOSED"

    r2 = engine.record_action(action, payload)
    assert r2["consecutive_repetitions"] == 2
    assert r2["loop_detected"] is False
    assert r2["circuit_state"] == "CLOSED"

    # Third repetition trips circuit breaker
    r3 = engine.record_action(action, payload)
    assert r3["consecutive_repetitions"] == 3
    assert r3["loop_detected"] is True
    assert r3["circuit_state"] == "OPEN"

    # Subsequent call raises CircuitBreakerOpenException
    with pytest.raises(CircuitBreakerOpenException, match="Circuit Breaker is OPEN"):
        engine.record_action(action, payload)


def test_action_resilience_reset():
    """Verifies reset restores CLOSED circuit state and clears histories."""
    engine = ActionResilienceEngine(loop_threshold=2)
    engine.record_action("a", 1)
    engine.record_action("a", 1)
    assert engine.circuit_state == "OPEN"

    engine.reset()
    assert engine.circuit_state == "CLOSED"
    assert engine.trip_reason is None
    assert len(engine.action_history) == 0
    assert len(engine.fingerprint_history) == 0

    # Can record actions again
    res = engine.record_action("a", 1)
    assert res["circuit_state"] == "CLOSED"


def test_action_resilience_delegated_methods():
    """Verifies calculate_backoff and match_error public interface."""
    engine = ActionResilienceEngine()
    ep = ErrorPath(r"ConnectionError.*", "Network hiccup", "retry", max_retries=4, backoff_seconds=1.5, backoff_multiplier=2.0)

    assert engine.calculate_backoff(0, ep, "exponential") == 1.5
    assert engine.calculate_backoff(1, ep, "exponential") == 3.0
    assert engine.calculate_backoff(2, ep, "exponential") == 6.0

    matched = engine.match_error("ConnectionError: failed to reach gateway", [ep])
    assert matched == ep
    assert engine.match_error("Unhandled", [ep]) is None


def test_action_resilience_execute_with_retry():
    """Verifies execute_with_resilience uses tenacity to retry until success."""
    engine = ActionResilienceEngine()
    ep = ErrorPath(".*", "retry hint", "retry", max_retries=3, backoff_seconds=0.01)

    attempts = 0

    def flaky_func(val):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("temporary error")
        return val * 2

    result = engine.execute_with_resilience(flaky_func, ep, 21, strategy="fixed")
    assert result == 42
    assert attempts == 3
