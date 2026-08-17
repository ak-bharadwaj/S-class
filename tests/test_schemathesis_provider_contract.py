"""
Unit tests for S-Class Schemathesis Provider Contract & Dependency Boundary Isolation.
Verifies all 8 fail-closed states, VersionPolicy, process crashes, hard timeouts, malformed output, and strict provenance.
"""

import json
import subprocess
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


# -----------------------------------------------------------------------------
# Dependency-Isolation Test Cases
# -----------------------------------------------------------------------------

def test_isolation_schemathesis_missing():
    """Verifies that missing Schemathesis package transitions to TOOL_NOT_AVAILABLE."""
    runner = SchemathesisRunner(source_sha="test_sha")
    with patch.object(VersionPolicy, "get_installed_version", return_value=None):
        result = runner.execute(schema_dict={"openapi": "3.0.0", "paths": {"/a": {}}})
        assert result.status == ProviderStatus.TOOL_NOT_AVAILABLE
        assert result.passed is False
        assert result.schemathesis_version is None


def test_isolation_schemathesis_unsupported_version():
    """Verifies that incompatible Schemathesis versions transition to TOOL_NOT_AVAILABLE."""
    runner = SchemathesisRunner(source_sha="test_sha")
    with patch.object(VersionPolicy, "get_installed_version", return_value="2.5.0"):
        result = runner.execute(schema_dict={"openapi": "3.0.0", "paths": {"/a": {}}})
        assert result.status == ProviderStatus.TOOL_NOT_AVAILABLE
        assert result.passed is False
        assert result.schemathesis_version == "2.5.0"


def test_isolation_strict_provenance_missing_source_sha():
    """Verifies certification mode fails closed on missing/UNKNOWN source SHA."""
    runner_unknown = SchemathesisRunner(source_sha="UNKNOWN", strict_provenance=True)
    res = runner_unknown.execute(schema_dict={"openapi": "3.0.0", "paths": {"/a": {}}})
    assert res.status == ProviderStatus.INPUT_INVALID
    assert res.passed is False
    assert "Strict provenance" in res.diagnostics[0]["error"]

    runner_empty = SchemathesisRunner(source_sha="", strict_provenance=True)
    res_empty = runner_empty.execute(schema_dict={"openapi": "3.0.0", "paths": {"/a": {}}})
    assert res_empty.status == ProviderStatus.INPUT_INVALID
    assert res_empty.passed is False


def test_isolation_process_crash():
    """Verifies that an unhandled process crash is captured as TOOL_EXECUTION_FAILED."""
    runner = SchemathesisRunner(source_sha="test_sha")
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "Segmentation fault (core dumped)")
    mock_proc.returncode = 139

    with patch("subprocess.Popen", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.TOOL_EXECUTION_FAILED
        assert result.passed is False
        assert result.exit_code == 139
        assert "crashed" in result.raw_output_summary


def test_isolation_process_timeout_hard_kill():
    """Verifies that hard subprocess timeout terminates child process and returns TIMEOUT status."""
    runner = SchemathesisRunner(source_sha="test_sha")
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd=["python", "-m", "worker"], timeout=5.0),
        ("", "")
    ]

    with patch("subprocess.Popen", return_value=mock_proc):
        result = runner.execute(schema_dict=schema, timeout_sec=5.0)
        mock_proc.kill.assert_called_once()
        assert result.status == ProviderStatus.TIMEOUT
        assert result.passed is False
        assert result.exit_code == 124


def test_isolation_malformed_stdout_non_json():
    """Verifies that non-JSON output from worker process returns OUTPUT_INVALID."""
    runner = SchemathesisRunner(source_sha="test_sha")
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("Traceback: SyntaxError in internal worker", "")
    mock_proc.returncode = 1

    with patch("subprocess.Popen", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False


def test_isolation_malformed_json_missing_fields():
    """Verifies that incomplete JSON report from worker returns OUTPUT_INVALID."""
    runner = SchemathesisRunner(source_sha="test_sha")
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (json.dumps({"unknown_field": 123}), "")
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False


def test_isolation_unknown_exit_code():
    """Verifies handling of non-standard exit code with valid payload."""
    runner = SchemathesisRunner(source_sha="test_sha")
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    worker_payload = {
        "status": "TOOL_EXECUTION_FAILED",
        "exit_code": 255,
        "violations": [],
        "stats": {"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.05},
        "diagnostics": [{"error": "Unknown fatal tool error"}],
        "summary": "Worker failed with unknown exit code"
    }

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (json.dumps(worker_payload), "")
    mock_proc.returncode = 255

    with patch("subprocess.Popen", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.TOOL_EXECUTION_FAILED
        assert result.passed is False
        assert result.exit_code == 255


def test_isolation_valid_pass():
    """Verifies normalized output parsing for a valid passing execution."""
    runner = SchemathesisRunner(source_sha="test_sha")
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    worker_payload = {
        "status": "TARGET_CLEAN",
        "exit_code": 0,
        "violations": [],
        "stats": {"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 10, "violations_count": 0, "duration_sec": 0.15},
        "diagnostics": [],
        "summary": "Target clean: All 10 checks passed."
    }

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (json.dumps(worker_payload), "")
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.TARGET_CLEAN
        assert result.passed is True
        assert result.stats.checks_executed == 10
        assert result.stats.violations_count == 0


def test_isolation_valid_contract_failure():
    """Verifies normalized output parsing for a detected contract violation."""
    runner = SchemathesisRunner(source_sha="test_sha")
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    worker_payload = {
        "status": "TARGET_CONTRACT_VIOLATED",
        "exit_code": 1,
        "violations": [
            {
                "error_type": "JsonSchemaError",
                "message": "Response violates schema: 'name' is required",
                "path": "/users",
                "method": "GET",
                "status_code": 200,
                "curl_command": "curl -X GET http://localhost/users",
                "schema_path": "properties/name",
                "details": {}
            }
        ],
        "stats": {"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 1, "duration_sec": 0.12},
        "diagnostics": [],
        "summary": "Contract violated: 1 violations detected."
    }

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (json.dumps(worker_payload), "")
    mock_proc.returncode = 1

    with patch("subprocess.Popen", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.TARGET_CONTRACT_VIOLATED
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].path == "/users"
        assert result.violations[0].status_code == 200
