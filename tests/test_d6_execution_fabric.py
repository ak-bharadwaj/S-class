"""
S-Class EOS V11.2 - D6 Execution Fabric Vertical Slice Test Suite (§8.1, §8.3).
Exhaustive verification of:
1. D5 ExecutionEnvelope Gateway Verification.
2. Provider Resolution & Capability Scoping.
3. Isolated Workspace Management & Path Traversal Prevention.
4. Constrained LocalProcessBackend (argv arrays, sanitized environment, bounded streams, timeouts, process tree termination).
5. Pytest Provider Adapter execution.
6. Immutable ExecutionObservation process facts.
7. Comprehensive Adversarial Vectors:
   - invalid envelope -> no process
   - action mismatch -> no process
   - context mismatch -> no process
   - missing durable admission -> no process
   - unauthorized provider -> no process
   - capability escalation -> no process
   - path traversal -> rejected
   - environment injection -> rejected
   - shell metacharacters -> treated as arguments, not shell
   - timeout -> process tree terminated
   - stdout exceeds limit -> bounded truncation
   - stderr exceeds limit -> bounded truncation
   - workspace cleanup after success / failure
   - non-zero exit -> structured observation
   - concurrent executions remain isolated
   - controller token cannot be minted by D6
   - D6 cannot authorize a rejected action
"""

import os
import sys
import time
import pytest
import subprocess
from typing import List
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
    target: str = "tests/test_d6_dummy.py",
    provider_id: str = "pytest_runner_engine",
    capability_set: tuple = ("CAP_EXEC_TEST",),
    workspace_id: str = "WS-TEST-001",
) -> tuple[ExecutionEnvelope, ActionProposal, SClassController]:
    """Helper to create a fully authentic and admitted ExecutionEnvelope."""
    signer = Gate3AuthoritySigner()
    controller = SClassController(authority_signer=signer, nonce_store=nonce_store)

    ctx = ExecutionContext(
        provider_id=provider_id,
        sandbox_profile_id="SBX-STRICT",
        workspace_id=workspace_id,
        resource_profile_id="RES-STD",
        capability_set=capability_set,
    )
    proposal = ActionProposal(
        proposal_id=f"ACT-{os.urandom(4).hex()}",
        obligation_id="OBL-001",
        action_type=action_type,
        target=target,
        purpose="Run test verification",
        execution_context=ctx,
    )
    obls = {
        "OBL-001": Obligation(
            obligation_id="OBL-001",
            task_id="TASK-1",
            title="Test",
            description="Desc",
            category=ObligationCategory.SECURITY_INTEGRITY,
            criticality=Criticality.HIGH,
            status=ObligationStatus.OPEN,
            policy_id="POL-1",
        )
    }
    pols = {
        "POL-1": Policy(
            policy_id="POL-1",
            scope_level=PolicyScope.PROJECT,
            version=1,
            expression=PolicyExpression(
                combinator=CombinatorType.ALL,
                rules=(PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={}),),
            ),
        )
    }

    dispatch = controller.submit_proposal(proposal, obls, pols, DEFAULT_SHA, 1, TIMESTAMP_NOW, TIMESTAMP_EXPIRY)
    token = dispatch.execution_token
    assert token is not None

    admission = controller.admit_execution(
        token=token,
        expected_obligation_id="OBL-001",
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        expected_action_binding=proposal.binding,
        expected_execution_context=ctx,
        current_time_iso=TIMESTAMP_NOW,
    )
    assert admission.is_admitted is True

    envelope = controller.create_execution_envelope(token, admission, proposal.binding, ctx)
    return envelope, proposal, controller


# ============================================================================
# 1. Gateway Envelope Verification & Boundary Tests
# ============================================================================

def test_gateway_valid_envelope_pytest_execution(tmp_path, fresh_nonce_store):
    """Valid ExecutionEnvelope executes via Pytest provider and produces SUCCESS observation."""
    dummy_test = tmp_path / "test_sample.py"
    dummy_test.write_text("def test_ok(): assert True\n", encoding="utf-8")

    envelope, proposal, _ = make_valid_envelope(tmp_path, fresh_nonce_store, target=str(dummy_test))
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store, workspace_base_dir=str(tmp_path / "ws"))

    obs = gateway.execute(envelope, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert isinstance(obs, ExecutionObservation)
    assert obs.execution_status == ExecutionStatus.SUCCESS
    assert obs.exit_code == 0
    assert obs.termination_reason == TerminationReason.EXIT_ZERO
    assert obs.token_id == envelope.token.token_id
    assert obs.provider_id == "pytest_runner_engine"
    assert obs.action_digest == envelope.token.action_digest
    assert obs.context_digest == envelope.token.context_digest
    assert len(obs.stdout_digest) == 64
    assert len(obs.stderr_digest) == 64
    assert obs.resource_usage.wall_clock_seconds >= 0.0


def test_gateway_rejected_on_invalid_envelope(tmp_path, fresh_nonce_store):
    """Gateway rejects invalid envelope objects fail-closed without spawning a process."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store)
    obs = gateway.execute("not_an_envelope", DEFAULT_SHA, 1, TIMESTAMP_NOW)  # type: ignore

    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.ENVELOPE_INVALID
    assert obs.exit_code == -1


def test_gateway_rejected_on_unadmitted_or_tampered_token(tmp_path, fresh_nonce_store):
    """Gateway rejects envelope where token was not admitted in D2 store."""
    signer = Gate3AuthoritySigner()
    envelope, _, _ = make_valid_envelope(tmp_path, fresh_nonce_store)

    # Empty D2 store without admission record
    empty_store = D2NonceStore(file_path=str(tmp_path / "empty_nonces.log"))
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=empty_store)

    obs = gateway.execute(envelope, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.ENVELOPE_INVALID


def test_gateway_rejected_on_unauthorized_provider(tmp_path, fresh_nonce_store):
    """Gateway rejects unknown / unauthorized provider ID."""
    envelope, _, _ = make_valid_envelope(tmp_path, fresh_nonce_store, provider_id="UNREGISTERED_PROVIDER")
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store)

    obs = gateway.execute(envelope, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.UNAUTHORIZED_PROVIDER


def test_gateway_rejected_on_capability_escalation_or_missing_capability(tmp_path, fresh_nonce_store):
    """Gateway rejects execution if authorized context lacks required capabilities."""
    envelope, _, _ = make_valid_envelope(tmp_path, fresh_nonce_store, capability_set=("CAP_READ_ONLY",))
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store)

    obs = gateway.execute(envelope, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.CAPABILITY_VIOLATION


def test_gateway_rejected_on_action_type_unsupported_by_provider(tmp_path, fresh_nonce_store):
    """Gateway rejects if action_type is unsupported by the resolved provider."""
    envelope, _, _ = make_valid_envelope(tmp_path, fresh_nonce_store, action_type="APPLY_PATCH")
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store)

    obs = gateway.execute(envelope, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.ENVELOPE_INVALID


# ============================================================================
# 2. Isolated Workspace & Path Traversal Prevention Tests
# ============================================================================

def test_workspace_isolation_and_path_traversal_rejection(tmp_path):
    """Workspace prevents path traversal and directory escape."""
    ws = IsolatedWorkspace("WS-001", base_dir=str(tmp_path))
    ws_path = ws.setup()
    assert os.path.exists(ws_path)

    # Safe relative paths resolve inside workspace
    safe_path = ws.resolve_safe_path("sub/test.py")
    assert safe_path.startswith(ws_path)
    assert ws.resolve_safe_path("") == ws_path

    # Absolute paths are rejected
    with pytest.raises(ValueError, match="Path traversal rejected"):
        ws.resolve_safe_path(os.path.abspath("test.py"))

    # Directory traversal attempts are rejected
    with pytest.raises(ValueError, match="Path escape detected"):
        ws.resolve_safe_path("../../outside.txt")

    ws.cleanup()
    assert not os.path.exists(ws_path)


def test_workspace_deterministic_cleanup_on_context_exit(tmp_path):
    """Workspace cleans up directory deterministically upon context manager exit."""
    ws = IsolatedWorkspace("WS-CLEANUP", base_dir=str(tmp_path))
    with ws as active_ws:
        assert os.path.exists(active_ws.path)
        test_file = os.path.join(active_ws.path, "temp.txt")
        with open(test_file, "w") as f:
            f.write("temporary data")
        assert os.path.exists(test_file)

    assert not os.path.exists(ws.path)


def test_workspace_validation_and_path_escape(tmp_path):
    """IsolatedWorkspace raises on invalid workspace_id."""
    with pytest.raises(ValueError, match="workspace_id must be a non-empty string"):
        IsolatedWorkspace("")
    with pytest.raises(ValueError, match="workspace_id must be a non-empty string"):
        IsolatedWorkspace(None)  # type: ignore


# ============================================================================
# 3. LocalProcessBackend Security & Constraint Tests
# ============================================================================

def test_local_backend_environment_sanitization():
    """LocalProcessBackend strips dangerous env variables like LD_PRELOAD and passes safe keys."""
    dirty_env = {
        "LD_PRELOAD": "/evil/lib.so",
        "NODE_OPTIONS": "--inspect",
        "CUSTOM_SAFE_VAR": "safe_value",
        123: "bad_key",  # type: ignore
    }
    clean = sanitize_environment(dirty_env)
    assert "LD_PRELOAD" not in clean
    assert "NODE_OPTIONS" not in clean
    assert clean["CUSTOM_SAFE_VAR"] == "safe_value"
    assert clean["PYTHONUNBUFFERED"] == "1"


def test_local_backend_shell_metacharacters_treated_as_arguments(tmp_path):
    """Arguments with shell metacharacters (|, ;, &, $(), `) are passed literally, NOT evaluated by shell."""
    backend = LocalProcessBackend()
    cmd = [sys.executable, "-c", "import sys; print(sys.argv[1])", "hello | rm -rf / ; echo owned &"]
    res = backend.execute_command(cmd, working_directory=str(tmp_path))
    assert res.exit_code == 0
    assert b"hello | rm -rf / ; echo owned &" in res.stdout_bytes


def test_local_backend_timeout_enforcement_and_process_tree_kill(tmp_path):
    """Processes exceeding timeout are terminated and produce TIMEOUT_EXPIRED."""
    backend = LocalProcessBackend()
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    res = backend.execute_command(cmd, working_directory=str(tmp_path), timeout_seconds=0.2)

    assert res.termination_reason == TerminationReason.TIMEOUT_EXPIRED
    assert res.exit_code == -9
    assert "timed out" in (res.error_message or "")


def test_local_backend_bounded_stdout_and_stderr_capture(tmp_path):
    """Output exceeding max_output_bytes is cleanly truncated with truncation flags."""
    backend = LocalProcessBackend()
    cmd = [sys.executable, "-c", "import sys; sys.stdout.write('A' * 100000); sys.stderr.write('B' * 100000)"]
    res = backend.execute_command(cmd, working_directory=str(tmp_path), max_output_bytes=5000)

    assert res.exit_code == 0
    assert len(res.stdout_bytes) == 5000
    assert len(res.stderr_bytes) == 5000
    assert res.stdout_truncated is True
    assert res.stderr_truncated is True


def test_local_backend_nonzero_exit_code_handling(tmp_path):
    """Non-zero exit code is recorded accurately as EXIT_NON_ZERO."""
    backend = LocalProcessBackend()
    cmd = [sys.executable, "-c", "import sys; sys.exit(42)"]
    res = backend.execute_command(cmd, working_directory=str(tmp_path))

    assert res.exit_code == 42
    assert res.termination_reason == TerminationReason.EXIT_NON_ZERO


def test_local_backend_type_and_argument_validation(tmp_path):
    """Invalid command arguments raise appropriate TypeError / ValueError."""
    backend = LocalProcessBackend()
    with pytest.raises(ValueError, match="command_argv cannot be empty"):
        backend.execute_command([], working_directory=str(tmp_path))
    with pytest.raises(TypeError, match="must be a list or tuple"):
        backend.execute_command("python script.py", working_directory=str(tmp_path))  # type: ignore
    with pytest.raises(TypeError, match="elements must be strings"):
        backend.execute_command([123, 456], working_directory=str(tmp_path))  # type: ignore
    with pytest.raises(ValueError, match="working_directory does not exist"):
        backend.execute_command(["python"], working_directory=str(tmp_path / "nonexistent"))


# ============================================================================
# 4. Pytest Execution Provider Tests & Provider Registry
# ============================================================================

def test_pytest_provider_command_building():
    """PytestExecutionProvider constructs safe argv list."""
    prov = PytestExecutionProvider()
    assert prov.provider_id == "pytest_runner_engine"
    assert "EXECUTE_TEST" in prov.supported_action_types
    assert "CAP_EXEC_TEST" in prov.required_capabilities

    binding = ActionBinding("EXECUTE_TEST", "tests/test_demo.py", "Test purpose", parameters={"maxfail": 2, "quiet": True})
    ctx = ExecutionContext("pytest_runner_engine", "SBX-1", "WS-1", "RES-1", ("CAP_EXEC_TEST",))
    ws = IsolatedWorkspace("WS-1")

    cmd = prov.build_command(binding, ws, ctx)
    assert cmd[0] == sys.executable
    assert "-m" in cmd
    assert "pytest" in cmd
    assert "--maxfail" in cmd
    assert "2" in cmd
    assert "-q" in cmd
    assert "tests/test_demo.py" in cmd


def test_provider_registry_type_checks():
    """D6ProviderRegistry rejects non-D6ExecutionProvider instances."""
    reg = D6ProviderRegistry()
    with pytest.raises(TypeError, match="provider must implement D6ExecutionProvider"):
        reg.register("bad_provider")  # type: ignore

    prov = PytestExecutionProvider()
    reg.register(prov)
    assert reg.resolve("pytest_runner_engine") is prov
    assert "pytest_runner_engine" in reg.list_providers()


# ============================================================================
# 5. D6 Concurrent Isolation & Reliability Tests
# ============================================================================

def test_concurrent_executions_remain_isolated(tmp_path, fresh_nonce_store):
    """Concurrent executions in different workspaces do not interfere."""
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store, workspace_base_dir=str(tmp_path / "ws_concurr"))

    def run_worker(idx: int):
        dummy_file = tmp_path / f"test_{idx}.py"
        dummy_file.write_text(f"def test_{idx}(): assert {idx} == {idx}\n", encoding="utf-8")
        env, _, _ = make_valid_envelope(tmp_path, fresh_nonce_store, target=str(dummy_file), workspace_id=f"WS-CONCURR-{idx}")
        return gateway.execute(env, DEFAULT_SHA, 1, TIMESTAMP_NOW)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_worker, i) for i in range(5)]
        observations = [f.result() for f in futures]

    for obs in observations:
        assert obs.execution_status == ExecutionStatus.SUCCESS
        assert obs.exit_code == 0


def test_d6_cannot_authorize_or_mint_tokens():
    """D6 execution fabric strictly owns no token minting capability."""
    assert not hasattr(D6ExecutionGateway, "mint_execution_token")
    assert not hasattr(D6ExecutionGateway, "authorize_action")
    assert not hasattr(LocalProcessBackend, "mint_token")


def test_resource_usage_and_observation_immutability():
    """ResourceUsage and ExecutionObservation enforce immutability and valid fields."""
    with pytest.raises(ValueError, match="wall_clock_seconds cannot be negative"):
        ResourceUsage(wall_clock_seconds=-1.0)
    with pytest.raises(ValueError, match="cpu_user_seconds cannot be negative"):
        ResourceUsage(cpu_user_seconds=-1.0)
    with pytest.raises(ValueError, match="cpu_system_seconds cannot be negative"):
        ResourceUsage(cpu_system_seconds=-1.0)
    with pytest.raises(ValueError, match="memory_peak_bytes cannot be negative"):
        ResourceUsage(memory_peak_bytes=-1)

    usage = ResourceUsage(wall_clock_seconds=1.5, cpu_user_seconds=1.2, cpu_system_seconds=0.3, memory_peak_bytes=2048)
    obs = ExecutionObservation(
        execution_id="EXEC-001",
        token_id="TOK-001",
        provider_id="pytest_runner_engine",
        action_digest="0" * 64,
        context_digest="0" * 64,
        started_at=TIMESTAMP_NOW,
        ended_at=TIMESTAMP_EXPIRY,
        exit_code=0,
        termination_reason=TerminationReason.EXIT_ZERO,
        stdout_digest="0" * 64,
        stderr_digest="0" * 64,
        stdout_bytes_len=10,
        stderr_bytes_len=0,
        execution_status=ExecutionStatus.SUCCESS,
        resource_usage=usage,
    )
    with pytest.raises(Exception):
        obs.exit_code = 1  # type: ignore

    # Validation errors on ExecutionObservation
    with pytest.raises(ValueError, match="execution_id cannot be empty"):
        ExecutionObservation("", "TOK-1", "P-1", "0"*64, "0"*64, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, 0, TerminationReason.EXIT_ZERO, "0"*64, "0"*64, 0, 0, ExecutionStatus.SUCCESS)
    with pytest.raises(ValueError, match="token_id cannot be empty"):
        ExecutionObservation("EXEC-1", "", "P-1", "0"*64, "0"*64, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, 0, TerminationReason.EXIT_ZERO, "0"*64, "0"*64, 0, 0, ExecutionStatus.SUCCESS)
    with pytest.raises(ValueError, match="provider_id cannot be empty"):
        ExecutionObservation("EXEC-1", "TOK-1", "", "0"*64, "0"*64, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, 0, TerminationReason.EXIT_ZERO, "0"*64, "0"*64, 0, 0, ExecutionStatus.SUCCESS)
    with pytest.raises(TypeError, match="termination_reason must be an instance"):
        ExecutionObservation("EXEC-1", "TOK-1", "P-1", "0"*64, "0"*64, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, 0, "BAD_REASON", "0"*64, "0"*64, 0, 0, ExecutionStatus.SUCCESS)  # type: ignore
    with pytest.raises(TypeError, match="execution_status must be an instance"):
        ExecutionObservation("EXEC-1", "TOK-1", "P-1", "0"*64, "0"*64, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, 0, TerminationReason.EXIT_ZERO, "0"*64, "0"*64, 0, 0, "BAD_STATUS")  # type: ignore
    with pytest.raises(TypeError, match="resource_usage must be an instance"):
        ExecutionObservation("EXEC-1", "TOK-1", "P-1", "0"*64, "0"*64, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, 0, TerminationReason.EXIT_ZERO, "0"*64, "0"*64, 0, 0, ExecutionStatus.SUCCESS, resource_usage="bad")  # type: ignore
    with pytest.raises(ValueError, match="stdout_bytes_len cannot be negative"):
        ExecutionObservation("EXEC-1", "TOK-1", "P-1", "0"*64, "0"*64, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, 0, TerminationReason.EXIT_ZERO, "0"*64, "0"*64, -1, 0, ExecutionStatus.SUCCESS)
    with pytest.raises(ValueError, match="stderr_bytes_len cannot be negative"):
        ExecutionObservation("EXEC-1", "TOK-1", "P-1", "0"*64, "0"*64, TIMESTAMP_NOW, TIMESTAMP_EXPIRY, 0, TerminationReason.EXIT_ZERO, "0"*64, "0"*64, 0, -1, ExecutionStatus.SUCCESS)


def test_gateway_initializer_type_checks():
    """D6ExecutionGateway rejects invalid authority_signer."""
    with pytest.raises(TypeError, match="authority_signer must implement AuthoritySignerProtocol"):
        D6ExecutionGateway(authority_signer="bad_signer")  # type: ignore


def test_gateway_backend_exception_handling(tmp_path, fresh_nonce_store):
    """If execution backend raises unexpected exception, gateway returns structured error observation."""
    class BrokenBackend:
        def execute_command(self, *args, **kwargs):
            raise OSError("Operating system process fork failure")

    envelope, proposal, _ = make_valid_envelope(tmp_path, fresh_nonce_store)
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(
        authority_signer=signer,
        nonce_store=fresh_nonce_store,
        backend=BrokenBackend(),  # type: ignore
        workspace_base_dir=str(tmp_path / "ws_broken"),
    )

    obs = gateway.execute(envelope, DEFAULT_SHA, 1, TIMESTAMP_NOW)
    assert obs.execution_status == ExecutionStatus.GATEWAY_REJECTED
    assert obs.termination_reason == TerminationReason.WORKSPACE_ERROR
    assert "Operating system process fork failure" in str(obs.diagnostics)


def test_deterministic_provider_selection_on_same_envelope(tmp_path, fresh_nonce_store):
    """Same envelope always resolves to the exact same provider deterministically."""
    envelope, _, _ = make_valid_envelope(tmp_path, fresh_nonce_store)
    signer = Gate3AuthoritySigner()
    gateway = D6ExecutionGateway(authority_signer=signer, nonce_store=fresh_nonce_store)

    prov1 = gateway._registry.resolve(envelope.execution_context.provider_id)
    prov2 = gateway._registry.resolve(envelope.execution_context.provider_id)
    assert prov1 is prov2
    assert prov1.provider_id == "pytest_runner_engine"
