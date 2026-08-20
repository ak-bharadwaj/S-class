"""
S-Class EOS V11.2 - D7 Agent Session Manager & Turn Lifecycle (§8.1, §8.3).
Orchestrates bounded multi-turn agent conversations, enforces cost budgets, max turns,
cryptographic AgentMessage chaining (detecting replay/reorder/tamper), stale repository SHA checks,
and coordinates action proposals with the D5 Controller.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Mapping, Optional, Sequence, List, Tuple, Any, Callable
from domain.models import Obligation, Policy
from controller.controller import SClassController, ControllerDispatchResult
from agent.models import (
    AgentSessionContext,
    AgentTurnResponse,
    AgentTurnStatus,
    AgentSessionRecord,
    AgentToolCall,
    AgentMessage,
    create_agent_message,
    GENESIS_DIGEST,
)
from agent.protocol import AgentWorkerProtocol
from agent.tools import AgentToolRegistry
from agent.context import AgentContextBuilder
from agent.synthesizer import ActionProposalSynthesizer


class AgentSessionManager:
    """Manages multi-turn cognitive agent sessions with strict resource, repository, and capability bounding."""

    def __init__(
        self,
        worker: AgentWorkerProtocol,
        controller: SClassController,
        tool_registry: Optional[AgentToolRegistry] = None,
        context_builder: Optional[AgentContextBuilder] = None,
        current_repo_sha_provider: Optional[Callable[[], str]] = None,
    ):
        if not isinstance(worker, AgentWorkerProtocol):
            raise TypeError("worker must implement AgentWorkerProtocol.")
        if not isinstance(controller, SClassController):
            raise TypeError("controller must be an instance of SClassController.")
        self._worker = worker
        self._controller = controller
        self._tool_registry = tool_registry or AgentToolRegistry()
        self._context_builder = context_builder or AgentContextBuilder(self._tool_registry)
        self._current_repo_sha_provider = current_repo_sha_provider

    def run_session(
        self,
        repository_id: str,
        source_sha: str,
        task_id: str,
        objective: str,
        obligations: Mapping[str, Obligation],
        policies: Mapping[str, Policy],
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
        advisory_total_cost = 0.0
        authoritative_usage_cost = 0.0
        final_status = AgentTurnStatus.CONTINUE

        # Inbound Message Chain Tracker
        current_sequence = 0
        last_digest = GENESIS_DIGEST

        # Frozen capability tuple for this session
        session_capabilities = tuple(granted_capabilities)

        while turn_index < max_turns and budget_remaining > 0.0:
            # 1. Repository State Invariant: check for stale context
            if self._current_repo_sha_provider is not None:
                current_sha = self._current_repo_sha_provider()
                if current_sha != source_sha:
                    final_status = AgentTurnStatus.STALE_CONTEXT
                    break

            # 2. Build immutable turn context
            ctx = self._context_builder.build_context(
                session_id=session_id,
                repository_id=repository_id,
                source_sha=source_sha,
                task_id=task_id,
                objective=objective,
                obligations=obligations,
                policies=policies,
                granted_capabilities=session_capabilities,
                turn_index=turn_index,
                max_turns=max_turns,
                remaining_budget_usd=budget_remaining,
            )

            # 3. Create canonical USER_CONTEXT AgentMessage
            context_msg = create_agent_message(
                session_id=session_id,
                sequence=current_sequence,
                message_type="USER_CONTEXT",
                payload={"turn_index": turn_index, "task_id": task_id, "frontier": ctx.frontier_obligation_ids},
                previous_digest=last_digest,
            )
            current_sequence += 1
            last_digest = context_msg.message_digest

            # 4. Invoke cognitive worker
            try:
                turn_resp = self._worker.generate_turn(ctx, tuple(history))
            except TimeoutError:
                final_status = AgentTurnStatus.WORKER_TIMEOUT
                break
            except ConnectionError:
                final_status = AgentTurnStatus.WORKER_DISCONNECT
                break
            except Exception:
                final_status = AgentTurnStatus.FAILED
                break

            history.append(turn_resp)
            advisory_total_cost += turn_resp.advisory_estimated_cost_usd

            # 5. Create canonical AGENT_TURN AgentMessage
            turn_msg = create_agent_message(
                session_id=session_id,
                sequence=current_sequence,
                message_type="AGENT_TURN",
                payload={
                    "thought": turn_resp.thought,
                    "status": turn_resp.turn_status.value,
                    "advisory_cost_usd": turn_resp.advisory_estimated_cost_usd,
                    "tool_calls": [
                        {"call_id": tc.call_id, "tool": tc.tool_name, "args": dict(tc.arguments)}
                        for tc in turn_resp.tool_calls
                    ],
                },
                previous_digest=last_digest,
            )
            current_sequence += 1
            last_digest = turn_msg.message_digest

            turn_entry = {
                "turn_index": turn_index,
                "thought": turn_resp.thought,
                "status": turn_resp.turn_status.value,
                "advisory_cost_usd": turn_resp.advisory_estimated_cost_usd,
                "message_digest": turn_msg.message_digest,
                "tool_calls": [
                    {"call_id": tc.call_id, "tool": tc.tool_name, "args": dict(tc.arguments)}
                    for tc in turn_resp.tool_calls
                ],
            }
            transcript.append(turn_entry)

            # 6. Process tool calls with strict capability enforcement & schema validation
            for tc in turn_resp.tool_calls:
                is_valid, err_msg = self._tool_registry.validate_tool_call(tc, session_capabilities)
                if not is_valid:
                    turn_entry["validation_error"] = err_msg
                    continue

                tool_def = self._tool_registry.get_tool(tc.tool_name)
                if tool_def and tool_def.is_proposal_tool:
                    # Enforce repository state invariant before proposal synthesis
                    if self._current_repo_sha_provider is not None:
                        current_sha = self._current_repo_sha_provider()
                        if current_sha != source_sha:
                            final_status = AgentTurnStatus.STALE_CONTEXT
                            break

                    proposal, synth_err = ActionProposalSynthesizer.synthesize_proposal(
                        tool_call=tc,
                        granted_capabilities=session_capabilities,
                    )
                    if proposal:
                        now_dt = datetime.now(timezone.utc)
                        eval_iso = now_dt.isoformat()
                        exp_iso = (now_dt + timedelta(hours=1)).isoformat()
                        
                        # Authoritative accounting for proposal submission
                        authoritative_cost_step = 0.05
                        authoritative_usage_cost += authoritative_cost_step
                        budget_remaining = max(0.0, budget_remaining - authoritative_cost_step)

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

            # 7. Check terminal statuses
            if final_status == AgentTurnStatus.STALE_CONTEXT:
                break

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

        record = AgentSessionRecord(
            session_id=session_id,
            repository_id=repository_id,
            source_sha=source_sha,
            task_id=task_id,
            total_turns=len(history),
            advisory_total_cost_usd=advisory_total_cost,
            authoritative_usage_cost_usd=authoritative_usage_cost,
            final_status=final_status,
            started_at=started_at,
            ended_at=ended_at,
            proposed_action_count=len(dispatches),
            turns_transcript=tuple(transcript),
            final_message_digest=last_digest,
        )

        return record, dispatches
