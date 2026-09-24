"""
S-Class Execution: Durable Effect Sandwich & Boundary Coordinator.
Implements the mature Step-Code effect boundary pattern:
  INTENT -> EFFECT_PENDING -> EXTERNAL EFFECT -> SETTLEMENT
Under strict transactional persistence:
  TX1:
    - Persist operation intent
    - Persist immutable operation identity
    - Persist expected result identity
    - Persist replay class
  EFFECT:
    - Invoke external runtime substrate (Step-Code / Native / etc.)
  TX2:
    - Persist actual runtime result
    - Persist settlement record
    - Advance durable operation state to SETTLED (or FAILED)

Absolute Invariants (Directive Section 3 & 37):
1. Never infer effect completion from process death.
2. Never infer effect completion from missing state.
3. Never infer effect completion from model narrative.
4. Runtime settlement != project truth; settlement is an untrusted candidate evidence signal.
"""

from __future__ import annotations
import os
import json
import time
import uuid
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, Union

from sclass.execution.operations import (
    OperationState,
    ReplayClass,
    CrossRuntimeOperation,
    CanonicalOperationStore,
    compute_action_hash,
)
from sclass.core.errors import SecurityViolationError, ObservationIntegrityError


@dataclass(frozen=True)
class IntentDescriptor:
    """Immutable intent declaration for a planned operation."""
    actor: str
    action: str
    target: str
    parameters: Dict[str, Any]
    workspace: str
    task_id: str
    session_id: str
    replay_class: ReplayClass
    expected_result_schema: str = "json"
    runtime_name: str = "step-code"

    def compute_intent_hash(self) -> str:
        data = {
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "parameters": self.parameters,
            "workspace": self.workspace,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "replay_class": self.replay_class.value,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EffectSettlementReceipt:
    """Immutable settlement receipt produced upon completion of the effect sandwich."""
    operation_id: str
    runtime_name: str
    intent_hash: str
    action_hash: str
    replay_class: ReplayClass
    state: OperationState
    raw_result: Optional[Dict[str, Any]]
    settlement_data: Dict[str, Any]
    start_time_iso: str
    end_time_iso: str
    duration_ms: float
    untrusted_candidate: bool = True  # Always untrusted candidate until independent verification


class DurableEffectBoundary:
    """
    Executes external mutations inside the two-phase durable transaction sandwich (TX1 -> EFFECT -> TX2).
    """

    def __init__(self, operation_store: CanonicalOperationStore):
        self.operation_store = operation_store

    def execute_sandwich(
        self,
        intent: IntentDescriptor,
        effect_fn: Callable[[], Dict[str, Any]],
        authorization_id: Optional[str] = None,
        parent_operation_id: Optional[str] = None,
    ) -> EffectSettlementReceipt:
        """
        Executes an action within the complete TX1 -> EFFECT -> TX2 boundary.
        """
        op_id = f"op_{uuid.uuid4().hex[:12]}"
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        intent_h = intent.compute_intent_hash()
        action_h = compute_action_hash(intent.action, intent.target, intent.parameters)
        start_iso = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()

        # =========================================================================
        # TX1: Persist operation intent, identity, expected result, replay class
        # =========================================================================
        initial_op = CrossRuntimeOperation(
            operation_id=op_id,
            runtime_name=intent.runtime_name,
            runtime_operation_id="",
            session_id=intent.session_id,
            task_id=intent.task_id,
            action_id=action_id,
            workspace_id=intent.workspace,
            intent_hash=intent_h,
            action_hash=action_h,
            replay_class=intent.replay_class,
            state=OperationState.AUTHORIZED if authorization_id else OperationState.PLANNED,
            authorization_id=authorization_id,
            metadata={
                "actor": intent.actor,
                "action": intent.action,
                "target": intent.target,
                "parameters": intent.parameters,
                "parent_operation_id": parent_operation_id,
                "expected_result_schema": intent.expected_result_schema,
                "tx1_committed_at": start_iso,
            },
        )
        # Advance through AUTHORIZED to EFFECT_PENDING
        auth_op = initial_op
        if auth_op.state == OperationState.PLANNED:
            auth_op = initial_op.transition_to(
                OperationState.AUTHORIZED,
                {"authorized_at": start_iso, "auto_authorized": authorization_id is None},
            )

        pending_op = auth_op.transition_to(
            OperationState.EFFECT_PENDING,
            {"effect_pending_at": datetime.now(timezone.utc).isoformat()},
        )
        self.operation_store.save_operation(pending_op)

        # =========================================================================
        # EFFECT: Call external runtime substrate
        # =========================================================================
        runtime_result: Optional[Dict[str, Any]] = None
        execution_error: Optional[Exception] = None
        t1 = time.perf_counter()

        try:
            runtime_result = effect_fn()
        except Exception as ex:
            execution_error = ex

        duration_ms = (time.perf_counter() - t0) * 1000.0
        end_iso = datetime.now(timezone.utc).isoformat()

        # Invariant checks: Never infer completion from narrative or process death
        if runtime_result is not None and isinstance(runtime_result, dict):
            # Strip any forged assurance claims from runtime result
            if "project_truth" in runtime_result:
                runtime_result = dict(runtime_result)
                del runtime_result["project_truth"]

        # =========================================================================
        # TX2: Persist actual result, settlement, advance durable operation state
        # =========================================================================
        if execution_error is not None:
            failed_settlement = {
                "status": "FAILED",
                "error": str(execution_error),
                "error_class": execution_error.__class__.__name__,
                "duration_ms": duration_ms,
                "completed_at": end_iso,
            }
            settled_op = pending_op.transition_to(
                OperationState.FAILED,
                {
                    "effect_result": None,
                    "settlement": failed_settlement,
                    "failure_reason": str(execution_error),
                    "tx2_committed_at": end_iso,
                },
            )
            self.operation_store.save_operation(settled_op)

            return EffectSettlementReceipt(
                operation_id=op_id,
                runtime_name=intent.runtime_name,
                intent_hash=intent_h,
                action_hash=action_h,
                replay_class=intent.replay_class,
                state=OperationState.FAILED,
                raw_result=None,
                settlement_data=failed_settlement,
                start_time_iso=start_iso,
                end_time_iso=end_iso,
                duration_ms=duration_ms,
                untrusted_candidate=True,
            )

        # Successful effect invocation -> advance through EFFECT_EXECUTED to SETTLED
        executed_op = pending_op.transition_to(
            OperationState.EFFECT_EXECUTED,
            {"effect_executed_at": end_iso},
        )
        self.operation_store.save_operation(executed_op)

        settlement_info = {
            "status": "SETTLED",
            "runtime_exit_code": runtime_result.get("exit_code") if isinstance(runtime_result, dict) else 0,
            "duration_ms": duration_ms,
            "completed_at": end_iso,
        }
        settled_op = executed_op.transition_to(
            OperationState.SETTLED,
            {
                "effect_result": runtime_result,
                "settlement": settlement_info,
                "tx2_committed_at": end_iso,
            },
        )
        self.operation_store.save_operation(settled_op)

        return EffectSettlementReceipt(
            operation_id=op_id,
            runtime_name=intent.runtime_name,
            intent_hash=intent_h,
            action_hash=action_h,
            replay_class=intent.replay_class,
            state=OperationState.SETTLED,
            raw_result=runtime_result,
            settlement_data=settlement_info,
            start_time_iso=start_iso,
            end_time_iso=end_iso,
            duration_ms=duration_ms,
            untrusted_candidate=True,
        )
