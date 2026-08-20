"""
S-Class EOS V11.2 - D4 Claim & Evidence Engine Package.
"""

from claim.relevance import (
    RelevanceResult,
    evaluate_relevance,
    is_capability_compatible,
    is_scope_compatible,
)
from claim.coverage import (
    CoverageStatus,
    CoverageResult,
    evaluate_coverage,
    extract_claim_aspects,
    extract_evidence_aspects,
)
from claim.reducer import (
    ClaimEpistemicState,
    ClaimReductionState,
    ClaimEvidenceState,
    reduce_claim,
    fold_claim_evidence_state,
)
from claim.convergence import (
    ConvergenceEngine,
    ConvergenceFinding,
    ConvergenceReport,
)
from claim.receipts import (
    mint_assessment_receipt,
    verify_assessment_receipt_signature,
)

__all__ = [
    "RelevanceResult",
    "evaluate_relevance",
    "is_capability_compatible",
    "is_scope_compatible",
    "CoverageStatus",
    "CoverageResult",
    "evaluate_coverage",
    "extract_claim_aspects",
    "extract_evidence_aspects",
    "ClaimEpistemicState",
    "ClaimReductionState",
    "ClaimEvidenceState",
    "reduce_claim",
    "fold_claim_evidence_state",
    "ConvergenceEngine",
    "ConvergenceFinding",
    "ConvergenceReport",
    "mint_assessment_receipt",
    "verify_assessment_receipt_signature",
]
