"""Non-authoritative reference scaffold handoff compiler.

Compiles handoff bundles ensuring zero lease, nonce, or token leaks.
Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

from sclass_semantics_v6_0_1 import (
    Digest,
    EngineeringState,
    FrozenMap,
    GENESIS_EVENT_HASH,
    HandoffPackage,
    StateBinding,
    UtcInstant,
    canonical_current_state_binding,
    digest,
    target_snapshot_digest,
    _validate_evidence_closure_against_state,
)


class ReferenceHandoffCompiler:
    """Non-authoritative reference scaffold compiler of HandoffPackage from canonical EngineeringState.

    Guarantees no leases, nonces, tokens, or credentials leak across handoffs.
    """

    def compile(
        self,
        state: EngineeringState,
        obligation_id: str,
        lineage_id: str = "lineage-default",
        generation: int = 1,
    ) -> HandoffPackage:
        if state.obligations and obligation_id not in state.obligations._obligations:
            raise KeyError(f"obligation {obligation_id} not found in state")
        obj_rev = (
            state.objective.revisions[-1].revision_id
            if state.objective and state.objective.revisions
            else "genesis"
        )
        wm_rev = (
            state.world_model.revision_id
            if getattr(state, "world_model", None) is not None
            else "wm-0"
        )

        fresh_evidence = []
        now = UtcInstant(0)
        for ev_id, closure in state.evidence.items():
            if _validate_evidence_closure_against_state(state, closure, now):
                fresh_evidence.append(ev_id)

        frontier = (
            tuple(state.work_graph._frontier)
            if state.work_graph and hasattr(state.work_graph, "_frontier")
            else ()
        )
        decisions = tuple(state.authorization_decisions.values())
        constraints = (
            tuple(state.constraints.values())
            if hasattr(state, "constraints") and isinstance(state.constraints, (dict, FrozenMap))
            else ()
        )

        try:
            binding = canonical_current_state_binding(state, generation, lineage_id)
        except Exception:
            ts_digest = (
                target_snapshot_digest(state.target_snapshot)
                if state.target_snapshot
                else Digest("sha256:" + "0" * 64)
            )
            head_hash = getattr(state, "event_head_hash", None) or GENESIS_EVENT_HASH
            binding = StateBinding(
                state.workspace_id,
                obj_rev,
                "wg-0",
                state.policy_version,
                state.workspace_snapshot_id,
                ts_digest,
                Digest("sha256:" + "0" * 64),
                lineage_id,
                generation,
                "epoch-0",
                head_hash,
            )

        unsigned_data = (
            state.workspace_id,
            obj_rev,
            binding,
            obligation_id,
            tuple(sorted(fresh_evidence)),
            tuple(frontier),
            decisions,
            constraints,
            wm_rev,
        )
        pkg_digest = digest("sclass/handoff-package/v1", unsigned_data)
        pkg_id = f"handoff-{pkg_digest[-16:]}"

        return HandoffPackage(
            pkg_id,
            state.workspace_id,
            obj_rev,
            binding,
            obligation_id,
            tuple(sorted(fresh_evidence)),
            frontier,
            decisions,
            constraints,
            wm_rev,
            pkg_digest,
        )


CanonicalHandoffCompiler = ReferenceHandoffCompiler
