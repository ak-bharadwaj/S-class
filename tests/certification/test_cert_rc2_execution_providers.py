"""
Certification Suite: Reality Closure RC.2 (Execution Provider Closure & Sandboxing).

Certifies:
1. Abstract Interface Decoupling: ExecutionProvider formalizes contract (execute, inspect_capabilities, health_check)
   decoupling policy from low-level execution mechanisms.
2. NativeProcessProvider Deterministic Host Baseline: Executes real host processes, emits canonical Observation
   and cryptographically anchored ObservedReceipt into LocalLedger.
3. Fail-Closed Authorization Gating (L3 & L8): All execution paths strictly gate on S-Class authorization;
   denied or unauthorized actions fail closed before process invocation.
4. Isolated Provider Fail-Closed Semantics: BubblewrapProvider, OCIProvider, GVisorProvider, DaggerProvider,
   and IsolatedSandboxProvider enforce NO SANDBOX -> NO SANDBOXED EXECUTION (zero uncontained host degradation).
5. ExecutionProviderRegistry Fail-Closed Resolution: Registry rejects unknown providers and enforces isolation constraints.
6. Epistemic Provenance & Dependency Invalidation (L5, L6, L7): Independent observation captures authentic
   PID, stdout/stderr hashes, and workspace fingerprints; post-execution workspace mutation invalidates dependent receipts.
7. Execution Bypass Audit: Backend and observer entry points eliminate authorization bypass vectors.
"""

import os
import sys
import pytest
from typing import Dict, Any, List

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import CAP_TERMINAL_EXECUTE
from sclass.execution.base import (
    ExecutionProvider,
    ProviderCapabilities,
    ProviderHealth,
    ProviderExecutionResult,
)
from sclass.execution.native import NativeProcessProvider
from sclass.execution.isolated import (
    BubblewrapProvider,
    OCIProvider,
    GVisorProvider,
    DaggerProvider,
    IsolatedSandboxProvider,
)
from sclass.execution.registry import (
    ExecutionProviderRegistry,
    get_provider_registry,
    reset_provider_registry,
    get_execution_provider,
)
from sclass.execution.backend import HostProcessBackend, SandboxBackend
from sclass.execution.modes import ExecutionMode
from sclass.observation.observer import observe_command
from sclass.trust.ledger import LocalLedger
from sclass.core.errors import SecurityViolationError


def test_rc2_execution_provider_abstract_interface():
    """Certifies that ExecutionProvider abstract contract cannot be instantiated directly without implementations."""
    with pytest.raises(TypeError):
        ExecutionProvider()  # type: ignore

    # Subclass missing abstract methods must also fail
    class IncompleteProvider(ExecutionProvider):
        @property
        def name(self) -> str:
            return "incomplete"

    with pytest.raises(TypeError):
        IncompleteProvider()  # type: ignore


def test_rc2_native_process_provider_determinism_and_observation(tmp_path):
    """
    Certifies NativeProcessProvider executes real host commands, returning authentic exit code,
    stdout/stderr, canonical Observation, and cryptographically anchored ObservedReceipt.
    """
    ws = tmp_path / "native_ws"
    ws.mkdir()

    provider = NativeProcessProvider()
    assert provider.name == "native"
    assert provider.provider_type == "host"
    assert provider.is_available() is True

    # 1. Health check & Capabilities
    health = provider.health_check()
    assert health.is_healthy is True
    assert health.status == "healthy"
    assert health.latency_ms >= 0.0

    caps = provider.inspect_capabilities()
    assert caps.provider_name == "native"
    assert caps.provider_type == "host"
    assert caps.network_isolation is False
    assert "host_argv" in caps.supported_modes

    # 2. Authoritative Execution
    ledger = LocalLedger(workspace_dir=str(ws))
    cmd = [sys.executable, "-c", "print('sclass_native_ok')"]
    req = ActionRequest(
        actor="codex_agent",
        session="sess_native_001",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target=f"{sys.executable} -c \"print('sclass_native_ok')\"",
        workspace=str(ws),
    )

    res: ProviderExecutionResult = provider.execute(
        command=cmd,
        cwd=str(ws),
        request=req,
        ledger=ledger,
    )

    # 3. Verify execution reality
    assert res.success is True
    assert res.exit_code == 0
    assert "sclass_native_ok" in res.stdout
    assert res.pid > 0
    assert res.duration_ms > 0.0

    # 4. Verify canonical Observation
    obs = res.observation
    assert obs.observation_id == res.evidence_receipt.receipt_id
    assert obs.exit_code == 0
    assert len(obs.stdout_hash) == 64
    assert obs.compute_hash() is not None

    # 5. Verify cryptographically sealed ObservedReceipt in LocalLedger
    receipt = res.evidence_receipt
    assert receipt.receipt_id is not None
    assert receipt.is_observed is True
    assert receipt.exit_code == 0
    assert ledger.verify_chain() is True

    # 6. Verify Windows backslash path execution without stripping path separators
    script_file = ws / "sub dir" / "test_target.py"
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_file.write_text("print('path_execution_success')\n", encoding="utf-8")

    backslash_cmd = f'{sys.executable} "{script_file}"'
    res_path = provider.execute(command=backslash_cmd, cwd=str(ws), ledger=ledger)
    assert res_path.success is True
    assert "path_execution_success" in res_path.stdout


def test_rc2_fail_closed_authorization_gate(tmp_path):
    """
    Certifies that ANY command attempting prohibited actions (e.g. secret leakage,
    protected directory tampering) fails closed immediately at the authorization gate
    BEFORE low-level process invocation.
    """
    ws = tmp_path / "auth_gate_ws"
    ws.mkdir()

    provider = NativeProcessProvider()
    ledger = LocalLedger(workspace_dir=str(ws))

    # Prohibited target: tampering with .agents/ internal trust ledger
    forbidden_cmd = "rm -rf .agents/ledger"
    req = ActionRequest(
        actor="untrusted_agent",
        session="sess_attack_001",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target=forbidden_cmd,
        parameters={"command": forbidden_cmd},
        workspace=str(ws),
    )

    # Execution MUST raise SecurityViolationError
    with pytest.raises(SecurityViolationError) as excinfo:
        provider.execute(
            command=forbidden_cmd,
            cwd=str(ws),
            request=req,
            ledger=ledger,
        )

    assert "policy" in str(excinfo.value).lower() or "violation" in str(excinfo.value).lower()


def test_rc2_isolated_providers_fail_closed_semantics(tmp_path):
    """
    Certifies that isolated providers (Bubblewrap, OCI, gVisor, Dagger) strictly adhere
    to NO SANDBOX -> NO SANDBOXED EXECUTION: if the runtime is unavailable, execution fails closed
    rather than silently degrading to uncontained host execution.
    """
    ws = tmp_path / "isolated_ws"
    ws.mkdir()

    # 1. Bubblewrap provider
    bwrap_p = BubblewrapProvider()
    assert bwrap_p.provider_type == "sandbox"
    b_caps = bwrap_p.inspect_capabilities()
    assert b_caps.network_isolation is True
    assert b_caps.filesystem_isolation is True

    if not bwrap_p.is_available():
        h = bwrap_p.health_check()
        assert h.status == "unavailable"
        assert h.is_healthy is False

        with pytest.raises(SecurityViolationError) as excinfo:
            bwrap_p.execute(
                command="echo isolation_test",
                cwd=str(ws),
            )
        assert "NO SANDBOX -> NO SANDBOXED EXECUTION" in str(excinfo.value)

    # 2. gVisor provider
    gvisor_p = GVisorProvider()
    assert gvisor_p.provider_type == "virtualized"
    g_caps = gvisor_p.inspect_capabilities()
    assert g_caps.network_isolation is True
    assert g_caps.filesystem_isolation is True

    if not gvisor_p.is_available():
        h = gvisor_p.health_check()
        assert h.status == "unavailable"
        assert h.is_healthy is False

        with pytest.raises(SecurityViolationError) as excinfo:
            gvisor_p.execute(
                command="echo gvisor_test",
                cwd=str(ws),
            )
        assert "NO SANDBOX -> NO SANDBOXED EXECUTION" in str(excinfo.value)

    # 3. OCI Container provider (Docker/Podman)
    oci_p = OCIProvider()
    assert oci_p.provider_type == "container"
    o_caps = oci_p.inspect_capabilities()
    assert o_caps.network_isolation is True
    assert o_caps.filesystem_isolation is True

    if not oci_p.is_available():
        h = oci_p.health_check()
        assert h.status == "unavailable"
        assert h.is_healthy is False
        assert "daemon_running" in h.details or "reason" in h.details

        with pytest.raises(SecurityViolationError) as excinfo:
            oci_p.execute(
                command="echo oci_test",
                cwd=str(ws),
            )
        assert "NO SANDBOX -> NO SANDBOXED EXECUTION" in str(excinfo.value)

    # 4. Dagger provider
    dagger_p = DaggerProvider()
    assert dagger_p.provider_type == "reproducible_pipeline"
    d_caps = dagger_p.inspect_capabilities()
    assert d_caps.network_isolation is True

    if not dagger_p.is_available():
        h = dagger_p.health_check()
        assert h.status == "unavailable"
        assert h.is_healthy is False

        with pytest.raises(SecurityViolationError) as excinfo:
            dagger_p.execute(
                command="echo dagger_test",
                cwd=str(ws),
            )
        assert "NO SANDBOX -> NO SANDBOXED EXECUTION" in str(excinfo.value)

    # 5. Unified IsolatedSandboxProvider (auto and backend-specific)
    sandbox_auto = IsolatedSandboxProvider()
    if not sandbox_auto.is_available():
        with pytest.raises(SecurityViolationError) as excinfo:
            sandbox_auto.execute(
                command="echo sandbox_auto_test",
                cwd=str(ws),
            )
        assert "NO SANDBOX -> NO SANDBOXED EXECUTION" in str(excinfo.value)

    sandbox_p = IsolatedSandboxProvider(preferred_backend="gvisor")
    if not sandbox_p.is_available():
        with pytest.raises(SecurityViolationError):
            sandbox_p.execute(
                command="echo sandbox_test",
                cwd=str(ws),
            )


def test_rc2_execution_provider_registry_resolution_and_fail_closed():
    """
    Certifies ExecutionProviderRegistry:
    - Registers canonical providers (native, bubblewrap, oci, gvisor, dagger, sandbox)
    - Rejects unknown providers fail-closed with SecurityViolationError
    - Enforces require_isolation flag by rejecting uncontained host providers.
    """
    registry = reset_provider_registry()

    # 1. Canonical provider lookup
    assert registry.has("native") is True
    assert registry.has("host") is True
    assert registry.has("oci") is True
    assert registry.has("container") is True
    assert registry.has("bubblewrap") is True
    assert registry.has("bwrap") is True
    assert registry.has("gvisor") is True
    assert registry.has("dagger") is True
    assert registry.has("sandbox") is True

    native_p = registry.get("native")
    assert isinstance(native_p, NativeProcessProvider)

    # 2. Unknown provider resolution fails closed
    with pytest.raises(SecurityViolationError) as exc:
        registry.get("untrusted_custom_sandbox_v99")
    assert "UNKNOWN PROVIDER -> NO EXECUTION" in str(exc.value)

    # 3. Isolation enforcement
    # Requesting native when isolation is mandatory must fail closed
    with pytest.raises(SecurityViolationError) as exc:
        registry.resolve(name="native", require_isolation=True)
    assert "INSUFFICIENT ISOLATION" in str(exc.value)

    # 4. Capabilities & Health diagnostics
    all_caps = registry.inspect_all()
    assert "native" in all_caps
    assert "oci" in all_caps
    assert "bubblewrap" in all_caps

    all_health = registry.health_check_all()
    assert "native" in all_health
    assert all_health["native"]["status"] == "healthy"


def test_rc2_observation_provenance_and_workspace_invalidation(tmp_path):
    """
    Certifies Invariant L5 (Evidence has provenance), L6 (Durable truth depends on evidence),
    and L7 (Relevant mutation invalidates dependent evidence).
    """
    ws = tmp_path / "provenance_ws"
    ws.mkdir()
    target_file = ws / "module.py"
    target_file.write_text("INITIAL_STATE = True\n", encoding="utf-8")

    provider = NativeProcessProvider()
    ledger = LocalLedger(workspace_dir=str(ws))

    # Execute observed command that modifies module.py
    cmd = [sys.executable, "-c", "with open('module.py', 'a') as f: f.write('OBSERVED_STEP = 1\\n')"]
    res = provider.execute(
        command=cmd,
        cwd=str(ws),
        ledger=ledger,
    )

    receipt = res.evidence_receipt
    assert receipt.is_observed is True
    # Initial state after observation matches fingerprint
    valid, reason = receipt.validate_dependencies(str(ws))
    assert valid is True
    assert reason is None

    # Mutate workspace post-observation
    target_file.write_text("TAMPERED_CONTENT_AFTER_OBSERVATION\n", encoding="utf-8")

    # Invariant L7: mutation invalidates dependent evidence
    valid_after, reason_after = receipt.validate_dependencies(str(ws))
    assert valid_after is False
    assert "Workspace mutation detected" in str(reason_after)


def test_rc2_execution_bypass_elimination_audit(tmp_path):
    """
    Audits execution entry points (HostProcessBackend, SandboxBackend, observe_command)
    to certify that passing a denied ActionRequest fails closed without running subprocess.
    """
    ws = tmp_path / "bypass_audit_ws"
    ws.mkdir()

    denied_req = ActionRequest(
        actor="rogue_agent",
        session="sess_bypass_001",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="rm -rf .agents/ledger",
        workspace=str(ws),
    )

    # 1. HostProcessBackend must fail closed
    host_backend = HostProcessBackend()
    with pytest.raises(SecurityViolationError):
        host_backend.execute(
            command="rm -rf .agents/ledger",
            cwd=str(ws),
            request=denied_req,
        )

    # 2. SandboxBackend must fail closed
    sb_backend = SandboxBackend(backend_type="host")
    with pytest.raises(SecurityViolationError):
        sb_backend.execute(
            command="rm -rf .agents/ledger",
            cwd=str(ws),
            request=denied_req,
        )

    # 3. observe_command with request must fail closed
    with pytest.raises(SecurityViolationError):
        observe_command(
            command="rm -rf .agents/ledger",
            workspace_dir=str(ws),
            request=denied_req,
        )


def test_rc2_ledger_append_atomic_backward_compatibility_with_legacy_signatures(tmp_path):
    """
    Certifies that LocalLedger.append_atomic() and verify_integrity() gracefully handle
    legacy ledger records containing 'signature' instead of 'hash', preventing KeyError: 'hash'.
    """
    import json
    ws = tmp_path / "legacy_ledger_ws"
    ws.mkdir()
    ledger = LocalLedger(workspace_dir=str(ws))

    # Simulate legacy genesis entry with signature
    legacy_entry = {
        "sequence": 1,
        "event": "legacy_genesis",
        "previous_hash": "0" * 64,
        "payload_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "timestamp": "2026-09-14T00:00:00.000000+00:00",
        "signature": "37199002c414fab5ee6035e0da997ce46d58d08d4b50b76df6ee6c8a68606ffd",
        "payload": {"legacy_field": "test"},
    }
    with open(ledger.ledger_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(legacy_entry) + "\n")

    # Appending atomic observation onto legacy entry MUST succeed without KeyError: 'hash'
    new_entry = ledger.append_atomic("OBSERVATION", {"observed_step": 1})
    assert new_entry["sequence"] == 2
    assert new_entry["previous_hash"] == "37199002c414fab5ee6035e0da997ce46d58d08d4b50b76df6ee6c8a68606ffd"
    assert "hash" in new_entry
    assert len(new_entry["hash"]) == 64

