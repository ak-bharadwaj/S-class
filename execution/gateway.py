"""
S-Class EOS V11.2 - D6 Main Execution Gateway (§8.1, §8.3).
Consumes D5 ExecutionEnvelope, enforces gateway gate checks, resolves provider,
allocates isolated workspace, executes via ExecutionBackend, and produces immutable ExecutionObservation.
"""

from __future__ import annotations
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, Mapping, Any
from controller.token import ExecutionEnvelope, verify_execution_envelope
from policy.models import AuthoritySignerProtocol
from events.store import D2NonceStore
from execution.models import (
    ExecutionStatus,
    TerminationReason,
    ResourceUsage,
    ExecutionObservation,
)
from execution.workspace import IsolatedWorkspace
from execution.backend import ExecutionBackend
from execution.local_backend import LocalProcessBackend
from execution.provider import D6ProviderRegistry, D6ExecutionProvider
from execution.adapters.pytest_adapter import PytestExecutionProvider


class D6ExecutionGateway:
    """Authoritative D6 Execution Gateway."""

    def __init__(
        self,
        authority_signer: AuthoritySignerProtocol,
        nonce_store: D2NonceStore,
        registry: Optional[D6ProviderRegistry] = None,
        backend: Optional[ExecutionBackend] = None,
        workspace_base_dir: Optional[str] = None,
    ):
        if not isinstance(authority_signer, AuthoritySignerProtocol):
            raise TypeError("authority_signer must implement AuthoritySignerProtocol.")
        if not isinstance(nonce_store, D2NonceStore):
            raise TypeError("nonce_store must be an explicit, valid D2NonceStore instance (authoritative dependency required).")
        self._authority_signer = authority_signer
        self._nonce_store = nonce_store
        self._registry = registry or D6ProviderRegistry()
        self._backend = backend or LocalProcessBackend()
        self._workspace_base_dir = workspace_base_dir

        # Auto-register default pytest provider if not present
        if not self._registry.resolve("pytest_runner_engine"):
            self._registry.register(PytestExecutionProvider())

    def execute(
        self,
        envelope: ExecutionEnvelope,
        expected_source_sha: str,
        expected_policy_version: int,
        current_time_iso: str,
        timeout_seconds: float = 30.0,
        max_output_bytes: int = 1048576,
    ) -> ExecutionObservation:
        """Executes an action given an authentic ExecutionEnvelope.
        
        Gateway Gate Steps:
        1. Pure verification of envelope (token/admission/action/context equality, signatures, time validity, D2 ADMIT:<nonce>).
        2. Resolve provider from authorized provider_id.
        3. Verify provider supports action_type.
        4. Verify authorized capability_set satisfies provider required_capabilities.
        5. Setup IsolatedWorkspace under workspace_id.
        6. Build argv command from provider (with workspace containment check).
        7. Execute command on ExecutionBackend.
        8. Compute stdout/stderr SHA-256 digests and construct immutable ExecutionObservation.
        9. Cleanup workspace deterministically on all exit paths, capturing cleanup status.
        """
        exec_id = f"EXEC-{uuid.uuid4().hex[:12].upper()}"
        started_at = datetime.now(timezone.utc).isoformat()

        # Step 1: Envelope Verification (Fail-Closed)
        if not isinstance(envelope, ExecutionEnvelope):
            return self._make_rejected_observation(
                exec_id=exec_id,
                token_id="UNKNOWN",
                provider_id="UNKNOWN",
                action_digest="0" * 64,
                context_digest="0" * 64,
                started_at=started_at,
                reason=TerminationReason.ENVELOPE_INVALID,
                diag_msg="Invalid ExecutionEnvelope instance provided.",
            )

        token = envelope.token
        admission = envelope.admission
        action_binding = envelope.action_binding
        ctx = envelope.execution_context

        is_valid_env = verify_execution_envelope(
            envelope=envelope,
            expected_source_sha=expected_source_sha,
            expected_policy_version=expected_policy_version,
            current_time_iso=current_time_iso,
            authority_signer=self._authority_signer,
            nonce_store=self._nonce_store,
        )
        if not is_valid_env:
            return self._make_rejected_observation(
                exec_id=exec_id,
                token_id=token.token_id,
                provider_id=ctx.provider_id,
                action_digest=token.action_digest,
                context_digest=token.context_digest,
                started_at=started_at,
                reason=TerminationReason.ENVELOPE_INVALID,
                diag_msg="ExecutionEnvelope cryptographic, binding, or durable admission verification failed.",
            )

        # Step 2: Provider Resolution
        provider = self._registry.resolve(ctx.provider_id)
        if not provider:
            return self._make_rejected_observation(
                exec_id=exec_id,
                token_id=token.token_id,
                provider_id=ctx.provider_id,
                action_digest=token.action_digest,
                context_digest=token.context_digest,
                started_at=started_at,
                reason=TerminationReason.UNAUTHORIZED_PROVIDER,
                diag_msg=f"Provider '{ctx.provider_id}' is not registered or authorized.",
            )

        # Step 3: Action Type Compatibility Check
        if action_binding.action_type not in provider.supported_action_types:
            return self._make_rejected_observation(
                exec_id=exec_id,
                token_id=token.token_id,
                provider_id=ctx.provider_id,
                action_digest=token.action_digest,
                context_digest=token.context_digest,
                started_at=started_at,
                reason=TerminationReason.ENVELOPE_INVALID,
                diag_msg=f"Action type '{action_binding.action_type}' not supported by provider '{provider.provider_id}'.",
            )

        # Step 4: Capability Set Check
        granted_caps = set(ctx.capability_set)
        for req_cap in provider.required_capabilities:
            if req_cap not in granted_caps:
                return self._make_rejected_observation(
                    exec_id=exec_id,
                    token_id=token.token_id,
                    provider_id=ctx.provider_id,
                    action_digest=token.action_digest,
                    context_digest=token.context_digest,
                    started_at=started_at,
                    reason=TerminationReason.CAPABILITY_VIOLATION,
                    diag_msg=f"Required capability '{req_cap}' not present in authorized capability_set {ctx.capability_set}.",
                )

        # Step 5: Isolated Workspace Setup & Process Execution
        workspace = IsolatedWorkspace(workspace_id=ctx.workspace_id, base_dir=self._workspace_base_dir)
        cleanup_warning = None
        try:
            workspace.setup()

            # Step 6: Build argv command with workspace containment verification
            try:
                cmd_argv = provider.build_command(action_binding, workspace, ctx)
            except ValueError as ve:
                return self._make_rejected_observation(
                    exec_id=exec_id,
                    token_id=token.token_id,
                    provider_id=ctx.provider_id,
                    action_digest=token.action_digest,
                    context_digest=token.context_digest,
                    started_at=started_at,
                    reason=TerminationReason.PATH_ESCAPE_DETECTED,
                    diag_msg=f"Provider build_command rejected path: {str(ve)}",
                )

            # Step 7: Execute via Backend
            res = self._backend.execute_command(
                command_argv=cmd_argv,
                working_directory=workspace.path,
                timeout_seconds=timeout_seconds,
                max_output_bytes=max_output_bytes,
            )

            # Step 8: Build Immutable Observation
            stdout_digest = hashlib.sha256(res.stdout_bytes).hexdigest()
            stderr_digest = hashlib.sha256(res.stderr_bytes).hexdigest()
            status = ExecutionStatus.SUCCESS if res.exit_code == 0 else (
                ExecutionStatus.TIMEOUT if res.termination_reason == TerminationReason.TIMEOUT_EXPIRED else ExecutionStatus.FAILURE
            )

            diag = []
            if res.error_message:
                diag.append({"error": res.error_message})
            if res.stdout_truncated:
                diag.append({"warning": f"stdout truncated at {max_output_bytes} bytes"})
            if res.stderr_truncated:
                diag.append({"warning": f"stderr truncated at {max_output_bytes} bytes"})

            # Clean workspace before final observation assembly to include cleanup issues if any
            cleanup_err = workspace.cleanup()
            if cleanup_err:
                diag.append({"cleanup_warning": cleanup_err})

            return ExecutionObservation(
                execution_id=exec_id,
                token_id=token.token_id,
                provider_id=provider.provider_id,
                action_digest=token.action_digest,
                context_digest=token.context_digest,
                started_at=res.started_at,
                ended_at=res.ended_at,
                exit_code=res.exit_code,
                termination_reason=res.termination_reason,
                stdout_digest=stdout_digest,
                stderr_digest=stderr_digest,
                stdout_bytes_len=len(res.stdout_bytes),
                stderr_bytes_len=len(res.stderr_bytes),
                execution_status=status,
                resource_usage=res.resource_usage,
                raw_stdout_sample=res.stdout_bytes[:1024].decode("utf-8", errors="replace"),
                raw_stderr_sample=res.stderr_bytes[:1024].decode("utf-8", errors="replace"),
                diagnostics=tuple(diag),
            )

        except Exception as e:
            return self._make_rejected_observation(
                exec_id=exec_id,
                token_id=token.token_id,
                provider_id=ctx.provider_id,
                action_digest=token.action_digest,
                context_digest=token.context_digest,
                started_at=started_at,
                reason=TerminationReason.WORKSPACE_ERROR,
                diag_msg=f"Execution failed during workspace setup or command execution: {str(e)}",
            )
        finally:
            # Step 9: Workspace cleanup on all exit paths
            if workspace.is_active:
                workspace.cleanup()

    def _make_rejected_observation(
        self,
        exec_id: str,
        token_id: str,
        provider_id: str,
        action_digest: str,
        context_digest: str,
        started_at: str,
        reason: TerminationReason,
        diag_msg: str,
    ) -> ExecutionObservation:
        ended_at = datetime.now(timezone.utc).isoformat()
        empty_digest = hashlib.sha256(b"").hexdigest()
        return ExecutionObservation(
            execution_id=exec_id,
            token_id=token_id,
            provider_id=provider_id,
            action_digest=action_digest,
            context_digest=context_digest,
            started_at=started_at,
            ended_at=ended_at,
            exit_code=-1,
            termination_reason=reason,
            stdout_digest=empty_digest,
            stderr_digest=empty_digest,
            stdout_bytes_len=0,
            stderr_bytes_len=0,
            execution_status=ExecutionStatus.GATEWAY_REJECTED,
            resource_usage=ResourceUsage(),
            raw_stdout_sample="",
            raw_stderr_sample="",
            diagnostics=({"gateway_rejection": diag_msg},),
        )
