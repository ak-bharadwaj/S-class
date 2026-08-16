"""
S-Class EOS V11.2 - Static Analysis & Type Verification Provider Test Suite
Verifies Ruff linter integration, Python type audit receipts, and evidence hash verification.
"""

import os
import json
import tempfile
import pytest
from static_analysis_provider import StaticAnalysisProvider, StaticAnalysisEvidenceReceipt
from type_verification_provider import TypeVerificationProvider, TypeEvidenceReceipt


def test_ruff_static_analysis_provider_pass():
    # Run on clean file (e.g. sclass_schemas.py)
    target_file = os.path.abspath("sclass_schemas.py")
    receipt = StaticAnalysisProvider.run_ruff_audit(target_file, "OBL-STATIC-SCHEMA-001", max_violations_allowed=10)
    assert receipt.obligation_id == "OBL-STATIC-SCHEMA-001"
    assert receipt.linter == "Ruff"
    assert len(receipt.evidence_hash) == 64
    assert receipt.environment["engine"] == "Ruff Static Analysis Provider V11.2"


def test_type_verification_provider_pass():
    target_file = os.path.abspath("sclass_schemas.py")
    receipt = TypeVerificationProvider.run_type_check(target_file, "OBL-TYPE-SCHEMA-001")
    assert receipt.passed is True
    assert receipt.obligation_id == "OBL-TYPE-SCHEMA-001"
    assert receipt.diagnostics_count == 0
    assert len(receipt.evidence_hash) == 64


def test_static_and_type_evidence_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        target_file = os.path.abspath("sclass_schemas.py")
        static_receipt = StaticAnalysisProvider.run_ruff_audit(target_file)
        static_file = StaticAnalysisProvider.save_evidence_receipt(static_receipt, tmpdir)
        assert os.path.exists(static_file)
        
        type_receipt = TypeVerificationProvider.run_type_check(target_file)
        type_file = TypeVerificationProvider.save_evidence_receipt(type_receipt, tmpdir)
        assert os.path.exists(type_file)
