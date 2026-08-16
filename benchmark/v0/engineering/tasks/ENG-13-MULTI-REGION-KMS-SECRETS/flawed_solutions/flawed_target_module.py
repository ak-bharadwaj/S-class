# target_module.py
class EnvelopeKMS:
    def __init__(self, kek_secret: str):
        pass
    def encrypt_secret(self, plaintext: str) -> dict:
        return {"ciphertext": plaintext} # Flawed: plaintext leak, no envelope encryption
    def decrypt_secret(self, encrypted_payload: dict) -> str:
        return encrypted_payload["ciphertext"]
