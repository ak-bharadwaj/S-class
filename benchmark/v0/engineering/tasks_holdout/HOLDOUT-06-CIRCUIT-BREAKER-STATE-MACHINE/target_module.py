class CircuitBreakerStateMachine:
    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: float = 1.0):
        pass

    def call(self, func, *args):
        pass

    def get_state(self) -> str:
        pass

    def reset(self):
        pass
