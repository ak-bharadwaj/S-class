from target_module import NonceShieldV2, NonceReuseError
import pytest
def test_nonce_l2():
    s = NonceShieldV2()
    with pytest.raises(ValueError):
        s.register_nonce(b'short')
