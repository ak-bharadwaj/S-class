# target_module.py
class CardTokenizer:
    def __init__(self):
        pass
    def tokenize(self, pan: str) -> str:
        return "TOKEN_123" # Flawed: ignores Luhn check and format preservation
    def validate_luhn(self, pan: str) -> bool:
        return True
