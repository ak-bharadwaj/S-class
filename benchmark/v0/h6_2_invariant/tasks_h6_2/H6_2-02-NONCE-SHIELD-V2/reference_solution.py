class NonceReuseError(Exception): pass
class NonceShieldV2:
    def __init__(self): self.used = set()
    def register_nonce(self, n: bytes):
        if len(n) != 12: raise ValueError('Invalid length')
        if n in self.used: raise NonceReuseError('Replay')
        self.used.add(n)
