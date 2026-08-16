from target_module import PHIMaskingGuard

def test_phi_adversarial_probes():
    g = PHIMaskingGuard()
    # Probe 1: Obfuscated SSN with spaces and dots
    res1 = g.mask_phi('Patient SSN is 123 . 45 . 6789 confidential')
    assert '123 . 45 . 6789' not in res1
    # Probe 2: Multiple MRN entries in single record
    res2 = g.mask_phi('MRN-111111 and MRN-222222')
    assert '111111' not in res2 and '222222' not in res2
