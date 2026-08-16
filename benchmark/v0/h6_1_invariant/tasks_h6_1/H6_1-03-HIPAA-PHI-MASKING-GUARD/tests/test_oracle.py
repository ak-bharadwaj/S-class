from target_module import PHIMaskingGuard

def test_phi_basic():
    g = PHIMaskingGuard()
    clean = g.mask_phi('SSN: 123-45-6789 MRN: MRN-998877 email: test@hosp.org')
    assert '123-45-6789' not in clean
    assert '[REDACTED]' in clean or 'XXX-XX-XXXX' in clean or '***' in clean
