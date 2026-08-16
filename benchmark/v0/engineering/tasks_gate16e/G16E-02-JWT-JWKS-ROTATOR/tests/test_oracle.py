from target_module import JWKSRotator

def test_jwks_rotation():
    r = JWKSRotator()
    kid = r.rotate_keys()
    tok = r.sign_token({'sub': 'user123'})
    assert r.verify_token(tok)['sub'] == 'user123'
    assert 'keys' in r.get_jwks()
