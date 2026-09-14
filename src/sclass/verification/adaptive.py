"""
S-Class Verification: Adaptive Verification Engine (B.8).
Synthesizes dynamic verification policies combining:
- Task Complexity & Domain (TRIVIAL, SMALL, FEATURE, LARGE, HIGH_RISK)
- Platform Profile & Compensation Policy (Codex vs Claude Code vs Antigravity)
- Change Impact & Target Paths (blast radius, security-sensitive boundaries)
- Performance Budget & Overhead Limits

Produces AdaptiveVerificationPolicy and compiles executable VerificationPlans.
"""

from __future__ import annotations
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set

from sclass.domain.claim import Claim, ClaimType
from sclass.platform.profile import PlatformProfile
from sclass.platform.archetypes import get_archetype_profile
from sclass.platform.budget import PerformanceBudget
from sclass.verification.plan import VerificationPlan
from sclass.verification.provider import get_provider_registry


class VerificationLevel(str, Enum):
    """Graduated levels of verification rigor."""
    NONE = "none"
    MINIMAL = "minimal"
    TARGETED = "targeted"
    COMPREHENSIVE = "comprehensive"
    DEEP = "deep"


@dataclass
class AdaptiveVerificationPolicy:
    """Dynamic policy specifying verification requirements and constraints."""
    verification_level: VerificationLevel
    required_providers: List[str]
    required_evidence_kinds: List[str]
    interruption_allowed: bool = True
    concurrency_allowed: bool = False
    timeout_seconds: float = 120.0
    rationale: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def create_verification_plan(
        self,
        target_claims: Optional[List[Claim]] = None,
        goal: str = "",
        workspace_dir: str = "",
    ) -> VerificationPlan:
        """Compiles this adaptive policy into an executable VerificationPlan."""
        return VerificationPlan(
            goal=goal,
            target_claims=target_claims or [],
            required_evidence_kinds=list(self.required_evidence_kinds),
            verifier_ids=list(self.required_providers),
            timeout_seconds=self.timeout_seconds,
            parameters={
                "verification_level": self.verification_level.value,
                "interruption_allowed": self.interruption_allowed,
                "concurrency_allowed": self.concurrency_allowed,
                "rationale": self.rationale,
                "metadata": dict(self.metadata),
            },
        )


class AdaptiveVerificationEngine:
    """
    Synthesizes adaptive verification policies by evaluating task risk,
    platform archetype compensation policies, and change impact.
    """

    HIGH_RISK_PATH_PATTERNS = (
        "auth", "login", "token", "crypto", "secret", "password",
        "permission", "session", "payment", "credential", "cert",
        ".env", "security", "jwt", "oauth",
    )

    @classmethod
    def synthesize_policy(
        cls,
        platform_or_id: Optional[Any] = None,
        complexity_tier: str = "feature",
        changed_files: Optional[List[str]] = None,
        task_goal: str = "",
        budget: Optional[PerformanceBudget] = None,
    ) -> AdaptiveVerificationPolicy:
        """
        Synthesizes an AdaptiveVerificationPolicy tailored to the platform,
        task risk, and modified files.
        """
        # 1. Resolve Platform Profile
        profile: Optional[PlatformProfile] = None
        if isinstance(platform_or_id, PlatformProfile):
            profile = platform_or_id
        elif isinstance(platform_or_id, str):
            profile = get_archetype_profile(platform_or_id)
        elif hasattr(platform_or_id, "platform_id"):
            profile = get_archetype_profile(getattr(platform_or_id, "platform_id"))
        else:
            profile = get_archetype_profile("generic")

        # 2. Analyze change impact & security sensitivity
        files = changed_files or []
        affects_security = False
        goal_lower = task_goal.lower()
        tier_clean = str(complexity_tier).lower().strip()

        for f in files:
            f_norm = f.replace("\\", "/").lower()
            if any(p in f_norm for p in cls.HIGH_RISK_PATH_PATTERNS):
                affects_security = True
                break

        if any(p in goal_lower for p in cls.HIGH_RISK_PATH_PATTERNS):
            affects_security = True

        if tier_clean in ("high_risk", "security"):
            affects_security = True

        # 3. Derive Baseline Verification Level
        if affects_security:
            level = VerificationLevel.DEEP
            rationale = "High-risk or security-sensitive paths targeted: requires deep multi-layered verification (pytest + semgrep + syft)."
            required_providers = ["pytest", "semgrep", "syft"]
            required_evidence = ["test_pass", "security_scan", "sbom"]
        elif tier_clean in ("trivial", "minor") and len(files) <= 1 and not affects_security:
            level = VerificationLevel.MINIMAL
            rationale = "Trivial task with single low-risk file: minimal verification preserving agent autonomy."
            required_providers = ["pytest"]
            required_evidence = ["test_pass"]
        elif tier_clean in ("large", "multi_component") or len(files) > 8:
            level = VerificationLevel.COMPREHENSIVE
            rationale = "Large multi-component blast radius: comprehensive regression testing and dependency validation."
            required_providers = ["pytest", "syft"]
            required_evidence = ["test_pass", "sbom"]
        else:
            level = VerificationLevel.TARGETED
            rationale = "Standard feature development: targeted test verification."
            required_providers = ["pytest"]
            required_evidence = ["test_pass"]

        # 4. Apply Platform-Specific Archetype Compensation Rules
        p_id = profile.platform_id if profile else "generic"
        interruption_allowed = True
        concurrency_allowed = False

        if p_id == "codex":
            # Codex strength: long-horizon execution. Avoid micro-interruptions for non-security tasks.
            if level in (VerificationLevel.MINIMAL, VerificationLevel.TARGETED):
                interruption_allowed = False
                rationale += " [Codex optimization: background verification without execution interruption]"
        elif p_id == "claude_code":
            # Claude Code strength: deep reasoning. Keep verification targeted to avoid context inflation.
            if level == VerificationLevel.COMPREHENSIVE and not affects_security:
                level = VerificationLevel.TARGETED
                rationale += " [Claude Code optimization: context-efficient targeted verification]"
        elif p_id == "antigravity":
            # Antigravity strength: multi-agent parallelism. Concurrency allowed for verification tasks.
            concurrency_allowed = True
            rationale += " [Antigravity optimization: concurrent multi-verifier dispatch enabled]"

        # 5. Check Performance Budget Limits
        if budget is not None:
            # If budget headroom is exhausted and not high-risk, degrade gracefully to avoid blocking
            if budget.is_exhausted() and not affects_security:
                level = VerificationLevel.MINIMAL
                required_providers = ["pytest"]
                rationale += " [PerformanceBudget limit reached: degraded to minimal baseline verification]"

        # Filter required providers by availability if registry is available
        reg = get_provider_registry()
        avail_providers = reg.list_available_providers()
        # Note: We keep required_providers intact so uninstalled critical tools fail-closed rather than silently bypassing

        return AdaptiveVerificationPolicy(
            verification_level=level,
            required_providers=required_providers,
            required_evidence_kinds=required_evidence,
            interruption_allowed=interruption_allowed,
            concurrency_allowed=concurrency_allowed,
            timeout_seconds=120.0 if level != VerificationLevel.DEEP else 300.0,
            rationale=rationale,
            metadata={
                "platform_id": p_id,
                "complexity_tier": tier_clean,
                "affects_security": affects_security,
                "file_count": len(files),
            },
        )
