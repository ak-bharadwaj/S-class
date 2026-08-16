# target_module.py
import re, hashlib

class CardTokenizer:
    def __init__(self):
        self.vault = {}

    @staticmethod
    def validate_luhn(pan: str) -> bool:
        digits = [int(c) for c in pan if c.isdigit()]
        if len(digits) < 13 or len(digits) > 19:
            return False
        checksum = 0
        reverse_digits = digits[::-1]
        for i, digit in enumerate(reverse_digits):
            if i % 2 == 1:
                doubled = digit * 2
                checksum += doubled - 9 if doubled > 9 else doubled
            else:
                checksum += digit
        return checksum % 10 == 0

    def tokenize(self, pan: str) -> str:
        clean_pan = "".join(c for c in pan if c.isdigit())
        if not self.validate_luhn(clean_pan):
            raise ValueError("Invalid PAN: Luhn checksum failed")
        token = f"{clean_pan[:6]}TOKEN{clean_pan[-4:]}"
        # Vault stores hashed PAN, never plaintext
        pan_hash = hashlib.sha256(clean_pan.encode()).hexdigest()
        self.vault[token] = pan_hash
        return token
