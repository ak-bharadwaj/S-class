"""Non-authoritative reference scaffold coordinated recovery.

Orchestrates saga-style compensation and reports deterministic RecoveryReport.
Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

from typing import Optional, Sequence

from sclass_semantics_v6_0_1 import (
    CompensationCapability,
    CompensationResult,
    EffectCompensationProvider,
    RecoveryOutcome,
    RecoveryReport,
    RepairPlan,
    RollbackResult,
    SideEffectReceipt,
    SideEffectStatus,
)


class ReferenceCoordinatedRecovery:
    """Non-authoritative reference scaffold saga-style compensation coordinator.

    Effects that cannot be verified or compensated transition to IN_DOUBT, never assumed.
    """

    def recover(
        self,
        node_id: str,
        plan: RepairPlan,
        effects: Sequence[SideEffectReceipt],
        compensation_provider: Optional[EffectCompensationProvider] = None,
    ) -> RecoveryReport:
        compensated = []
        unresolved = []
        for eff in sorted(effects, key=lambda x: x.effect_id):
            if eff.status is SideEffectStatus.COMPENSATED:
                compensated.append(eff.effect_id)
            elif compensation_provider is not None:
                try:
                    cap = getattr(
                        compensation_provider,
                        "capability",
                        lambda e: CompensationCapability.COMPENSABLE,
                    )(eff)
                    if cap is CompensationCapability.REVERSIBLE or cap is CompensationCapability.COMPENSABLE:
                        cres = compensation_provider.compensate(eff, f"comp-{eff.effect_id}")
                        if cres is CompensationResult.COMPENSATED or cres is CompensationResult.ALREADY_COMPENSATED:
                            compensated.append(eff.effect_id)
                        else:
                            unresolved.append(eff.effect_id)
                    else:
                        unresolved.append(eff.effect_id)
                except Exception:
                    unresolved.append(eff.effect_id)
            else:
                unresolved.append(eff.effect_id)

        outcome = RecoveryOutcome.IN_DOUBT if unresolved else RecoveryOutcome.RECOVERED
        rollback = (
            RollbackResult.ROLLED_BACK
            if outcome is RecoveryOutcome.RECOVERED
            else RollbackResult.PARTIAL
        )
        return RecoveryReport(
            outcome=outcome,
            compensated_effect_ids=tuple(compensated),
            unresolved_effect_ids=tuple(unresolved),
            rollback=rollback,
        )


CanonicalCoordinatedRecovery = ReferenceCoordinatedRecovery
