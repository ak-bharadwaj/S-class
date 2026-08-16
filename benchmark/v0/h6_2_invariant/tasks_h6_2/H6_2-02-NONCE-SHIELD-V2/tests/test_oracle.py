from target_module import NonceShieldV2, NonceReuseError
import pytest
def test_nonce_l1():
    s = NonceShieldV2()
    s.register_nonce(b'123456789012')
    with pytest.raises(NonceReuseError):
        s.register_nonce(b'123456789012')
