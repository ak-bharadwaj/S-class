import pytest
import os
from target_module import EnvelopeKMS

def test_kms_envelope_encryption():
    kms = EnvelopeKMS("master_kek_v1")
    enc = kms.encrypt_secret("sensitive_api_token_99")
    assert enc["ciphertext"] != "sensitive_api_token_99"
    dec = kms.decrypt_secret(enc)
    assert dec == "sensitive_api_token_99"
