from target_module import AESGCMNonceGuard, NonceReuseError
import pytest

def test_nonce_basic():
    g = AESGCMNonceGuard()
    n1 = g.generate_nonce()
    g.register_nonce(n1)
    with pytest.raises(NonceReuseError):
        g.register_nonce(n1)
