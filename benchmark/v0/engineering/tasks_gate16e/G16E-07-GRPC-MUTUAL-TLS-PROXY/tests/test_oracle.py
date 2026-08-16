from target_module import MutualTLSProxy

def test_mtls():
    p = MutualTLSProxy('CA_ROOT')
    res = p.authenticate_peer('VALID_CERT')
    assert res.get('authenticated') is True
