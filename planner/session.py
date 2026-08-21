"""D8 Autonomous Planning Substrate - Planning Session Coordinator (§3.6, §8.1).

End-to-end planning session coordinator orchestrating lease ownership,
state projection, candidate generation, hard gating, and proposal emission.
"""

from __future__ import annotations
from typing import Optional, Sequence, Tuple

from controller.authorization import ActionProposal
from controller.token import ExecutionContext
from domain.types import HEX_64_PATTERN
from planner.convergence import ConvergenceMonitor
from planner.emitter import ProposalEmitter
from planner.evaluator import PlanEvaluator
from planner.fingerprint import (
    compute_execution_strategy_fingerprint,
    compute_plan_semantic_fingerprint,
)
from planner.generator import CandidateGenerator
from planner.lease import PlanningLease, PlanningLeaseManager
from planner.models import (
    ExecutionStrategyArtifact,
    Plan,
    PlanQualityScore,
    PlanRuntimeEnvelope,
    PlanStatus,
    PlannerStateView,
)


class NoAdmissiblePlanError(RuntimeError):
    """Raised when all candidate plans are rejected by hard constraint or risk gates."""
    pass


class PlannerSession:
    """Orchestrates an active planning session for a governed task."""

    def __init__(
        self,
        task_id: str,
        owner_id: str,
        lease_manager: PlanningLeaseManager,
        generator: Optional[CandidateGenerator] = None,
        convergence_monitor: Optional[ConvergenceMonitor] = None,
        ttl_seconds: float = 60.0,
    ):
        self.task_id = task_id
        self.owner_id = owner_id
        self._lease_manager = lease_manager
        self._generator = generator or CandidateGenerator()
        self._convergence = convergence_monitor or ConvergenceMonitor()
        self._ttl_seconds = ttl_seconds
        self._active_lease: Optional[PlanningLease] = None
        self._active_envelope: Optional[PlanRuntimeEnvelope] = None

    @property
    def active_lease(self) -> Optional[PlanningLease]:
        return self._active_lease

    @property
    def active_envelope(self) -> Optional[PlanRuntimeEnvelope]:
        return self._active_envelope

    def __enter__(self) -> 'PlannerSession':
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self) -> PlanningLease:
        """Acquires the exclusive planning lease."""
        self._active_lease = self._lease_manager.acquire_lease(
            task_id=self.task_id,
            owner_id=self.owner_id,
            ttl_seconds=self._ttl_seconds,
        )
        return self._active_lease

    def close(self) -> bool:
        """Releases the planning lease."""
        if self._active_lease:
            released = self._lease_manager.release_lease(self._active_lease)
            self._active_lease = None
            return released
        return True

    def plan(
        self,
        state_view: PlannerStateView,
        context: ExecutionContext,
        budget_remaining: float = 100.0,
    ) -> Tuple[PlanRuntimeEnvelope, PlanQualityScore]:
        """Generates, evaluates, and establishes the initial validated plan."""
        if not self._active_lease or not self._lease_manager.is_lease_valid(self._active_lease):
            raise RuntimeError("Cannot plan without a valid active planning lease.")

        # Renew lease to ensure freshness
        self._active_lease = self._lease_manager.renew_lease(
            self._active_lease,
            ttl_seconds=self._ttl_seconds,
        )

        candidates_with_prov = self._generator.generate(
            state_view=state_view,
            context=context,
            max_candidates=3,
        )

        admissible_plans: list[Tuple[ExecutionStrategyArtifact, PlanQualityScore]] = []
        for strat, _ in candidates_with_prov:
            is_admissible, score = PlanEvaluator.evaluate(
                strategy=strat,
                state_view=state_view,
                budget_remaining=budget_remaining,
            )
            if is_admissible:
                admissible_plans.append((strat, score))

        if not admissible_plans:
            raise NoAdmissiblePlanError(
                f"No candidate plan satisfied hard constraint and risk gates for task '{self.task_id}'."
            )

        # Select highest progress potential plan
        admissible_plans.sort(key=lambda item: item[1].progress_potential, reverse=True)
        best_strategy, best_score = admissible_plans[0]

        # Extract obligation IDs
        obligation_ids = tuple(
            obl.get("obligation_id", "") for obl in state_view.content.obligations if isinstance(obl, dict) and "obligation_id" in obl
        ) or tuple(state_view.content.executable_frontier)

        d0_plan = Plan(
            plan_id=best_strategy.plan_id,
            task_id=self.task_id,
            version=best_strategy.plan_revision,
            milestones=state_view.content.milestones,
            architecture_claims=state_view.content.claims,
            obligation_ids=obligation_ids,
            status=PlanStatus.VALIDATED,
            created_at=state_view.metadata.projected_at,
            rationale="Deterministic S-Class plan synthesized from state projection",
        )

        # Compute fingerprints
        strat_fp = compute_execution_strategy_fingerprint(best_strategy)
        semantic_fp = compute_plan_semantic_fingerprint(d0_plan)

        envelope = PlanRuntimeEnvelope(
            plan=d0_plan,
            strategy=best_strategy,
            fencing_token=self._active_lease.fencing_token,
            lease_epoch=self._active_lease.lease_epoch,
            owner_id=self._active_lease.owner_id,
            state_version=state_view.content.state_version,
            state_digest=state_view.content.state_digest,
            planner_state_digest=state_view.planner_state_digest,
            plan_semantic_fingerprint=semantic_fp,
            execution_strategy_fingerprint=strat_fp,
            status=PlanStatus.VALIDATED,
        )

        self._convergence.record_initial_plan(
            strategy_fingerprint=strat_fp,
            state_view=state_view,
            progress_potential=best_score.progress_potential,
        )

        self._active_envelope = envelope
        return envelope, best_score

    def replan(
        self,
        state_view: PlannerStateView,
        context: ExecutionContext,
        budget_remaining: float = 100.0,
    ) -> Tuple[PlanRuntimeEnvelope, PlanQualityScore]:
        """Performs bounded replanning triggered by state delta."""
        if not self._active_lease or not self._lease_manager.is_lease_valid(self._active_lease):
            raise RuntimeError("Cannot replan without a valid active planning lease.")

        # Renew lease
        self._active_lease = self._lease_manager.renew_lease(
            self._active_lease,
            ttl_seconds=self._ttl_seconds,
        )

        candidates_with_prov = self._generator.generate(
            state_view=state_view,
            context=context,
            max_candidates=3,
        )

        admissible_plans: list[Tuple[ExecutionStrategyArtifact, PlanQualityScore]] = []
        for strat, _ in candidates_with_prov:
            is_admissible, score = PlanEvaluator.evaluate(
                strategy=strat,
                state_view=state_view,
                budget_remaining=budget_remaining,
            )
            if is_admissible:
                admissible_plans.append((strat, score))

        if not admissible_plans:
            raise NoAdmissiblePlanError(
                f"Replanning failed: No admissible candidate for task '{self.task_id}'."
            )

        admissible_plans.sort(key=lambda item: item[1].progress_potential, reverse=True)
        best_strategy, best_score = admissible_plans[0]

        obligation_ids = tuple(
            obl.get("obligation_id", "") for obl in state_view.content.obligations if isinstance(obl, dict) and "obligation_id" in obl
        ) or tuple(state_view.content.executable_frontier)

        d0_plan = Plan(
            plan_id=best_strategy.plan_id,
            task_id=self.task_id,
            version=best_strategy.plan_revision,
            milestones=state_view.content.milestones,
            architecture_claims=state_view.content.claims,
            obligation_ids=obligation_ids,
            status=PlanStatus.VALIDATED,
            created_at=state_view.metadata.projected_at,
            rationale="Replanned S-Class plan synthesized from state delta",
        )

        strat_fp = compute_execution_strategy_fingerprint(best_strategy)
        semantic_fp = compute_plan_semantic_fingerprint(d0_plan)

        # Record replan in convergence monitor (validates budget, state delta, and oscillation)
        self._convergence.record_replan(
            new_strategy_fingerprint=strat_fp,
            current_state_view=state_view,
            progress_potential=best_score.progress_potential,
        )

        envelope = PlanRuntimeEnvelope(
            plan=d0_plan,
            strategy=best_strategy,
            fencing_token=self._active_lease.fencing_token,
            lease_epoch=self._active_lease.lease_epoch,
            owner_id=self._active_lease.owner_id,
            state_version=state_view.content.state_version,
            state_digest=state_view.content.state_digest,
            planner_state_digest=state_view.planner_state_digest,
            plan_semantic_fingerprint=semantic_fp,
            execution_strategy_fingerprint=strat_fp,
            status=PlanStatus.VALIDATED,
        )

        self._active_envelope = envelope
        return envelope, best_score

    def next_proposal(
        self,
        envelope: Optional[PlanRuntimeEnvelope] = None,
        completed_nodes: Sequence[str] = (),
    ) -> Optional[ActionProposal]:
        """Emits the next executable ActionProposal bound to the active lease."""
        env = envelope or self._active_envelope
        if not env:
            raise RuntimeError("No active plan envelope available.")
        if not self._active_lease or not self._lease_manager.is_lease_valid(self._active_lease):
            raise RuntimeError("Planning lease has expired or is invalid.")

        return ProposalEmitter.emit_next_proposal(
            strategy=env.strategy,
            lease=self._active_lease,
            state_version=env.state_version,
            state_digest=env.state_digest,
            completed_node_ids=completed_nodes,
        )
