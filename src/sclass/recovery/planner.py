"""
S-Class Bounded Canonical Recovery Planner (D9.4).
Converts validated canonical recovery state and frontier into a declarative,
bounded repair plan for Controller authorization and execution.

Invariants:
- Canonical inputs only: loads exclusively from authoritative persistence.
- Rejects caller assertions of unaccepted obligations or forged frontiers.
- Deterministic planning: identical canonical state -> identical plan.
- Bounded: respects attempt bounds, recursion depth bounds, and budget bounds.
- Controller boundary: declarative only; executes nothing; cannot transition state.
- Derived state persistence: persists plan with canonical provenance without replacing authoritative state.
"""

from __future__ import annotations
import os
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union, Tuple

from sclass.core.errors import RecoveryError, SecurityViolationError
from sclass.recovery.models import (
    RecoveryRecord,
    RecoveryState,
    RepairObligation,
    RegressionAssessment,
    FrontierRecomputation,
    RepairPlan,
    RepairStep,
    RepairStrategy,
    RecoveryBounds,
)
from sclass.recovery.persistence import RecoveryPersistence
from sclass.state.tasks import StateRepository


class RecoveryPlanner:
    """
    Deterministic, bounded recovery planner.
    Converts canonical recovery state into an actionable, bounded repair plan.
    Planner output is strictly declarative; all execution requires Controller authorization.
    """

    def __init__(
        self,
        workspace_dir: str,
        persistence: Optional[RecoveryPersistence] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.persistence = persistence or RecoveryPersistence(workspace_dir)

    def direct_execute(self, action: Any) -> None:
        """
        Direct action execution from the planner is strictly forbidden.
        Enforces Criterion A / Controller boundary: Planner cannot directly execute.
        All actions must be submitted to D5 Controller for authorization.
        """
        raise SecurityViolationError(
            "Criterion A Violation: Planner cannot directly execute actions. "
            "All actions must be submitted to D5 Controller for authorization."
        )

    def create_plan(
        self,
        recovery_id: Union[str, RecoveryRecord],
        caller_frontier: Optional[Any] = None,
        caller_accepted_obligations: Optional[List[str]] = None,
        fail_closed: bool = True,
        recursion_depth: int = 0,
        max_recursion_depth: int = 3,
        budget_limit: Optional[float] = None,
        current_cost: float = 0.0,
    ) -> RepairPlan:
        """
        Converts canonical recovery state into a bounded, deterministic RepairPlan.

        Enforces:
        - Canonical inputs only: loads strictly from authoritative StateRepository / persistence.
        - Fails closed when recovery record, repair obligation, or canonical frontier is missing.
        - Rejects forged caller frontiers or unaccepted obligation assertions.
        - Enforces monotonic attempt limits, recursion depth bounds, and budget limits.
        - Declarative only: does not execute actions or transition recovery state.
        """
        # 1. Authoritative canonical recovery record lookup
        if isinstance(recovery_id, str):
            rec_id = recovery_id
        elif hasattr(recovery_id, "recovery_id"):
            rec_id = recovery_id.recovery_id
        else:
            raise RecoveryError("Invalid recovery_id provided for recovery planning.")

        canonical_record = self.persistence.load_recovery(rec_id)
        if not canonical_record:
            raise RecoveryError(
                f"Missing canonical recovery record: recovery '{rec_id}' not found in authoritative state store."
            )
        record = canonical_record

        # 2. Reject caller assertions of unaccepted obligations
        state_repo = StateRepository(self.workspace_dir)
        if caller_accepted_obligations:
            for ob_id in caller_accepted_obligations:
                if not ob_id:
                    continue
                claim_obj = state_repo.get_claim(ob_id)
                verifs = state_repo.list_verifications(claim_id=ob_id) if claim_obj else []
                if not any(str(v.get("status", "")).upper() in ("ACCEPT", "PASS") for v in verifs):
                    raise RecoveryError(
                        f"Untrusted obligation assertion: obligation '{ob_id}' is not an authoritatively accepted claim in StateRepository."
                    )

        # 3. Canonical repair obligation requirement
        repair_ob = record.current_repair_obligation
        if not repair_ob:
            raise RecoveryError(
                f"Required repair obligation is unavailable for recovery '{rec_id}'."
            )

        # 4. Canonical frontier binding
        canonical_frontier = self._resolve_canonical_frontier(record, fail_closed=fail_closed)
        if canonical_frontier is None or not canonical_frontier.is_valid:
            raise RecoveryError(
                f"Missing canonical frontier: authoritative frontier recomputation is missing or invalid for recovery '{rec_id}'."
            )

        # Reject forged caller-supplied frontier
        if caller_frontier is not None:
            c_valid = getattr(caller_frontier, "is_valid", False)
            c_obs = tuple(getattr(caller_frontier, "frontier_obligations", ()))
            c_pres = tuple(getattr(caller_frontier, "preserved_obligation_ids", ()))
            if (
                c_valid != canonical_frontier.is_valid
                or set(c_obs) != set(canonical_frontier.frontier_obligations)
                or set(c_pres) != set(canonical_frontier.preserved_obligation_ids)
            ):
                raise RecoveryError(
                    "Forged frontier rejected: caller-supplied frontier diverges from authoritative canonical frontier."
                )

        # 5. Bounded recovery enforcement
        # 5a. Attempts bound
        if record.attempt_number >= record.max_attempts:
            if fail_closed:
                raise RecoveryError(
                    f"Recovery attempts exhausted: attempt {record.attempt_number} >= max_attempts {record.max_attempts}."
                )
            return None

        # 5b. Recursion depth bound
        eff_depth = max(recursion_depth, int(record.metadata.get("recursion_depth", 0)))
        eff_max_depth = int(record.metadata.get("max_recursion_depth", max_recursion_depth))
        if eff_depth >= eff_max_depth:
            if fail_closed:
                raise RecoveryError(
                    f"Recovery recursion depth limit exceeded: depth {eff_depth} >= max {eff_max_depth}."
                )
            return None

        # 5c. Budget limit bound
        eff_budget = budget_limit if budget_limit is not None else record.metadata.get("budget_limit")
        eff_cost = current_cost if current_cost > 0 else float(record.metadata.get("current_cost", 0.0))
        if eff_budget is not None and eff_cost >= float(eff_budget):
            if fail_closed:
                raise RecoveryError(
                    f"Recovery budget exhausted: current cost {eff_cost} >= limit {eff_budget}."
                )
            return None

        # 6. Deterministic Strategy Selection
        classification = str(record.failure_classification).upper()
        staleness = record.staleness_cause
        target = repair_ob.target or record.affected_obligation_id

        if staleness or "STALE" in classification:
            strategy = RepairStrategy.WORKSPACE_RECONCILIATION
            rationale = f"Reconcile workspace drift caused by: {staleness or classification}."
        elif "DEPENDENCY" in classification:
            strategy = RepairStrategy.DEPENDENCY_RECOMPILATION
            rationale = f"Recompile affected dependencies for target: {target}."
        elif "ROLLBACK" in classification:
            strategy = RepairStrategy.ISOLATED_ROLLBACK
            rationale = f"Roll back regression defects affecting target: {target}."
        else:
            strategy = RepairStrategy.TARGETED_REPAIR
            rationale = f"Apply deterministic targeted repair patch for obligation {repair_ob.obligation_id}."

        # 7. Deterministic Ordered Steps
        steps = (
            RepairStep(
                step_id="step_01_isolate",
                action_type="isolate_target",
                target=target,
                description=f"Isolate target workspace state for {target}",
                parameters={"target": target, "recovery_id": record.recovery_id},
            ),
            RepairStep(
                step_id="step_02_patch",
                action_type="apply_repair",
                target=target,
                description=f"Execute bounded repair strategy {strategy.value} on {target}",
                parameters={
                    "target": target,
                    "strategy": strategy.value,
                    "obligation_id": repair_ob.obligation_id,
                    "attempt_number": record.attempt_number + 1,
                },
            ),
            RepairStep(
                step_id="step_03_reverify_target",
                action_type="reverify_target",
                target=target,
                description=f"Independently verify repaired target {target}",
                parameters={
                    "target": target,
                    "claim_id": record.affected_claim_id or "",
                    "obligation_id": repair_ob.obligation_id,
                },
            ),
            RepairStep(
                step_id="step_04_regression_reverify",
                action_type="regression_reverify",
                target=",".join(sorted(canonical_frontier.preserved_obligation_ids)),
                description="Re-verify preserved obligations to guarantee zero regressions",
                parameters={
                    "preserved_obligation_ids": list(canonical_frontier.preserved_obligation_ids),
                },
            ),
        )

        bounds = RecoveryBounds(
            max_attempts=record.max_attempts,
            current_attempt=record.attempt_number,
            max_recursion_depth=eff_max_depth,
            current_recursion_depth=eff_depth,
            budget_limit=float(eff_budget) if eff_budget is not None else None,
            current_cost=float(eff_cost),
        )

        provenance = {
            "recovery_id": record.recovery_id,
            "canonical_state_ref": record.project_state_ref or record.created_at,
            "repair_obligation_id": repair_ob.obligation_id,
            "frontier_recomputed_at": canonical_frontier.recomputed_at,
            "preserved_count": len(canonical_frontier.preserved_obligation_ids),
        }

        # Deterministic created_at tied to canonical state
        existing_plan = record.metadata.get("repair_plan") if isinstance(record.metadata, dict) else None
        if existing_plan and isinstance(existing_plan, dict) and "created_at" in existing_plan:
            created_at_ts = existing_plan["created_at"]
        else:
            created_at_ts = (
                repair_ob.created_at
                or record.created_at
                or "2026-09-23T00:00:00Z"
            )

        plan = RepairPlan(
            recovery_id=record.recovery_id,
            task_id=record.task_id,
            repair_obligation_id=repair_ob.obligation_id,
            selected_strategy=strategy.value,
            ordered_repair_steps=steps,
            constraints=bounds.to_dict(),
            rationale=rationale,
            is_valid=True,
            provenance=provenance,
            created_at=created_at_ts,
        )

        # 8. Persist generated plan only as derived planner state with canonical provenance
        record.metadata["repair_plan"] = plan.to_dict()
        record.repair_plan = plan
        self.persistence.save_recovery(record)

        return plan

    def _resolve_canonical_frontier(
        self,
        record: RecoveryRecord,
        fail_closed: bool = True,
    ) -> Optional[FrontierRecomputation]:
        """Resolves the canonical frontier from authoritative persistence or derives it canonically."""
        if record.frontier_recomputation and record.frontier_recomputation.is_valid:
            return record.frontier_recomputation

        state_repo = StateRepository(self.workspace_dir)
        frontier_meta = state_repo.get_task_frontier(record.task_id)
        if frontier_meta and frontier_meta.get("is_valid"):
            rec = FrontierRecomputation.from_dict(frontier_meta)
            record.frontier_recomputation = rec
            return rec

        # Recompute canonically via RecoveryEngine
        from sclass.recovery.engine import RecoveryEngine
        engine = RecoveryEngine(self.workspace_dir, persistence=self.persistence)
        try:
            frontier = engine.recompute_frontier(record.recovery_id, fail_closed=fail_closed)
            if frontier and frontier.is_valid:
                record.frontier_recomputation = frontier
                record.metadata["frontier_recomputation"] = frontier.to_dict()
                try:
                    self.persistence.save_recovery(record)
                except Exception:
                    pass
            return frontier
        except Exception:
            return None
