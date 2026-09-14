"""
Tests for S-Class Secret Scanner & Credential Redaction Engine.
"""

import pytest
from sclass.control.secret_scanner import SecretScanner, HIGH_CONFIDENCE_PATTERNS, POSSIBLE_SECRET_PATTERNS


def test_secret_scanner_clean_content():
    content = "def hello_world():\n    return 'no secrets here'"
    has_high_conf, redacted, findings = SecretScanner.scan(content)
    assert has_high_conf is False
    assert redacted == content
    assert len(findings) == 0


def test_secret_scanner_private_key():
    content = """
    -----BEGIN RSA PRIVATE KEY-----
    MIIEowIBAAKCAQEA0m...
    -----END RSA PRIVATE KEY-----
    """
    has_high_conf, redacted, findings = SecretScanner.scan(content)
    assert has_high_conf is True
    assert len(findings) >= 1
    assert findings[0]["type"] == "private_key"
    assert findings[0]["confidence"] == "HIGH_CONFIDENCE"
    assert "-----BEGIN RSA PRIVATE KEY-----" not in redacted
    assert "[REDACTED:private_key:" in redacted


def test_secret_scanner_aws_and_google_keys():
    content = "aws_key = 'AKIAIOSFODNN7EXAMPLE' and gkey = 'AIzaSyA_fake_google_api_key_12345678901'"
    has_high_conf, redacted, findings = SecretScanner.scan(content)
    assert has_high_conf is True
    types = [f["type"] for f in findings]
    assert "aws_access_key" in types
    assert "google_api_key" in types
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "AIzaSyA_fake_google_api_key_12345678901" not in redacted


def test_secret_scanner_possible_secret_patterns():
    content = "api_key = 'some_random_secret_token_value_123'"
    has_high_conf, redacted, findings = SecretScanner.scan(content)
    assert has_high_conf is False
    assert any(f["type"] == "credential_assignment" for f in findings)
    assert any(f["confidence"] == "POSSIBLE_SECRET" for f in findings)


def test_secret_scanner_redact_convenience_method():
    content = "Token: ghp_123456789012345678901234567890123456"
    redacted = SecretScanner.redact(content)
    assert "ghp_" not in redacted
    assert "[REDACTED:api_token:" in redacted


def test_secret_scanner_empty_and_non_string():
    assert SecretScanner.scan("")[0] is False
    assert SecretScanner.scan(None)[0] is False
    assert SecretScanner.redact("") == ""
