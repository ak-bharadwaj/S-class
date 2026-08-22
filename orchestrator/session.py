"""
S-Class Governed Orchestration Session.

Coordinates multi-turn cognitive reasoning and deterministic S-Class execution
across reasoning modes until task closure.

Strictly preserves architectural boundaries:
- Authoritative State Projections: Derived strictly from canonical D1/D2/D4 state (claims, receipts, DAG).
- Zero Manufactured Facts: Unestablished repository/risk facts remain None / UNKNOWN.
- Governed Plan-as-Artifact: Validated deterministically outside LLM via PlanArtifactValidator.
- Public Authority Ingress: Consumes controller.resolve_proposal_authority_context() and public gateway methods.
"""

from typing import Dict, List, Optional, Tuple, Mapping
import hashlib
from datetime import datetime, timezone

from domain.models import (
    Task,
    Obligation,
    Claim,
    Policy,
    Evidence,
    AssessmentReceipt,
)
from domain.types import (
    ObligationStatus,
    ClaimStatus,
    AssessmentVerdict,
)
from domain.compiler import CompiledDomainPackage
from claim.reducer import reduce_claim, ClaimReductionState, ClaimEpistemicState
from claim.receipts import mint_assessment_receipt, verify_assessment_receipt_signature
from claim.adapter import ObservationEvidenceAdapter
from controller.controller import SClassController
from controller.authorization import ActionProposal, AuthorizationStatus
from controller.token import ActionBinding, ExecutionContext, ExecutionEnvelope
from execution.gateway import D6ExecutionGateway
from agent.live_worker import LiveModelWorker
from agent.models import GENESIS_DIGEST, AgentTurnStatus
from agent.protocol import AgentMessageChainValidator
from benchmark.parity.gate_3_authority import Gate3AuthoritySigner
from orchestrator.models import (
    ReasoningMode,
    OrchestrationStateSnapshot,
    RoutingDecision,
    StrategicPlanArtifact,
    PlanStage,
    RepositoryFacts,
    TaskRiskAssessment,
    VerificationProfile,
)
from orchestrator.optimizer import StateOptimizerRouter
from orchestrator.context import BoundedContextBuilder
from orchestrator.validator import PlanArtifactValidator
from planner.models import PlanStatus


class GovernedOrchestrationSession:
    """
    Manages multi-turn governed reasoning and execution lifecycle for an S-Class task.
    Distinguishes strictly between authoritative state projections and ephemeral working state.
    """

    def __init__(
        self,
        package: CompiledDomainPackage,
        session_id: str = "SESS-ORCH-001",
        max_turns: int = 10,
        initial_budget_units: float = 10.0,
        available_providers: Tuple[str, ...] = ("gemini", "openai", "anthropic", "local"),
    ):
        # 1. Immutable Input Package & Authoritative Projections
        self.package: CompiledDomainPackage = package
        self.session_id: str = session_id
        self.max_turns: int = max_turns
        self.available_providers: Tuple[str, ...] = available_providers

        self.obligations_by_id: Dict[str, Obligation] = dict(package.obligations_by_id)
        self.claims_by_id: Dict[str, Claim] = dict(package.claims_by_id)
        self.policies_by_id: Dict[str, Policy] = dict(package.policies_by_id)
        self.claim_states: Dict[str, ClaimReductionState] = {}
        self.latest_receipts: Dict[str, AssessmentReceipt] = {}

        # 2. Ephemeral Session Working Memory (Transient)
        self.remaining_budget_units: float = initial_budget_units
        self.turn_index: int = 1
        self.previous_digest: str = GENESIS_DIGEST
        self.active_plan: Optional[StrategicPlanArtifact] = None
        self.repair_attempts: Dict[str, int] = {obl_id: 0 for obl_id in self.obligations_by_id}
        self.turn_summaries: List[str] = []
        self.latest_failure_diagnostics: List[str] = []
        self.current_code_content: str = ""

        # Compute initial ready frontier
        self._refresh_frontier()

    def _refresh_frontier(self) -> None:
        """Projects ready, failed, and satisfied obligation sets from authoritative receipts."""
        ready = []
        failed = []
        satisfied = []

        for obl_id, obl in self.obligations_by_id.items():
            receipt = self.latest_receipts.get(obl_id)
            if receipt and receipt.verdict == AssessmentVerdict.SATISFIED:
                satisfied.append(obl_id)
            elif receipt and receipt.verdict == AssessmentVerdict.REJECTED:
                failed.append(obl_id)
            else:
                # Check prerequisites
                prereqs_satisfied = all(
                    dep in satisfied for dep in obl.depends_on
                )
                if prereqs_satisfied:
                    ready.append(obl_id)

        self.ready_obligation_ids = tuple(ready)
        self.failed_obligation_ids = tuple(failed)
        self.satisfied_obligation_ids = tuple(satisfied)

    def snapshot(self) -> OrchestrationStateSnapshot:
        """
        Builds an immutable projection snapshot of current authoritative and session state.
        Derives all facts strictly from authoritative package/task data without manufactured constants.
        """
        self._refresh_frontier()

        # Derive facts strictly from authoritative input package
        task = self.package.task
        repo_facts = RepositoryFacts(
            languages=task.constraints.languages,
            dirty_working_tree=task.repository_context.dirty_working_tree,
            has_test_framework=None,
            test_framework_name="UNKNOWN",
            estimated_symbol_count=None,
        )

        task_risk = TaskRiskAssessment(
            criticality_score=None,
            blast_radius="UNKNOWN",
            complexity_score=None,
            requires_formal_verification=None,
        )

        verif_profile = VerificationProfile(
            requires_unit_tests=None,
            requires_property_tests=None,
            requires_regression_run=None,
            requires_security_audit=None,
            requires_soak_test=None,
        )

        return OrchestrationStateSnapshot(
            task_id=self.package.task.task_id,
            source_sha=self.package.task.repository_context.base_commit_sha,
            policy_version=1,
            obligations=tuple(self.obligations_by_id.values()),
            claims=tuple(self.claims_by_id.values()),
            policies=tuple(self.policies_by_id.values()),
            claim_states=dict(self.claim_states),
            latest_receipts=dict(self.latest_receipts),
            ready_obligation_ids=self.ready_obligation_ids,
            satisfied_obligation_ids=self.satisfied_obligation_ids,
            failed_obligation_ids=self.failed_obligation_ids,
            active_plan=self.active_plan,
            repository_facts=repo_facts,
            task_risk=task_risk,
            verification_profile=verif_profile,
            available_providers=self.available_providers,
            repair_attempts_by_obligation=dict(self.repair_attempts),
            turn_index=self.turn_index,
            max_turns=self.max_turns,
            remaining_budget_units=self.remaining_budget_units,
        )

    def execute_turn(
        self,
        worker: LiveModelWorker,
        controller: SClassController,
        gateway: D6ExecutionGateway,
        authority_signer: Gate3AuthoritySigner,
        workspace_id: str,
        test_harness_template: str,
        current_time_iso: str = "2026-08-20T12:00:00Z",
        expires_time_iso: str = "2026-08-20T13:00:00Z",
    ) -> Tuple[RoutingDecision, Optional[AssessmentReceipt], bool]:
        """
        Executes a single end-to-end governed reasoning and execution turn.
        Returns: (RoutingDecision, Optional[AssessmentReceipt], is_terminal).
        """
        state_snap = self.snapshot()
        decision = StateOptimizerRouter.derive_next_decision(state_snap)

        if decision.mode in (ReasoningMode.CLOSE, ReasoningMode.ESCALATE):
            return decision, None, True

        # 1. Build bounded context
        active_target_code = self.current_code_content if self.current_code_content else None
        agent_context = BoundedContextBuilder.build_agent_context(
            state=state_snap,
            decision=decision,
            session_id=self.session_id,
            repository_id=self.package.task.repository_context.repository_id,
            symbol_context=active_target_code,
            failure_diagnostics=self.latest_failure_diagnostics,
            prior_turn_summaries=self.turn_summaries,
        )

        # 2. Query Live Model Worker
        msg = worker.generate_inbound_message(
            context=agent_context,
            sequence=self.turn_index,
            previous_digest=self.previous_digest,
            history=(),
        )

        valid, err, _, turn_resp = AgentMessageChainValidator.validate_inbound_message(
            message=msg,
            expected_session_id=self.session_id,
            expected_worker_id=worker.worker_id,
            expected_sequence=self.turn_index,
            expected_previous_digest=self.previous_digest,
        )

        if not valid or turn_resp is None:
            self.turn_summaries.append(f"Turn {self.turn_index} failed chain validation: {err}")
            self.turn_index += 1
            self._refresh_frontier()
            return decision, None, False

        self.previous_digest = msg.message_digest

        # 3. Handle PLAN / REPLAN Artifact Synthesis with Out-of-LLM Validation
        if decision.mode in (ReasoningMode.PLAN, ReasoningMode.REPLAN):
            stages = tuple(
                PlanStage(
                    stage_id=f"STAGE-{i+1}",
                    title=f"Execute {obl_id}",
                    target_obligation_ids=(obl_id,),
                    prerequisite_stage_ids=(),
                    description=f"Plan stage for {obl_id}",
                    verification_gate="D6 sandbox test",
                    evidence_types_required=("D6_EXECUTION_OBSERVATION",),
                )
                for i, obl_id in enumerate(self.ready_obligation_ids)
            )
            candidate_plan = StrategicPlanArtifact(
                plan_id=f"PLAN-{self.turn_index:03d}",
                task_id=self.package.task.task_id,
                version=1 if decision.mode == ReasoningMode.PLAN else (self.active_plan.version + 1 if self.active_plan else 2),
                strategy_name="TDD_INVARIANCE_STRATEGY",
                rationale=turn_resp.thought[:200],
                plan_claims=tuple(self.claims_by_id.keys()),
                stages=stages,
                dependency_edges=(),
                evidence_requirements=("D6_EXECUTION_OBSERVATION",),
                identified_risks=("Potential regression",),
                potential_contradictions=(),
                revision_lineage=(self.active_plan.plan_id,) if self.active_plan else (),
                status=PlanStatus.DRAFT,
                created_at_iso=current_time_iso,
            )

            # Deterministically validate plan artifact outside LLM
            is_valid, val_reason, validated_plan = PlanArtifactValidator.validate(
                candidate_plan,
                self.obligations_by_id,
            )

            if is_valid:
                self.active_plan = validated_plan
                self.turn_summaries.append(f"Turn {self.turn_index} (PLAN): Formulated and validated plan {self.active_plan.plan_id}")
            else:
                self.active_plan = validated_plan
                self.turn_summaries.append(f"Turn {self.turn_index} (PLAN): Candidate plan rejected: {val_reason}")

            self.turn_index += 1
            self.remaining_budget_units -= 1.0
            self._refresh_frontier()
            return decision, None, False

        tool_calls = turn_resp.tool_calls
        if not tool_calls:
            self.turn_summaries.append(f"Turn {self.turn_index} ({decision.mode.value}): {turn_resp.thought[:100]}")
            self.turn_index += 1
            self.remaining_budget_units -= 1.0
            self._refresh_frontier()
            return decision, None, False

        # 4. Extract tool call parameters
        first_call = tool_calls[0]
        code_content = first_call.arguments.get("code_content", self.current_code_content)
        if "code_content" in first_call.arguments:
            self.current_code_content = code_content

        target_obl_id = decision.active_frontier_ids[0] if decision.active_frontier_ids else list(self.obligations_by_id.keys())[0]
        target_claim = next((c for c in self.claims_by_id.values() if c.obligation_id == target_obl_id), list(self.claims_by_id.values())[0])

        # 5. Route through D5 Controller using strictly PUBLIC APIs
        provider = gateway.resolve_provider_for_action("EXECUTE_TEST")
        provider_id = provider.provider_id if provider else "pytest_runner_engine"

        exec_ctx = ExecutionContext(
            provider_id=provider_id,
            sandbox_profile_id="standard_sbx",
            workspace_id=workspace_id,
            resource_profile_id="default_res",
            capability_set=("CAP_EXEC_TEST",),
        )

        # Authoritatively resolve coordinates via Controller's public authority resolver
        auth_ctx = controller.resolve_proposal_authority_context(self.package.task.task_id)

        proposal = ActionProposal(
            proposal_id=f"PROP-ORCH-{self.turn_index:03d}",
            obligation_id=target_obl_id,
            action_type="EXECUTE_TEST",
            target="test_target_module.py",
            purpose=f"Execute verification for turn {self.turn_index}",
            execution_context=exec_ctx,
            parameters={"code_content": self.current_code_content, "test_content": test_harness_template},
            owner_id=auth_ctx.owner_id,
            fencing_token=auth_ctx.fencing_token,
            lease_epoch=auth_ctx.lease_epoch,
            state_version=auth_ctx.state_version,
            state_digest=auth_ctx.state_digest,
        )

        dispatch = controller.submit_proposal(
            proposal=proposal,
            obligations=self.package.obligations_by_id,
            policies=self.package.policies_by_id,
            source_sha=self.package.task.repository_context.base_commit_sha,
            policy_version=1,
            evaluated_at=current_time_iso,
            expires_at=expires_time_iso,
            allowed_action_types=["EXECUTE_TEST"],
        )

        if dispatch.decision.status != AuthorizationStatus.AUTHORIZED:
            reasons_str = ", ".join(dispatch.decision.rejection_reasons)
            self.turn_summaries.append(f"Turn {self.turn_index} REJECTED by D5 Controller: {reasons_str}")
            self.turn_index += 1
            self._refresh_frontier()
            return decision, None, False

        token = dispatch.execution_token
        binding = ActionBinding(
            action_type="EXECUTE_TEST",
            target="test_target_module.py",
            purpose=proposal.purpose,
            parameters=proposal.parameters,
        )

        admission = controller.admit_execution(
            token=token,
            expected_obligation_id=target_obl_id,
            expected_source_sha=self.package.task.repository_context.base_commit_sha,
            expected_policy_version=1,
            expected_action_binding=binding,
            expected_execution_context=exec_ctx,
            current_time_iso=current_time_iso,
        )

        if not admission.is_admitted:
            self.turn_summaries.append(f"Turn {self.turn_index} ADMISSION FAILED: {admission.reason}")
            self.turn_index += 1
            self._refresh_frontier()
            return decision, None, False

        # 6. Execute in D6 Gateway
        envelope = ExecutionEnvelope(
            token=token,
            admission=admission,
            action_binding=binding,
            execution_context=exec_ctx,
        )

        obs = gateway.execute(
            envelope=envelope,
            expected_source_sha=self.package.task.repository_context.base_commit_sha,
            expected_policy_version=1,
            current_time_iso=current_time_iso,
            timeout_seconds=20.0,
        )

        # 7. Convert to Evidence & Reduce Claim
        ev = ObservationEvidenceAdapter.create_evidence(
            observation=obs,
            claim=target_claim,
            source_sha=self.package.task.repository_context.base_commit_sha,
        )
        reduction = reduce_claim(target_claim, [ev], self.package.task.repository_context.base_commit_sha)
        self.claim_states[target_claim.claim_id] = reduction

        receipt = mint_assessment_receipt(
            receipt_id=f"RCPT-ORCH-{self.turn_index:03d}",
            obligation_id=target_obl_id,
            policy_version=1,
            repository_sha=self.package.task.repository_context.base_commit_sha,
            claim_states={target_claim.claim_id: reduction},
            intended_claims={target_claim.claim_id: target_claim},
            evaluated_at=current_time_iso,
            authority_signer=authority_signer,
        )
        self.latest_receipts[target_obl_id] = receipt

        # 8. Update turn state & diagnostics
        if receipt.verdict == AssessmentVerdict.SATISFIED:
            self.latest_failure_diagnostics = []
            self.turn_summaries.append(f"Turn {self.turn_index}: Obligation '{target_obl_id}' SATISFIED.")
        else:
            self.repair_attempts[target_obl_id] = self.repair_attempts.get(target_obl_id, 0) + 1
            diags = []
            if obs.raw_stdout_sample:
                diags.extend([line for line in obs.raw_stdout_sample.splitlines() if line.strip()])
            if obs.raw_stderr_sample:
                diags.extend([line for line in obs.raw_stderr_sample.splitlines() if line.strip()])
            for d in obs.diagnostics:
                diags.append(d.get("msg", d.get("error", str(d))))
            if not diags:
                diags.append(f"Execution failed with exit code {obs.exit_code}")
            self.latest_failure_diagnostics = diags
            self.turn_summaries.append(f"Turn {self.turn_index}: Obligation '{target_obl_id}' REJECTED.")

        self.turn_index += 1
        self.remaining_budget_units -= 1.0
        self._refresh_frontier()

        return decision, receipt, False
