import pytest
from error_recovery import ErrorPath, RecoveryEngine

def test_error_path_regex_matching():
    ep1 = ErrorPath(r"TimeoutError.*", "Network issue", "retry")
    ep2 = ErrorPath(r"ValueError: \d+", "Bad input", "skip")
    engine = RecoveryEngine()
    
    assert engine.match_error("Got a TimeoutError during fetch", [ep1, ep2]) == ep1
    assert engine.match_error("ValueError: 42 on line 5", [ep1, ep2]) == ep2
    assert engine.match_error("UnknownError happened", [ep1, ep2]) is None

def test_backoff_calculation():
    ep = ErrorPath("err", "hint", "retry", backoff_seconds=2.0, backoff_multiplier=3.0)
    engine = RecoveryEngine()
    
    # Exponential
    assert engine.calculate_backoff(0, ep, "exponential") == 2.0
    assert engine.calculate_backoff(1, ep, "exponential") == 6.0
    assert engine.calculate_backoff(2, ep, "exponential") == 18.0
    
    # Linear
    assert engine.calculate_backoff(0, ep, "linear") == 2.0
    assert engine.calculate_backoff(1, ep, "linear") == 4.0
    assert engine.calculate_backoff(2, ep, "linear") == 6.0
    
    # Fixed
    assert engine.calculate_backoff(0, ep, "fixed") == 2.0
    assert engine.calculate_backoff(5, ep, "fixed") == 2.0

def test_should_stop():
    ep = ErrorPath("err", "hint", "retry", max_retries=3)
    engine = RecoveryEngine()
    
    assert engine.should_stop(0, ep) is False
    assert engine.should_stop(2, ep) is False
    assert engine.should_stop(3, ep) is True
    assert engine.should_stop(4, ep) is True

def test_smart_multi_tier_recovery():
    engine = RecoveryEngine()
    
    # Syntax Error -> CODING
    assert engine.classify_failure_target_phase("SyntaxError: invalid syntax at line 42") == "CODING"
    
    # Dependency Error -> INTEGRATION
    assert engine.classify_failure_target_phase("ModuleNotFoundError: No module named 'express'") == "INTEGRATION"
    
    # Type Mismatch -> DESIGN
    assert engine.classify_failure_target_phase("TypeError: Interface mismatch in DTO schema") == "DESIGN"
    
    # Ambiguity Error -> CLARIFICATION
    assert engine.classify_failure_target_phase("SpecificationMissing: Ambiguity in user role permissions") == "CLARIFICATION"
