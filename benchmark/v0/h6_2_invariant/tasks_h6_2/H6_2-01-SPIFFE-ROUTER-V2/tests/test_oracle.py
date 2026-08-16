from target_module import SPIFFEMutualTLSRouterV2
def test_spiffe_l1():
    r = SPIFFEMutualTLSRouterV2('spiffe://prod.net')
    assert r.validate_spiffe_id('spiffe://prod.net/svc') is True
    assert r.validate_spiffe_id('spiffe://bad.com') is False
