"""
Integration test corpus for S-Class Schemathesis Provider Boundary.
Tests 5 distinct scenarios:
1. Clean conforming API -> TARGET_CLEAN
2. Contract-violating API -> TARGET_CONTRACT_VIOLATED
3. HTTP 5xx Server Error endpoint -> TARGET_CONTRACT_VIOLATED (ServerError)
4. Malformed OpenAPI schema -> INPUT_INVALID
5. Unreachable live target -> TARGET_CONTRACT_VIOLATED / TOOL_EXECUTION_FAILED (Fail-Closed)
"""

import json
import pytest
from wsgiref.simple_server import make_server
import threading

from benchmark.providers.schemathesis.adapter import SchemathesisProviderAdapter
from benchmark.providers.schemathesis.models import ProviderStatus


# -----------------------------------------------------------------------------
# 1. Clean Conforming API
# -----------------------------------------------------------------------------
CLEAN_CORPUS_SCHEMA = {
    "openapi": "3.0.0",
    "info": {"title": "Health Check Service", "version": "1.0.0"},
    "paths": {
        "/health": {
            "get": {
                "summary": "Health status",
                "responses": {
                    "200": {
                        "description": "System health payload",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "uptime_sec": {"type": "integer"}
                                    },
                                    "required": ["status", "uptime_sec"]
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


def clean_health_app(environ, start_response):
    path = environ.get("PATH_INFO", "")
    if path == "/health":
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps({"status": "operational", "uptime_sec": 3600}).encode("utf-8")]
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]


def test_corpus_scenario_1_clean_api():
    """Scenario 1: Fully conforming API returns valid payload -> TARGET_CLEAN."""
    adapter = SchemathesisProviderAdapter(source_sha="corpus_test_sha")
    result = adapter.verify_api_contract(
        schema_dict=CLEAN_CORPUS_SCHEMA,
        target_app=clean_health_app,
        obligation_id="CORPUS-01-CLEAN",
        max_examples_per_operation=5
    )

    assert result.status == ProviderStatus.TARGET_CLEAN
    assert result.passed is True
    assert len(result.violations) == 0
    assert result.stats.endpoints_tested == 1
    assert result.stats.checks_executed >= 5


# -----------------------------------------------------------------------------
# 2. Contract-Violating API
# -----------------------------------------------------------------------------
VIOLATION_CORPUS_SCHEMA = {
    "openapi": "3.0.0",
    "info": {"title": "Inventory Service", "version": "1.0.0"},
    "paths": {
        "/inventory": {
            "get": {
                "summary": "List inventory",
                "responses": {
                    "200": {
                        "description": "Inventory list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "sku": {"type": "string"},
                                            "qty": {"type": "integer"}
                                        },
                                        "required": ["sku", "qty"]
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


def violating_inventory_app(environ, start_response):
    path = environ.get("PATH_INFO", "")
    if path == "/inventory":
        start_response("200 OK", [("Content-Type", "application/json")])
        # Returns string qty instead of integer qty -> schema violation!
        return [json.dumps([{"sku": "SKU-100", "qty": "ten_units"}]).encode("utf-8")]
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]


def test_corpus_scenario_2_schema_violation():
    """Scenario 2: API returns response violating type constraints -> TARGET_CONTRACT_VIOLATED."""
    adapter = SchemathesisProviderAdapter(source_sha="corpus_test_sha")
    result = adapter.verify_api_contract(
        schema_dict=VIOLATION_CORPUS_SCHEMA,
        target_app=violating_inventory_app,
        obligation_id="CORPUS-02-VIOLATION",
        max_examples_per_operation=3
    )

    assert result.status == ProviderStatus.TARGET_CONTRACT_VIOLATED
    assert result.passed is False
    assert len(result.violations) > 0
    assert result.violations[0].path == "/inventory"
    assert result.violations[0].status_code == 200


# -----------------------------------------------------------------------------
# 3. HTTP 5xx Server Error Endpoint
# -----------------------------------------------------------------------------
def server_error_app(environ, start_response):
    start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
    return [b"Critical Database Deadlock"]


def test_corpus_scenario_3_server_error_5xx():
    """Scenario 3: Endpoint crashes with HTTP 500 -> TARGET_CONTRACT_VIOLATED (ServerError)."""
    adapter = SchemathesisProviderAdapter(source_sha="corpus_test_sha")
    result = adapter.verify_api_contract(
        schema_dict=CLEAN_CORPUS_SCHEMA,
        target_app=server_error_app,
        obligation_id="CORPUS-03-SERVER-ERROR",
        max_examples_per_operation=3
    )

    assert result.status == ProviderStatus.TARGET_CONTRACT_VIOLATED
    assert result.passed is False
    assert len(result.violations) > 0
    assert any(v.error_type == "ServerError" or v.status_code == 500 for v in result.violations)


# -----------------------------------------------------------------------------
# 4. Malformed Schema Dictionary
# -----------------------------------------------------------------------------
def test_corpus_scenario_4_malformed_schema():
    """Scenario 4: Malformed or unparseable schema dictionary -> INPUT_INVALID."""
    adapter = SchemathesisProviderAdapter(source_sha="corpus_test_sha")

    # Missing paths
    res_no_paths = adapter.verify_api_contract(schema_dict={"openapi": "3.0.0", "info": {}})
    assert res_no_paths.status == ProviderStatus.INPUT_INVALID
    assert res_no_paths.passed is False

    # Invalid paths type
    res_bad_paths = adapter.verify_api_contract(schema_dict={"openapi": "3.0.0", "paths": "not_a_dict"})
    assert res_bad_paths.status == ProviderStatus.INPUT_INVALID
    assert res_bad_paths.passed is False


# -----------------------------------------------------------------------------
# 5. Unreachable Target Base URL
# -----------------------------------------------------------------------------
def test_corpus_scenario_5_unreachable_target():
    """Scenario 5: Live base URL pointing to closed/unreachable port -> TARGET_CONTRACT_VIOLATED."""
    adapter = SchemathesisProviderAdapter(source_sha="corpus_test_sha")
    result = adapter.verify_api_contract(
        schema_dict=CLEAN_CORPUS_SCHEMA,
        base_url="http://127.0.0.1:59999",
        obligation_id="CORPUS-05-UNREACHABLE",
        max_examples_per_operation=2
    )

    assert result.status in [ProviderStatus.TARGET_CONTRACT_VIOLATED, ProviderStatus.TOOL_EXECUTION_FAILED]
    assert result.passed is False
    assert len(result.violations) > 0
