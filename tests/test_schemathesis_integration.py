"""
Integration tests executing the Schemathesis provider boundary against local OpenAPI services.
Verifies real isolated Schemathesis subprocess execution, WSGI app importing, and response validation.
"""

import json
import pytest

from benchmark.providers.schemathesis.adapter import SchemathesisProviderAdapter
from benchmark.providers.schemathesis.models import ProviderStatus


def clean_wsgi_app(environ, start_response):
    """Compliant WSGI service returning valid array of objects matching schema."""
    path = environ.get("PATH_INFO", "")
    if path == "/users":
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps([{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]).encode("utf-8")]
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]


def flawed_wsgi_app(environ, start_response):
    """Flawed WSGI service violating OpenAPI contract by returning string ID and non-array object."""
    path = environ.get("PATH_INFO", "")
    if path == "/users":
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps({"error": "unauthorized_leak", "id": "not_an_int"}).encode("utf-8")]
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]


SAMPLE_INTEGRATION_SCHEMA = {
    "openapi": "3.0.0",
    "info": {"title": "Users Service", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {
                "summary": "List all users",
                "responses": {
                    "200": {
                        "description": "A list of users",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
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
        }
    }
}


def test_schemathesis_integration_clean_local_api():
    """Executes Schemathesis in an isolated child process against a compliant WSGI endpoint."""
    adapter = SchemathesisProviderAdapter(source_sha="integration_test_sha")
    result = adapter.verify_api_contract(
        schema_dict=SAMPLE_INTEGRATION_SCHEMA,
        target_app=clean_wsgi_app,
        obligation_id="OBL-USERS-CLEAN",
        max_examples_per_operation=5
    )

    assert result.status == ProviderStatus.TARGET_CLEAN
    assert result.passed is True
    assert len(result.violations) == 0
    assert result.stats.endpoints_tested == 1
    assert result.stats.operations_tested == 1
    assert result.stats.checks_executed >= 5


def test_schemathesis_integration_contract_violating_api():
    """Executes Schemathesis in an isolated child process against a contract-violating WSGI endpoint."""
    adapter = SchemathesisProviderAdapter(source_sha="integration_test_sha")
    result = adapter.verify_api_contract(
        schema_dict=SAMPLE_INTEGRATION_SCHEMA,
        target_app=flawed_wsgi_app,
        obligation_id="OBL-USERS-FLAWED",
        max_examples_per_operation=3
    )

    assert result.status == ProviderStatus.TARGET_CONTRACT_VIOLATED
    assert result.passed is False
    assert len(result.violations) > 0
    assert result.violations[0].path == "/users"
    assert result.violations[0].method == "GET"
    assert result.violations[0].status_code == 200
