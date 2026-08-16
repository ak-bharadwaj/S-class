from target_module import SPIFFEMutualTLSRouter

def test_spiffe_router():
    r = SPIFFEMutualTLSRouter('spiffe://example.org')
    assert r.validate_spiffe_id('spiffe://example.org/ns/prod/sa/svc1') is True
    assert r.validate_spiffe_id('spiffe://attacker.com/bad') is False
    res = r.route_request('spiffe://example.org/ns/prod/sa/svc1', {'data': 1})
    assert res.get('routed') is True
