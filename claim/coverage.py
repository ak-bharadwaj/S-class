"""
S-Class EOS V11.2 - D4 Multi-Dimensional Aspect Coverage Calculus (§7.3, CORE-21).
Formal set-theoretic aspect coverage derivation: FULL, PARTIAL, NONE.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Set, Tuple, Mapping, Any
from domain.models import Claim, Evidence


class CoverageStatus(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


@dataclass(frozen=True)
class CoverageResult:
    """Output of Set-Theoretic Aspect Coverage Calculus."""
    status: CoverageStatus
    required_aspects: Tuple[str, ...]
    covered_aspects: Tuple[str, ...]
    missing_aspects: Tuple[str, ...]


def extract_claim_aspects(claim: Claim) -> Set[str]:
    """Extracts target aspect set A(C) from claim context or expected mappings."""
    if not claim:
        return set()
    aspects: Set[str] = set()

    # 1. From context['aspects']
    ctx_aspects = claim.context.get("aspects") if isinstance(claim.context, (dict, Mapping)) else None
    if isinstance(ctx_aspects, (list, tuple, set)):
        aspects.update(str(a) for a in ctx_aspects if a)

    # 2. From expected['aspects']
    exp_aspects = claim.expected.get("aspects") if isinstance(claim.expected, (dict, Mapping)) else None
    if isinstance(exp_aspects, (list, tuple, set)):
        aspects.update(str(a) for a in exp_aspects if a)

    return aspects


def extract_evidence_aspects(evidence_items: Sequence[Evidence]) -> Set[str]:
    """Extracts union of covered aspects U A(E_i) across evidence sequence."""
    covered: Set[str] = set()
    for ev in evidence_items:
        if ev and ev.scope and ev.scope.aspects_covered:
            for asp in ev.scope.aspects_covered:
                if asp:
                    covered.add(str(asp))
    return covered


def evaluate_coverage(claim: Claim, evidence_items: Sequence[Evidence]) -> CoverageResult:
    """Set-theoretic aspect coverage calculus (§7.3, CORE-21).
    
    Let A(C) be the required aspects of Claim C.
    Let U = Union(A(E_i)) be the aspects covered by evidence items.
    
    If A(C) is not empty:
      - FULL:    A(C) is a subset of U
      - PARTIAL: Empty != (A(C) intersect U) is a proper subset of A(C)
      - NONE:    A(C) intersect U is Empty
      
    If A(C) is empty:
      - FULL:    evidence_items is non-empty
      - NONE:    evidence_items is empty
    """
    req_aspects = extract_claim_aspects(claim)
    cov_aspects = extract_evidence_aspects(evidence_items)

    req_tuple = tuple(sorted(req_aspects))
    cov_tuple = tuple(sorted(cov_aspects))

    if not req_aspects:
        # Default baseline: presence of valid target evidence constitutes FULL coverage
        status = CoverageStatus.FULL if evidence_items else CoverageStatus.NONE
        return CoverageResult(
            status=status,
            required_aspects=req_tuple,
            covered_aspects=cov_tuple,
            missing_aspects=(),
        )

    intersection = req_aspects.intersection(cov_aspects)
    missing = req_aspects - cov_aspects
    missing_tuple = tuple(sorted(missing))

    if req_aspects.issubset(cov_aspects):
        status = CoverageStatus.FULL
    elif intersection:
        status = CoverageStatus.PARTIAL
    else:
        status = CoverageStatus.NONE

    return CoverageResult(
        status=status,
        required_aspects=req_tuple,
        covered_aspects=tuple(sorted(intersection)),
        missing_aspects=missing_tuple,
    )
