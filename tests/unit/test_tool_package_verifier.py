"""
Unit tests verifying cryptographic package verification and tamper rejection.
"""
import hashlib
import pytest
from sclass.verification.tool_package_verifier import ToolPackageVerifier

def test_valid_package_passes():
    payload = b"console.log('safe payload');"
    digest = hashlib.sha256(payload).hexdigest()
    verifier = ToolPackageVerifier({"tool.js": digest})
    assert verifier.verify_package("tool.js", payload) is True

def test_tampered_package_fails():
    payload = b"console.log('safe payload');"
    tampered = b"console.log('tampered payload');"
    digest = hashlib.sha256(payload).hexdigest()
    verifier = ToolPackageVerifier({"tool.js": digest})
    assert verifier.verify_package("tool.js", tampered) is False
