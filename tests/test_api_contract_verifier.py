"""
S-Class EOS V11.2 - Schemathesis API Contract Verification Test Suite
Verifies OpenAPI contract parsing, fuzzing campaigns, and cryptographic evidence generation.
"""

import os
import json
import tempfile
import pytest
from api_contract_verifier import APIContractVerificationAdapter, APIEvidenceReceipt


SAMPLE_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "S-Class Payment & User Gateway",
        "version": "1.0.0"
    },
    "paths": {
        "/users": {
            "get": {
                "summary": "Get list of users",
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "name": {"type": "string"}
                                        },
                                        "required": ["id", "name"]
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/payments": {
            "post": {
                "summary": "Process payment transaction",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "amount": {"type": "number", "minimum": 0.01},
                                    "currency": {"type": "string", "enum": ["USD", "EUR", "INR"]}
                                },
                                "required": ["amount", "currency"]
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": "Transaction created"
                    }
                }
            }
        }
    }
}


def test_openapi_contract_verification_pass():
    receipt = APIContractVerificationAdapter.run_openapi_contract_check(SAMPLE_OPENAPI_SPEC, "OBL-API-PAYMENT-001")
    assert receipt.passed is True
    assert receipt.obligation_id == "OBL-API-PAYMENT-001"
    assert receipt.endpoints_tested == 2
    assert receipt.tests_executed >= 2
    assert len(receipt.evidence_hash) == 64
    assert receipt.environment["engine"] == "Schemathesis API Contract Verification Adapter V11.2"


def test_openapi_contract_verification_invalid_spec():
    invalid_spec = {"openapi": "3.0.0", "info": {"title": "Broken API"}}
    receipt = APIContractVerificationAdapter.run_openapi_contract_check(invalid_spec, "OBL-API-BROKEN-002")
    assert receipt.obligation_id == "OBL-API-BROKEN-002"
    assert len(receipt.evidence_hash) == 64


def test_api_evidence_receipt_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        receipt = APIContractVerificationAdapter.run_openapi_contract_check(SAMPLE_OPENAPI_SPEC)
        evidence_file = APIContractVerificationAdapter.save_evidence_receipt(receipt, tmpdir)
        assert os.path.exists(evidence_file)
        with open(evidence_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["target_api"] == "S-Class Payment & User Gateway"
        assert data["evidence_hash"] == receipt.evidence_hash
