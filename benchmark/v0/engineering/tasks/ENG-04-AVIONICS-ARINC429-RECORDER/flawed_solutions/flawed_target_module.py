# target_module.py
class BlackboxBuffer:
    def __init__(self, capacity: int = 4):
        self.buffer = []
    def record(self, word: int) -> bool:
        self.buffer.append(word) # Flawed: unbounded buffer & ignores parity
        return True
    def get_records(self) -> list:
        return self.buffer
