from target_module import ShamirSecretSharing

def test_shamir_split_combine():
    s = ShamirSecretSharing()
    shares = s.split(12345, n=5, k=3)
    assert len(shares) == 5
    rec = s.combine(shares[:3])
    assert rec == 12345
