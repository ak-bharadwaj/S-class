from target_module import ZKProofVerifier

def test_zk_proof_lifecycle():
    v = ZKProofVerifier()
    proof = v.generate_proof('my_secret_key', 'pub_key_123')
    assert 'commitment' in proof
    assert v.verify_proof(proof, 'pub_key_123') is True
    assert v.verify_proof(proof, 'wrong_key') is False
