from target_module import ZKProofVerifier

def test_zk():
    v = ZKProofVerifier()
    proof = v.generate_proof('secret123', 'key1')
    assert v.verify_proof(proof, 'key1') is True
    assert v.verify_proof(proof, 'wrong') is False
