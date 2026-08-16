"""
S-Class EOS V11.2 - Hypothesis Property Verification Test Suite
Verifies SPIFFE, PHI sanitizer, and double-entry ledger property testing and evidence generation.
"""

import os
import json
import tempfile
import pytest
from property_verifier import PropertyVerificationAdapter, PropertyEvidenceReceipt


def test_spiffe_invariant_property_verification():
    receipt = PropertyVerificationAdapter.run_spiffe_invariant_check(max_examples=50)
    assert receipt.passed is True
    assert receipt.obligation_id == "OBL-SEC-SPIFFE-001"
    assert receipt.cases_generated >= 50
    assert len(receipt.evidence_hash) == 64
    assert receipt.environment["engine"] == "Hypothesis Property Verification Adapter V11.2"


def test_phi_sanitizer_invariant_property_verification():
    receipt = PropertyVerificationAdapter.run_phi_sanitizer_invariant_check(max_examples=50)
    assert receipt.passed is True
    assert receipt.obligation_id == "OBL-PRIVACY-PHI-002"
    assert receipt.cases_generated >= 50
    assert len(receipt.evidence_hash) == 64


def test_double_entry_ledger_invariant_property_verification():
    receipt = PropertyVerificationAdapter.run_double_entry_ledger_invariant_check(max_examples=50)
    assert receipt.passed is True
    assert receipt.obligation_id == "OBL-FIN-LEDGER-003"
    assert receipt.cases_generated >= 50
    assert len(receipt.evidence_hash) == 64


def test_property_evidence_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        receipt = PropertyVerificationAdapter.run_spiffe_invariant_check(max_examples=20)
        evidence_file = PropertyVerificationAdapter.save_evidence_receipt(receipt, tmpdir)
        assert os.path.exists(evidence_file)
        with open(evidence_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["obligation_id"] == "OBL-SEC-SPIFFE-001"
        assert data["evidence_hash"] == receipt.evidence_hash
