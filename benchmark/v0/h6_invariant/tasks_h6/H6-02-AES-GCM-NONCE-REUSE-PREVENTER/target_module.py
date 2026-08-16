class NonceReuseError(Exception): pass

class AESGCMNonceGuard:
    def __init__(self):
        self.used_nonces = set()

    def generate_nonce(self) -> bytes:
        pass

    def register_nonce(self, nonce: bytes):
        pass
