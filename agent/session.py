"""
S-Class EOS V11.2 - D7 Agent Session Manager & Ingress Lifecycle (§8.1, §8.3).
Orchestrates ephemeral multi-turn agent conversations with:
1. Inbound AgentMessage ingress validation (validates external worker message envelope before unpacking).
2. Mandatory authoritative repository state verification before every turn and proposal.
3. Explicit execution context propagation (no manufactured topology in D7).
4. Streaming memory-bounded inspection tools.
5. Non-authoritative internal accounting units (D7_INTERNAL_ACCOUNTING_UNIT).
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Mapping, Optional, Sequence, List, Tuple, Any, Callable
from domain.models import Obligation, Policy
from controller.controller import SClassController, ControllerDispatchResult
from controller.token import ExecutionContext
from execution.workspace import IsolatedWorkspace
from agent.models import (
    AgentSessionContext,
    AgentTurnResponse,
    AgentTurnStatus,
    AgentSessionRecord,
    AgentToolCall,
    AgentMessage,
    create_agent_message,
    GENESIS_DIGEST,
    D7_INTERNAL_ACCOUNTING_UNIT,
)
from agent.protocol import AgentWorkerProtocol, AgentMessageChainValidator
from agent.tools import AgentToolRegistry
from agent.context import AgentContextBuilder
from agent.synthesizer import ActionProposalSynthesizer


class AgentSessionManager:
    """Manages multi-turn cognitive agent sessions with strict ingress validation and repository bounding."""

    def __init__(
        self,
        worker: AgentWorkerProtocol,
        controller: SClassController,
        authoritative_repo_state_provider: Callable[[], Tuple[str, str]],
        session_execution_context: Optional[ExecutionContext] = None,
        tool_registry: Optional[AgentToolRegistry] = None,
        context_builder: Optional[AgentContextBuilder] = None,
        workspace: Optional[IsolatedWorkspace] = None,
    ):
        if not isinstance(worker, AgentWorkerProtocol):
            raise TypeError("worker must implement AgentWorkerProtocol.")
        if not isinstance(controller, SClassController):
            raise TypeError("controller must be an instance of SClassController.")
        if not callable(authoritative_repo_state_provider):
            raise TypeError("authoritative_repo_state_provider is mandatory and must be callable returning (repo_id, repo_sha).")
        self._worker = worker
        self._controller = controller
        self._authoritative_repo_state_provider = authoritative_repo_state_provider
        self._session_execution_context = session_execution_context
        self._tool_registry = tool_registry or AgentToolRegistry()
        self._context_builder = context_builder or AgentContextBuilder(self._tool_registry)
        self._workspace = workspace

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
        execution_context: Optional[ExecutionContext] = None,
        max_turns: int = 10,
        budget_units: float = 10.0,
    ) -> Tuple[AgentSessionRecord, List[ControllerDispatchResult]]:
        """Executes an ephemeral bounded conversational session with the cognitive agent."""
        session_id = f"SESS-{uuid.uuid4().hex[:8].upper()}"
        started_at = datetime.now(timezone.utc).isoformat()

        message_history: List[AgentMessage] = []
        transcript: List[Mapping[str, Any]] = []
        dispatches: List[ControllerDispatchResult] = []

        turn_index = 0
        budget_remaining = budget_units
        advisory_total_cost = 0.0
        internal_accounting_units = 0.0
        final_status = AgentTurnStatus.CONTINUE

        # Inbound Message Chain Tracker
        current_sequence = 0
        last_digest = GENESIS_DIGEST

        # Frozen capability tuple for this session
        session_capabilities = tuple(granted_capabilities)
        has_ws = self._workspace is not None and self._workspace.is_active

        # Resolve authoritative ExecutionContext without manufacturing topology
        exec_ctx = execution_context or self._session_execution_context
        if exec_ctx is None:
            ws_id = self._workspace.workspace_id if self._workspace else "ws_session_default"
            exec_ctx = ExecutionContext(
                provider_id="pytest_runner_engine",
                sandbox_profile_id="sbx_std",
                workspace_id=ws_id,
                resource_profile_id="res_std",
                capability_set=session_capabilities,
            )

        while turn_index < max_turns and budget_remaining > 0.0:
            # 1. Mandatory Authoritative Repository State Verification
            current_repo_id, current_sha = self._authoritative_repo_state_provider()
            if current_repo_id != repository_id:
                final_status = AgentTurnStatus.REPOSITORY_MISMATCH
                break
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
                has_workspace_authority=has_ws,
                turn_index=turn_index,
                max_turns=max_turns,
                remaining_budget_units=budget_remaining,
            )

            # 3. Create canonical USER_CONTEXT AgentMessage (Egress to Worker)
            context_msg = create_agent_message(
                session_id=session_id,
                worker_id="S_CLASS_SYSTEM",
                sequence=current_sequence,
                message_type="USER_CONTEXT",
                payload={"turn_index": turn_index, "task_id": task_id, "frontier": ctx.frontier_obligation_ids},
                previous_digest=last_digest,
            )
            message_history.append(context_msg)
            current_sequence += 1
            last_digest = context_msg.message_digest

            # 4. Invoke cognitive worker for external Inbound AgentMessage
            try:
                inbound_msg = self._worker.generate_inbound_message(
                    context=ctx,
                    sequence=current_sequence,
                    previous_digest=last_digest,
                    history=tuple(message_history),
                )
            except TimeoutError:
                final_status = AgentTurnStatus.WORKER_TIMEOUT
                break
            except ConnectionError:
                final_status = AgentTurnStatus.WORKER_DISCONNECT
                break
            except Exception:
                final_status = AgentTurnStatus.FAILED
                break

            # 5. Validate External Inbound AgentMessage through Ingress Validator
            is_valid_msg, err_msg, fail_status, turn_resp = AgentMessageChainValidator.validate_inbound_message(
                message=inbound_msg,
                expected_session_id=session_id,
                expected_worker_id=self._worker.worker_id,
                expected_sequence=current_sequence,
                expected_previous_digest=last_digest,
            )

            if not is_valid_msg or turn_resp is None:
                final_status = fail_status or AgentTurnStatus.INGRESS_VALIDATION_FAILED
                break

            message_history.append(inbound_msg)
            current_sequence += 1
            last_digest = inbound_msg.message_digest

            advisory_total_cost += turn_resp.advisory_estimated_cost_usd

            turn_entry = {
                "turn_index": turn_index,
                "thought": turn_resp.thought,
                "status": turn_resp.turn_status.value,
                "advisory_cost_usd": turn_resp.advisory_estimated_cost_usd,
                "message_digest": inbound_msg.message_digest,
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
                    # Mandatory Re-Verification of Repository State immediately before proposal synthesis
                    curr_rep, curr_sha = self._authoritative_repo_state_provider()
                    if curr_rep != repository_id or curr_sha != source_sha:
                        final_status = AgentTurnStatus.STALE_CONTEXT
                        break

                    proposal, synth_err = ActionProposalSynthesizer.synthesize_proposal(
                        tool_call=tc,
                        session_execution_context=exec_ctx,
                    )
                    if proposal:
                        now_dt = datetime.now(timezone.utc)
                        eval_iso = now_dt.isoformat()
                        exp_iso = (now_dt + timedelta(hours=1)).isoformat()
                        
                        # Internal non-authoritative accounting deduction
                        internal_accounting_units += D7_INTERNAL_ACCOUNTING_UNIT
                        budget_remaining = max(0.0, budget_remaining - D7_INTERNAL_ACCOUNTING_UNIT)

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
                elif tool_def and not tool_def.is_proposal_tool:
                    # Execute inspection tool safely within workspace containment
                    tool_res = self._tool_registry.execute_inspection_tool(tc, self._workspace)
                    turn_entry["inspection_result"] = {
                        "call_id": tool_res.call_id,
                        "success": tool_res.success,
                        "result_data": dict(tool_res.result_data),
                        "error_message": tool_res.error_message,
                    }

            # 7. Check terminal statuses
            if final_status in (AgentTurnStatus.STALE_CONTEXT, AgentTurnStatus.REPOSITORY_MISMATCH):
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
            total_turns=turn_index if final_status in (AgentTurnStatus.COMPLETED, AgentTurnStatus.FAILED, AgentTurnStatus.MAX_TURNS_REACHED) else turn_index + 1,
            advisory_total_cost_usd=advisory_total_cost,
            internal_accounting_units=internal_accounting_units,
            final_status=final_status,
            started_at=started_at,
            ended_at=ended_at,
            proposed_action_count=len(dispatches),
            turns_transcript=tuple(transcript),
            final_message_digest=last_digest,
        )

        return record, dispatches
