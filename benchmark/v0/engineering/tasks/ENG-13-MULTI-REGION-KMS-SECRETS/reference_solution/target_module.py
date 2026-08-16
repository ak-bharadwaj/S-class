# target_module.py
import os, hmac, hashlib, base64

class EnvelopeKMS:
    def __init__(self, kek_secret: str):
        self.kek_secret = kek_secret

    def _derive_key(self, kek: str) -> bytes:
        return hashlib.sha256(kek.encode()).digest()

    def encrypt_secret(self, plaintext: str) -> dict:
        # Simple XOR cipher for demonstration envelope encryption
        dk = hashlib.sha256(os.urandom(16)).digest()
        kek = self._derive_key(self.kek_secret)
        wrapped_dk = bytes(a ^ b for a, b in zip(dk, kek))
        
        ciphertext = bytes(a ^ b for a, b in zip(plaintext.encode(), dk * 10))
        return {
            "wrapped_dk": base64.b64encode(wrapped_dk).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode()
        }

    def decrypt_secret(self, encrypted_payload: dict) -> str:
        wrapped_dk = base64.b64decode(encrypted_payload["wrapped_dk"])
        ciphertext = base64.b64decode(encrypted_payload["ciphertext"])
        kek = self._derive_key(self.kek_secret)
        dk = bytes(a ^ b for a, b in zip(wrapped_dk, kek))
        plaintext = bytes(a ^ b for a, b in zip(ciphertext, dk * 10))
        return plaintext.decode()
