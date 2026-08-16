# target_module.py
class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_sec: float):
        pass
    def allow_request(self, client_id: str, timestamp: float) -> bool:
        return True # Flawed: allows infinite rate
