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
        exceptions: Sequence[Any] = (),
        milestones: Sequence[Mapping[str, Any]] = (),
        analysis_artifacts: Sequence[Any] = (),
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
            cat_val = obl.get("category") if isinstance(obl, dict) else (obl.category.value if hasattr(obl.category, "value") else str(obl.category))
            crit_val = obl.get("criticality") if isinstance(obl, dict) else (obl.criticality.value if hasattr(obl.criticality, "value") else str(obl.criticality))
            stat_val = obl.get("status") if isinstance(obl, dict) else (obl.status.value if hasattr(obl.status, "value") else str(obl.status))
            title_val = obl.get("title", "Governed Obligation") if isinstance(obl, dict) else getattr(obl, "title", "Governed Obligation")
            desc_val = obl.get("description", "Governed Obligation") if isinstance(obl, dict) else getattr(obl, "description", "Governed Obligation")
            deps_val = obl.get("depends_on", []) if isinstance(obl, dict) else list(getattr(obl, "depends_on", []))
            claims_val = obl.get("claim_ids", []) if isinstance(obl, dict) else list(getattr(obl, "claim_ids", []))
            pol_id_val = obl.get("policy_id") if isinstance(obl, dict) else getattr(obl, "policy_id", None)

            obl_dict = {
                "obligation_id": obl.get("obligation_id", obl_id) if isinstance(obl, dict) else getattr(obl, "obligation_id", obl_id),
                "title": title_val,
                "description": desc_val,
                "category": cat_val.value if hasattr(cat_val, "value") else str(cat_val),
                "criticality": crit_val.value if hasattr(crit_val, "value") else str(crit_val),
                "status": stat_val.value if hasattr(stat_val, "value") else str(stat_val),
                "depends_on": deps_val,
                "claim_ids": claims_val,
                "policy_id": pol_id_val,
            }
            normalized_obligations.append(obl_dict)

        # Build normalized representation of claims
        normalized_claims = []
        for clm_id in sorted(claims.keys()):
            clm = claims[clm_id]
            tier_val = clm.get("tier") if isinstance(clm, dict) else (clm.tier.value if hasattr(clm.tier, "value") else str(clm.tier))
            pred_val = clm.get("predicate", "") if isinstance(clm, dict) else getattr(clm, "predicate", "")
            status_val = clm.get("status") if isinstance(clm, dict) else (clm.status.value if hasattr(clm.status, "value") else str(clm.status))
            clm_dict = {
                "claim_id": clm.get("claim_id", clm_id) if isinstance(clm, dict) else getattr(clm, "claim_id", clm_id),
                "tier": tier_val.value if hasattr(tier_val, "value") else str(tier_val),
                "predicate": pred_val,
                "status": status_val.value if hasattr(status_val, "value") else str(status_val),
            }
            normalized_claims.append(clm_dict)

        analysis_digests = tuple(
            sorted(a.artifact_digest for a in analysis_artifacts if hasattr(a, "artifact_digest"))
        )

        content = PlannerStateContent(
            task_id=task_id,
            milestones=tuple(milestones),
            claims=tuple(normalized_claims),
            obligations=tuple(normalized_obligations),
            executable_frontier=tuple(executable_frontier),
            blocked_frontier=tuple(blocked_frontier),
            evidence_digests=tuple(evidence_digests),
            active_policies=tuple(active_policies),
            exceptions=tuple(exceptions),
            analysis_digests=analysis_digests,
            analysis_artifacts=tuple(analysis_artifacts),
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
        exceptions: Sequence[Any] = (),
        analysis_artifacts: Sequence[Any] = (),
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
            exceptions=exceptions,
            analysis_artifacts=analysis_artifacts,
            state_version=mat_state.last_sequence_number,
            state_digest=mat_state.last_digest,
            worker_id=worker_id,
        )
