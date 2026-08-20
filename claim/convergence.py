"""
S-Class EOS V11.2 - D4 Convergence Analysis Engine & Drift Calculus (§7.6, CORE-24).
Computes Delta_conv = Convergence(IntendedState, ObservedState).
Taxonomy: MISSING | PARTIAL | CONTRADICTORY | UNREQUESTED | STALE.
CORE-24 Invariant: Strictly diagnostic. Cannot issue tokens, mutate controller state, or authorize actions.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple
from domain.models import Claim, Evidence
from domain.types import DriftType
from claim.reducer import ClaimReductionState, ClaimEpistemicState
from claim.coverage import CoverageStatus


@dataclass(frozen=True)
class ConvergenceFinding:
    """Structured drift observation in convergence delta."""
    finding_type: DriftType
    target_id: str
    details: str
    affected_evidence_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ConvergenceReport:
    """Immutable diagnostic report of architectural and behavioral convergence."""
    report_id: str
    task_id: str
    repository_sha: str
    findings: Tuple[ConvergenceFinding, ...]
    drift_count: int
    is_converged: bool
    evaluated_at: str


class ConvergenceEngine:
    """Observational and diagnostic engine evaluating convergence without execution authority."""

    @staticmethod
    def analyze_convergence(
        task_id: str,
        repository_sha: str,
        intended_claims: Mapping[str, Claim],
        claim_states: Mapping[str, ClaimReductionState],
        evidence_catalog: Mapping[str, Evidence],
        report_id: Optional[str] = None,
        timestamp_iso: str = "1970-01-01T00:00:00Z",
    ) -> ConvergenceReport:
        """Pure diagnostic convergence analysis (§7.6, CORE-24).
        
        Evaluates drift delta:
        - MISSING: Intended claim has no valid supporting evidence
        - PARTIAL: Intended claim has partial aspect coverage
        - CONTRADICTORY: Intended claim is CONTRADICTED or CONFLICTED
        - UNREQUESTED: Evidence exists for un-tracked / un-requested claims
        - STALE: Evidence was collected against an older repository commit SHA
        """
        if not report_id:
            report_id = f"CNV-{task_id}-{repository_sha[:8]}"

        findings: List[ConvergenceFinding] = []
        intended_ids = set(intended_claims.keys())

        # 1. Inspect intended claims for MISSING, PARTIAL, CONTRADICTORY, STALE
        for claim_id, claim in intended_claims.items():
            state = claim_states.get(claim_id)
            if not state:
                findings.append(
                    ConvergenceFinding(
                        finding_type=DriftType.MISSING,
                        target_id=claim_id,
                        details=f"Intended claim '{claim_id}' has no evaluation state.",
                    )
                )
                continue

            if state.epistemic_state == ClaimEpistemicState.UNSUPPORTED:
                if state.coverage_status == CoverageStatus.PARTIAL:
                    findings.append(
                        ConvergenceFinding(
                            finding_type=DriftType.PARTIAL,
                            target_id=claim_id,
                            details=f"Claim '{claim_id}' has partial aspect coverage; missing aspects: {state.missing_aspects}.",
                            affected_evidence_ids=state.supporting_evidence_ids,
                        )
                    )
                else:
                    findings.append(
                        ConvergenceFinding(
                            finding_type=DriftType.MISSING,
                            target_id=claim_id,
                            details=f"Intended claim '{claim_id}' is UNSUPPORTED (missing valid evidence).",
                            affected_evidence_ids=state.supporting_evidence_ids,
                        )
                    )

            elif state.epistemic_state in (ClaimEpistemicState.CONTRADICTED, ClaimEpistemicState.CONFLICTED):
                findings.append(
                    ConvergenceFinding(
                        finding_type=DriftType.CONTRADICTORY,
                        target_id=claim_id,
                        details=f"Claim '{claim_id}' is in contradictory state '{state.epistemic_state.value}': {state.conflicts}",
                        affected_evidence_ids=state.refuting_evidence_ids + state.supporting_evidence_ids,
                    )
                )

            elif state.epistemic_state == ClaimEpistemicState.STALE:
                findings.append(
                    ConvergenceFinding(
                        finding_type=DriftType.STALE,
                        target_id=claim_id,
                        details=f"Claim '{claim_id}' evidence is stale with respect to HEAD SHA '{repository_sha}'.",
                        affected_evidence_ids=state.stale_evidence_ids,
                    )
                )

        # 2. Inspect evidence catalog for UNREQUESTED drift & individual STALE evidence
        for ev_id, ev in evidence_catalog.items():
            if ev.claim_id not in intended_ids:
                findings.append(
                    ConvergenceFinding(
                        finding_type=DriftType.UNREQUESTED,
                        target_id=ev_id,
                        details=f"Evidence '{ev_id}' collected for un-requested claim '{ev.claim_id}'.",
                        affected_evidence_ids=(ev_id,),
                    )
                )
            elif ev.source_sha != repository_sha:
                findings.append(
                    ConvergenceFinding(
                        finding_type=DriftType.STALE,
                        target_id=ev_id,
                        details=f"Evidence '{ev_id}' source SHA '{ev.source_sha}' does not match repository HEAD '{repository_sha}'.",
                        affected_evidence_ids=(ev_id,),
                    )
                )

        drift_count = len(findings)
        is_converged = (drift_count == 0)

        return ConvergenceReport(
            report_id=report_id,
            task_id=task_id,
            repository_sha=repository_sha,
            findings=tuple(findings),
            drift_count=drift_count,
            is_converged=is_converged,
            evaluated_at=timestamp_iso,
        )
