from target_module import OAuth2AudienceGuard, InvalidAudienceError
import pytest

def test_aud_adversarial_probes():
    g = OAuth2AudienceGuard('https://api.company.com')
    # Probe 1: Wildcard audience attack
    with pytest.raises(InvalidAudienceError):
        g.validate_token_claims({'aud': '*', 'sub': 'user1'})
    # Probe 2: Missing aud claim
    with pytest.raises(InvalidAudienceError):
        g.validate_token_claims({'sub': 'user1'})
