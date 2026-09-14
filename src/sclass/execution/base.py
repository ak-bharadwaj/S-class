"""
S-Class Execution: Execution Provider Base Abstraction.
Decouples execution policy from execution mechanisms (host, sandbox, OCI container, gVisor, Dagger).
All execution paths emit canonical Observation and ObservedReceipt with cryptographic provenance.
All execution requests are gated by S-Class authorization (L3 & L8).
"""

from __future__ import annotations
import os
import sys
import time
import shlex
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from sclass.domain.action import ActionRequest, AuthorizationDecision
    from sclass.domain.capability import Capability
    from sclass.domain.evidence import ObservedReceipt
    from sclass.domain.observation import Observation
    from sclass.trust.ledger import LocalLedger
    from sclass.observation.record import ObservationRecord

from sclass.execution.modes import (
    ExecutionMode,
    ExecutionPolicy,
    check_protected_resource_targeting,
)
from sclass.execution.process import ProcessExecutionResult
from sclass.core.errors import SecurityViolationError, ObservationIntegrityError


def split_command(cmd_str: str) -> List[str]:
    """
    Platform-aware command tokenizer.
    On Windows (nt), preserves directory path backslashes while respecting quotes.
    On POSIX, uses standard POSIX shell escaping.
    Strictly fails closed with SecurityViolationError on unparseable quotes or syntax.
    """
    if not cmd_str or not cmd_str.strip():
        return []
    if os.name == "nt":
        try:
            raw_tokens = shlex.split(cmd_str, posix=False)
            tokens: List[str] = []
            for t in raw_tokens:
                if ((t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'"))) and len(t) >= 2:
                    tokens.append(t[1:-1])
                else:
                    tokens.append(t)
            return tokens
        except ValueError as ve:
            raise SecurityViolationError(f"Command contains unparseable syntax: {ve}") from ve
    else:
        try:
            return shlex.split(cmd_str)
        except ValueError as ve:
            raise SecurityViolationError(f"Command contains unparseable syntax: {ve}") from ve


@dataclass(frozen=True)
class ProviderCapabilities:
    """Introspected capability profile of an execution provider."""
    provider_name: str
    provider_type: str  # "host", "sandbox", "container", "virtualized", "reproducible_pipeline"
    network_isolation: bool = False
    filesystem_isolation: bool = False
    resource_limits: bool = False
    user_namespace: bool = False
    supported_modes: List[str] = field(default_factory=lambda: ["host_argv"])
    runtime_path: Optional[str] = None
    version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "provider_type": self.provider_type,
            "network_isolation": self.network_isolation,
            "filesystem_isolation": self.filesystem_isolation,
            "resource_limits": self.resource_limits,
            "user_namespace": self.user_namespace,
            "supported_modes": list(self.supported_modes),
            "runtime_path": self.runtime_path,
            "version": self.version,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProviderHealth:
    """Health and responsiveness status of an execution provider."""
    provider_name: str
    status: str  # "healthy", "degraded", "unavailable", "failed"
    is_healthy: bool
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "status": self.status,
            "is_healthy": self.is_healthy,
            "latency_ms": round(self.latency_ms, 2),
            "details": dict(self.details),
            "checked_at": self.checked_at,
        }


@dataclass(frozen=True)
class ProviderExecutionResult:
    """
    Authentic execution outcome produced by an ExecutionProvider.
    Binds raw process results to canonical Observation and cryptographically sealed ObservedReceipt.
    """
    provider_name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    pid: int
    success: bool
    observation: Observation
    evidence_receipt: ObservedReceipt
    raw_result: Optional[ProcessExecutionResult] = None
    authorization_decision: Optional[AuthorizationDecision] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    observation_record: Optional[ObservationRecord] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": round(self.duration_ms, 2),
            "pid": self.pid,
            "success": self.success,
            "observation": self.observation.to_dict(),
            "evidence_receipt": self.evidence_receipt.to_dict(),
            "authorization_decision": self.authorization_decision.to_dict() if self.authorization_decision else None,
            "metadata": dict(self.metadata),
            "observation_record": self.observation_record.to_dict() if self.observation_record else None,
        }


class ExecutionProvider(ABC):
    """
    Abstract interface for all execution providers in S-Class.
    Decouples execution policy from execution mechanisms (host, sandbox, OCI container, gVisor, Dagger).
    Enforces authorization gating (L3 & L8) and emits canonical Observation and EvidenceReceipt.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier (e.g., 'native', 'bubblewrap', 'oci', 'gvisor', 'dagger')."""
        ...

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider taxonomy ('host', 'sandbox', 'container', 'virtualized', 'reproducible_pipeline')."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the required runtime and dependencies are available on the host system."""
        ...

    @abstractmethod
    def inspect_capabilities(self) -> ProviderCapabilities:
        """Introspects and returns isolation and execution capabilities of this provider."""
        ...

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Probes the provider environment to ensure responsiveness and operational integrity."""
        ...

    @abstractmethod
    def execute_raw(
        self,
        command: List[str],
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
        mode: ExecutionMode = ExecutionMode.HOST_ARGV,
        task_id: Optional[str] = None,
        config: Optional[Any] = None,
        **kwargs,
    ) -> ProcessExecutionResult:
        """
        Executes the low-level process mechanism within this provider's containment boundary.
        Decoupled from authorization policy.
        """
        ...

    def execute(
        self,
        command: Union[str, List[str], ActionRequest],
        cwd: Optional[str] = None,
        request: Optional[ActionRequest] = None,
        capability: Optional[Capability] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
        mode: ExecutionMode = ExecutionMode.HOST_ARGV,
        allow_shell: Optional[bool] = None,
        task_id: Optional[str] = None,
        ledger: Optional[LocalLedger] = None,
        authorization_decision: Optional[AuthorizationDecision] = None,
        config: Optional[Any] = None,
        require_authorization: bool = True,
        **kwargs,
    ) -> ProviderExecutionResult:
        """
        Authoritative execution pipeline:
        1. Normalizes ActionRequest and parameters.
        2. Enforces S-Class Authorization Gate (L3 & L8 fail-closed).
        3. Enforces Provider Availability (NO SANDBOX -> NO SANDBOXED EXECUTION).
        4. Snapshots workspace before execution.
        5. Dispatches execution to provider mechanism.
        6. Emits canonical Observation and cryptographically sealed ObservedReceipt into LocalLedger.
        """
        from sclass.domain.action import ActionRequest
        from sclass.domain.observation import Observation
        from sclass.observation.factory import ObservationFactory
        from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
        from sclass.trust.ledger import LocalLedger

        # 1. Normalize command tokens and workspace
        action_req: Optional[ActionRequest] = None
        cmd_tokens: List[str] = []
        cmd_str: str = ""

        if isinstance(command, ActionRequest):
            action_req = command
            cmd_raw = action_req.target or action_req.parameters.get("command", "")
            if isinstance(cmd_raw, list):
                cmd_tokens = list(cmd_raw)
                import subprocess
                cmd_str = subprocess.list2cmdline(cmd_tokens) if os.name == "nt" else shlex.join(cmd_tokens)
            else:
                cmd_str = str(cmd_raw)
                cmd_tokens = split_command(cmd_str)
            resolved_cwd = cwd or action_req.workspace or os.getcwd()
            t_id = task_id or action_req.session or "task_default"
        else:
            if isinstance(command, str):
                cmd_str = command
                cmd_tokens = split_command(cmd_str)
            else:
                cmd_tokens = list(command)
                import subprocess
                cmd_str = subprocess.list2cmdline(cmd_tokens) if os.name == "nt" else shlex.join(cmd_tokens)

            resolved_cwd = cwd or (request.workspace if request else os.getcwd())
            t_id = task_id or (request.session if request else "task_default")
            action_req = request

        ws = os.path.abspath(resolved_cwd)

        if not cmd_tokens:
            raise SecurityViolationError("Empty command string provided for execution.")

        # 2. Authorization Gate (L3: S-Class owns authorization; L8: Unknown security state fails closed)
        decision: Optional[AuthorizationDecision] = authorization_decision
        if require_authorization:
            if decision is None:
                # Construct canonical ActionRequest if not already present
                if action_req is None:
                    cap_name = capability.name if capability else "terminal.execute"
                    action_req = ActionRequest(
                        actor="agent",
                        session=t_id,
                        capability=cap_name,
                        action="run_command",
                        target=cmd_str,
                        parameters={"command": cmd_str, "cwd": ws},
                        workspace=ws,
                    )
                from sclass.control.authorization import authorize
                decision = authorize(action_req, mode="enforce", workspace_dir=ws)

            if not decision.is_allowed:
                raise SecurityViolationError(
                    f"Execution blocked by S-Class security policy [{decision.policy_id}]: {decision.reason}"
                )

        # Evaluate execution policy and protected resource targeting
        if allow_shell is not None:
            mode = ExecutionMode.HOST_SHELL if allow_shell else ExecutionMode.HOST_ARGV

        eval_result = ExecutionPolicy.evaluate(
            mode=mode,
            command=cmd_str,
            cwd=ws,
            task_id=t_id,
        )
        if not eval_result.allowed:
            raise SecurityViolationError(f"Execution policy violation: {eval_result.reason}")

        # 3. Provider Availability Check (Invariant: NO SANDBOX -> NO SANDBOXED EXECUTION)
        if not self.is_available():
            raise SecurityViolationError(
                f"NO SANDBOX -> NO SANDBOXED EXECUTION: Requested execution provider '{self.name}' is not available on this host. "
                "Fail-closed policy strictly prohibits uncontained execution."
            )

        # 4. Snapshot workspace before execution
        snapshot_before = compute_workspace_snapshot(ws)
        fingerprint_before = compute_workspace_fingerprint(snapshot_before)

        # Initialize ledger if not provided
        if ledger is None:
            try:
                ledger = LocalLedger(workspace_dir=ws)
            except Exception as l_err:
                raise ObservationIntegrityError(
                    f"Local ledger could not be initialized for execution: {l_err}"
                ) from l_err

        # 5. Low-level execution via provider mechanism
        raw_result = self.execute_raw(
            command=cmd_tokens,
            cwd=ws,
            env=env,
            timeout=timeout,
            mode=mode,
            task_id=t_id,
            config=config,
            **kwargs,
        )

        # 6. Cryptographic Observation & Receipt Emission
        agent_name = action_req.actor if action_req else "agent"
        action_name = action_req.action if action_req else "run_command"
        claim_id = (action_req.context.get("claim_id") if (action_req and action_req.context) else None) or getattr(action_req, "claim_id", None) or f"claim_{t_id}"

        receipt = ObservationFactory.create_observation(
            execution_result=raw_result,
            workspace_dir=ws,
            task_id=t_id,
            claim_id=claim_id,
            agent=agent_name,
            action=action_name,
            fingerprint_before=fingerprint_before,
            snapshot_before=snapshot_before,
            ledger=ledger,
        )

        # Construct canonical domain Observation
        stdout_hash = hashlib.sha256(raw_result.stdout.encode("utf-8")).hexdigest()
        stderr_hash = hashlib.sha256(raw_result.stderr.encode("utf-8")).hexdigest()

        obs = Observation(
            observation_id=receipt.receipt_id,
            task_id=t_id,
            execution_identity=raw_result.identity,
            command=cmd_str,
            exit_code=raw_result.exit_code,
            stdout_hash=stdout_hash,
            stderr_hash=stderr_hash,
            workspace_fingerprint_before=fingerprint_before,
            workspace_fingerprint_after=receipt.workspace_fingerprint,
            started_at=raw_result.started_at,
            finished_at=raw_result.finished_at,
            duration_ms=raw_result.duration_ms,
            files_changed=receipt.files_changed,
            raw_stdout=raw_result.stdout,
            raw_stderr=raw_result.stderr,
            metadata={
                "provider": self.name,
                "provider_type": self.provider_type,
                "policy_id": decision.policy_id if decision else "N/A",
            },
            observation_record=getattr(receipt, "observation_record", None),
        )

        obs_rec = getattr(receipt, "observation_record", None)

        return ProviderExecutionResult(
            provider_name=self.name,
            command=cmd_str,
            exit_code=raw_result.exit_code,
            stdout=raw_result.stdout,
            stderr=raw_result.stderr,
            duration_ms=raw_result.duration_ms,
            pid=raw_result.identity.pid,
            success=(raw_result.exit_code == 0 and not raw_result.timed_out),
            observation=obs,
            evidence_receipt=receipt,
            raw_result=raw_result,
            authorization_decision=decision,
            metadata={"provider_type": self.provider_type},
            observation_record=obs_rec,
        )

