import pytest
import target_module

def test_oauth2_token_exchange():
    res = target_module.exchange_token("valid_sub_tok", "urn:ietf:params:oauth:token-type:access_token", "api.payment.service")
    assert res["access_token"].startswith("exchanged_tok_")
    
    with pytest.raises(PermissionError):
        target_module.exchange_token("valid_sub_tok", "urn:ietf:params:oauth:token-type:access_token", "unauthorized.aud")
        
    with pytest.raises(PermissionError):
        target_module.exchange_token("invalid_tok", "urn:ietf:params:oauth:token-type:access_token", "api.payment.service")
