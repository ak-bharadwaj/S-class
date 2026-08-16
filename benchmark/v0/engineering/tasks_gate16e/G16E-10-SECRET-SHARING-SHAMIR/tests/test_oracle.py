from target_module import ShamirSecretSharing

def test_shamir():
    s = ShamirSecretSharing()
    shares = s.split(9999, 5, 3)
    assert len(shares) == 5
    assert s.combine(shares[:3]) == 9999
