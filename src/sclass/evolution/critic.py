"""
S-Class Evolution: Pre-Evaluation Critic Gate.
Implements Directive Sections 24 and 36:
- Every candidate must pass a deterministic and heuristic critic before evaluation.
- Strictly rejects candidates attempting:
    1. Benchmark or test oracle leakage
    2. Modification of existing tests or assertions
    3. Verifier manipulation or reward tampering
    4. Credential abuse or token extraction
    5. Bypass of S-Class dual-layer authorization
    6. Modification of non-evolvable Trust Kernel files or symbols
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from sclass.evolution.candidate import EvolutionCandidate
from sclass.evolution.components import NON_EVOLVABLE_COMPONENTS


@dataclass(frozen=True)
class CriticResult:
    passed: bool
    rejection_reasons: List[str]
    critic_name: str = "DeterministicSecurityCritic"


class CandidateCritic:
    """
    Evaluates candidate edits against strict epistemic and security barriers.
    """

    FORBIDDEN_DIFF_PATTERNS = [
        re.compile(r"def\s+test_.*\(.*\):", re.IGNORECASE), # Modifying existing tests
        re.compile(r"@pytest\.mark\.skip", re.IGNORECASE),   # Skipping tests
        re.compile(r"assert\s+True", re.IGNORECASE),          # Trivializing assertions
        re.compile(r"CompletionVerdict\.ACCEPT", re.IGNORECASE), # Forging verdict constants
        re.compile(r"DualLayerAuthorizer", re.IGNORECASE),   # Tampering with auth
        re.compile(r"NON_EVOLVABLE_COMPONENTS", re.IGNORECASE), # Attempting to unfreeze trust kernel
        re.compile(r"os\.environ\[[\"'](SCLASS_SECRET|API_KEY|TOKEN)", re.IGNORECASE), # Credential sniffing
        re.compile(r"chmod\s+777|chown", re.IGNORECASE),      # Privilege escalation
    ]

    FORBIDDEN_FILE_PATHS = [
        "src/sclass/trust/",
        "src/sclass/security/",
        "src/sclass/control/",
        "src/sclass/verification/",
        "src/sclass/assurance/",
        "tests/",
    ]

    @classmethod
    def evaluate_candidate(cls, candidate: EvolutionCandidate) -> CriticResult:
        rejections: List[str] = []

        # 1. Non-evolvable component violation check
        for c in candidate.component_set:
            if c.lower() in NON_EVOLVABLE_COMPONENTS:
                rejections.append(f"CRITIC_VIOLATION: Candidate targets non-evolvable Trust Kernel component '{c}'.")

        # 2. Inspect hypothesis edits
        for edit in candidate.edits:
            # Check component
            if edit.component.lower() in NON_EVOLVABLE_COMPONENTS:
                rejections.append(f"CRITIC_VIOLATION: Edit {edit.edit_id} attempts to modify protected component '{edit.component}'.")

            # Check diff for forbidden patterns
            diff_text = edit.diff or ""
            # Normalize path separators for Windows/POSIX cross-platform consistency
            norm_diff = diff_text.replace("\\", "/")

            for pat in cls.FORBIDDEN_DIFF_PATTERNS:
                if pat.search(diff_text) or pat.search(norm_diff):
                    rejections.append(f"CRITIC_VIOLATION: Edit {edit.edit_id} matched forbidden pattern: {pat.pattern}")

            # Check for forbidden target paths (normalized against forward slashes)
            for forbidden_path in cls.FORBIDDEN_FILE_PATHS:
                if forbidden_path in norm_diff:
                    rejections.append(f"CRITIC_VIOLATION: Edit {edit.edit_id} attempts to modify protected path '{forbidden_path}'.")

        passed = (len(rejections) == 0)
        return CriticResult(passed=passed, rejection_reasons=rejections)
