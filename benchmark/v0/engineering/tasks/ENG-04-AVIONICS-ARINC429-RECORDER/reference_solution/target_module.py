# target_module.py
class BlackboxBuffer:
    def __init__(self, capacity: int = 4):
        self.capacity = capacity
        self.buffer = []

    @staticmethod
    def verify_odd_parity(word: int) -> bool:
        # 32-bit odd parity test
        return bin(word & 0xFFFFFFFF).count('1') % 2 == 1

    def record(self, word: int) -> bool:
        if not self.verify_odd_parity(word):
            raise ValueError("Parity check failed: word does not have odd parity")
        if len(self.buffer) >= self.capacity:
            self.buffer.pop(0)
        self.buffer.append(word)
        return True

    def get_records(self) -> list:
        return list(self.buffer)
