"""
S-Class EOS V11.2 - D4 Deterministic Claim Epistemic Reducer (§4.2, §5.3, §5.4).
Pure mathematical fold over evidence and events.
Strict Discrete Epistemic States: UNSUPPORTED, SUPPORTED, CONTRADICTED, CONFLICTED, STALE.
Universal Ban on Majority Voting (CORE-20): 1 refuting evidence item strictly forces CONFLICTED against N supporting items.
Preserves CONFLICTED state throughout claim assessment without mapping CONFLICTED -> CONTRADICTED.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple
from domain.models import Claim, Evidence
from domain.types import EvidencePolarity, EvidenceValidity, ClaimStatus
from claim.relevance import evaluate_relevance
from claim.coverage import evaluate_coverage, CoverageStatus


class ClaimEpistemicState(str, Enum):
    """Frozen D0 §4.2 Claim Epistemic State Machine."""
    UNSUPPORTED = "UNSUPPORTED"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"

    def to_domain_status(self) -> ClaimStatus:
        """Maps epistemic state to canonical D0/D1 ClaimStatus enum.
        Preserves CONFLICTED directly without lossy downgrade.
        """
        if self == ClaimEpistemicState.SUPPORTED:
            return ClaimStatus.SUPPORTED
        elif self == ClaimEpistemicState.CONTRADICTED:
            return ClaimStatus.CONTRADICTED
        elif self == ClaimEpistemicState.CONFLICTED:
            return ClaimStatus.CONFLICTED
        elif self == ClaimEpistemicState.STALE:
            return ClaimStatus.STALE
        return ClaimStatus.UNSUPPORTED


@dataclass(frozen=True)
class ClaimReductionState:
    """Immutable state snapshot for a claim under epistemic reduction."""
    claim_id: str
    epistemic_state: ClaimEpistemicState
    supporting_evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    refuting_evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    stale_evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    conflicts: Tuple[str, ...] = field(default_factory=tuple)
    coverage_status: CoverageStatus = CoverageStatus.NONE
    missing_aspects: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ClaimEvidenceState:
    """Immutable collection of claim reduction states resulting from deterministic fold."""
    claims: Mapping[str, ClaimReductionState] = field(default_factory=dict)
    repository_sha: str = ""


def reduce_claim(
    claim: Claim,
    evidence_items: Sequence[Evidence],
    repository_sha: str,
    trust_certificates: Optional[Mapping[str, Any]] = None,
) -> ClaimReductionState:
    """Pure, deterministic state reduction function for a single claim (§4.2, §5.3, §5.4).
    
    Zero I/O, zero wall-clock dependencies, zero mutable global state.
    """
    if not claim:
        raise ValueError("Claim cannot be None.")

    trust_certs = trust_certificates or {}

    supporting_ids: List[str] = []
    refuting_ids: List[str] = []
    stale_ids: List[str] = []
    active_supporting: List[Evidence] = []
    active_refuting: List[Evidence] = []

    for ev in evidence_items:
        if not ev or ev.claim_id != claim.claim_id:
            continue

        # Check commit / staleness
        if ev.source_sha != repository_sha or ev.validity == EvidenceValidity.STALE:
            stale_ids.append(ev.evidence_id)
            continue

        # Check validity & relevance
        if ev.validity != EvidenceValidity.VALID:
            continue

        cert = trust_certs.get(ev.evidence_id)
        rel = evaluate_relevance(
            claim=claim,
            evidence=ev,
            expected_source_sha=repository_sha,
            trust_certificate=cert,
        )
        if not rel.is_relevant:
            continue

        if ev.polarity == EvidencePolarity.SUPPORTS:
            supporting_ids.append(ev.evidence_id)
            active_supporting.append(ev)
        elif ev.polarity == EvidencePolarity.REFUTES:
            refuting_ids.append(ev.evidence_id)
            active_refuting.append(ev)

    cov = evaluate_coverage(claim, active_supporting)

    # Deterministic Epistemic Reduction Calculus
    conflicts: List[str] = []
    if active_supporting and active_refuting:
        # CORE-20: Universal Ban on Majority Voting
        state = ClaimEpistemicState.CONFLICTED
        conflicts.append(
            f"Contradiction conflict: {len(active_supporting)} SUPPORTS vs {len(active_refuting)} REFUTES on claim {claim.claim_id}."
        )
    elif active_refuting:
        state = ClaimEpistemicState.CONTRADICTED
    elif active_supporting:
        if cov.status == CoverageStatus.FULL:
            state = ClaimEpistemicState.SUPPORTED
        else:
            # Partial or None aspect coverage cannot satisfy claim
            state = ClaimEpistemicState.UNSUPPORTED
    elif stale_ids and not active_supporting and not active_refuting:
        state = ClaimEpistemicState.STALE
    else:
        state = ClaimEpistemicState.UNSUPPORTED

    return ClaimReductionState(
        claim_id=claim.claim_id,
        epistemic_state=state,
        supporting_evidence_ids=tuple(sorted(set(supporting_ids))),
        refuting_evidence_ids=tuple(sorted(set(refuting_ids))),
        stale_evidence_ids=tuple(sorted(set(stale_ids))),
        conflicts=tuple(conflicts),
        coverage_status=cov.status,
        missing_aspects=cov.missing_aspects,
    )


def fold_claim_evidence_state(
    claims: Mapping[str, Claim],
    evidence_catalog: Mapping[str, Evidence],
    repository_sha: str,
    trust_certificates: Optional[Mapping[str, Any]] = None,
) -> ClaimEvidenceState:
    """Pure mathematical fold computing ClaimEvidenceState across all claims in repository."""
    reduced_claims: Dict[str, ClaimReductionState] = {}
    ev_list = list(evidence_catalog.values())

    for claim_id, claim in claims.items():
        claim_ev = [e for e in ev_list if e.claim_id == claim_id]
        reduced = reduce_claim(
            claim=claim,
            evidence_items=claim_ev,
            repository_sha=repository_sha,
            trust_certificates=trust_certificates,
        )
        reduced_claims[claim_id] = reduced

    return ClaimEvidenceState(
        claims=reduced_claims,
        repository_sha=repository_sha,
    )
