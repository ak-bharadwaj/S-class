class AvionicsRingBufferGuard:
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.buffer = []
        self.overrun_count = 0

    def push(self, frame: dict):
        pass

    def pop(self) -> dict:
        pass
