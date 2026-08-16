from target_module import PHIMaskingGuard

def test_phi_masking():
    g = PHIMaskingGuard()
    clean = g.mask_phi('Patient SSN: 123-45-6789 MRN: MRN-998877 email: test@hosp.org')
    assert '123-45-6789' not in clean
    assert '[REDACTED_SSN]' in clean or 'XXX-XX-XXXX' in clean or '***' in clean
