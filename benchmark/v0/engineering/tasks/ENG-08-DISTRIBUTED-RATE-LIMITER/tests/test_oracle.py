import pytest
from target_module import SlidingWindowRateLimiter

def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_sec=10.0)
    assert limiter.allow_request('client_1', 1.0) is True
    assert limiter.allow_request('client_1', 2.0) is True
    assert limiter.allow_request('client_1', 3.0) is False # Cap exceeded
    # Window slide check after t > 11.0
    assert limiter.allow_request('client_1', 11.5) is True # Old timestamps evicted
