"""
Unit and Regression Tests for Hardened Trust Boundaries.
Tests:
1. Actual process identity (child PID != parent PID, parent_pid == os.getpid()).
2. Token-based test runner detection without substring regex (anti-spoofing).
3. Explicit ExecutionMode enum (HOST_ARGV, HOST_SHELL, etc.).
4. Strict GenericVerifier claim semantics (INCONCLUSIVE for semantic/feature claims backed only by generic execution).
"""

import os
import sys
import pytest

from sclass.domain.claim import Claim
from sclass.domain.evidence import EvidenceReceipt
from sclass.domain.execution import ExecutionIdentity, ExecutionMode
from sclass.execution.process import ProcessRunner
from sclass.observation.observer import detect_execution_kind, observe_command
from sclass.verification.verifiers.generic_verifier import GenericVerifier
from sclass.verification.verifiers.pytest_verifier import PytestVerifier
from sclass.core.errors import SecurityViolationError


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "test_hardened_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_token_based_test_runner_detection_anti_spoofing():
    """Confirms substring matching is eliminated and python -c cannot spoof test runners."""
    # Spoof attempts with python -c
    assert detect_execution_kind("python -c \"print('pytest')\"") == ("generic_command", "")
    assert detect_execution_kind("python3 -c 'import pytest; print(1)'") == ("generic_command", "")
    assert detect_execution_kind("py -c pytest") == ("generic_command", "")

    # Spoof attempts with echo or arbitrary CLI
    assert detect_execution_kind("echo pytest") == ("generic_command", "")
    assert detect_execution_kind("node -e \"console.log('pytest')\"") == ("generic_command", "")

    # Legitimate python -m test runners
    assert detect_execution_kind("python -m pytest tests/") == ("test_runner", "pytest")
    assert detect_execution_kind("python3 -m unittest discover") == ("test_runner", "unittest")
    assert detect_execution_kind(["python", "-m", "pytest", "-v"]) == ("test_runner", "pytest")

    # Direct binaries
    assert detect_execution_kind("pytest tests/unit") == ("test_runner", "pytest")
    assert detect_execution_kind("jest --coverage") == ("test_runner", "jest")
    assert detect_execution_kind("vitest run") == ("test_runner", "vitest")
    assert detect_execution_kind("cargo test") == ("test_runner", "cargo")
    assert detect_execution_kind("go test ./...") == ("test_runner", "go")
    assert detect_execution_kind("npm test") == ("test_runner", "npm")


def test_actual_child_process_identity(workspace):
    """Verifies that ExecutionIdentity captures the actual spawned child PID, not the caller PID."""
    runner = ProcessRunner()
    current_pid = os.getpid()

    result = runner.run([sys.executable, "-c", "import os; print(os.getpid())"], cwd=workspace)
    assert result.exit_code == 0

    child_printed_pid = int(result.stdout.strip())

    # ExecutionIdentity.pid MUST be the actual child PID
    assert result.identity.pid == child_printed_pid
    # ExecutionIdentity.pid MUST NOT be the caller/observer PID
    assert result.identity.pid != current_pid
    # Parent PID must be the caller
    assert result.identity.parent_pid == current_pid
    # ExecutionMode default is HOST_ARGV
    assert result.identity.execution_mode == ExecutionMode.HOST_ARGV.value


def test_execution_mode_shell_gating(workspace):
    """Verifies ExecutionMode gating and explicit shell execution recording."""
    runner = ProcessRunner()

    # Default HOST_ARGV mode
    res_argv = runner.run([sys.executable, "-c", "print('argv_ok')"], cwd=workspace, mode=ExecutionMode.HOST_ARGV)
    assert res_argv.exit_code == 0
    assert res_argv.identity.execution_mode == ExecutionMode.HOST_ARGV.value

    # Explicit HOST_SHELL mode
    res_shell = runner.run([sys.executable, "-c", "print('shell_ok')"], cwd=workspace, mode=ExecutionMode.HOST_SHELL)
    assert res_shell.exit_code == 0
    assert res_shell.identity.execution_mode == ExecutionMode.HOST_SHELL.value


def test_observe_command_records_child_pid_and_mode(workspace):
    """Verifies observe_command anchors child PID and execution mode into receipts and ledger."""
    cmd = f'"{sys.executable}" -c "print(12345)"'
    receipt = observe_command(
        command=cmd,
        workspace_dir=workspace,
        mode=ExecutionMode.HOST_ARGV,
    )

    assert receipt.exit_code == 0
    assert receipt.metadata is not None
    exec_id_data = receipt.metadata.get("execution_identity")
    assert exec_id_data is not None
    assert exec_id_data["pid"] is not None
    assert exec_id_data["pid"] != os.getpid()
    assert exec_id_data["parent_pid"] == os.getpid()
    assert exec_id_data["execution_mode"] == ExecutionMode.HOST_ARGV.value


def test_observe_command_rejects_unauthorized_shell_chaining(workspace):
    """Verifies that non-HOST_SHELL mode rejects shell chaining characters."""
    with pytest.raises(SecurityViolationError):
        observe_command(
            command="echo hello && echo bad",
            workspace_dir=workspace,
            mode=ExecutionMode.HOST_ARGV,
        )


def test_generic_verifier_inconclusive_for_semantic_feature_claims(workspace):
    """
    Verifies that GenericVerifier distinguishes EXECUTION_VERIFIED from CLAIM_VERIFIED.
    A generic command receipt (e.g. build or script) is INCONCLUSIVE for semantic/feature claims.
    """
    verifier = GenericVerifier()

    # Fake evidence with files changed and exit_code 0, but execution_kind="generic_command"
    receipt = EvidenceReceipt(
        receipt_id="rcpt_feature_test",
        task_id="t1",
        claim_id="c1",
        agent="agent",
        action="run_command",
        workspace=workspace,
        command="python setup.py build",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_hash="abc",
        stderr_hash="def",
        files_changed=["src/auth.py"],
        execution_kind="generic_command",
        verified=False,
    )

    # Feature claim: must be INCONCLUSIVE because generic command does not prove feature correctness
    claim_feat = Claim(
        claim_id="c1",
        task_id="t1",
        statement="Implemented OAuth JWT authentication",
        claim_type="feature",
    )
    res_feat = verifier.verify(claim_feat, receipt, workspace)
    assert res_feat.status == "INCONCLUSIVE"
    assert "inconclusive for semantic feature claim" in res_feat.reason
    assert "EXECUTION_VERIFIED" in res_feat.reason

    # Pure execution claim: ACCEPT because claim is only that the execution ran
    claim_exec = Claim(
        claim_id="c2",
        task_id="t1",
        statement="Executed build command",
        claim_type="execution",
    )
    res_exec = verifier.verify(claim_exec, receipt, workspace)
    assert res_exec.status == "ACCEPT"

    # Test claim on generic command: REJECT because no test runner executed
    claim_test = Claim(
        claim_id="c3",
        task_id="t1",
        statement="All test suites pass",
        claim_type="test_pass",
    )
    res_test = verifier.verify(claim_test, receipt, workspace)
    assert res_test.status == "REJECT"
