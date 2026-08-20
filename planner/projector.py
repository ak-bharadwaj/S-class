"""D8 Autonomous Planning Substrate - State Projector (§3.6, §8.1).

Projects D4 MaterializedState and Frontier Calculus into an immutable PlannerStateView,
strictly separating semantic state from volatile telemetry metadata.
"""

from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from events.state import MaterializedState
from planner.fingerprint import compute_planner_state_digest
from planner.models import (
    PlannerStateContent,
    PlannerStateProjectionMetadata,
    PlannerStateView,
)


class StateProjector:
    """Projects D4 domain state into immutable D8 PlannerStateView."""

    @staticmethod
    def project(
        task_id: str,
        obligations: Mapping[str, Any],
        claims: Mapping[str, Any],
        executable_frontier: Sequence[str] = (),
        blocked_frontier: Sequence[str] = (),
        evidence_digests: Sequence[str] = (),
        active_policies: Sequence[Mapping[str, Any]] = (),
        milestones: Sequence[Mapping[str, Any]] = (),
        state_version: int = 0,
        state_digest: str = "",
        worker_id: str = "",
    ) -> PlannerStateView:
        """Projects given state attributes into a PlannerStateView."""
        t_start = time.perf_counter()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Build normalized representation of obligations
        normalized_obligations = []
        for obl_id in sorted(obligations.keys()):
            obl = obligations[obl_id]
            obl_dict = {
                "obligation_id": obl.obligation_id if hasattr(obl, "obligation_id") else obl_id,
                "category": obl.category.value if hasattr(obl.category, "value") else str(obl.category),
                "criticality": obl.criticality.value if hasattr(obl.criticality, "value") else str(obl.criticality),
                "status": obl.status.value if hasattr(obl.status, "value") else str(obl.status),
                "depends_on": list(obl.depends_on) if hasattr(obl, "depends_on") else [],
                "claim_ids": list(obl.claim_ids) if hasattr(obl, "claim_ids") else [],
            }
            normalized_obligations.append(obl_dict)

        # Build normalized representation of claims
        normalized_claims = []
        for clm_id in sorted(claims.keys()):
            clm = claims[clm_id]
            clm_dict = {
                "claim_id": clm.claim_id if hasattr(clm, "claim_id") else clm_id,
                "tier": clm.tier.value if hasattr(clm.tier, "value") else str(clm.tier),
                "predicate": clm.predicate if hasattr(clm, "predicate") else "",
                "status": clm.status.value if hasattr(clm.status, "value") else str(clm.status),
            }
            normalized_claims.append(clm_dict)

        content = PlannerStateContent(
            task_id=task_id,
            milestones=tuple(milestones),
            claims=tuple(normalized_claims),
            obligations=tuple(normalized_obligations),
            executable_frontier=tuple(executable_frontier),
            blocked_frontier=tuple(blocked_frontier),
            evidence_digests=tuple(evidence_digests),
            active_policies=tuple(active_policies),
            state_version=state_version,
            state_digest=state_digest,
        )

        state_digest_value = compute_planner_state_digest(content)

        latency_ms = (time.perf_counter() - t_start) * 1000.0
        metadata = PlannerStateProjectionMetadata(
            projected_at=now_iso,
            projection_latency_ms=latency_ms,
            worker_id=worker_id,
        )

        return PlannerStateView(
            content=content,
            metadata=metadata,
            planner_state_digest=state_digest_value,
        )

    @staticmethod
    def project_materialized_state(
        task_id: str,
        mat_state: MaterializedState,
        executable_frontier: Sequence[str] = (),
        blocked_frontier: Sequence[str] = (),
        active_policies: Sequence[Mapping[str, Any]] = (),
        worker_id: str = "",
    ) -> PlannerStateView:
        """Projects a D4 MaterializedState directly into PlannerStateView."""
        return StateProjector.project(
            task_id=task_id,
            obligations=mat_state.obligations,
            claims=mat_state.claims,
            executable_frontier=executable_frontier,
            blocked_frontier=blocked_frontier,
            evidence_digests=tuple(mat_state.evidence.keys()),
            active_policies=active_policies,
            state_version=mat_state.last_sequence_number,
            state_digest=mat_state.last_digest,
            worker_id=worker_id,
        )
