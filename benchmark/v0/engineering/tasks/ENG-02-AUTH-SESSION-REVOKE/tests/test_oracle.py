import pytest
import target_module

def test_session_revocation():
    target_module.active_tokens.clear()
    target_module.blacklist.clear()
    t1 = target_module.issue_token('user_1')
    assert target_module.validate_token(t1) is True
    target_module.reset_password('user_1', 'new_secure_pass')
    assert target_module.validate_token(t1) is False
