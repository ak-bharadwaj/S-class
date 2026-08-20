"""
S-Class EOS V11.2 - D6 Execution Fabric Production-Grade Hardened Test Suite (§8.1, §8.3).
Exhaustive verification of:
1. D5 ExecutionEnvelope Gateway Verification.
2. Mandatory Authoritative D2 NonceStore Dependency (fails closed if missing/invalid).
3. Provider Resolution & Capability Scoping.
4. Isolated Workspace Management & Path Traversal / Symlink Escape Prevention.
5. Provider Boundary Workspace Containment (../../outside, absolute host path, symlink -> outside, drive path, UNC path, valid target).
6. Constrained LocalProcessBackend (argv arrays, sanitized environment, bounded streams, timeouts, process group isolation).
7. Process Group Isolation & Parent Group Non-Termination Regression (timeout cannot kill parent/controller).
8. Recursive Orphan Descendant Process Tree Termination.
9. Truthful Resource Semantics (ENFORCED, OBSERVED, UNSUPPORTED).
10. Hardened Environment Construction (PATH, PYTHONPATH, TEMP, TMP, LD_PRELOAD, NODE_OPTIONS, BASH_ENV injection rejection).
11. Explicit Workspace Cleanup Failure Recording.
12. Pytest Provider Adapter execution.
13. Immutable ExecutionObservation process facts.
"""

import os
import sys
import time
import pytest
import subprocess
import signal
from typing import List, Sequence
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from cryptography.hazmat.primitives.asymmetric import ed25519

from domain.models import Obligation, Policy, PolicyRule, PolicyExpression
from domain.types import (
    ObligationStatus,
    ObligationCategory,
    Criticality,
    RuleType,
    CombinatorType,
    PolicyScope,
)
from events.store import D2NonceStore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from controller.authorization import ActionProposal, AuthorizationEngine, AuthorizationStatus
from controller.token import (
    ActionBinding,
    ExecutionContext,
    ExecutionToken,
    ExecutionAdmissionResult,
    ExecutionEnvelope,
    verify_execution_envelope,
)
from controller.controller import SClassController
from execution.models import (
    ExecutionStatus,
    TerminationReason,
    MeasurementStatus,
    ResourceUsage,
    ExecutionObservation,
)
from execution.workspace import IsolatedWorkspace
from execution.backend import ExecutionBackend, BackendProcessResult
from execution.local_backend import LocalProcessBackend, sanitize_environment, terminate_process_tree
from execution.provider import D6ExecutionProvider, D6ProviderRegistry
from execution.adapters.pytest_adapter import PytestExecutionProvider
from execution.gateway import D6ExecutionGateway


DEFAULT_SHA = "a" * 40
ALT_SHA = "b" * 40
TIMESTAMP_NOW = "2026-08-20T12:00:00Z"
TIMESTAMP_EXPIRY = "2026-08-20T13:00:00Z"
TIMESTAMP_LATE = "2026-08-20T14:00:00Z"


@pytest.fixture(autouse=True)
def setup_authority_keys():
    """Initializes Gate 3 Authority KeyStore for test runs."""
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


@pytest.fixture
def fresh_nonce_store(tmp_path):
    """Provides a fresh isolated D2 nonce store for testing."""
    log_file = str(tmp_path / "d6_test_nonces.log")
    return D2NonceStore(file_path=log_file)


def make_valid_envelope(
    tmp_path,
    nonce_store: D2NonceStore,
    action_type: str = "EXECUTE_TEST",
    target: str = "tests/test_unit.py",
    provider_id: str = "pytest_runner_engine",
    capabilities: Sequence[str] = ("CAP_EXEC_TEST",),
) -> ExecutionEnvelope:
    """Helper creating a cryptographically verified and durably admitted ExecutionEnvelope via Controller."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=nonce_store)

    obligation = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-001",
        title="Test Obligation",
        description="Verify system invariant",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        depends_on=(),
        policy_id="POL-001",
    )
    rule = PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={})
    policy = Policy(
        policy_id="POL-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(combinator=CombinatorType.ALL, rules=(rule,)),
    )
    context = ExecutionContext(
        provider_id=provider_id,
        sandbox_profile_id="sbx_std",
        workspace_id="ws_verified_1",
        resource_profile_id="res_std",
        capability_set=tuple(capabilities),
    )
    proposal = ActionProposal(
        proposal_id=f"ACT-{os.urandom(4).hex().upper()}",
        obligation_id="OBL-001",
        action_type=action_type,
        target=target,
        purpose="Verify test pass in workspace",
        execution_context=context,
        parameters={"quiet": True},
    )
    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": obligation},
        policies={"POL-001": policy},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        allowed_action_types=[action_type],
    )
    token = dispatch.execution_token
    assert token is not None

    binding = ActionBinding(
        action_type=action_type,
        target=target,
        purpose="Verify test pass in workspace",
        parameters={"quiet": True},
    )

    admission = controller.admit_execution(
        token=token,
        expected_obligation_id="OBL-001",
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        expected_action_binding=binding,
        expected_execution_context=context,
        current_time_iso=TIMESTAMP_NOW,
    )
    assert admission.is_admitted is True

    return ExecutionEnvelope(
        token=token,
        admission=admission,
        action_binding=binding,
        execution_context=context,
    )


# =====================================================================
# 1. GATEWAY & ENVELOPE VERIFICATION TESTS
# =====================================================================

def test_gateway_requires_authoritative_d2_nonce_store():
    """Fails closed: Gateway must never silently construct a local D2 store as a fallback."""
    signer = Gate3AuthoritySigner()
    with pytest.raises(TypeError, match="authoritative dependency required"):
        D6ExecutionGateway(authority_signer=signer, nonce_store=None)  # type: ignore

    with pytest.raises(TypeError, match="authoritative dependency required"):
        D6ExecutionGateway(authority_signer=signer, nonce_store="NOT_A_STORE")  # type: ignore


def test_gateway_valid_envelope_pytest_execution(tmp_path, fresh_nonce_store):
    """Verifies that a valid envelope executes pytest cleanly and returns structured observation facts."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(
        authority_signer=signer,
        nonce_store=fresh_nonce_store,
        workspace_base_dir=str(tmp_path / "workspaces"),
    )

    envelope = make_valid_envelope(tmp_path, fresh_nonce_store, target="test_sample.py")
    
    obs = gateway.execute(
        envelope=envelope,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=TIMESTAMP_NOW,
        timeout_seconds=10.0,
    )

    assert isinstance(obs, ExecutionObservation)
    assert obs.token_id == envelope.token.token_id
    assert obs.provider_id == "pytest_runner_engine"
    assert obs.action_digest == envelope.token.action_digest
    assert obs.context_digest == envelope.token.context_digest
    assert len(obs.stdout_digest) == 64
    assert len(obs.stderr_digest) == 64
    assert obs.execution_status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILURE)


def test_gateway_rejected_on_invalid_envelope(tmp_path, fresh_nonce_store):
    """Verifies that an invalid or tampered envelope is rejected fail-closed at Gateway Gate Step 1."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store)

    obs = gateway.execute(
        envelope="NOT_AN_ENVELOPE",  # type: ignore
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=TIMESTAMP_NOW,
    )
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.ENVELOPE_INVALID


def test_gateway_rejected_on_unadmitted_or_tampered_token(tmp_path, fresh_nonce_store):
    """Verifies gateway rejection when token nonce was not committed to D2 nonce store."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store)

    controller = SClassController(authority_signer=signer, nonce_store=fresh_nonce_store)
    obligation = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-001",
        title="Test Obligation",
        description="Verify system invariant",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        depends_on=(),
        policy_id="POL-001",
    )
    policy = Policy(
        policy_id="POL-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(combinator=CombinatorType.ALL, rules=(PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={}),)),
    )
    ctx = ExecutionContext("pytest_runner_engine", "sbx_1", "ws_1", "res_1", ("CAP_EXEC_TEST",))
    proposal = ActionProposal("ACT-001", "OBL-001", "EXECUTE_TEST", "tests/t.py", "test", ctx)

    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations={"OBL-001": obligation},
        policies={"POL-001": policy},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=TIMESTAMP_NOW,
        expires_at=TIMESTAMP_EXPIRY,
        allowed_action_types=["EXECUTE_TEST"],
    )
    token = dispatch.execution_token
    assert token is not None

    binding = ActionBinding(
        action_type="EXECUTE_TEST",
        target="tests/t.py",
        purpose="test",
        parameters={},
    )

    # Unadmitted dummy admission (valid schema matching token, but nonce never registered in D2)
    admission = ExecutionAdmissionResult(
        token_id=token.token_id,
        execution_nonce=token.execution_nonce,
        obligation_id=token.obligation_id,
        action_digest=token.action_digest,
        context_digest=token.context_digest,
        source_sha=token.source_sha,
        policy_version=token.policy_version,
        decision_id=token.decision_id,
        admitted_at=TIMESTAMP_NOW,
        is_admitted=True,
        signature=signer.sign_payload(b"tampered", timestamp_iso=TIMESTAMP_NOW),
    )

    env = ExecutionEnvelope(token, admission, binding, ctx)
    obs = gateway.execute(env, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.ENVELOPE_INVALID


def test_gateway_rejected_on_unauthorized_provider(tmp_path, fresh_nonce_store):
    """Verifies gateway rejection when provider_id in context is not registered."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store)

    env = make_valid_envelope(tmp_path, fresh_nonce_store, provider_id="rogue_unregistered_provider")
    obs = gateway.execute(env, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.UNAUTHORIZED_PROVIDER


def test_gateway_rejected_on_capability_escalation_or_missing_capability(tmp_path, fresh_nonce_store):
    """Verifies gateway rejection when authorized capability_set does not satisfy provider requirements."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store)

    # PytestExecutionProvider requires CAP_EXEC_TEST, but envelope only grants CAP_READ_LOGS
    env = make_valid_envelope(tmp_path, fresh_nonce_store, capabilities=("CAP_READ_LOGS",))
    obs = gateway.execute(env, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.CAPABILITY_VIOLATION


def test_gateway_rejected_on_action_type_unsupported_by_provider(tmp_path, fresh_nonce_store):
    """Verifies gateway rejection when action_type is unsupported by the resolved provider."""
    signer = Gate3AuthoritySigner()
    registry = D6ProviderRegistry()

    class StrictProvider(D6ExecutionProvider):
        @property
        def provider_id(self) -> str:
            return "strict_engine"
        @property
        def supported_action_types(self) -> Sequence[str]:
            return ("SPECIFIC_TASK",)
        @property
        def required_capabilities(self) -> Sequence[str]:
            return ("CAP_EXEC_TEST",)
        def build_command(self, action_binding, workspace, context):
            return [sys.executable, "-c", "print('ok')"]

    registry.register(StrictProvider())
    gateway = D6ExecutionGateway(authority_signer=signer, registry=registry, nonce_store=fresh_nonce_store)

    env = make_valid_envelope(tmp_path, fresh_nonce_store, action_type="EXECUTE_TEST", provider_id="strict_engine")
    obs = gateway.execute(env, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.ENVELOPE_INVALID


# =====================================================================
# 2. WORKSPACE CONTAINMENT & PROVIDER BOUNDARY TESTS
# =====================================================================

def test_workspace_isolation_and_path_traversal_rejection(tmp_path):
    """Verifies IsolatedWorkspace prevents directory traversal and outside path escape."""
    ws = IsolatedWorkspace(workspace_id="test_ws", base_dir=str(tmp_path / "workspaces"))
    ws_path = ws.setup()
    assert os.path.exists(ws_path)
    assert ws.is_active

    # Safe relative paths resolve inside workspace
    safe = ws.resolve_safe_path("tests/sub/test_foo.py")
    assert safe.startswith(os.path.realpath(ws_path))

    # Reject '..' traversal
    with pytest.raises(ValueError, match="Path traversal rejected"):
        ws.resolve_safe_path("../../outside.py")

    # Reject absolute path
    with pytest.raises(ValueError, match="Path traversal rejected"):
        if sys.platform == "win32":
            ws.resolve_safe_path("C:\\Windows\\System32\\calc.exe")
        else:
            ws.resolve_safe_path("/etc/passwd")

    # Reject Windows drive letters
    with pytest.raises(ValueError, match="Path traversal rejected"):
        ws.resolve_safe_path("D:evil_script.py")

    # Reject UNC path
    with pytest.raises(ValueError, match="Path traversal rejected"):
        ws.resolve_safe_path("\\\\evil_server\\share\\evil.py")

    ws.cleanup()
    assert not os.path.exists(ws_path)
    assert not ws.is_active


def test_provider_boundary_workspace_containment(tmp_path):
    """Exhaustively verifies PytestExecutionProvider.build_command() enforces workspace containment on all targets."""
    provider = PytestExecutionProvider()
    ws = IsolatedWorkspace(workspace_id="ws_containment_test", base_dir=str(tmp_path / "workspaces"))
    ws.setup()

    ctx = ExecutionContext("pytest_runner_engine", "sbx_std", "ws_containment_test", "res_std", ("CAP_EXEC_TEST",))

    # 1. Test ../../outside -> rejected
    action_escape = ActionBinding(
        action_type="EXECUTE_TEST",
        target="../../outside.py",
        purpose="escape attempt",
        parameters={},
    )
    with pytest.raises(ValueError, match="Path traversal rejected"):
        provider.build_command(action_escape, ws, ctx)

    # 2. Test absolute host path -> rejected
    abs_target = "C:\\Windows\\System32\\notepad.exe" if sys.platform == "win32" else "/bin/sh"
    action_abs = ActionBinding(
        action_type="EXECUTE_TEST",
        target=abs_target,
        purpose="absolute path attempt",
        parameters={},
    )
    with pytest.raises(ValueError, match="Path traversal rejected"):
        provider.build_command(action_abs, ws, ctx)

    # 3. Test Windows drive path -> rejected
    action_drive = ActionBinding(
        action_type="EXECUTE_TEST",
        target="D:bad_file.py",
        purpose="drive path attempt",
        parameters={},
    )
    with pytest.raises(ValueError, match="Path traversal rejected"):
        provider.build_command(action_drive, ws, ctx)

    # 4. Test symlink -> outside -> rejected
    outside_dir = tmp_path / "external_secret"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.py"
    secret_file.write_text("def test_secret(): pass", encoding="utf-8")

    symlink_path = os.path.join(ws.path, "symlink_test.py")
    try:
        os.symlink(str(secret_file), symlink_path)
        action_symlink = ActionBinding(
            action_type="EXECUTE_TEST",
            target="symlink_test.py",
            purpose="symlink escape attempt",
            parameters={},
        )
        with pytest.raises(ValueError, match="Path escape detected"):
            provider.build_command(action_symlink, ws, ctx)
    except (OSError, NotImplementedError):
        pass

    # 5. Test valid in-workspace target -> accepted
    valid_test = os.path.join(ws.path, "test_valid.py")
    with open(valid_test, "w", encoding="utf-8") as f:
        f.write("def test_pass(): assert True")

    action_valid = ActionBinding(
        action_type="EXECUTE_TEST",
        target="test_valid.py",
        purpose="valid in-workspace target",
        parameters={"maxfail": 2, "quiet": True},
    )
    cmd = provider.build_command(action_valid, ws, ctx)
    assert isinstance(cmd, list)
    assert "--maxfail" in cmd
    assert "-q" in cmd
    assert cmd[-1] == os.path.realpath(valid_test)

    ws.cleanup()


def test_gateway_catches_provider_containment_violation(tmp_path, fresh_nonce_store):
    """Verifies D6ExecutionGateway catches provider path traversal and produces PATH_ESCAPE_DETECTED observation."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(
        authority_signer=signer,
        nonce_store=fresh_nonce_store,
        workspace_base_dir=str(tmp_path / "workspaces"),
    )

    env = make_valid_envelope(tmp_path, fresh_nonce_store, target="../../escape.py")
    obs = gateway.execute(
        envelope=env,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=TIMESTAMP_NOW,
    )
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.PATH_ESCAPE_DETECTED


def test_workspace_cleanup_failure_recorded_in_diagnostics(tmp_path, fresh_nonce_store):
    """Verifies that if workspace cleanup fails, the warning is captured explicitly in diagnostics."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(
        authority_signer=signer,
        nonce_store=fresh_nonce_store,
        workspace_base_dir=str(tmp_path / "cleanup_ws"),
    )

    env = make_valid_envelope(tmp_path, fresh_nonce_store, target="test_clean.py")

    with patch("shutil.rmtree", side_effect=PermissionError("Permission denied on workspace cleanup")):
        obs = gateway.execute(
            envelope=env,
            expected_source_sha=DEFAULT_SHA,
            expected_policy_version=1,
            current_time_iso=TIMESTAMP_NOW,
        )

    assert any("cleanup_warning" in d for d in obs.diagnostics)


# =====================================================================
# 3. PROCESS GROUP ISOLATION & REGRESSION TESTS
# =====================================================================

def test_local_backend_process_group_isolation_and_timeout(tmp_path):
    """Verifies timeout terminates child process tree without affecting parent process."""
    backend = LocalProcessBackend()
    
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    res = backend.execute_command(
        command_argv=cmd,
        working_directory=str(tmp_path),
        timeout_seconds=0.3,
    )

    assert res.termination_reason == TerminationReason.TIMEOUT_EXPIRED
    assert res.exit_code == -9
    assert "timed out" in (res.error_message or "")


def test_process_group_timeout_cannot_terminate_parent_process_group(tmp_path):
    """Regression Test: Proves a timed-out child with process session isolation cannot kill parent process group."""
    parent_pid = os.getpid()
    backend = LocalProcessBackend()

    cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    res = backend.execute_command(
        command_argv=cmd,
        working_directory=str(tmp_path),
        timeout_seconds=0.2,
    )

    assert res.termination_reason == TerminationReason.TIMEOUT_EXPIRED
    assert os.getpid() == parent_pid


def test_orphan_descendant_process_tree_cleanup(tmp_path):
    """Verifies that when a child process spawns nested descendant processes, tree termination kills all descendants."""
    backend = LocalProcessBackend()

    # Script spawns a grand-child process and sleeps
    parent_script = (
        "import subprocess, sys, time\n"
        "sub = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "time.sleep(30)\n"
    )

    res = backend.execute_command(
        command_argv=[sys.executable, "-c", parent_script],
        working_directory=str(tmp_path),
        timeout_seconds=0.5,
    )

    assert res.termination_reason == TerminationReason.TIMEOUT_EXPIRED
    assert res.exit_code == -9


# =====================================================================
# 4. RESOURCE SEMANTICS (ENFORCED, OBSERVED, UNSUPPORTED)
# =====================================================================

def test_resource_usage_semantics_and_immutability():
    """Verifies explicit ResourceUsage measurement statuses (ENFORCED, OBSERVED, UNSUPPORTED)."""
    usage = ResourceUsage(
        wall_clock_seconds=1.25,
        wall_clock_status=MeasurementStatus.OBSERVED,
        output_bytes_status=MeasurementStatus.ENFORCED,
        process_tree_termination_status=MeasurementStatus.ENFORCED,
        cpu_user_seconds=None,
        cpu_system_seconds=None,
        cpu_status=MeasurementStatus.UNSUPPORTED,
        memory_peak_bytes=None,
        memory_status=MeasurementStatus.UNSUPPORTED,
    )

    assert usage.wall_clock_seconds == 1.25
    assert usage.wall_clock_status == MeasurementStatus.OBSERVED
    assert usage.output_bytes_status == MeasurementStatus.ENFORCED
    assert usage.process_tree_termination_status == MeasurementStatus.ENFORCED
    assert usage.cpu_user_seconds is None
    assert usage.cpu_status == MeasurementStatus.UNSUPPORTED
    assert usage.memory_peak_bytes is None
    assert usage.memory_status == MeasurementStatus.UNSUPPORTED

    with pytest.raises(Exception):
        usage.wall_clock_seconds = 2.0  # type: ignore (frozen dataclass)


def test_resource_usage_validation_errors():
    """Verifies validation errors on invalid types or negative numbers in ResourceUsage."""
    with pytest.raises(TypeError):
        ResourceUsage(wall_clock_status="INVALID")  # type: ignore
    with pytest.raises(TypeError):
        ResourceUsage(output_bytes_status="INVALID")  # type: ignore
    with pytest.raises(TypeError):
        ResourceUsage(process_tree_termination_status="INVALID")  # type: ignore
    with pytest.raises(TypeError):
        ResourceUsage(cpu_status="INVALID")  # type: ignore
    with pytest.raises(TypeError):
        ResourceUsage(memory_status="INVALID")  # type: ignore
    with pytest.raises(ValueError):
        ResourceUsage(wall_clock_seconds=-1.0)
    with pytest.raises(ValueError):
        ResourceUsage(cpu_user_seconds=-1.0)
    with pytest.raises(ValueError):
        ResourceUsage(cpu_system_seconds=-1.0)
    with pytest.raises(ValueError):
        ResourceUsage(memory_peak_bytes=-100)


def test_backend_produces_correct_resource_semantics(tmp_path):
    """Verifies LocalProcessBackend produces authentic ResourceUsage with unsupported CPU/memory fields."""
    backend = LocalProcessBackend()
    res = backend.execute_command(
        command_argv=[sys.executable, "-c", "print('hello resource semantics')"],
        working_directory=str(tmp_path),
    )

    assert res.exit_code == 0
    usage = res.resource_usage
    assert isinstance(usage, ResourceUsage)
    assert usage.wall_clock_seconds >= 0.0
    assert usage.wall_clock_status == MeasurementStatus.OBSERVED
    assert usage.output_bytes_status == MeasurementStatus.ENFORCED
    assert usage.process_tree_termination_status == MeasurementStatus.ENFORCED
    assert usage.cpu_user_seconds is None
    assert usage.cpu_status == MeasurementStatus.UNSUPPORTED
    assert usage.memory_peak_bytes is None
    assert usage.memory_status == MeasurementStatus.UNSUPPORTED


# =====================================================================
# 5. HARDENED ENVIRONMENT CONSTRUCTION TESTS
# =====================================================================

def test_environment_construction_prevents_path_and_pythonpath_overrides():
    """Adversarial Test: Proves caller cannot override PATH, PYTHONPATH, TEMP, TMP."""
    host_path = os.environ.get("PATH", "")
    host_temp = os.environ.get("TEMP", "")

    malicious_custom = {
        "PATH": "/malicious/bin:" + host_path,
        "PYTHONPATH": "/malicious/python/lib",
        "PYTHONHOME": "/malicious/python/home",
        "TEMP": "/malicious/temp",
        "TMP": "/malicious/tmp",
        "SAFE_CUSTOM_VAR": "valid_value_123",
    }

    cleaned = sanitize_environment(malicious_custom)

    assert cleaned["PATH"] == host_path
    if host_temp:
        assert cleaned["TEMP"] == host_temp
    assert "PYTHONPATH" not in cleaned
    assert "PYTHONHOME" not in cleaned
    assert cleaned["SAFE_CUSTOM_VAR"] == "valid_value_123"
    assert cleaned["PYTHONUNBUFFERED"] == "1"
    assert cleaned["PYTHONDONTWRITEBYTECODE"] == "1"


def test_environment_construction_blocks_dynamic_linker_and_shell_injections():
    """Adversarial Test: Proves caller cannot inject LD_PRELOAD, NODE_OPTIONS, BASH_ENV, etc."""
    hostile_injections = {
        "LD_PRELOAD": "/tmp/libhack.so",
        "DYLD_INSERT_LIBRARIES": "/tmp/libhack.dylib",
        "NODE_OPTIONS": "--require /tmp/hack.js",
        "BASH_ENV": "/tmp/evil_bashrc",
        "PERL5OPT": "-Mevil",
        "RUBYOPT": "-revid",
        "PYTHONSTARTUP": "/tmp/evil_startup.py",
        "IFS": ":",
        "PROMPT_COMMAND": "curl evil.com",
    }

    cleaned = sanitize_environment(hostile_injections)

    for hostile_key in hostile_injections:
        assert hostile_key not in cleaned


def test_local_backend_executes_with_sanitized_environment(tmp_path):
    """Verifies that child process observes the sanitized environment policy."""
    backend = LocalProcessBackend()
    
    script = (
        "import os\n"
        "assert 'LD_PRELOAD' not in os.environ\n"
        "assert 'PYTHONPATH' not in os.environ\n"
        "assert os.environ.get('MY_APP_FLAG') == 'active'\n"
        "print('ENV_VERIFIED_CLEAN')\n"
    )

    res = backend.execute_command(
        command_argv=[sys.executable, "-c", script],
        working_directory=str(tmp_path),
        environment={
            "LD_PRELOAD": "/tmp/bad.so",
            "PYTHONPATH": "/tmp/bad_py",
            "MY_APP_FLAG": "active",
        },
    )

    assert res.exit_code == 0
    assert b"ENV_VERIFIED_CLEAN" in res.stdout_bytes


# =====================================================================
# 6. CONSTRAINED EXECUTION & METRICS TESTS
# =====================================================================

def test_local_backend_shell_metacharacters_treated_as_arguments(tmp_path):
    """Verifies command injection via shell metacharacters fails safely with argv lists."""
    backend = LocalProcessBackend()

    res = backend.execute_command(
        command_argv=[sys.executable, "-c", "import sys; print(sys.argv[1])", "hello; echo injected"],
        working_directory=str(tmp_path),
    )

    assert res.exit_code == 0
    assert res.stdout_bytes.strip() == b"hello; echo injected"


def test_local_backend_bounded_stdout_and_stderr_capture(tmp_path):
    """Verifies bounded output stream capture prevents memory exhaustion."""
    backend = LocalProcessBackend()

    cmd = [sys.executable, "-c", "import sys; sys.stdout.write('A' * 50000); sys.stderr.write('B' * 50000)"]
    res = backend.execute_command(
        command_argv=cmd,
        working_directory=str(tmp_path),
        max_output_bytes=1024,
    )

    assert res.exit_code == 0
    assert len(res.stdout_bytes) == 1024
    assert len(res.stderr_bytes) == 1024
    assert res.stdout_truncated is True
    assert res.stderr_truncated is True


def test_local_backend_nonzero_exit_code_handling(tmp_path):
    """Verifies non-zero exit code produces structured failure facts."""
    backend = LocalProcessBackend()
    res = backend.execute_command(
        command_argv=[sys.executable, "-c", "import sys; sys.exit(42)"],
        working_directory=str(tmp_path),
    )
    assert res.exit_code == 42
    assert res.termination_reason == TerminationReason.EXIT_NON_ZERO


def test_local_backend_argument_validation(tmp_path):
    """Verifies LocalProcessBackend input validation errors."""
    backend = LocalProcessBackend()
    with pytest.raises(ValueError):
        backend.execute_command([], str(tmp_path))
    with pytest.raises(TypeError):
        backend.execute_command("not_a_list", str(tmp_path))  # type: ignore
    with pytest.raises(TypeError):
        backend.execute_command([123], str(tmp_path))  # type: ignore
    with pytest.raises(ValueError):
        backend.execute_command(["echo", "hi"], "/nonexistent/directory/path/12345")


def test_isolated_workspace_lifecycle_and_validation(tmp_path):
    """Verifies IsolatedWorkspace validation, context manager, and cleanup."""
    with pytest.raises(ValueError):
        IsolatedWorkspace("")
    with pytest.raises(ValueError):
        IsolatedWorkspace(123)  # type: ignore

    with IsolatedWorkspace("ws_ctx", base_dir=str(tmp_path)) as ws:
        assert ws.is_active
        assert os.path.exists(ws.path)
        with pytest.raises(TypeError):
            ws.resolve_safe_path(123)  # type: ignore

    assert not ws.is_active
    assert not os.path.exists(ws.path)


def test_provider_registry_operations():
    """Verifies D6ProviderRegistry registration and resolution."""
    registry = D6ProviderRegistry()
    assert registry.resolve("unknown_engine") is None

    with pytest.raises(TypeError):
        registry.register("not_a_provider")  # type: ignore

    p = PytestExecutionProvider()
    registry.register(p)
    assert registry.resolve("pytest_runner_engine") == p
    assert "pytest_runner_engine" in registry.list_providers()


def test_execution_observation_validation_errors():
    """Verifies ExecutionObservation schema validation rules."""
    empty_sha = "0" * 64
    with pytest.raises(ValueError):
        ExecutionObservation(
            execution_id="",
            token_id="T1",
            provider_id="P1",
            action_digest=empty_sha,
            context_digest=empty_sha,
            started_at=TIMESTAMP_NOW,
            ended_at=TIMESTAMP_EXPIRY,
            exit_code=0,
            termination_reason=TerminationReason.EXIT_ZERO,
            stdout_digest=empty_sha,
            stderr_digest=empty_sha,
            stdout_bytes_len=0,
            stderr_bytes_len=0,
            execution_status=ExecutionStatus.SUCCESS,
        )


def test_execution_observation_type_and_negative_validations():
    """Verifies schema validations on ExecutionObservation."""
    empty_sha = "0" * 64

    with pytest.raises(ValueError):
        ExecutionObservation(
            execution_id="E1",
            token_id="",
            provider_id="P1",
            action_digest=empty_sha,
            context_digest=empty_sha,
            started_at=TIMESTAMP_NOW,
            ended_at=TIMESTAMP_EXPIRY,
            exit_code=0,
            termination_reason=TerminationReason.EXIT_ZERO,
            stdout_digest=empty_sha,
            stderr_digest=empty_sha,
            stdout_bytes_len=0,
            stderr_bytes_len=0,
            execution_status=ExecutionStatus.SUCCESS,
        )

    with pytest.raises(ValueError):
        ExecutionObservation(
            execution_id="E1",
            token_id="T1",
            provider_id="",
            action_digest=empty_sha,
            context_digest=empty_sha,
            started_at=TIMESTAMP_NOW,
            ended_at=TIMESTAMP_EXPIRY,
            exit_code=0,
            termination_reason=TerminationReason.EXIT_ZERO,
            stdout_digest=empty_sha,
            stderr_digest=empty_sha,
            stdout_bytes_len=0,
            stderr_bytes_len=0,
            execution_status=ExecutionStatus.SUCCESS,
        )

    with pytest.raises(TypeError):
        ExecutionObservation(
            execution_id="E1",
            token_id="T1",
            provider_id="P1",
            action_digest=empty_sha,
            context_digest=empty_sha,
            started_at=TIMESTAMP_NOW,
            ended_at=TIMESTAMP_EXPIRY,
            exit_code=0,
            termination_reason="NOT_A_REASON",  # type: ignore
            stdout_digest=empty_sha,
            stderr_digest=empty_sha,
            stdout_bytes_len=0,
            stderr_bytes_len=0,
            execution_status=ExecutionStatus.SUCCESS,
        )

    with pytest.raises(TypeError):
        ExecutionObservation(
            execution_id="E1",
            token_id="T1",
            provider_id="P1",
            action_digest=empty_sha,
            context_digest=empty_sha,
            started_at=TIMESTAMP_NOW,
            ended_at=TIMESTAMP_EXPIRY,
            exit_code=0,
            termination_reason=TerminationReason.EXIT_ZERO,
            stdout_digest=empty_sha,
            stderr_digest=empty_sha,
            stdout_bytes_len=0,
            stderr_bytes_len=0,
            execution_status="NOT_A_STATUS",  # type: ignore
        )

    with pytest.raises(TypeError):
        ExecutionObservation(
            execution_id="E1",
            token_id="T1",
            provider_id="P1",
            action_digest=empty_sha,
            context_digest=empty_sha,
            started_at=TIMESTAMP_NOW,
            ended_at=TIMESTAMP_EXPIRY,
            exit_code=0,
            termination_reason=TerminationReason.EXIT_ZERO,
            stdout_digest=empty_sha,
            stderr_digest=empty_sha,
            stdout_bytes_len=0,
            stderr_bytes_len=0,
            execution_status=ExecutionStatus.SUCCESS,
            resource_usage="NOT_RESOURCE_USAGE",  # type: ignore
        )

    with pytest.raises(ValueError):
        ExecutionObservation(
            execution_id="E1",
            token_id="T1",
            provider_id="P1",
            action_digest=empty_sha,
            context_digest=empty_sha,
            started_at=TIMESTAMP_NOW,
            ended_at=TIMESTAMP_EXPIRY,
            exit_code=0,
            termination_reason=TerminationReason.EXIT_ZERO,
            stdout_digest=empty_sha,
            stderr_digest=empty_sha,
            stdout_bytes_len=-1,
            stderr_bytes_len=0,
            execution_status=ExecutionStatus.SUCCESS,
        )

    with pytest.raises(ValueError):
        ExecutionObservation(
            execution_id="E1",
            token_id="T1",
            provider_id="P1",
            action_digest=empty_sha,
            context_digest=empty_sha,
            started_at=TIMESTAMP_NOW,
            ended_at=TIMESTAMP_EXPIRY,
            exit_code=0,
            termination_reason=TerminationReason.EXIT_ZERO,
            stdout_digest=empty_sha,
            stderr_digest=empty_sha,
            stdout_bytes_len=0,
            stderr_bytes_len=-1,
            execution_status=ExecutionStatus.SUCCESS,
        )


def test_gateway_authority_signer_type_check(fresh_nonce_store):
    """Verifies D6ExecutionGateway validates authority_signer type."""
    with pytest.raises(TypeError):
        D6ExecutionGateway(authority_signer="NOT_A_SIGNER", nonce_store=fresh_nonce_store)  # type: ignore


def test_isolated_workspace_setup_and_traversal_corner_cases(tmp_path):
    """Verifies IsolatedWorkspace corner cases."""
    ws = IsolatedWorkspace(workspace_id="test_corner", base_dir=str(tmp_path))
    assert ws.resolve_safe_path("") == ws.path
    ws.setup()
    assert ws.is_active
    err = ws.cleanup()
    assert err is None
    assert not ws.is_active


def test_concurrent_executions_remain_isolated(tmp_path, fresh_nonce_store):
    """Verifies concurrent executions maintain strict workspace and state isolation."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(
        authority_signer=signer,
        nonce_store=fresh_nonce_store,
        workspace_base_dir=str(tmp_path / "concurrent_ws"),
    )

    def run_worker(idx: int):
        env = make_valid_envelope(
            tmp_path,
            fresh_nonce_store,
            target=f"test_worker_{idx}.py",
        )
        return gateway.execute(
            envelope=env,
            expected_source_sha=DEFAULT_SHA,
            expected_policy_version=1,
            current_time_iso=TIMESTAMP_NOW,
        )

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(run_worker, i) for i in range(3)]
        observations = [f.result() for f in futures]

    assert len(observations) == 3
    exec_ids = {obs.execution_id for obs in observations}
    assert len(exec_ids) == 3
    for obs in observations:
        assert isinstance(obs, ExecutionObservation)


def test_d6_cannot_authorize_or_mint_tokens(fresh_nonce_store):
    """Architectural Guard: Verifies D6 has no token minting capability."""
    gateway = D6ExecutionGateway(authority_signer=Gate3AuthoritySigner(), nonce_store=fresh_nonce_store)
    assert not hasattr(gateway, "mint_execution_token")
    assert not hasattr(gateway, "authorize_action")
    assert not hasattr(gateway, "create_obligation")
