"""
S-Class EOS V11.2 - Hypothesis Property Verification Test Suite
Tests PropertyVerificationAdapter against reference (passing) and intentionally flawed (failing) implementations.
Verifies exact minimized input counterexample capture, reproducibility metadata, and provenance checksums.
"""

import os
import re
import json
import tempfile
from typing import Dict, List, Tuple
import pytest
from property_verifier import PropertyVerificationAdapter, PropertyEvidenceReceipt


# -----------------------------------------------------------------------------
# 1. SPIFFE Parser Implementations (Reference vs Flawed)
# -----------------------------------------------------------------------------

def reference_spiffe_parser(spiffe_id: str) -> Dict[str, str]:
    """Reference implementation: correctly parses SPIFFE URI."""
    if not spiffe_id.startswith("spiffe://"):
        raise ValueError("Invalid SPIFFE scheme")
    remainder = spiffe_id[len("spiffe://"):]
    parts = remainder.split("/", 1)
    trust_domain = parts[0]
    path = ("/" + parts[1]) if len(parts) > 1 else ""
    return {"scheme": "spiffe", "trust_domain": trust_domain, "path": path}


def flawed_spiffe_parser(spiffe_id: str) -> Dict[str, str]:
    """Flawed implementation: hardcodes incorrect trust domain."""
    return {"scheme": "spiffe", "trust_domain": "hardcoded.domain.org", "path": ""}


# -----------------------------------------------------------------------------
# 2. PHI Sanitizer Implementations (Reference vs Flawed)
# -----------------------------------------------------------------------------

def reference_phi_sanitizer(text: str) -> str:
    """Reference implementation: thoroughly redacts SSNs and Emails."""
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    email_pattern = re.compile(r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+")
    text = ssn_pattern.sub("[REDACTED_SSN]", text)
    text = email_pattern.sub("[REDACTED_EMAIL]", text)
    return text


def flawed_phi_sanitizer(text: str) -> str:
    """Flawed implementation: redacts SSNs but leaks emails."""
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    return ssn_pattern.sub("[REDACTED_SSN]", text)


# -----------------------------------------------------------------------------
# 3. Double-Entry Ledger Implementations (Reference vs Flawed)
# -----------------------------------------------------------------------------

def reference_ledger(entries: List[Tuple[str, str, float]]) -> Dict[str, float]:
    """Reference implementation: perfectly conserves debit/credit balances."""
    balances: Dict[str, float] = {}
    for src, dst, amt in entries:
        amt_f = float(amt)
        balances[src] = balances.get(src, 0.0) - amt_f
        balances[dst] = balances.get(dst, 0.0) + amt_f
    return balances


def flawed_ledger(entries: List[Tuple[str, str, float]]) -> Dict[str, float]:
    """Flawed implementation: skims 5% fee without offsetting account, violating zero-sum conservation."""
    balances: Dict[str, float] = {}
    for src, dst, amt in entries:
        amt_f = float(amt)
        balances[src] = balances.get(src, 0.0) - amt_f
        balances[dst] = balances.get(dst, 0.0) + (amt_f * 0.95)  # 5% leakage
    return balances


# -----------------------------------------------------------------------------
# Test Cases
# -----------------------------------------------------------------------------

def test_spiffe_reference_passes():
    receipt = PropertyVerificationAdapter.verify_spiffe_parser(reference_spiffe_parser, max_examples=40)
    assert receipt.passed is True
    assert receipt.cases_generated >= 40
    assert receipt.falsifying_example is None
    assert len(receipt.provenance_hash) == 64
    assert receipt.target_identifier == "reference_spiffe_parser"


def test_spiffe_flawed_fails_and_captures_counterexample():
    receipt = PropertyVerificationAdapter.verify_spiffe_parser(flawed_spiffe_parser, max_examples=40)
    assert receipt.passed is False
    assert receipt.shrunk_counterexample is not None
    assert isinstance(receipt.shrunk_counterexample, dict)
    assert "input_spiffe_id" in receipt.shrunk_counterexample
    assert "Trust domain mismatch" in str(receipt.error_message)
    assert len(receipt.provenance_hash) == 64


def test_phi_sanitizer_reference_passes():
    receipt = PropertyVerificationAdapter.verify_phi_sanitizer(reference_phi_sanitizer, max_examples=40)
    assert receipt.passed is True
    assert receipt.cases_generated >= 40
    assert receipt.falsifying_example is None
    assert len(receipt.provenance_hash) == 64


def test_phi_sanitizer_flawed_fails_and_captures_counterexample():
    receipt = PropertyVerificationAdapter.verify_phi_sanitizer(flawed_phi_sanitizer, max_examples=40)
    assert receipt.passed is False
    assert receipt.shrunk_counterexample is not None
    assert isinstance(receipt.shrunk_counterexample, dict)
    assert "email" in receipt.shrunk_counterexample
    assert "Email leak detected" in str(receipt.error_message)


def test_ledger_reference_passes():
    receipt = PropertyVerificationAdapter.verify_double_entry_ledger(reference_ledger, max_examples=40)
    assert receipt.passed is True
    assert receipt.cases_generated >= 40
    assert receipt.falsifying_example is None


def test_ledger_flawed_fails_and_captures_counterexample():
    receipt = PropertyVerificationAdapter.verify_double_entry_ledger(flawed_ledger, max_examples=40)
    assert receipt.passed is False
    assert receipt.shrunk_counterexample is not None
    assert isinstance(receipt.shrunk_counterexample, dict)
    assert "transactions" in receipt.shrunk_counterexample
    assert "Double-entry ledger invariant violated" in str(receipt.error_message)


def test_property_evidence_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        receipt = PropertyVerificationAdapter.verify_spiffe_parser(reference_spiffe_parser, max_examples=20)
        evidence_file = PropertyVerificationAdapter.save_evidence_receipt(receipt, tmpdir)
        assert os.path.exists(evidence_file)
        with open(evidence_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["obligation_id"] == "OBL-SEC-SPIFFE-001"
        assert data["provenance_hash"] == receipt.provenance_hash


def test_property_common_ir_conversion():
    receipt = PropertyVerificationAdapter.verify_spiffe_parser(reference_spiffe_parser, max_examples=20)
    ir = receipt.to_ir()
    assert ir.obligation_id == receipt.obligation_id
    assert ir.passed is True
    assert ir.engine_name == "Hypothesis"
    assert ir.provenance_hash == receipt.provenance_hash
    assert ir.execution_metadata["cases_generated"] >= 20

    flawed_receipt = PropertyVerificationAdapter.verify_spiffe_parser(flawed_spiffe_parser, max_examples=20)
    flawed_ir = flawed_receipt.to_ir()
    assert flawed_ir.passed is False
    assert len(flawed_ir.reproducible_cases) == 1
    assert len(flawed_ir.diagnostics) == 1
