from target_module import SPIFFEMutualTLSRouterV2
def test_spiffe_l2():
    r = SPIFFEMutualTLSRouterV2('spiffe://prod.net')
    assert r.validate_spiffe_id('spiffe://prod.net.attacker.com/bad') is False
