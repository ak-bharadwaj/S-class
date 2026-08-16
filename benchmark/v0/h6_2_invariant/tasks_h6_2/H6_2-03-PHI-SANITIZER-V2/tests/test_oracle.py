from target_module import PHISanitizerV2
def test_phi_l1():
    s = PHISanitizerV2()
    assert '123-45-6789' not in s.sanitize('SSN: 123-45-6789')
