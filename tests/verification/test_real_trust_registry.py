"""
Verification Unit & Adversarial Tests for Verifier Trust Registry.
Verifies authoritative trust classification across five essential scenarios:
1. System-trusted pytest
2. Workspace pytest
3. Temp-dir pytest
4. Explicitly untrusted binary hash
5. PATH-shadowed untrusted binary
"""

import os
import sys
import tempfile
import pytest

from sclass.execution.identity import ExecutionIdentity
from sclass.verification.verifier_definition import VerifierTrustMode
from sclass.verification.trust_registry import TrustRegistry, TrustPolicy


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "trust_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_system_trusted_pytest(workspace):
    """Verifies that standard Python interpreter or system binary evaluates to SYSTEM_TRUSTED."""
    registry = TrustRegistry()
    execution = ExecutionIdentity(
        requested_argv=("python", "-m", "pytest", "tests/"),
        actual_argv=("python", "-m", "pytest", "tests/"),
        executable_name="python",
        executable_path=sys.executable,
        executable_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        pid=1001,
        parent_pid=1000,
        process_start_time="2026-09-13T00:00:00Z",
        cwd=workspace,
        environment_digest="dig1",
        execution_mode="HOST_ARGV",
    )
    defn, mode, status = registry.evaluate_verifier(execution, workspace_dir=workspace)
    assert defn is not None
    assert defn.verifier_id == "pytest"
    assert mode == VerifierTrustMode.SYSTEM_TRUSTED
    assert status == "AUTHORIZED_PYTEST"


def test_workspace_pytest(workspace):
    """Verifies that a test runner inside the project workspace/venv is WORKSPACE_TRUSTED."""
    registry = TrustRegistry()
    ws_pytest = os.path.join(workspace, ".venv", "bin", "pytest.exe" if os.name == "nt" else "pytest")
    execution = ExecutionIdentity(
        requested_argv=("pytest", "tests/unit"),
        actual_argv=("pytest", "tests/unit"),
        executable_name="pytest",
        executable_path=ws_pytest,
        executable_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        pid=1002,
        parent_pid=1000,
        process_start_time="2026-09-13T00:00:00Z",
        cwd=workspace,
        environment_digest="dig2",
        execution_mode="HOST_ARGV",
    )
    defn, mode, status = registry.evaluate_verifier(execution, workspace_dir=workspace)
    assert defn is not None
    assert defn.verifier_id == "pytest"
    assert mode == VerifierTrustMode.WORKSPACE_TRUSTED
    assert status == "AUTHORIZED_PYTEST"


def test_temp_dir_pytest(workspace):
    """Verifies that an executable spawned from a temp directory is flagged UNTRUSTED."""
    registry = TrustRegistry()
    temp_dir = tempfile.gettempdir()
    temp_pytest = os.path.join(temp_dir, "pytest.exe" if os.name == "nt" else "pytest")
    execution = ExecutionIdentity(
        requested_argv=("pytest", "tests/"),
        actual_argv=("pytest", "tests/"),
        executable_name="pytest",
        executable_path=temp_pytest,
        executable_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        pid=1003,
        parent_pid=1000,
        process_start_time="2026-09-13T00:00:00Z",
        cwd=workspace,
        environment_digest="dig3",
        execution_mode="HOST_ARGV",
    )
    defn, mode, status = registry.evaluate_verifier(execution, workspace_dir=workspace)
    assert defn is not None
    assert defn.verifier_id == "pytest"
    assert mode == VerifierTrustMode.UNTRUSTED
    assert status == "IDENTIFIED_AS_PYTEST+UNTRUSTED_BINARY"


def test_explicitly_untrusted_hash(workspace):
    """Verifies that a compromised binary with a blacklisted hash is UNTRUSTED regardless of path."""
    registry = TrustRegistry()
    compromised_hash = "badcafe1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    registry.mark_untrusted_hash(compromised_hash)

    execution = ExecutionIdentity(
        requested_argv=("python", "-m", "pytest", "tests/"),
        actual_argv=("python", "-m", "pytest", "tests/"),
        executable_name="python",
        executable_path=sys.executable,
        executable_hash=compromised_hash,
        pid=1004,
        parent_pid=1000,
        process_start_time="2026-09-13T00:00:00Z",
        cwd=workspace,
        environment_digest="dig4",
        execution_mode="HOST_ARGV",
    )
    defn, mode, status = registry.evaluate_verifier(execution, workspace_dir=workspace)
    assert defn is not None
    assert defn.verifier_id == "pytest"
    assert mode == VerifierTrustMode.UNTRUSTED
    assert status == "IDENTIFIED_AS_PYTEST+UNTRUSTED_BINARY"


def test_path_shadowed_pytest(workspace):
    """Verifies that an adversary shadow binary earlier in PATH is detected and UNTRUSTED."""
    policy = TrustPolicy()
    shadow_dir = os.path.join(workspace, "adversary_shadow_bin")
    policy.untrusted_dirs.add(os.path.normpath(shadow_dir).lower())
    registry = TrustRegistry(policy=policy)

    shadow_pytest = os.path.join(shadow_dir, "pytest.exe" if os.name == "nt" else "pytest")
    execution = ExecutionIdentity(
        requested_argv=("pytest", "tests/"),
        actual_argv=("pytest", "tests/"),
        executable_name="pytest",
        executable_path=shadow_pytest,
        executable_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        pid=1005,
        parent_pid=1000,
        process_start_time="2026-09-13T00:00:00Z",
        cwd=workspace,
        environment_digest="dig5",
        execution_mode="HOST_ARGV",
    )
    defn, mode, status = registry.evaluate_verifier(execution, workspace_dir=workspace)
    assert defn is not None
    assert defn.verifier_id == "pytest"
    assert mode == VerifierTrustMode.UNTRUSTED
    assert status == "IDENTIFIED_AS_PYTEST+UNTRUSTED_BINARY"
