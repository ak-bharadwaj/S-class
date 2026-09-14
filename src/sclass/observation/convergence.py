"""
S-Class Observation: Observation Convergence.
Ensures ALL executions converge on S-Class execution backend -> independent OS observation -> immutable receipt -> LocalLedger.
"""

from __future__ import annotations
import os
import uuid
import shlex
from typing import Tuple, Optional, Any, List, Union

from sclass.domain.action import ActionRequest
from sclass.domain.evidence import ObservedReceipt
from sclass.execution.process import ProcessExecutionResult
from sclass.execution.backend import ExecutionBackend, HostProcessBackend, get_execution_backend
from sclass.execution.provenance import redact_secrets
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.observation.factory import ObservationFactory
from sclass.trust.ledger import LocalLedger
from sclass.telemetry.tracing import (
    get_local_tracer,
    SPAN_SESSION_TURN,
    SPAN_ACTION_AUTHORIZE,
    SPAN_ACTION_EXECUTE,
    SPAN_OBSERVATION_RECORD,
)
from sclass.platform.budget import PerformanceBudget


class ObservationConvergence:
    """
    Convergence pipeline guaranteeing that any execution:
    1. Runs inside an authorized ExecutionBackend
    2. Undergoes independent OS process observation (ExecutionIdentity, process tree, outputs)
    3. Produces a sealed, immutable ObservedReceipt
    4. Commits atomically to the append-only LocalLedger
    """

    @classmethod
    def execute_and_observe(
        cls,
        request: ActionRequest,
        command: Optional[Union[str, List[str]]] = None,
        backend: Optional[ExecutionBackend] = None,
        ledger: Optional[LocalLedger] = None,
        timeout: float = 60.0,
        claim_id: Optional[str] = None,
        authorization: Optional[Any] = None,
        capability: Optional[Any] = None,
        policy_engine: Optional[Any] = None,
        policy_provider: Optional[Any] = None,
        auth_service: Optional[Any] = None,
        capability_registry: Optional[Any] = None,
        budget: Optional[Any] = None,
        **kwargs,
    ) -> Tuple[ProcessExecutionResult, ObservedReceipt]:
        """
        Executes an ActionRequest through the backend and seals observed evidence in LocalLedger.
        Strictly enforces that the action is authorized before dispatching to execution backend.
        Instruments execution lifecycle with OpenTelemetry process semantics and S-Class span tracing.
        """
        # 0. Authoritative authorization enforcement (mandatory choke point)
        if request is None:
            from sclass.core.errors import SecurityViolationError
            raise SecurityViolationError("NO AUTHORIZATION -> NO EXECUTION: ActionRequest is required before execution.")

        ws = os.path.abspath(request.workspace or os.getcwd())
        tracer = get_local_tracer(ws)
        resolved_task_id = request.session or request.task_id or f"task_{uuid.uuid4().hex[:8]}"
        resolved_claim_id = claim_id or (request.parameters.get("claim_id") if request.parameters else None) or f"claim_{uuid.uuid4().hex[:8]}"

        with tracer.span(SPAN_SESSION_TURN, trace_id=resolved_task_id) as turn_span:
            turn_span.set_attributes({
                "session_id": resolved_task_id,
                "actor": request.actor,
                "action": request.action,
                "target": redact_secrets(str(request.target or "")),
            })

            with tracer.span(SPAN_ACTION_AUTHORIZE, attributes={
                "actor": request.actor,
                "capability": request.capability,
                "action": request.action,
                "target": redact_secrets(str(request.target or "")),
            }) as auth_span:
                from sclass.policy.authorization_service import AuthorizationService, verify_decision_integrity
                from sclass.core.errors import SecurityViolationError

                service = auth_service or AuthorizationService(capability_registry=capability_registry)

                # Resolve authoritative capability exclusively from the authoritative registry
                resolved_cap = service.capability_registry.resolve(request, workspace_dir=ws)

                # Invariant: NO CALLER-SUPPLIED CAPABILITY MAY BECOME AUTHORITY
                if capability is not None:
                    if resolved_cap is None or (capability is not resolved_cap and capability != resolved_cap):
                        raise SecurityViolationError(
                            "NO CALLER-SUPPLIED CAPABILITY MAY BECOME AUTHORITY: Caller-supplied capability rejected on execution API. "
                            "Capabilities must resolve exclusively from the authoritative registry."
                        )

                if resolved_cap is None:
                    raise SecurityViolationError(
                        "NO AUTHORITATIVE CAPABILITY -> NO EXECUTION: No capability granted to actor for this action in authoritative registry."
                    )

                if authorization is not None:
                    # Authoritatively verify that the supplied decision is genuine, S-Class issued, bound to this exact request, capability, registry generation, and policy version
                    valid, verify_reason = verify_decision_integrity(
                        authorization,
                        request,
                        capability=resolved_cap,
                        expected_registry_generation=service.capability_registry.generation,
                        expected_policy_version=service.policy_version,
                    )
                    if not valid:
                        raise SecurityViolationError(
                            f"NO AUTHORIZATION -> NO EXECUTION: Supplied authorization is unauthentic, forged, tampered, "
                            f"or not bound to this exact ActionRequest, capability, registry generation, or policy version: {verify_reason}"
                        )
                    decision = authorization
                else:
                    decision = service.authorize(
                        request,
                        capability=resolved_cap,
                        workspace_dir=ws,
                        policy_engine=policy_engine,
                        policy_provider=policy_provider,
                    )

                if decision is None:
                    raise SecurityViolationError("UNKNOWN POLICY STATE -> NO EXECUTION: Policy engine returned no decision.")

                outcome_val = getattr(decision.outcome, "value", str(decision.outcome)).lower()
                auth_span.set_attributes({
                    "policy_id": getattr(decision, "policy_id", "UNKNOWN"),
                    "decision_outcome": outcome_val,
                })

                if not getattr(decision, "is_allowed", False):
                    pol_id = getattr(decision, "policy_id", "UNKNOWN")
                    reason = getattr(decision, "reason", "Action is not permitted by security policy")
                    raise SecurityViolationError(
                        f"NO AUTHORIZATION -> NO EXECUTION: ActionRequest unauthorized under policy [{pol_id}]: {reason}"
                    )

                if outcome_val not in ("allow", "warn"):
                    raise SecurityViolationError(
                        f"NO AUTHORIZATION -> NO EXECUTION: Action outcome '{outcome_val}' is not authorized for execution."
                    )

            # 1. Resolve target command
            if command is not None:
                cmd = command
            elif request.parameters and "command" in request.parameters:
                cmd = request.parameters["command"]
            elif request.target and request.capability in ("terminal.execute", "process.spawn"):
                cmd = request.target
            elif request.action in ("run_command", "bash", "terminal.execute") and request.target:
                cmd = request.target
            else:
                cmd = request.target or "echo ''"

            # 2. Capture workspace snapshot and fingerprint before execution
            snap_before = compute_workspace_snapshot(ws)
            fp_before = compute_workspace_fingerprint(snap_before)

            # 3. Execute via ExecutionBackend
            exec_backend = backend or HostProcessBackend()
            cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
            with tracer.span(SPAN_ACTION_EXECUTE, attributes={
                "backend": exec_backend.__class__.__name__,
                "command": redact_secrets(cmd_str),
                "cwd": ws,
            }) as exec_span:
                exec_result = exec_backend.execute(
                    command=cmd,
                    cwd=ws,
                    request=request,
                    capability=resolved_cap,
                    timeout=timeout,
                    **kwargs,
                )
                pid_val = getattr(exec_result, "pid", None)
                if pid_val is None and hasattr(exec_result, "identity") and exec_result.identity is not None:
                    pid_val = getattr(exec_result.identity, "pid", None)
                exec_span.set_attributes({
                    "exit_code": exec_result.exit_code,
                    "pid": pid_val,
                    "duration_ms": exec_result.duration_ms,
                })

            # Record budget overhead if active
            active_budget = budget or kwargs.get("budget")
            if active_budget is not None and hasattr(active_budget, "record_overhead"):
                active_budget.record_overhead(
                    latency_ms=exec_result.duration_ms,
                    tool_calls=1,
                )

            # 4. Independent OS observation and immutable receipt sealing
            local_ledger = ledger or LocalLedger(workspace_dir=ws)
            with tracer.span(SPAN_OBSERVATION_RECORD, attributes={
                "task_id": resolved_task_id,
                "claim_id": resolved_claim_id,
                "agent": request.actor,
                "action": request.action,
            }) as obs_span:
                receipt = ObservationFactory.create_observation(
                    execution_result=exec_result,
                    workspace_dir=ws,
                    task_id=resolved_task_id,
                    claim_id=resolved_claim_id,
                    agent=request.actor,
                    action=request.action,
                    fingerprint_before=fp_before,
                    snapshot_before=snap_before,
                    ledger=local_ledger,
                )
                obs_span.set_attributes({
                    "receipt_id": receipt.receipt_id,
                    "receipt_hash": receipt.receipt_hash,
                    "files_changed_count": len(receipt.files_changed),
                })

            return exec_result, receipt


def converge_execution(
    request: ActionRequest,
    command: Optional[Union[str, List[str]]] = None,
    backend: Optional[ExecutionBackend] = None,
    ledger: Optional[LocalLedger] = None,
    timeout: float = 60.0,
    authorization: Optional[Any] = None,
    policy_engine: Optional[Any] = None,
    budget: Optional[Any] = None,
    **kwargs,
) -> Tuple[ProcessExecutionResult, ObservedReceipt]:
    """Convenience functional interface for execution observation convergence."""
    return ObservationConvergence.execute_and_observe(
        request=request,
        command=command,
        backend=backend,
        ledger=ledger,
        timeout=timeout,
        authorization=authorization,
        policy_engine=policy_engine,
        budget=budget,
        **kwargs,
    )

