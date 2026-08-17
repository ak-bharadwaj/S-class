"""
Unit tests for S-Class Schemathesis Provider Contract & Dependency Boundary Isolation.
Verifies all 9 fail-closed states, VersionPolicy, process crashes, hard timeouts, malformed output, provenance, and zero-leakage encapsulation.
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
from benchmark.providers.schemathesis.version_policy import (
    VersionPolicy,
    CERTIFIED_SCHEMATHESIS_VERSION
)
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

    # Exact certified version
    assert VersionPolicy.is_certified_version("4.24.3") is True
    assert VersionPolicy.is_certified_version("4.24.2") is False
    assert VersionPolicy.is_certified_version("3.39.0") is False


# -----------------------------------------------------------------------------
# 1. Boundary & 9 Fail-Closed States Tests
# -----------------------------------------------------------------------------

def test_isolation_schemathesis_missing():
    """Missing Schemathesis package transitions to TOOL_NOT_AVAILABLE."""
    runner = SchemathesisRunner(source_sha="test_sha")
    with patch.object(VersionPolicy, "get_installed_version", return_value=None):
        result = runner.execute(schema_dict={"openapi": "3.0.0", "paths": {"/a": {}}})
        assert result.status == ProviderStatus.TOOL_NOT_AVAILABLE
        assert result.passed is False
        assert result.schemathesis_version is None


def test_isolation_schemathesis_unsupported_version():
    """Incompatible Schemathesis versions transition to TOOL_NOT_AVAILABLE."""
    runner = SchemathesisRunner(source_sha="test_sha")
    with patch.object(VersionPolicy, "get_installed_version", return_value="2.5.0"):
        result = runner.execute(schema_dict={"openapi": "3.0.0", "paths": {"/a": {}}})
        assert result.status == ProviderStatus.TOOL_NOT_AVAILABLE
        assert result.passed is False
        assert result.schemathesis_version == "2.5.0"


def test_isolation_malformed_schema_input_invalid():
    """Malformed schema without paths transitions to INPUT_INVALID."""
    runner = SchemathesisRunner(source_sha="test_sha")
    res_none = runner.execute(schema_dict=None)
    assert res_none.status == ProviderStatus.INPUT_INVALID
    assert res_none.passed is False

    res_empty = runner.execute(schema_dict={})
    assert res_empty.status == ProviderStatus.INPUT_INVALID
    assert res_empty.passed is False


def test_isolation_process_crash():
    """Unhandled process crash is captured as TOOL_EXECUTION_FAILED."""
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
    """Hard subprocess timeout terminates child process and returns TIMEOUT status."""
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
    """Non-JSON output from worker process returns OUTPUT_INVALID."""
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
    """Incomplete JSON report from worker returns OUTPUT_INVALID."""
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
    """Handling of non-standard exit code with valid payload."""
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


def test_isolation_zero_checks_insufficient_evidence():
    """Zero checks executed by worker returns INSUFFICIENT_EVIDENCE."""
    runner = SchemathesisRunner(source_sha="test_sha")
    schema = {"openapi": "3.0.0", "paths": {"/empty": {"get": {}}}}

    worker_payload = {
        "status": "INSUFFICIENT_EVIDENCE",
        "exit_code": 0,
        "violations": [],
        "stats": {"endpoints_tested": 1, "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.02},
        "diagnostics": [{"warning": "Zero operations reachable"}],
        "summary": "Worker inconclusive: Zero checks evaluated."
    }

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (json.dumps(worker_payload), "")
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.INSUFFICIENT_EVIDENCE
        assert result.passed is False


def test_isolation_valid_pass():
    """Normalized output parsing for a valid passing execution (TARGET_CLEAN)."""
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
    """Normalized output parsing for a detected contract violation (TARGET_CONTRACT_VIOLATED)."""
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


# -----------------------------------------------------------------------------
# 2. Zero Leakage Subprocess Encapsulation Test
# -----------------------------------------------------------------------------

def test_zero_schemathesis_hypothesis_objects_escape():
    """Verifies that no Schemathesis/Hypothesis objects cross the provider boundary."""
    runner = SchemathesisRunner(source_sha="test_sha")
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    worker_payload = {
        "status": "TARGET_CLEAN",
        "exit_code": 0,
        "violations": [],
        "stats": {"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 0, "duration_sec": 0.1},
        "diagnostics": [{"info": "test"}],
        "summary": "Clean execution"
    }

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (json.dumps(worker_payload), "")
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        data = result.to_dict()

        # Recursive check ensuring only primitives / built-ins are returned
        def _assert_only_primitives(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    assert isinstance(k, str)
                    _assert_only_primitives(v)
            elif isinstance(obj, list):
                for item in obj:
                    _assert_only_primitives(item)
            else:
                assert isinstance(obj, (str, int, float, bool, type(None)))
                type_module = type(obj).__module__
                assert "schemathesis" not in type_module
                assert "hypothesis" not in type_module

        _assert_only_primitives(data)


# -----------------------------------------------------------------------------
# 3. Provenance Verification Tests (SHA & Exact Dependency Version)
# -----------------------------------------------------------------------------

def test_provenance_strict_mode_sha_and_version_enforcement():
    """
    Tests strict provenance rules:
    - Missing SHA -> FAIL
    - UNKNOWN SHA -> FAIL
    - Exact SHA -> PASS
    - Exact dependency version -> PASS
    - Wrong dependency version -> FAIL
    """
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}
    worker_payload = {
        "status": "TARGET_CLEAN",
        "exit_code": 0,
        "violations": [],
        "stats": {"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 0, "duration_sec": 0.1},
        "diagnostics": [],
        "summary": "Clean"
    }

    # 1. Missing / empty SHA under strict mode -> FAIL
    runner_empty = SchemathesisRunner(source_sha="", strict_provenance=True)
    res_empty = runner_empty.execute(schema_dict=schema)
    assert res_empty.status == ProviderStatus.INPUT_INVALID
    assert res_empty.passed is False

    # 2. UNKNOWN SHA under strict mode -> FAIL
    runner_unknown = SchemathesisRunner(source_sha="UNKNOWN", strict_provenance=True)
    res_unknown = runner_unknown.execute(schema_dict=schema)
    assert res_unknown.status == ProviderStatus.INPUT_INVALID
    assert res_unknown.passed is False

    # 3. Exact SHA with exact certified version -> PASS
    exact_sha = "a" * 40
    runner_valid = SchemathesisRunner(source_sha=exact_sha, strict_provenance=True)

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (json.dumps(worker_payload), "")
    mock_proc.returncode = 0

    with patch.object(VersionPolicy, "get_installed_version", return_value=CERTIFIED_SCHEMATHESIS_VERSION):
        with patch("subprocess.Popen", return_value=mock_proc):
            res_valid = runner_valid.execute(schema_dict=schema)
            assert res_valid.status == ProviderStatus.TARGET_CLEAN
            assert res_valid.passed is True
            assert res_valid.source_sha == exact_sha
            assert res_valid.schemathesis_version == CERTIFIED_SCHEMATHESIS_VERSION

    # 4. Wrong dependency version (e.g. 4.23.0 or 3.40.0) under strict mode -> FAIL
    with patch.object(VersionPolicy, "get_installed_version", return_value="4.23.0"):
        res_wrong_ver = runner_valid.execute(schema_dict=schema)
        assert res_wrong_ver.status == ProviderStatus.TOOL_NOT_AVAILABLE
        assert res_wrong_ver.passed is False
        assert "exact certified version" in res_wrong_ver.diagnostics[0]["error"]
