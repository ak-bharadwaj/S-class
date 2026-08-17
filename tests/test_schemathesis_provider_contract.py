"""
Unit tests for S-Class Schemathesis Provider Contract & Dependency Boundary Isolation (D0 Keyed Protocol).
Verifies all 9 fail-closed states, VersionPolicy, keyed HMAC-SHA256 challenge-response handshake,
adversarial forgery rejection, process crashes, hard timeouts, malformed output, provenance, and zero-leakage encapsulation.
"""

import json
import hmac
import hashlib
import subprocess
import pytest
from unittest.mock import patch, MagicMock

from benchmark.providers.schemathesis.models import (
    ProviderStatus,
    ContractViolation,
    ExecutionStats,
    ProviderExecutionResult,
    WorkerInvocationEnvelope,
    WorkerOutputEnvelope
)
from benchmark.providers.schemathesis.version_policy import (
    VersionPolicy,
    CERTIFIED_SCHEMATHESIS_VERSION
)
from benchmark.providers.schemathesis.parser import SchemathesisParser
from benchmark.providers.schemathesis.runner import SchemathesisRunner
from benchmark.providers.schemathesis.adapter import SchemathesisProviderAdapter


def _build_valid_worker_output(
    status: str = "TARGET_CLEAN",
    exit_code: int = 0,
    violations: list = None,
    stats: dict = None,
    diagnostics: list = None,
    summary: str = "Clean run",
    execution_id: str = "EXEC-001",
    parent_nonce: str = "NONCE-001",
    execution_secret: str = "SECRET-001",
    worker_pid: int = 1234
) -> dict:
    """Helper constructing a valid signed WorkerOutputEnvelope dictionary with keyed HMAC-SHA256."""
    payload = {
        "execution_id": execution_id,
        "parent_nonce": parent_nonce,
        "worker_pid": worker_pid,
        "status": status,
        "exit_code": exit_code,
        "violations": violations or [],
        "stats": stats or {"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": len(violations or []), "duration_sec": 0.1},
        "diagnostics": diagnostics or [],
        "summary": summary
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    payload["worker_digest"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    payload["worker_hmac"] = hmac.new(execution_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return payload


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
        execution_nonce="nonce_12345",
        provider_version="1.0.0",
        schemathesis_version="4.24.3",
        source_sha="a" * 40,
        schema_hash="schema_hash_12345",
        target_identifier="http://localhost:8000",
        target_hash="target_hash_67890",
        config_hash="config_hash_abc",
        input_digest="input_digest_123",
        worker_digest="worker_digest_456",
        worker_hmac="worker_hmac_789",
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
    assert d["input_digest"] == "input_digest_123"
    assert d["worker_digest"] == "worker_digest_456"
    assert d["worker_hmac"] == "worker_hmac_789"


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
    runner = SchemathesisRunner(source_sha="a" * 40)
    with patch.object(VersionPolicy, "get_installed_version", return_value=None):
        result = runner.execute(schema_dict={"openapi": "3.0.0", "paths": {"/a": {}}})
        assert result.status == ProviderStatus.TOOL_NOT_AVAILABLE
        assert result.passed is False
        assert result.schemathesis_version is None


def test_isolation_schemathesis_unsupported_version():
    """Incompatible Schemathesis versions transition to TOOL_NOT_AVAILABLE."""
    runner = SchemathesisRunner(source_sha="a" * 40)
    with patch.object(VersionPolicy, "get_installed_version", return_value="2.5.0"):
        result = runner.execute(schema_dict={"openapi": "3.0.0", "paths": {"/a": {}}})
        assert result.status == ProviderStatus.TOOL_NOT_AVAILABLE
        assert result.passed is False
        assert result.schemathesis_version == "2.5.0"


def test_isolation_malformed_schema_input_invalid():
    """Malformed schema without paths transitions to INPUT_INVALID."""
    runner = SchemathesisRunner(source_sha="a" * 40)
    res_none = runner.execute(schema_dict=None)
    assert res_none.status == ProviderStatus.INPUT_INVALID
    assert res_none.passed is False

    res_empty = runner.execute(schema_dict={})
    assert res_empty.status == ProviderStatus.INPUT_INVALID
    assert res_empty.passed is False


def test_isolation_process_crash():
    """Unhandled process crash is captured as TOOL_EXECUTION_FAILED."""
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("", "Segmentation fault (core dumped)")
    mock_proc.returncode = 139

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.TOOL_EXECUTION_FAILED
        assert result.passed is False
        assert result.exit_code == 139
        assert "crashed" in result.raw_output_summary


def test_isolation_process_timeout_hard_kill():
    """Hard subprocess timeout terminates child process and returns TIMEOUT status."""
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = [
        subprocess.TimeoutExpired(cmd=["python", "-m", "worker"], timeout=5.0),
        ("", "")
    ]

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema, timeout_sec=5.0)
        mock_proc.kill.assert_called_once()
        assert result.status == ProviderStatus.TIMEOUT
        assert result.passed is False
        assert result.exit_code == 124


def test_isolation_malformed_stdout_non_json():
    """Non-JSON output from worker process returns OUTPUT_INVALID."""
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ("Traceback: SyntaxError in internal worker", "")
    mock_proc.returncode = 1

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False


def test_isolation_zero_checks_insufficient_evidence():
    """Zero checks executed by worker returns INSUFFICIENT_EVIDENCE."""
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/empty": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        worker_out = _build_valid_worker_output(
            status="INSUFFICIENT_EVIDENCE",
            exit_code=0,
            violations=[],
            stats={"endpoints_tested": 1, "operations_tested": 0, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.02},
            summary="Worker inconclusive: Zero checks evaluated.",
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 0

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.INSUFFICIENT_EVIDENCE
        assert result.passed is False


def test_isolation_valid_pass():
    """Normalized output parsing for a valid passing execution (TARGET_CLEAN)."""
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        worker_out = _build_valid_worker_output(
            status="TARGET_CLEAN",
            exit_code=0,
            violations=[],
            stats={"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 10, "violations_count": 0, "duration_sec": 0.15},
            summary="Target clean: All 10 checks passed.",
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 0

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.TARGET_CLEAN
        assert result.passed is True
        assert result.stats.checks_executed == 10
        assert result.stats.violations_count == 0
        assert result.worker_hmac != ""


def test_isolation_valid_contract_failure():
    """Normalized output parsing for a detected contract violation (TARGET_CONTRACT_VIOLATED)."""
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    violations_data = [
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
    ]

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        worker_out = _build_valid_worker_output(
            status="TARGET_CONTRACT_VIOLATED",
            exit_code=1,
            violations=violations_data,
            stats={"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 1, "duration_sec": 0.12},
            summary="Contract violated: 1 violations detected.",
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 1

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.TARGET_CONTRACT_VIOLATED
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].path == "/users"
        assert result.violations[0].status_code == 200


# -----------------------------------------------------------------------------
# 2. Keyed HMAC Authentication & Adversarial Forgery Rejection Tests
# -----------------------------------------------------------------------------

def test_adversarial_worker_forges_status_with_recomputed_sha_fails_closed():
    """
    Adversarial Attack 1: Rogue worker changes status from TARGET_CONTRACT_VIOLATED to TARGET_CLEAN,
    recomputes the public SHA-256 digest, but cannot produce the parent-keyed HMAC signature.
    MUST FAIL CLOSED with OUTPUT_INVALID.
    """
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        # Rogue worker fabricates clean status and recomputes only plain SHA-256
        payload = {
            "execution_id": envelope["execution_id"],
            "parent_nonce": envelope["parent_nonce"],
            "worker_pid": 9999,
            "status": "TARGET_CLEAN",  # Forged!
            "exit_code": 0,
            "violations": [],
            "stats": {"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 0, "duration_sec": 0.1},
            "diagnostics": [],
            "summary": "Forged clean run"
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        payload["worker_digest"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        # Worker puts a dummy/unkeyed HMAC signature
        payload["worker_hmac"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return json.dumps(payload), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 0

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False
        assert "hmac" in result.diagnostics[0]["error"].lower()


def test_adversarial_worker_signs_with_wrong_secret_fails_closed():
    """
    Adversarial Attack 2: Rogue worker signs output using a forged or guessing secret.
    MUST FAIL CLOSED with OUTPUT_INVALID.
    """
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        # Worker signs with the WRONG secret
        worker_out = _build_valid_worker_output(
            status="TARGET_CLEAN",
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret="ATTACKER_SUPPLIED_SECRET_KEY_12345"
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 0

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False
        assert "hmac" in result.diagnostics[0]["error"].lower()


def test_adversarial_replay_envelope_against_new_execution_fails_closed():
    """
    Adversarial Attack 3: Replaying a previously valid signed envelope against a new execution.
    MUST FAIL CLOSED with OUTPUT_INVALID.
    """
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    # A previously recorded valid envelope from an old run
    stale_envelope = _build_valid_worker_output(
        status="TARGET_CLEAN",
        execution_id="EXEC-OLD-12345",
        parent_nonce="NONCE-OLD-67890",
        execution_secret="SECRET-OLD-ABCDE"
    )

    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (json.dumps(stale_envelope), "")
    mock_proc.returncode = 0

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False


def test_adversarial_worker_with_valid_secret_forges_clean_status_with_violations_fails_closed():
    """
    Adversarial Attack 4: Compromised worker possesses the real secret and computes a valid HMAC,
    but flips status to TARGET_CLEAN while including real contract violations.
    Parent semantic validator MUST FAIL CLOSED with OUTPUT_INVALID.
    """
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        # Worker signs with the REAL secret, but tries to assert TARGET_CLEAN while violations exist
        worker_out = _build_valid_worker_output(
            status="TARGET_CLEAN",  # Contradiction!
            exit_code=0,
            violations=[{"error_type": "ServerError", "message": "Crash", "path": "/users", "method": "GET"}],
            stats={"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 1, "duration_sec": 0.1},
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 0

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False
        assert "contradiction" in result.diagnostics[0]["error"].lower()


def test_adversarial_worker_with_valid_secret_forges_clean_status_with_zero_checks_fails_closed():
    """
    Adversarial Attack 5: Compromised worker signs with valid HMAC claiming TARGET_CLEAN with 0 checks executed.
    Parent semantic validator MUST FAIL CLOSED with OUTPUT_INVALID.
    """
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        worker_out = _build_valid_worker_output(
            status="TARGET_CLEAN",  # Claiming clean without doing work
            exit_code=0,
            violations=[],
            stats={"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 0, "violations_count": 0, "duration_sec": 0.1},
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 0

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False
        assert "checks_executed is 0" in result.diagnostics[0]["error"].lower()


def test_adversarial_worker_with_valid_secret_forges_violation_status_with_empty_violations_fails_closed():
    """
    Adversarial Attack 6: Compromised worker signs with valid HMAC claiming TARGET_CONTRACT_VIOLATED but provides 0 violations.
    Parent semantic validator MUST FAIL CLOSED with OUTPUT_INVALID.
    """
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        worker_out = _build_valid_worker_output(
            status="TARGET_CONTRACT_VIOLATED",
            exit_code=1,
            violations=[],  # Empty violations list
            stats={"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 0, "duration_sec": 0.1},
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 1

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False
        assert "empty" in result.diagnostics[0]["error"].lower()


def test_adversarial_worker_with_valid_secret_forges_unknown_endpoint_path_fails_closed():
    """
    Adversarial Attack 7: Compromised worker fabricates violations on an endpoint path not in the authoritative schema.
    Parent scope validator MUST FAIL CLOSED with OUTPUT_INVALID.
    """
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        worker_out = _build_valid_worker_output(
            status="TARGET_CONTRACT_VIOLATED",
            exit_code=1,
            violations=[{"error_type": "JsonSchemaError", "message": "Fake", "path": "/fabricated_endpoint_admin", "method": "GET"}],
            stats={"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 1, "duration_sec": 0.1},
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 1

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False
        assert "does not exist in authoritative schema" in result.diagnostics[0]["error"]


def test_adversarial_worker_with_valid_secret_inconsistent_violation_counts_fails_closed():
    """
    Adversarial Attack 8: Compromised worker produces mismatched stats.violations_count vs len(violations).
    Parent statistical validator MUST FAIL CLOSED with OUTPUT_INVALID.
    """
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        worker_out = _build_valid_worker_output(
            status="TARGET_CONTRACT_VIOLATED",
            exit_code=1,
            violations=[{"error_type": "ServerError", "message": "Crash", "path": "/users", "method": "GET"}],
            stats={"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 99, "duration_sec": 0.1},  # Mismatched 99 vs 1
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 1

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        assert result.status == ProviderStatus.OUTPUT_INVALID
        assert result.passed is False
        assert "statistical mismatch" in result.diagnostics[0]["error"].lower()


# -----------------------------------------------------------------------------
# 3. Provenance Verification & Strict Version Enforcement Tests
# -----------------------------------------------------------------------------

def test_provenance_strict_mode_sha_and_version_enforcement():
    """
    Tests strict provenance rules:
    - Missing SHA -> FAIL
    - UNKNOWN SHA -> FAIL
    - Invalid format SHA -> FAIL
    - Fabricated 40-char SHA not in Git object database -> FAIL
    - Authentic repository commit SHA -> PASS
    - Exact dependency version -> PASS
    - Wrong dependency version -> FAIL
    """
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

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

    # 3. Invalid format SHA (e.g. short or non-hex) -> FAIL
    runner_short = SchemathesisRunner(source_sha="short_sha", strict_provenance=True)
    res_short = runner_short.execute(schema_dict=schema)
    assert res_short.status == ProviderStatus.INPUT_INVALID
    assert res_short.passed is False

    # 4. Fabricated 40-char hex SHA not in git repository -> FAIL CLOSED
    fabricated_sha = "f" * 40
    runner_fabricated = SchemathesisRunner(source_sha=fabricated_sha, strict_provenance=True)
    res_fabricated = runner_fabricated.execute(schema_dict=schema)
    assert res_fabricated.status == ProviderStatus.INPUT_INVALID
    assert res_fabricated.passed is False
    assert "strict provenance requirement failed" in res_fabricated.diagnostics[0]["error"].lower()

    # 5. Authentic repository commit SHA -> PASS
    try:
        head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        head_sha = "a" * 40

    runner_valid = SchemathesisRunner(source_sha=head_sha, strict_provenance=True)

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        worker_out = _build_valid_worker_output(
            status="TARGET_CLEAN",
            exit_code=0,
            violations=[],
            stats={"endpoints_tested": 1, "operations_tested": 1, "checks_executed": 5, "violations_count": 0, "duration_sec": 0.1},
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 0

    with patch.object(VersionPolicy, "get_installed_version", return_value=CERTIFIED_SCHEMATHESIS_VERSION):
        with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
            res_valid = runner_valid.execute(schema_dict=schema)
            assert res_valid.status == ProviderStatus.TARGET_CLEAN
            assert res_valid.passed is True
            assert res_valid.source_sha == head_sha
            assert res_valid.schemathesis_version == CERTIFIED_SCHEMATHESIS_VERSION
            assert res_valid.input_digest != ""
            assert res_valid.worker_digest != ""
            assert res_valid.worker_hmac != ""

    # 6. Wrong dependency version (e.g. 4.23.0) under strict mode -> FAIL
    with patch.object(VersionPolicy, "get_installed_version", return_value="4.23.0"):
        res_wrong_ver = runner_valid.execute(schema_dict=schema)
        assert res_wrong_ver.status == ProviderStatus.TOOL_NOT_AVAILABLE
        assert res_wrong_ver.passed is False
        assert "exact certified version" in res_wrong_ver.diagnostics[0]["error"]


# -----------------------------------------------------------------------------
# 4. Zero Leakage Subprocess Encapsulation Test
# -----------------------------------------------------------------------------

def test_zero_schemathesis_hypothesis_objects_escape():
    """Verifies that no Schemathesis/Hypothesis objects cross the provider boundary."""
    runner = SchemathesisRunner(source_sha="a" * 40)
    schema = {"openapi": "3.0.0", "paths": {"/users": {"get": {}}}}

    def mock_communicate(input=None, timeout=None):
        envelope = json.loads(input)
        worker_out = _build_valid_worker_output(
            status="TARGET_CLEAN",
            execution_id=envelope["execution_id"],
            parent_nonce=envelope["parent_nonce"],
            execution_secret=envelope["execution_secret"]
        )
        return json.dumps(worker_out), ""

    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = mock_communicate
    mock_proc.returncode = 0

    with patch.object(SchemathesisRunner, "_spawn_worker_process", return_value=mock_proc):
        result = runner.execute(schema_dict=schema)
        data = result.to_dict()

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
