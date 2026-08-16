from target_module import JWKSRotator

def test_jwks_rotation_and_verification():
    r = JWKSRotator()
    kid1 = r.rotate_keys()
    t1 = r.sign_token({'user': 'alice'})
    assert r.verify_token(t1)['user'] == 'alice'

def test_jwks_export():
    r = JWKSRotator()
    r.rotate_keys()
    jwks = r.get_jwks()
    assert 'keys' in jwks
    assert len(jwks['keys']) >= 1
