"""
S-Class Runtime: Authentic Step-Code Provider Substrate.
Implements the deep Step-Code provider integrating all harvested runtime mechanisms:
- Real process lifecycle and JSONL RPC communication.
- Pre-execution tool call interception & 5-way permission conjunction.
- Post-execution tool result interception & hashing (UNTRUSTED CANDIDATE).
- Durable effect sandwich (TX1 -> EFFECT -> TX2).
- Session tree navigation and non-destructive context compaction.
- Lane state management & subagent bounded delegation.
- Workflow orchestration & journaling.
- Typed telemetry emission (observability only).

Invariant (Directive Section 37):
Step-Code is the execution engine.
Its status, tool results, test outputs, task complete proposals, and goal states
are UNTRUSTED_RUNTIME_FACTS. S-Class must convert them to evidence and independently verify them.
"""

from __future__ import annotations
import os
import time
import json
import logging
from typing import Dict, Any, Optional, List, Callable

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.execution.operations import (
    OperationState,
    ReplayClass,
    CrossRuntimeOperation,
    CanonicalOperationStore,
    compute_action_hash,
)
from sclass.execution.effect_boundary import (
    DurableEffectBoundary,
    IntentDescriptor,
    EffectSettlementReceipt,
)
from sclass.execution.harness import StepCodeRpcHarness
from sclass.runtime.provider import RuntimeProvider
from sclass.runtime.permissions import (
    ComprehensivePermissionEngine,
    PermissionPreset,
    WorkflowChildACL,
)
from sclass.runtime.lanes import LaneManager, LaneBudget, LaneType
from sclass.runtime.subagents import SubagentManager, SubagentDelegationScope, SubagentInstance
from sclass.runtime.workflows import WorkflowEngine, PluginRegistry
from sclass.runtime.sessions import SessionManager
from sclass.runtime.recovery import BoundedRecoveryLadder, FailureClass
from sclass.runtime.telemetry import RuntimeTelemetryLedger, TelemetryEventType
from sclass.core.errors import SecurityViolationError


logger = logging.getLogger("sclass.runtime.stepcode")


class StepCodeProvider(RuntimeProvider):
    """
    Production-grade Step-Code execution runtime provider.
    """

    def __init__(
        self,
        workspace_dir: str,
        step_cmd: Optional[List[str]] = None,
        permission_preset: PermissionPreset = PermissionPreset.AUTOPILOT,
        auto_start: bool = True,
        use_test_double: bool = False,
    ):
        super().__init__(workspace_dir, provider_name="step-code")
        self.preset = permission_preset
        self.use_test_double = use_test_double

        # Integrated substrates
        self.permission_engine = ComprehensivePermissionEngine(preset=self.preset)
        self.effect_boundary = DurableEffectBoundary(self.operation_store)
        self.lane_manager = LaneManager()
        self.subagent_manager = SubagentManager(self.lane_manager)
        self.workflow_engine = WorkflowEngine(self.workspace_dir)
        self.plugin_registry = PluginRegistry()
        self.session_manager = SessionManager(self.workspace_dir)
        self.telemetry = RuntimeTelemetryLedger(self.workspace_dir)

        # Underlying RPC process harness
        self.rpc_harness = StepCodeRpcHarness(
            workspace_dir=self.workspace_dir,
            step_cmd=step_cmd,
            fail_closed=True,
            auto_start=auto_start,
            use_test_double=use_test_double,
        )

        # Initialize main lane
        self.main_lane = self.lane_manager.create_main_lane(
            session_id=f"session_{int(time.time())}",
            task_id="main_task",
            workspace_id=self.workspace_dir,
        )

        self.telemetry.emit(
            TelemetryEventType.SESSION_STARTED,
            session_id=self.main_lane.session_id,
            task_id=self.main_lane.task_id,
            payload={"preset": self.preset.value, "workspace": self.workspace_dir},
        )

    def health_check(self) -> Dict[str, Any]:
        h = self.rpc_harness.health_check()
        h["provider"] = "StepCodeProvider"
        h["permission_preset"] = self.preset.value
        h["main_lane_status"] = self.main_lane.status.value
        return h

    def execute_action(
        self,
        action: ActionRequest,
        authorization: AuthorizationDecision,
        parent_operation_id: Optional[str] = None,
        child_acl: Optional[WorkflowChildACL] = None,
    ) -> Dict[str, Any]:
        """
        Executes an action through the 5-way permission check and durable effect boundary.
        """
        # Step 1: 5-way permission conjunction
        outcome_val = getattr(authorization, "outcome", None) or getattr(authorization, "decision", None)
        sclass_auth_allowed = (outcome_val == DecisionOutcome.ALLOW)
        verdict, rejections = self.permission_engine.evaluate_conjunction(
            tool_name=action.action,
            target=action.target,
            parameters=action.parameters,
            workspace_dir=self.workspace_dir,
            sclass_auth_allowed=sclass_auth_allowed,
            capability_allowed=True,
            workspace_policy_allowed=True,
            operation_state_allowed=True,
            child_acl=child_acl,
        )

        self.telemetry.emit(
            TelemetryEventType.PERMISSION_DECISION,
            session_id=self.main_lane.session_id,
            task_id=self.main_lane.task_id,
            payload={
                "tool_name": action.action,
                "target": action.target,
                "verdict": verdict,
                "rejections": rejections,
            },
        )

        if not verdict:
            raise SecurityViolationError(f"Action blocked by Step-Code conjunction gate: {rejections}")

        # Step 2: Formulate IntentDescriptor
        rc = action.parameters.get("replay_class", ReplayClass.NEVER)
        if isinstance(rc, str):
            try:
                rc = ReplayClass(rc)
            except ValueError:
                rc = ReplayClass.NEVER

        intent = IntentDescriptor(
            actor=action.actor,
            action=action.action,
            target=action.target,
            parameters=action.parameters,
            workspace=self.workspace_dir,
            task_id=self.main_lane.task_id,
            session_id=self.main_lane.session_id,
            replay_class=rc,
            runtime_name="step-code",
        )

        # Step 3: Execute inside DurableEffectBoundary (TX1 -> EFFECT -> TX2)
        def _invoke_runtime() -> Dict[str, Any]:
            return self.rpc_harness.submit_action(action=action, authorization=authorization)

        settlement = self.effect_boundary.execute_sandwich(
            intent=intent,
            effect_fn=_invoke_runtime,
            authorization_id=authorization.decision_id,
            parent_operation_id=parent_operation_id,
        )

        # Step 4: Record in session tree & telemetry
        self.session_manager.record_node(
            session_id=self.main_lane.session_id,
            node_type="tool_execution",
            data={
                "operation_id": settlement.operation_id,
                "action": action.action,
                "state": settlement.state.value,
                "settlement": settlement.settlement_data,
            },
        )

        self.telemetry.emit(
            TelemetryEventType.TOOL_CALL_COMPLETED,
            session_id=self.main_lane.session_id,
            task_id=self.main_lane.task_id,
            payload={
                "operation_id": settlement.operation_id,
                "action": action.action,
                "state": settlement.state.value,
                "duration_ms": settlement.duration_ms,
            },
        )

        return {
            "operation_id": settlement.operation_id,
            "status": "ok" if settlement.state == OperationState.SETTLED else "failed",
            "state": settlement.state.value,
            "result": settlement.raw_result,
            "settlement": settlement.settlement_data,
            "untrusted_candidate": True,  # Untrusted candidate evidence signal (Directive Section 37)
        }

    def prompt(self, message: str) -> Dict[str, Any]:
        """Sends prompt to Step-Code external process."""
        return self.rpc_harness.prompt(message)

    def spawn_subagent(
        self,
        task_id: str,
        task_scope: str,
        delegated_tools: List[str],
        budget_tokens: int = 25000,
        agent_name: str = "child_agent",
    ) -> SubagentInstance:
        """Spawns an isolated subagent with bounded capability delegation."""
        acl = WorkflowChildACL(
            allowed_tools=set(delegated_tools),
            can_execute_commands=("run_command" in delegated_tools),
            max_budget_tokens=budget_tokens,
        )
        scope = SubagentDelegationScope(
            task_id=task_id,
            task_scope=task_scope,
            workspace_dir=self.workspace_dir,
            delegated_tools=set(delegated_tools),
            budget=LaneBudget(max_tokens=budget_tokens),
            acl=acl,
        )

        subagent = self.subagent_manager.spawn_subagent(
            parent_agent_id=self.main_lane.agent_identity,
            parent_lane_id=self.main_lane.lane_id,
            scope=scope,
            agent_name=agent_name,
        )

        self.telemetry.emit(
            TelemetryEventType.SUBAGENT_TASK_CREATED,
            session_id=self.main_lane.session_id,
            task_id=task_id,
            payload={"subagent_id": subagent.subagent_id, "agent_name": agent_name},
        )

        return subagent

    def close(self) -> None:
        self.rpc_harness.close()
