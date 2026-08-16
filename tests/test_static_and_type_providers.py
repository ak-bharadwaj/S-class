"""
S-Class EOS V11.2 - Static & Type Verification Test Suite
Tests StaticAnalysisProvider and TypeVerificationProvider on reference (passing) and flawed (failing) files.
"""

import os
import json
import tempfile
import pytest
from static_analysis_provider import StaticAnalysisProvider, StaticAnalysisEvidenceReceipt
from type_verification_provider import TypeVerificationProvider, TypeEvidenceReceipt


CLEAN_PYTHON_CODE = """
def calculate_total(price: float, tax_rate: float) -> float:
    return price * (1.0 + tax_rate)
"""

SYNTAX_ERROR_PYTHON_CODE = """
def broken_function(:
    return 42
"""

FLAWED_UNUSED_IMPORT_CODE = """
import os
import sys

def hello():
    return "world"
"""


def test_type_verification_reference_passes():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(CLEAN_PYTHON_CODE)
        f_name = f.name

    try:
        receipt = TypeVerificationProvider.run_type_check(f_name)
        assert receipt.passed is True
        assert receipt.diagnostics_count == 0
        assert len(receipt.provenance_hash) == 64
    finally:
        if os.path.exists(f_name):
            os.unlink(f_name)


def test_type_verification_flawed_fails():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(SYNTAX_ERROR_PYTHON_CODE)
        f_name = f.name

    try:
        receipt = TypeVerificationProvider.run_type_check(f_name)
        assert receipt.passed is False
        assert receipt.diagnostics_count > 0
        assert any("invalid syntax" in d.get("message", "").lower() or "syntax" in d.get("message", "").lower() for d in receipt.diagnostics)
    finally:
        if os.path.exists(f_name):
            os.unlink(f_name)


def test_static_analysis_reference_passes():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(CLEAN_PYTHON_CODE)
        f_name = f.name

    try:
        receipt = StaticAnalysisProvider.run_ruff_audit(f_name)
        assert receipt.passed is True
        assert receipt.violations_count == 0
        assert len(receipt.provenance_hash) == 64
    finally:
        if os.path.exists(f_name):
            os.unlink(f_name)


def test_static_analysis_flawed_detects_violations():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(FLAWED_UNUSED_IMPORT_CODE)
        f_name = f.name

    try:
        receipt = StaticAnalysisProvider.run_ruff_audit(f_name, max_violations_allowed=0)
        # Unused imports should trigger violations or exit code != 0
        assert receipt.violations_count >= 1 or receipt.exit_code != 0
        assert len(receipt.provenance_hash) == 64
    finally:
        if os.path.exists(f_name):
            os.unlink(f_name)


def test_persistence_and_provenance():
    with tempfile.TemporaryDirectory() as tmpdir:
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(CLEAN_PYTHON_CODE)
            f_name = f.name

        try:
            receipt = StaticAnalysisProvider.run_ruff_audit(f_name)
            p = StaticAnalysisProvider.save_evidence_receipt(receipt, tmpdir)
            assert os.path.exists(p)
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["obligation_id"] == "OBL-STATIC-RUFF-001"
            assert data["provenance_hash"] == receipt.provenance_hash
        finally:
            if os.path.exists(f_name):
                os.unlink(f_name)
