from target_module import MutualTLSProxy

def test_mtls_authentication():
    p = MutualTLSProxy(trusted_ca_pem='CA_ROOT')
    res = p.authenticate_peer('VALID_CERT_PEM')
    assert res.get('authenticated') is True
