"""Test verifier hierarchy contracts."""
import pytest
from sclass.contracts.verifier_contracts import VerifierIdentity, IndependentAssessment

def test_verifier_identity_frozen():
    v = VerifierIdentity(verifier_id="pytest-v1", trust_tier="V3", executable_sha256="sha-abc", trusted=True)
    assert v.trusted is True
    assert v.trust_tier == "V3"

def test_independent_assessment():
    v = VerifierIdentity(verifier_id="pytest-v1", trust_tier="V3", executable_sha256="sha-abc", trusted=True)
    assess = IndependentAssessment(claim_id="c-01", verifier=v, verdict="PASS", evidence_ids=["ev-1"], details={})
    assert assess.verdict == "PASS"
