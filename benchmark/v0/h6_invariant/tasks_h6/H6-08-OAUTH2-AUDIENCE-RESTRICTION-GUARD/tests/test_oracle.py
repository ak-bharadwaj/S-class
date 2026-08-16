from target_module import OAuth2AudienceGuard, InvalidAudienceError
import pytest

def test_aud_guard():
    g = OAuth2AudienceGuard('https://api.company.com')
    assert g.validate_token_claims({'aud': 'https://api.company.com', 'sub': 'user1'}) is True
    with pytest.raises(InvalidAudienceError):
        g.validate_token_claims({'aud': 'https://attacker.com', 'sub': 'user1'})
