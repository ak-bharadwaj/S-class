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
from dataclasses import replace

from sclass.core.errors import RecoveryError, SecurityViolationError, RecoveryPersistenceError
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

        # 4. Canonical frontier binding (strictly recomputed from authoritative state)
        canonical_frontier = self._resolve_canonical_frontier(
            record,
            caller_frontier=caller_frontier,
            fail_closed=fail_closed,
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

        # Plan provenance and timestamps must derive strictly from canonical recovery/repair/frontier state.
        # Persisted metadata["repair_plan"] must NEVER be used as an input to generate a new plan.
        created_at_ts = (
            repair_ob.created_at
            or record.created_at
            or "2026-09-23T00:00:00Z"
        )
        frontier_ts = canonical_frontier.recomputed_at

        provenance = {
            "recovery_id": record.recovery_id,
            "canonical_state_ref": record.project_state_ref or record.created_at,
            "repair_obligation_id": repair_ob.obligation_id,
            "frontier_recomputed_at": frontier_ts,
            "preserved_count": len(canonical_frontier.preserved_obligation_ids),
        }

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

    def _validate_frontier_identity(
        self,
        candidate: Any,
        canonical: FrontierRecomputation,
        source_name: str,
    ) -> None:
        """
        Validates the complete frontier identity against the canonically recomputed frontier:
        - task ID
        - repaired obligation
        - preserved obligations
        - invalidated obligations
        - unresolved obligations
        - frontier obligations
        - validity
        All identity fields are required to exist and exactly match.
        Missing/empty required identity fields fail closed.
        Fails closed on any divergence.
        """
        is_caller = (source_name == "caller_frontier")
        prefix = "Forged frontier rejected" if is_caller else f"Forged persisted frontier rejected ({source_name})"

        if candidate is None:
            raise RecoveryError(f"{prefix}: frontier identity cannot be None.")

        # Determine field presence and values
        if isinstance(candidate, dict):
            has_task_id = "task_id" in candidate and candidate["task_id"] is not None and bool(str(candidate["task_id"]).strip())
            c_task_id = str(candidate.get("task_id", "") or "").strip()

            has_rep_ob = "repaired_obligation_id" in candidate and candidate["repaired_obligation_id"] is not None and bool(str(candidate["repaired_obligation_id"]).strip())
            c_rep_ob = str(candidate.get("repaired_obligation_id", "") or "").strip()

            has_pres = "preserved_obligation_ids" in candidate and candidate["preserved_obligation_ids"] is not None
            c_pres = tuple(candidate.get("preserved_obligation_ids") or ())

            has_inval = "invalidated_obligation_ids" in candidate and candidate["invalidated_obligation_ids"] is not None
            c_inval = tuple(candidate.get("invalidated_obligation_ids") or ())

            has_unres = "unresolved_obligation_ids" in candidate and candidate["unresolved_obligation_ids"] is not None
            c_unres = tuple(candidate.get("unresolved_obligation_ids") or ())

            has_front = "frontier_obligations" in candidate and candidate["frontier_obligations"] is not None
            c_front = tuple(candidate.get("frontier_obligations") or ())

            has_valid = "is_valid" in candidate and candidate["is_valid"] is not None
            c_valid = bool(candidate.get("is_valid"))
        else:
            has_task_id = hasattr(candidate, "task_id") and getattr(candidate, "task_id", None) is not None and bool(str(getattr(candidate, "task_id")).strip())
            c_task_id = str(getattr(candidate, "task_id", "") or "").strip()

            has_rep_ob = hasattr(candidate, "repaired_obligation_id") and getattr(candidate, "repaired_obligation_id", None) is not None and bool(str(getattr(candidate, "repaired_obligation_id")).strip())
            c_rep_ob = str(getattr(candidate, "repaired_obligation_id", "") or "").strip()

            has_pres = hasattr(candidate, "preserved_obligation_ids") and getattr(candidate, "preserved_obligation_ids", None) is not None
            c_pres = tuple(getattr(candidate, "preserved_obligation_ids", None) or ())

            has_inval = hasattr(candidate, "invalidated_obligation_ids") and getattr(candidate, "invalidated_obligation_ids", None) is not None
            c_inval = tuple(getattr(candidate, "invalidated_obligation_ids", None) or ())

            has_unres = hasattr(candidate, "unresolved_obligation_ids") and getattr(candidate, "unresolved_obligation_ids", None) is not None
            c_unres = tuple(getattr(candidate, "unresolved_obligation_ids", None) or ())

            has_front = hasattr(candidate, "frontier_obligations") and getattr(candidate, "frontier_obligations", None) is not None
            c_front = tuple(getattr(candidate, "frontier_obligations", None) or ())

            has_valid = hasattr(candidate, "is_valid") and getattr(candidate, "is_valid", None) is not None
            c_valid = bool(getattr(candidate, "is_valid", False))

        # Check divergence on present key fields first
        if has_task_id and c_task_id != canonical.task_id:
            raise RecoveryError(
                f"{prefix}: task_id '{c_task_id}' diverges from authoritative canonical frontier task_id '{canonical.task_id}'."
            )

        if has_rep_ob and c_rep_ob != canonical.repaired_obligation_id:
            raise RecoveryError(
                f"{prefix}: repaired_obligation_id '{c_rep_ob}' diverges from authoritative canonical frontier '{canonical.repaired_obligation_id}'."
            )

        if has_front and set(c_front) != set(canonical.frontier_obligations):
            raise RecoveryError(
                f"{prefix}: frontier_obligations {tuple(sorted(c_front))} diverge from authoritative canonical frontier {tuple(sorted(canonical.frontier_obligations))}."
            )

        # Check required identity fields presence
        if not has_task_id:
            raise RecoveryError(f"{prefix}: missing or empty required identity field 'task_id'.")

        if not has_rep_ob:
            raise RecoveryError(f"{prefix}: missing or empty required identity field 'repaired_obligation_id'.")

        if not has_pres:
            raise RecoveryError(f"{prefix}: missing required identity field 'preserved_obligation_ids'.")

        if not has_inval:
            raise RecoveryError(f"{prefix}: missing required identity field 'invalidated_obligation_ids'.")

        if not has_unres:
            raise RecoveryError(f"{prefix}: missing required identity field 'unresolved_obligation_ids'.")

        if not has_front:
            raise RecoveryError(f"{prefix}: missing required identity field 'frontier_obligations'.")

        if not has_valid:
            raise RecoveryError(f"{prefix}: missing required identity field 'is_valid'.")

        # Check exact matches across all 7 identity fields
        # 1. task ID
        if c_task_id != canonical.task_id:
            raise RecoveryError(
                f"{prefix}: task_id '{c_task_id}' diverges from authoritative canonical frontier task_id '{canonical.task_id}'."
            )

        # 2. repaired obligation
        if c_rep_ob != canonical.repaired_obligation_id:
            raise RecoveryError(
                f"{prefix}: repaired_obligation_id '{c_rep_ob}' diverges from authoritative canonical frontier '{canonical.repaired_obligation_id}'."
            )

        # 3. preserved obligations
        if set(c_pres) != set(canonical.preserved_obligation_ids):
            raise RecoveryError(
                f"{prefix}: preserved_obligation_ids {tuple(sorted(c_pres))} diverge from authoritative canonical frontier {tuple(sorted(canonical.preserved_obligation_ids))}."
            )

        # 4. invalidated obligations
        if set(c_inval) != set(canonical.invalidated_obligation_ids):
            raise RecoveryError(
                f"{prefix}: invalidated_obligation_ids {tuple(sorted(c_inval))} diverge from authoritative canonical frontier {tuple(sorted(canonical.invalidated_obligation_ids))}."
            )

        # 5. unresolved obligations
        if set(c_unres) != set(canonical.unresolved_obligation_ids):
            raise RecoveryError(
                f"{prefix}: unresolved_obligation_ids {tuple(sorted(c_unres))} diverge from authoritative canonical frontier {tuple(sorted(canonical.unresolved_obligation_ids))}."
            )

        # 6. frontier obligations
        if set(c_front) != set(canonical.frontier_obligations):
            raise RecoveryError(
                f"{prefix}: frontier_obligations {tuple(sorted(c_front))} diverge from authoritative canonical frontier {tuple(sorted(canonical.frontier_obligations))}."
            )

        # 7. validity
        if c_valid != canonical.is_valid:
            raise RecoveryError(
                f"{prefix}: is_valid '{c_valid}' diverges from authoritative canonical frontier '{canonical.is_valid}'."
            )

    def _resolve_canonical_frontier(
        self,
        record: RecoveryRecord,
        caller_frontier: Optional[Any] = None,
        fail_closed: bool = True,
    ) -> FrontierRecomputation:
        """
        Derives the frontier through canonical recomputation from authoritative state.
        Never trusts cached/persisted frontier metadata as planner authority.
        Cached record.frontier_recomputation and task.metadata['frontier'] are treated
        strictly as derived/cache data, never as sufficient proof of planner readiness.
        Validates complete identity:
        - task ID
        - repaired obligation
        - preserved obligations
        - invalidated obligations
        - unresolved obligations
        - frontier obligations
        - validity
        Fails closed on any mismatch against canonical recomputation.
        """
        # 1. Capture existing cached frontier in record and task metadata
        cached_record_frontier = record.frontier_recomputation
        if cached_record_frontier is None and isinstance(record.metadata, dict):
            cached_record_frontier = record.metadata.get("frontier_recomputation")

        state_repo = StateRepository(self.workspace_dir)
        task = state_repo.get_task(record.task_id)
        cached_task_frontier = None
        if task and task.metadata:
            cached_task_frontier = task.metadata.get("frontier") or task.metadata.get("frontier_recomputation")

        # 2. ALWAYS canonically recompute from authoritative state (without mutating persistence yet)
        from sclass.recovery.engine import RecoveryEngine
        engine = RecoveryEngine(self.workspace_dir, persistence=self.persistence)
        try:
            canonical_frontier = engine.recompute_frontier(record.recovery_id, fail_closed=fail_closed, persist=False)
        except RecoveryPersistenceError:
            raise
        except RecoveryError as e:
            if fail_closed:
                raise RecoveryError(f"Missing canonical frontier: {e}") from e
            return None
        if canonical_frontier is None or not canonical_frontier.is_valid:
            if fail_closed:
                raise RecoveryError(
                    f"Missing canonical frontier: authoritative frontier recomputation is missing or invalid for recovery '{record.recovery_id}'."
                )
            return None

        # 3. Validate cached record.frontier_recomputation if present
        if cached_record_frontier is not None:
            self._validate_frontier_identity(
                cached_record_frontier,
                canonical_frontier,
                source_name="record.frontier_recomputation",
            )
            # Section 18: Close D9 provenance edge - persisted derived frontier metadata
            # (e.g. from record.metadata or task.metadata) must NEVER override freshly canonical
            # recomputed frontier timestamps. Only an authoritative typed FrontierRecomputation on the
            # canonical record may preserve its recomputed_at; derived dict metadata cannot override.
            if isinstance(record.frontier_recomputation, FrontierRecomputation) and record.frontier_recomputation.recomputed_at:
                canonical_frontier = replace(canonical_frontier, recomputed_at=record.frontier_recomputation.recomputed_at)


        # 4. Validate task metadata frontier if present in StateRepository
        if cached_task_frontier is not None:
            self._validate_frontier_identity(
                cached_task_frontier,
                canonical_frontier,
                source_name="task.metadata['frontier']",
            )

        # 5. Validate caller-supplied frontier if present
        if caller_frontier is not None:
            self._validate_frontier_identity(
                caller_frontier,
                canonical_frontier,
                source_name="caller_frontier",
            )

        # 6. Persist canonical frontier to record and task metadata (fail-closed, no silent swallow)
        record.frontier_recomputation = canonical_frontier
        record.metadata["frontier_recomputation"] = canonical_frontier.to_dict()
        self.persistence.save_recovery(record)
        if task:
            task.metadata["frontier"] = canonical_frontier.to_dict()
            task.metadata["frontier_recomputation"] = canonical_frontier.to_dict()
            state_repo.save_task(task)

        return canonical_frontier
