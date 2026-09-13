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
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.observation.factory import ObservationFactory
from sclass.trust.ledger import LocalLedger


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
        policy_engine: Optional[Any] = None,
        **kwargs,
    ) -> Tuple[ProcessExecutionResult, ObservedReceipt]:
        """
        Executes an ActionRequest through the backend and seals observed evidence in LocalLedger.
        Strictly enforces that the action is authorized before dispatching to execution backend.
        """
        # 0. Authoritative authorization enforcement (mandatory choke point)
        if request is None:
            from sclass.core.errors import SecurityViolationError
            raise SecurityViolationError("NO AUTHORIZATION -> NO EXECUTION: ActionRequest is required before execution.")

        ws = os.path.abspath(request.workspace or os.getcwd())

        from sclass.policy.authorization_service import AuthorizationService, verify_decision_integrity
        from sclass.core.errors import SecurityViolationError

        auth_service = AuthorizationService()
        if authorization is not None:
            # Authoritatively verify that the supplied decision is genuine, S-Class issued, bound to this exact request, and untampered
            valid, verify_reason = verify_decision_integrity(authorization, request)
            if not valid:
                raise SecurityViolationError(
                    f"NO AUTHORIZATION -> NO EXECUTION: Supplied authorization is unauthentic, forged, tampered, "
                    f"or not bound to this exact ActionRequest: {verify_reason}"
                )
            decision = authorization
        else:
            decision = auth_service.authorize(request, workspace_dir=ws, policy_engine=policy_engine)

        if decision is None:
            raise SecurityViolationError("UNKNOWN POLICY STATE -> NO EXECUTION: Policy engine returned no decision.")

        if not getattr(decision, "is_allowed", False):
            pol_id = getattr(decision, "policy_id", "UNKNOWN")
            reason = getattr(decision, "reason", "Action is not permitted by security policy")
            raise SecurityViolationError(
                f"NO AUTHORIZATION -> NO EXECUTION: ActionRequest unauthorized under policy [{pol_id}]: {reason}"
            )

        outcome_val = getattr(decision.outcome, "value", str(decision.outcome)).lower()
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
        exec_result = exec_backend.execute(
            command=cmd,
            cwd=ws,
            request=request,
            timeout=timeout,
            **kwargs,
        )

        # 4. Independent OS observation and immutable receipt sealing
        resolved_claim_id = claim_id or request.parameters.get("claim_id") or f"claim_{uuid.uuid4().hex[:8]}"
        resolved_task_id = request.session or request.task_id or f"task_{uuid.uuid4().hex[:8]}"

        local_ledger = ledger or LocalLedger(workspace_dir=ws)

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

        return exec_result, receipt


def converge_execution(
    request: ActionRequest,
    command: Optional[Union[str, List[str]]] = None,
    backend: Optional[ExecutionBackend] = None,
    ledger: Optional[LocalLedger] = None,
    timeout: float = 60.0,
    authorization: Optional[Any] = None,
    policy_engine: Optional[Any] = None,
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
        **kwargs,
    )

