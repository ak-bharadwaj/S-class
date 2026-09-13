"""
S-Class Verification: Test-Scope Proof and Scope Coverage Engine.
Evaluates the geometric relationship between agent claim targets and
independently observed execution targets:
CLAIM -> required scope -> observed test targets -> COVERED / PARTIAL / NONE.
Guarantees that a claim asserting "All authentication tests pass" backed only
by "pytest tests/utils" is strictly rejected or deemed inconclusive.
"""

from __future__ import annotations
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Tuple, Optional, List, Dict, Any

from sclass.domain.claim import ClaimScope
from sclass.domain.verification import TestSelection


class CoverageRelation(str, Enum):
    """Categorical coverage relationship between claim scope and executed test selection."""
    COVERED = "COVERED"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


def normalize_target_path(path: str) -> str:
    """Normalizes path separators and casing for platform-independent target matching."""
    norm = path.replace("\\", "/").strip().lower()
    if norm.startswith("./"):
        norm = norm[2:]
    return norm.rstrip("/")


class ScopeEvaluator:
    """Evaluates coverage relation between declared claim scope and actual test selection."""

    @classmethod
    def evaluate(
        cls,
        claim_scope: Optional[ClaimScope],
        test_selection: Optional[TestSelection],
    ) -> Tuple[CoverageRelation, str]:
        """
        Determines whether observed test execution satisfies the required claim scope.
        Returns (CoverageRelation, diagnostic_explanation).
        """
        if not claim_scope:
            return CoverageRelation.COVERED, "No scope boundaries declared on claim."

        req_targets = list(claim_scope.test_targets) or list(claim_scope.paths)
        if not req_targets:
            return CoverageRelation.COVERED, "Claim scope contains zero explicit target constraints."

        if not test_selection:
            return CoverageRelation.NONE, "No test execution targets observed in evidence."

        obs_targets = [normalize_target_path(t) for t in (list(test_selection.selected_tests) + list(test_selection.test_files))]
        if not obs_targets:
            return CoverageRelation.NONE, "Observed test selection executed zero targets."

        matched = []
        unmatched = []

        for req in req_targets:
            norm_req = normalize_target_path(req)
            # A match occurs if observed target equals, is child of, or is parent of the required target
            is_match = any(
                norm_req == obs or norm_req in obs or obs.startswith(norm_req) or norm_req.startswith(obs)
                for obs in obs_targets
            )
            if is_match:
                matched.append(req)
            else:
                unmatched.append(req)

        if not matched:
            return (
                CoverageRelation.NONE,
                f"Required test targets {req_targets} have ZERO overlap with observed test selection {obs_targets}.",
            )

        if unmatched:
            return (
                CoverageRelation.PARTIAL,
                f"Partial test coverage: matched {matched}, but missing required targets {unmatched} (observed: {obs_targets}).",
            )

        return CoverageRelation.COVERED, f"All required targets {matched} covered by observed execution {obs_targets}."


evaluate_claim_scope = ScopeEvaluator.evaluate
