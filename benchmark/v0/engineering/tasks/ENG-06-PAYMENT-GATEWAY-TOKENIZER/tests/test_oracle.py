import pytest
from target_module import CardTokenizer

def test_luhn_and_tokenization():
    tokenizer = CardTokenizer()
    valid_pan = "4532015112830366" # Valid Luhn
    invalid_pan = "4532015112830367"
    
    assert tokenizer.validate_luhn(valid_pan) is True
    assert tokenizer.validate_luhn(invalid_pan) is False
    
    tok = tokenizer.tokenize(valid_pan)
    assert tok.startswith("453201")
    assert tok.endswith("0366")
    
    with pytest.raises(ValueError):
        tokenizer.tokenize(invalid_pan)
