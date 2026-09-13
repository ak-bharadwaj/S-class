"""
S-Class Verification: Claim Acceptance Matrix and Policy Engine.
Defines required evidence criteria and deterministic verdict outcomes
(ACCEPT, REJECT, INCONCLUSIVE) for all claim taxonomy categories.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List

from sclass.domain.claim import Claim, ClaimType
from sclass.domain.verification import VerificationResult


class RequiredEvidenceKind(str, Enum):
    """Minimum evidence requirement classification."""
    OBSERVED_EXECUTION = "OBSERVED_EXECUTION"
    WORKSPACE_FINGERPRINT = "WORKSPACE_FINGERPRINT"
    RECOGNIZED_TEST_RUNNER = "RECOGNIZED_TEST_RUNNER"
    STRUCTURED_TEST_RESULTS = "STRUCTURED_TEST_RESULTS"
    BEHAVIOR_EVIDENCE = "BEHAVIOR_EVIDENCE"
    SECURITY_VERIFIER = "SECURITY_VERIFIER"
    TARGET_FILE_EVIDENCE = "TARGET_FILE_EVIDENCE"
    BUILD_VERIFIER = "BUILD_VERIFIER"


@dataclass(frozen=True)
class ClaimRequirementRule:
    """Requirement specification for a claim category."""
    claim_type: str
    minimum_evidence: RequiredEvidenceKind
    default_missing_verdict: str  # REJECT or INCONCLUSIVE
    description: str


# Authoritative claim evidence requirements
CLAIM_REQUIREMENTS: Dict[str, ClaimRequirementRule] = {
    ClaimType.EXECUTION.value: ClaimRequirementRule(
        claim_type=ClaimType.EXECUTION.value,
        minimum_evidence=RequiredEvidenceKind.OBSERVED_EXECUTION,
        default_missing_verdict="REJECT",
        description="Command execution must be backed by an independently observed execution receipt.",
    ),
    ClaimType.FILE_CHANGE.value: ClaimRequirementRule(
        claim_type=ClaimType.FILE_CHANGE.value,
        minimum_evidence=RequiredEvidenceKind.WORKSPACE_FINGERPRINT,
        default_missing_verdict="REJECT",
        description="File modifications must be verified by workspace fingerprint mutation and target match.",
    ),
    ClaimType.BUILD.value: ClaimRequirementRule(
        claim_type=ClaimType.BUILD.value,
        minimum_evidence=RequiredEvidenceKind.BUILD_VERIFIER,
        default_missing_verdict="REJECT",
        description="Build success claims must be certified by a recognized build tool.",
    ),
    ClaimType.TEST_PASS.value: ClaimRequirementRule(
        claim_type=ClaimType.TEST_PASS.value,
        minimum_evidence=RequiredEvidenceKind.STRUCTURED_TEST_RESULTS,
        default_missing_verdict="REJECT",
        description="Test claims must be certified by a recognized test runner with structured zero-failure results.",
    ),
    ClaimType.TEST_COVERAGE.value: ClaimRequirementRule(
        claim_type=ClaimType.TEST_COVERAGE.value,
        minimum_evidence=RequiredEvidenceKind.STRUCTURED_TEST_RESULTS,
        default_missing_verdict="REJECT",
        description="Coverage claims require coverage report artifacts and recognized runner output.",
    ),
    ClaimType.TYPECHECK.value: ClaimRequirementRule(
        claim_type=ClaimType.TYPECHECK.value,
        minimum_evidence=RequiredEvidenceKind.OBSERVED_EXECUTION,
        default_missing_verdict="REJECT",
        description="Typechecking claims require observed typechecker execution (mypy, tsc, pyright).",
    ),
    ClaimType.LINT.value: ClaimRequirementRule(
        claim_type=ClaimType.LINT.value,
        minimum_evidence=RequiredEvidenceKind.OBSERVED_EXECUTION,
        default_missing_verdict="REJECT",
        description="Linting claims require observed linter execution (ruff, flake8, eslint).",
    ),
    ClaimType.SECURITY.value: ClaimRequirementRule(
        claim_type=ClaimType.SECURITY.value,
        minimum_evidence=RequiredEvidenceKind.SECURITY_VERIFIER,
        default_missing_verdict="INCONCLUSIVE",
        description="Security fixes require security verifier evidence; arbitrary commands are inconclusive.",
    ),
    ClaimType.BEHAVIOR.value: ClaimRequirementRule(
        claim_type=ClaimType.BEHAVIOR.value,
        minimum_evidence=RequiredEvidenceKind.BEHAVIOR_EVIDENCE,
        default_missing_verdict="INCONCLUSIVE",
        description="Behavior claims require behavioral contract tests; generic execution is inconclusive.",
    ),
    ClaimType.FEATURE.value: ClaimRequirementRule(
        claim_type=ClaimType.FEATURE.value,
        minimum_evidence=RequiredEvidenceKind.BEHAVIOR_EVIDENCE,
        default_missing_verdict="INCONCLUSIVE",
        description="Feature claims require behavioral test evidence; generic execution is inconclusive.",
    ),
    ClaimType.CORRECTNESS.value: ClaimRequirementRule(
        claim_type=ClaimType.CORRECTNESS.value,
        minimum_evidence=RequiredEvidenceKind.BEHAVIOR_EVIDENCE,
        default_missing_verdict="INCONCLUSIVE",
        description="Correctness claims require semantic verification; generic execution is inconclusive.",
    ),
    ClaimType.DOCUMENTATION.value: ClaimRequirementRule(
        claim_type=ClaimType.DOCUMENTATION.value,
        minimum_evidence=RequiredEvidenceKind.TARGET_FILE_EVIDENCE,
        default_missing_verdict="REJECT",
        description="Documentation claims require evidence of updated documentation files.",
    ),
    ClaimType.DEPLOYMENT.value: ClaimRequirementRule(
        claim_type=ClaimType.DEPLOYMENT.value,
        minimum_evidence=RequiredEvidenceKind.OBSERVED_EXECUTION,
        default_missing_verdict="REJECT",
        description="Deployment claims require observed deployment pipeline execution.",
    ),
    ClaimType.GIT.value: ClaimRequirementRule(
        claim_type=ClaimType.GIT.value,
        minimum_evidence=RequiredEvidenceKind.OBSERVED_EXECUTION,
        default_missing_verdict="REJECT",
        description="VCS / Git claims require observed git command execution.",
    ),
}


class ClaimAcceptanceMatrix:
    """Evaluates whether provided evidence meets the mandatory policy bar for a claim."""

    @classmethod
    def evaluate_evidence_sufficiency(
        cls,
        claim: Claim,
        evidence: Optional[Any],
    ) -> Tuple[bool, str, str]:
        """
        Returns (is_sufficient, verdict_if_insufficient, reason).
        Verdict if insufficient is either REJECT or INCONCLUSIVE per policy matrix.
        """
        rule = CLAIM_REQUIREMENTS.get(claim.claim_type)
        if not rule:
            # Fallback for unknown claim types
            return False, "INCONCLUSIVE", f"No acceptance policy defined for claim type '{claim.claim_type}'."

        if evidence is None:
            return False, rule.default_missing_verdict, f"No evidence provided for claim '{claim.statement}' ({rule.description})."

        # Check execution presence
        is_observed = getattr(evidence, "is_observed", False) or hasattr(evidence, "receipt_id")
        if not is_observed:
            return False, rule.default_missing_verdict, "Evidence is not an authoritative observed execution."

        # Check semantic claims backed only by generic commands
        if rule.minimum_evidence in (RequiredEvidenceKind.BEHAVIOR_EVIDENCE, RequiredEvidenceKind.SECURITY_VERIFIER):
            exec_kind = getattr(evidence, "execution_kind", "")
            if exec_kind != "test_runner":
                return (
                    False,
                    rule.default_missing_verdict,
                    (
                        f"Evidence is inconclusive: claim '{claim.statement}' is a semantic/feature claim requiring behavioral evidence, "
                        f"but evidence was only generic execution (EXECUTION_VERIFIED != CLAIM_VERIFIED)."
                    ),
                )

        # Check test claims
        if rule.minimum_evidence == RequiredEvidenceKind.STRUCTURED_TEST_RESULTS:
            exec_kind = getattr(evidence, "execution_kind", "")
            if exec_kind not in ("test_runner", "test_executor"):
                return False, "REJECT", f"Claim '{claim.statement}' asserts tests pass, but execution was not an authorized test runner."

        return True, "ACCEPT", "Evidence satisfies minimum policy requirements."
