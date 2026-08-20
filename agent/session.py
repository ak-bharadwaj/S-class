"""
S-Class EOS V11.2 - D7 Agent Session Manager & Turn Lifecycle (§8.1, §8.3).
Orchestrates bounded multi-turn agent conversations, enforces cost budgets and max turns,
and coordinates action proposals with the D5 Controller.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Mapping, Optional, Sequence, List, Tuple, Any
from domain.models import Obligation, Policy
from controller.controller import SClassController, ControllerDispatchResult
from agent.models import (
    AgentSessionContext,
    AgentTurnResponse,
    AgentTurnStatus,
    AgentSessionRecord,
    AgentToolCall,
)
from agent.protocol import AgentWorkerProtocol
from agent.tools import AgentToolRegistry
from agent.context import AgentContextBuilder
from agent.synthesizer import ActionProposalSynthesizer


class AgentSessionManager:
    """Manages multi-turn cognitive agent sessions with strict resource and turn bounding."""

    def __init__(
        self,
        worker: AgentWorkerProtocol,
        controller: SClassController,
        tool_registry: Optional[AgentToolRegistry] = None,
        context_builder: Optional[AgentContextBuilder] = None,
    ):
        if not isinstance(worker, AgentWorkerProtocol):
            raise TypeError("worker must implement AgentWorkerProtocol.")
        if not isinstance(controller, SClassController):
            raise TypeError("controller must be an instance of SClassController.")
        self._worker = worker
        self._controller = controller
        self._tool_registry = tool_registry or AgentToolRegistry()
        self._context_builder = context_builder or AgentContextBuilder(self._tool_registry)

    def run_session(
        self,
        task_id: str,
        objective: str,
        obligations: Mapping[str, Obligation],
        policies: Mapping[str, Policy],
        source_sha: str,
        policy_version: int,
        granted_capabilities: Sequence[str] = ("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
        max_turns: int = 10,
        cost_budget_usd: float = 10.0,
    ) -> Tuple[AgentSessionRecord, List[ControllerDispatchResult]]:
        """Executes a bounded conversational session with the cognitive agent."""
        session_id = f"SESS-{uuid.uuid4().hex[:8].upper()}"
        started_at = datetime.now(timezone.utc).isoformat()

        history: List[AgentTurnResponse] = []
        transcript: List[Mapping[str, Any]] = []
        dispatches: List[ControllerDispatchResult] = []

        turn_index = 0
        budget_remaining = cost_budget_usd
        final_status = AgentTurnStatus.CONTINUE

        while turn_index < max_turns and budget_remaining > 0.0:
            # 1. Build immutable turn context
            ctx = self._context_builder.build_context(
                session_id=session_id,
                task_id=task_id,
                objective=objective,
                obligations=obligations,
                policies=policies,
                granted_capabilities=granted_capabilities,
                turn_index=turn_index,
                max_turns=max_turns,
                budget_remaining_usd=budget_remaining,
            )

            # 2. Invoke cognitive worker
            turn_resp = self._worker.generate_turn(ctx, tuple(history))
            history.append(turn_resp)
            budget_remaining = max(0.0, budget_remaining - turn_resp.estimated_cost_usd)

            turn_entry = {
                "turn_index": turn_index,
                "thought": turn_resp.thought,
                "status": turn_resp.turn_status.value,
                "cost_usd": turn_resp.estimated_cost_usd,
                "tool_calls": [
                    {"call_id": tc.call_id, "tool": tc.tool_name, "args": dict(tc.arguments)}
                    for tc in turn_resp.tool_calls
                ],
            }
            transcript.append(turn_entry)

            # 3. Process tool calls
            for tc in turn_resp.tool_calls:
                is_valid, err_msg = self._tool_registry.validate_tool_call(tc)
                if not is_valid:
                    turn_entry["validation_error"] = err_msg
                    continue

                tool_def = self._tool_registry.get_tool(tc.tool_name)
                if tool_def and tool_def.is_proposal_tool:
                    proposal, synth_err = ActionProposalSynthesizer.synthesize_proposal(
                        tool_call=tc,
                        granted_capabilities=("CAP_EXEC_TEST",),
                    )
                    if proposal:
                        now_dt = datetime.now(timezone.utc)
                        eval_iso = now_dt.isoformat()
                        exp_iso = (now_dt + timedelta(hours=1)).isoformat()
                        # Submit proposal to D5 Controller authorization gate
                        dispatch = self._controller.submit_proposal(
                            proposal=proposal,
                            obligations=obligations,
                            policies=policies,
                            source_sha=source_sha,
                            policy_version=policy_version,
                            evaluated_at=eval_iso,
                            expires_at=exp_iso,
                            allowed_action_types=[proposal.action_type],
                        )
                        dispatches.append(dispatch)

            # 4. Evaluate turn completion status
            if turn_resp.turn_status in (AgentTurnStatus.COMPLETED, AgentTurnStatus.FAILED):
                final_status = turn_resp.turn_status
                break

            turn_index += 1

        if final_status == AgentTurnStatus.CONTINUE:
            if turn_index >= max_turns:
                final_status = AgentTurnStatus.MAX_TURNS_REACHED
            elif budget_remaining <= 0.0:
                final_status = AgentTurnStatus.BUDGET_EXCEEDED

        ended_at = datetime.now(timezone.utc).isoformat()
        total_cost = cost_budget_usd - budget_remaining

        record = AgentSessionRecord(
            session_id=session_id,
            task_id=task_id,
            total_turns=len(history),
            total_cost_usd=total_cost,
            final_status=final_status,
            started_at=started_at,
            ended_at=ended_at,
            proposed_action_count=len(dispatches),
            turns_transcript=tuple(transcript),
        )

        return record, dispatches
