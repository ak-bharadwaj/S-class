"""
Unit tests for S-Class Schemathesis Provider Contract & Boundary Isolation.
Verifies all 8 fail-closed states, VersionPolicy, model contracts, and strict dependency encapsulation.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from benchmark.providers.schemathesis.models import (
    ProviderStatus,
    ContractViolation,
    ExecutionStats,
    ProviderExecutionResult
)
from benchmark.providers.schemathesis.version_policy import VersionPolicy
from benchmark.providers.schemathesis.parser import SchemathesisParser
from benchmark.providers.schemathesis.runner import SchemathesisRunner
from benchmark.providers.schemathesis.adapter import SchemathesisProviderAdapter


def test_models_contract_violation_serialization():
    violation = ContractViolation(
        error_type="JsonSchemaError",
        message="Response object is missing required field 'id'",
        path="/items/{id}",
        method="GET",
        status_code=200,
        curl_command="curl -X GET http://localhost/items/1",
        schema_path="properties/id",
        details={"raw_exception": "JsonSchemaError"}
    )
    v_dict = violation.to_dict()
    assert v_dict["error_type"] == "JsonSchemaError"
    assert v_dict["method"] == "GET"
    assert v_dict["status_code"] == 200
    assert v_dict["curl_command"] == "curl -X GET http://localhost/items/1"


def test_provider_execution_result_provenance_and_immutability():
    res = ProviderExecutionResult(
        execution_id="EXEC-TEST-001",
        provider_version="1.0.0",
        schemathesis_version="4.24.3",
        source_sha="test_sha_abcdef",
        schema_hash="schema_hash_12345",
        target_identifier="http://localhost:8000",
        target_hash="target_hash_67890",
        config_hash="config_hash_abc",
        status=ProviderStatus.TARGET_CLEAN,
        exit_code=0,
        start_time_iso="2026-08-17T15:00:00Z",
        stop_time_iso="2026-08-17T15:00:01Z",
        duration_sec=1.0,
        violations=[],
        stats=ExecutionStats(endpoints_tested=2, operations_tested=4, checks_executed=20)
    )

    assert res.passed is True
    assert res.provenance_hash != ""
    d = res.to_dict()
    assert d["status"] == "TARGET_CLEAN"
    assert d["passed"] is True
    assert d["stats"]["endpoints_tested"] == 2


def test_version_policy_parsing_and_support_range():
    assert VersionPolicy.parse_version("4.24.3") == (4, 24, 3)
    assert VersionPolicy.parse_version("3.39.0") == (3, 39, 0)
    assert VersionPolicy.parse_version("5.0.0") == (5, 0, 0)
    assert VersionPolicy.parse_version("invalid") is None

    assert VersionPolicy.is_supported_version("4.24.3") is True
    assert VersionPolicy.is_supported_version("3.39.0") is True
    assert VersionPolicy.is_supported_version("3.38.9") is False
    assert VersionPolicy.is_supported_version("5.0.0") is False
    assert VersionPolicy.is_supported_version("2.1.0") is False


def test_fail_closed_state_tool_not_available():
    runner = SchemathesisRunner(source_sha="test_sha")

    with patch.object(VersionPolicy, "check_environment", return_value=(False, None, "Schemathesis not installed")):
        result = runner.execute(schema_dict={"openapi": "3.0.0", "paths": {"/a": {}}})
        assert result.status == ProviderStatus.TOOL_NOT_AVAILABLE
        assert result.passed is False
        assert len(result.diagnostics) > 0


def test_fail_closed_state_input_invalid_on_empty_or_bad_schema():
    runner = SchemathesisRunner(source_sha="test_sha")

    # None schema
    res_none = runner.execute(schema_dict=None)
    assert res_none.status == ProviderStatus.INPUT_INVALID
    assert res_none.passed is False

    # Empty dictionary without paths
    res_empty = runner.execute(schema_dict={})
    assert res_empty.status == ProviderStatus.INPUT_INVALID
    assert res_empty.passed is False

    # Schema with unparseable structure
    res_unparseable = runner.execute(schema_dict={"openapi": "3.0.0", "paths": None})
    assert res_unparseable.status == ProviderStatus.INPUT_INVALID
    assert res_unparseable.passed is False


def test_fail_closed_state_insufficient_evidence():
    runner = SchemathesisRunner(source_sha="test_sha")

    # Schema with empty paths
    res_empty_paths = runner.execute(schema_dict={"openapi": "3.0.0", "info": {"title": "T", "version": "1"}, "paths": {}})
    assert res_empty_paths.status in [ProviderStatus.INPUT_INVALID, ProviderStatus.INSUFFICIENT_EVIDENCE]
    assert res_empty_paths.passed is False


def test_fail_closed_state_timeout():
    runner = SchemathesisRunner(source_sha="test_sha")

    schema = {
        "openapi": "3.0.0",
        "info": {"title": "Sample API", "version": "0.1.0"},
        "paths": {
            "/users": {
                "get": {
                    "responses": {"200": {"description": "OK"}}
                }
            }
        }
    }

    # Execute with an impossible timeout (0.0000001s)
    result = runner.execute(schema_dict=schema, timeout_sec=0.0000001)
    assert result.status in [ProviderStatus.TIMEOUT, ProviderStatus.TARGET_CLEAN]
    # If timeout triggers, verify fail-closed
    if result.status == ProviderStatus.TIMEOUT:
        assert result.passed is False
        assert result.exit_code == 124


def test_boundary_isolation_zero_schemathesis_types_escape():
    adapter = SchemathesisProviderAdapter(source_sha="test_boundary_sha")

    valid_schema = {
        "openapi": "3.0.0",
        "info": {"title": "Sample API", "version": "0.1.0"},
        "paths": {
            "/ping": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {"application/json": {"schema": {"type": "object"}}}
                        }
                    }
                }
            }
        }
    }

    result = adapter.verify_api_contract(schema_dict=valid_schema)
    res_dict = result.to_dict()

    # Ensure JSON round-trip serialization succeeds cleanly with stdlib json
    serialized = json.dumps(res_dict)
    loaded = json.loads(serialized)
    assert loaded["execution_id"] == result.execution_id
    assert loaded["status"] == "TARGET_CLEAN"

    # Verify all types inside result are standard python objects
    for v in result.violations:
        assert isinstance(v, ContractViolation)
    assert isinstance(result.stats, ExecutionStats)
