from target_module import SPIFFEMutualTLSRouter
import pytest

def test_spiffe_adversarial_probes():
    r = SPIFFEMutualTLSRouter('spiffe://example.org')
    # Probe 1: Prefix confusion attack
    assert r.validate_spiffe_id('spiffe://example.org.attacker.com/bad') is False
    # Probe 2: Subdomain spoofing
    assert r.validate_spiffe_id('spiffe://sub.example.org/bad') is False
    # Probe 3: Empty identity
    assert r.validate_spiffe_id('') is False
    # Probe 4: Malformed routing attempt
    with pytest.raises(Exception):
        r.route_request('spiffe://attacker.com/bad', {'data': 1})
