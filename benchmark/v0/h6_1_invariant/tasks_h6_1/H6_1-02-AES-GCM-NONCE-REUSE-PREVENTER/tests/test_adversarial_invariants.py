from target_module import AESGCMNonceGuard, NonceReuseError
import pytest

def test_nonce_adversarial_probes():
    g = AESGCMNonceGuard()
    # Probe 1: Replay attack with same nonce 3 times
    n = b'123456789012'
    g.register_nonce(n)
    with pytest.raises(NonceReuseError):
        g.register_nonce(n)
    with pytest.raises(NonceReuseError):
        g.register_nonce(n)
    # Probe 2: Invalid short nonce length
    with pytest.raises(Exception):
        g.register_nonce(b'short')
