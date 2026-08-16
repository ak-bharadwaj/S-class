# target_module.py
from collections import defaultdict

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_sec: float):
        self.max_requests = max_requests
        self.window_sec = window_sec
        self.logs = defaultdict(list)

    def allow_request(self, client_id: str, timestamp: float) -> bool:
        window_start = timestamp - self.window_sec
        # Evict timestamps older than sliding window
        self.logs[client_id] = [t for t in self.logs[client_id] if t > window_start]
        
        if len(self.logs[client_id]) < self.max_requests:
            self.logs[client_id].append(timestamp)
            return True
        return False
