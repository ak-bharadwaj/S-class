"""
S-Class EOS V11.2 - Schemathesis API Contract Verification Test Suite
Tests APIContractVerificationAdapter against live reference (passing) and intentionally flawed (failing) HTTP services.
"""

import os
import json
import threading
import tempfile
from wsgiref.simple_server import make_server
import pytest
from api_contract_verifier import APIContractVerificationAdapter, APIEvidenceReceipt


SAMPLE_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Order Processing Service",
        "version": "1.0.0"
    },
    "paths": {
        "/orders": {
            "get": {
                "summary": "List orders",
                "responses": {
                    "200": {
                        "description": "Successful order list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "count": {"type": "integer"}
                                    },
                                    "required": ["status", "count"]
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


def reference_wsgi_app(environ, start_response):
    """Reference API: Conforms strictly to OpenAPI schema."""
    start_response("200 OK", [("Content-Type", "application/json")])
    payload = json.dumps({"status": "active", "count": 42}).encode("utf-8")
    return [payload]


def flawed_wsgi_app(environ, start_response):
    """Flawed API: Violates schema by returning string count and missing required status field."""
    start_response("200 OK", [("Content-Type", "application/json")])
    payload = json.dumps({"broken_field": "invalid", "count": "not_an_integer"}).encode("utf-8")
    return [payload]


def server_error_wsgi_app(environ, start_response):
    """Flawed API: Crashes with HTTP 500."""
    start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
    return [b"Database Connection Pool Exhausted"]


def test_live_api_reference_passes():
    """Verifies that compliant reference API passes Schemathesis live execution campaign."""
    server = make_server("127.0.0.1", 0, reference_wsgi_app)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{port}"
    try:
        receipt = APIContractVerificationAdapter.run_api_execution_campaign(
            SAMPLE_OPENAPI_SPEC,
            base_url=base_url,
            max_cases_per_operation=3
        )
        assert receipt.passed is True
        assert receipt.failures_detected == 0
        assert receipt.tests_executed >= 3
        assert len(receipt.provenance_hash) == 64
        assert receipt.target_api == "Order Processing Service"
    finally:
        server.shutdown()


def test_live_api_flawed_schema_fails():
    """Verifies that schema-violating API fails and records failure details."""
    server = make_server("127.0.0.1", 0, flawed_wsgi_app)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{port}"
    try:
        receipt = APIContractVerificationAdapter.run_api_execution_campaign(
            SAMPLE_OPENAPI_SPEC,
            base_url=base_url,
            max_cases_per_operation=3
        )
        assert receipt.passed is False
        assert receipt.failures_detected > 0
        assert any("Schema Violation" in f or "status" in f for f in receipt.failure_details)
        assert len(receipt.provenance_hash) == 64
    finally:
        server.shutdown()


def test_live_api_server_error_fails():
    """Verifies that HTTP 500 server errors fail and are captured in evidence receipt."""
    server = make_server("127.0.0.1", 0, server_error_wsgi_app)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{port}"
    try:
        receipt = APIContractVerificationAdapter.run_api_execution_campaign(
            SAMPLE_OPENAPI_SPEC,
            base_url=base_url,
            max_cases_per_operation=3
        )
        assert receipt.passed is False
        assert receipt.failures_detected > 0
        assert any("Server Error" in f or "500" in f for f in receipt.failure_details)
    finally:
        server.shutdown()


def test_openapi_static_contract_check():
    receipt = APIContractVerificationAdapter.run_openapi_contract_check(SAMPLE_OPENAPI_SPEC)
    assert receipt.passed is True
    assert receipt.endpoints_tested == 1
    assert receipt.tests_executed == 1


def test_api_evidence_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        receipt = APIContractVerificationAdapter.run_openapi_contract_check(SAMPLE_OPENAPI_SPEC)
        evidence_file = APIContractVerificationAdapter.save_evidence_receipt(receipt, tmpdir)
        assert os.path.exists(evidence_file)
        with open(evidence_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["target_api"] == "Order Processing Service"
        assert data["provenance_hash"] == receipt.provenance_hash
