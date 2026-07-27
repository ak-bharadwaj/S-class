"""
Strategy-Aware Planning Engine for S-Class EOS

Infers project scale, urgency, risk level, parallelism utility, and clarification necessity
from user goals and codebase metadata to produce an ExecutionStrategy.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from planner import WorkflowProfile


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Urgency(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class ReviewDepth(Enum):
    LIGHT = "light"
    STANDARD = "standard"
    DEEP = "deep"


class ProjectScale(Enum):
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class TierEnforcement:
    """Enforcement level constants for the 6-tier verification model."""
    HARD_BLOCK = "HARD_BLOCK"   # Zero tolerance — blocks release
    SOFT_WARN  = "SOFT_WARN"    # Advisory — allows release with logged warning
    SOFT_PASS  = "SOFT_PASS"    # Allows release silently, tracks as UX debt


VERIFICATION_PRIORITY_HIERARCHY = {
    "TIER_1_LOGIC": {
        "enforcement": TierEnforcement.HARD_BLOCK,
        "tolerance": 0,
        "domains": ["working_flow", "business_logic", "backend_routing", "db_schema", "rbac_security", "state_transitions", "data_persistence"],
        "description": "Working Logic & Business Flow — Zero tolerance. If EVEN ONE flaw exists, HARD BLOCK.",
    },
    "TIER_2_DATA_VISUAL": {
        "enforcement": TierEnforcement.HARD_BLOCK,
        "tolerance": 0,
        "domains": ["data_rendering_fidelity", "no_prop_leaks", "input_output_form_flow", "no_data_pollution"],
        "description": "Data Visual & Output Fidelity — Zero tolerance. Form inputs must render in output views.",
    },
    "TIER_3A_FUNCTIONAL_UI": {
        "enforcement": TierEnforcement.HARD_BLOCK,
        "tolerance": 0,
        "domains": ["button_reachability", "navigation_rendering", "scroll_access", "modal_dismiss", "content_visibility"],
        "description": "Functional UI that blocks user workflow — Escalates to Tier 1. Button off-screen, nav broken, content hidden.",
        "crossover_escalation": "TIER_1_LOGIC",
    },
    "TIER_3B_COSMETIC_UI": {
        "enforcement": TierEnforcement.SOFT_PASS,
        "tolerance": -1,
        "domains": ["margin_alignment", "padding_consistency", "font_size_variation", "color_mismatch", "border_radius"],
        "description": "Cosmetic UI imperfections — Soft pass. Track as UX debt for follow-up polish.",
        "track_debt": True,
    },
    "TIER_4A_FUNCTIONAL_UX": {
        "enforcement": TierEnforcement.SOFT_WARN,
        "tolerance": 5,
        "domains": ["destructive_action_confirmation", "loading_indicators", "error_feedback", "form_validation_feedback", "empty_state_guidance"],
        "description": "Functional UX preventing safe interaction — Warn and allow. Escalate to SOFT_BLOCK if count > 5.",
        "escalate_above_threshold": TierEnforcement.HARD_BLOCK,
        "track_debt": True,
    },
    "TIER_4B_COSMETIC_UX": {
        "enforcement": TierEnforcement.SOFT_PASS,
        "tolerance": -1,
        "domains": ["micro_animations", "gradient_effects", "hover_transitions", "dark_mode_refinements", "toast_aesthetics"],
        "description": "Cosmetic UX polish — Soft pass. Ship working software, polish later.",
        "track_debt": True,
    },
}


def classify_defect_tier(defect_domain: str, blocks_user_flow: bool = False) -> str:
    """Classifies a defect domain into its enforcement tier.

    Args:
        defect_domain: The domain of the defect (e.g., 'working_flow', 'micro_animations').
        blocks_user_flow: If True and the defect is in Tier 3b/4a/4b, escalates via crossover.

    Returns:
        The tier key (e.g., 'TIER_1_LOGIC', 'TIER_3A_FUNCTIONAL_UI').
    """
    for tier_key, tier_config in VERIFICATION_PRIORITY_HIERARCHY.items():
        if defect_domain in tier_config["domains"]:
            # Tier crossover: if a cosmetic/UX issue blocks a user workflow, escalate
            if blocks_user_flow and tier_key in ("TIER_3B_COSMETIC_UI", "TIER_4A_FUNCTIONAL_UX", "TIER_4B_COSMETIC_UX"):
                return tier_config.get("crossover_escalation", "TIER_3A_FUNCTIONAL_UI")
            return tier_key
    # Default: unknown defects treated as Tier 1 for safety
    return "TIER_1_LOGIC"


def get_enforcement_level(tier_key: str) -> str:
    """Returns the enforcement level for a given tier."""
    tier = VERIFICATION_PRIORITY_HIERARCHY.get(tier_key, {})
    return tier.get("enforcement", TierEnforcement.HARD_BLOCK)


def check_accumulation_threshold(tier_key: str, defect_count: int) -> str:
    """Checks if accumulated defects in a tier exceed its tolerance threshold.

    Returns the effective enforcement level after applying accumulation rules.
    """
    tier = VERIFICATION_PRIORITY_HIERARCHY.get(tier_key, {})
    tolerance = tier.get("tolerance", 0)
    base_enforcement = tier.get("enforcement", TierEnforcement.HARD_BLOCK)

    # tolerance == -1 means unlimited tolerance (always soft pass)
    if tolerance == -1:
        return base_enforcement

    # tolerance == 0 means zero tolerance (always hard block)
    if tolerance == 0:
        return TierEnforcement.HARD_BLOCK if defect_count > 0 else base_enforcement

    # Accumulation escalation: if count exceeds threshold, escalate
    if defect_count > tolerance:
        return tier.get("escalate_above_threshold", TierEnforcement.HARD_BLOCK)

    return base_enforcement


@dataclass
class ImpactAnalysis:
    """Evaluates multi-dimensional operational impact and likelihood vectors of a software defect."""
    workflow_blocking: float = 0.0     # [0.0 - 1.0] Blocks critical user journey / API flow
    data_loss_risk: float = 0.0        # [0.0 - 1.0] Potential data corruption, double submit, or leak
    user_reachability: float = 0.0     # [0.0 - 1.0] User unable to see/interact with UI component
    security_auth_risk: float = 0.0    # [0.0 - 1.0] Bypasses auth / security boundary
    cosmetic_only: float = 0.0         # [0.0 - 1.0] Aesthetic/visual alignment only
    frequency_likelihood: float = 1.0  # [0.0 - 1.0] Occurs every request (1.0) vs 1 in 1M edge case (0.05)

    def to_dict(self) -> Dict[str, float]:
        return {
            "workflow_blocking": self.workflow_blocking,
            "data_loss_risk": self.data_loss_risk,
            "user_reachability": self.user_reachability,
            "security_auth_risk": self.security_auth_risk,
            "cosmetic_only": self.cosmetic_only,
            "frequency_likelihood": self.frequency_likelihood,
        }


@dataclass
class DefectEvaluationVerdict:
    """Verdict produced by the Impact-Driven Evaluation Engine with explainability & confidence."""
    defect_description: str
    impact: ImpactAnalysis
    risk_score: float               # Calculated Risk Score [0.0 - 10.0]
    confidence: float               # Evaluation Confidence [0.0 - 1.0]
    policy_enforcement: str         # HARD_BLOCK | SOFT_WARN | SOFT_PASS
    decision: str                   # REJECT_RELEASE | ALLOW_WITH_WARN | ALLOW_RELEASE
    top_contributors: List[str]     # Explainable breakdown of risk drivers
    evidence: List[str]             # Evidence receipts backing evaluation
    invariant_triggered: bool       # True if a short-circuit hard invariant fired
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "defect_description": self.defect_description,
            "impact": self.impact.to_dict(),
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "policy_enforcement": self.policy_enforcement,
            "decision": self.decision,
            "top_contributors": self.top_contributors,
            "evidence": self.evidence,
            "invariant_triggered": self.invariant_triggered,
            "rationale": self.rationale,
        }


class ImpactDrivenPolicyEngine:
    """Executes the dynamic 5-stage impact pipeline with Hard Invariants, Multiplicative Amplification,

    Conditional Cosmetic Discount, Time/Likelihood Scaling, Explainability, and Confidence Metrics.

    Pipeline: Defect -> Impact Analysis -> Hard Invariant Check -> Risk Score Engine -> Policy -> Decision
    """

    @staticmethod
    def evaluate_defect(
        defect_description: str,
        defect_domain: str,
        blocks_user_flow: bool = False,
        causes_double_submit: bool = False,
        causes_data_loss: bool = False,
        is_auth_security: bool = False,
        is_pure_cosmetic: bool = False,
        frequency_likelihood: float = 1.0,
        evidence_list: Optional[List[str]] = None,
        threshold_hard_block: float = 7.0,
        threshold_soft_warn: float = 4.0,
        impact_override: Optional[ImpactAnalysis] = None,
    ) -> DefectEvaluationVerdict:
        """Evaluates a defect through the hardened 5-stage impact pipeline."""
        evidence = evidence_list or ["heuristic_analysis"]
        contributors: List[str] = []

        # 1. Stage 1: Impact Analysis Vectors
        if impact_override is not None:
            impact = impact_override
        else:
            wf_block = 1.0 if blocks_user_flow or defect_domain in ["working_flow", "business_logic", "backend_routing", "state_transitions"] else 0.0
            dl_risk = 1.0 if causes_data_loss or causes_double_submit else (0.5 if defect_domain == "input_output_form_flow" else 0.0)
            reachability = 1.0 if defect_domain in ["button_reachability", "navigation_rendering", "content_visibility"] or blocks_user_flow else 0.0
            sec_risk = 1.0 if is_auth_security or defect_domain in ["rbac_security", "auth"] else 0.0
            cosmetic = 1.0 if is_pure_cosmetic or defect_domain in ["micro_animations", "hover_transitions", "margin_alignment", "padding_consistency", "border_radius"] else 0.0

            impact = ImpactAnalysis(
                workflow_blocking=wf_block,
                data_loss_risk=dl_risk,
                user_reachability=reachability,
                security_auth_risk=sec_risk,
                cosmetic_only=cosmetic,
                frequency_likelihood=frequency_likelihood,
            )

        # 2. Stage 2: Hard Invariants Check (Short-Circuit Gates before Math)
        if impact.security_auth_risk >= 0.9:
            contributors.append("CRITICAL: Security/Auth Bypass Invariant Triggered (1.0)")
            return DefectEvaluationVerdict(
                defect_description=defect_description,
                impact=impact,
                risk_score=10.0,
                confidence=0.95,
                policy_enforcement=TierEnforcement.HARD_BLOCK,
                decision="REJECT_RELEASE",
                top_contributors=contributors,
                evidence=evidence,
                invariant_triggered=True,
                rationale="INVARIANT TRIGGERED: Critical security/auth risk (>= 0.9) short-circuits to HARD_BLOCK regardless of cosmetic factors.",
            )

        if impact.data_loss_risk >= 0.95:
            contributors.append("CRITICAL: Data Loss / Corruption Invariant Triggered (1.0)")
            return DefectEvaluationVerdict(
                defect_description=defect_description,
                impact=impact,
                risk_score=10.0,
                confidence=0.95,
                policy_enforcement=TierEnforcement.HARD_BLOCK,
                decision="REJECT_RELEASE",
                top_contributors=contributors,
                evidence=evidence,
                invariant_triggered=True,
                rationale="INVARIANT TRIGGERED: Data loss / corruption risk (>= 0.95) short-circuits to HARD_BLOCK.",
            )

        if impact.workflow_blocking >= 0.95:
            contributors.append("CRITICAL: Total Workflow Blockage Invariant Triggered (1.0)")
            return DefectEvaluationVerdict(
                defect_description=defect_description,
                impact=impact,
                risk_score=10.0,
                confidence=0.95,
                policy_enforcement=TierEnforcement.HARD_BLOCK,
                decision="REJECT_RELEASE",
                top_contributors=contributors,
                evidence=evidence,
                invariant_triggered=True,
                rationale="INVARIANT TRIGGERED: Total user workflow blockage (>= 0.95) short-circuits to HARD_BLOCK.",
            )

        # 3. Stage 3: Additive Base Score calculation
        base_score = 0.0
        if impact.workflow_blocking > 0:
            val = impact.workflow_blocking * 3.5
            base_score += val
            contributors.append(f"Workflow Blocking: +{val:.2f}")

        if impact.data_loss_risk > 0:
            val = impact.data_loss_risk * 4.0
            base_score += val
            contributors.append(f"Data Loss Risk: +{val:.2f}")

        if impact.security_auth_risk > 0:
            val = impact.security_auth_risk * 4.0
            base_score += val
            contributors.append(f"Security Auth Risk: +{val:.2f}")

        if impact.user_reachability > 0:
            val = impact.user_reachability * 2.5
            base_score += val
            contributors.append(f"User Reachability: +{val:.2f}")

        # Conditional Cosmetic Discount Rule: ONLY apply if NO functional risk vectors are active
        has_functional_vectors = (impact.workflow_blocking > 0 or impact.data_loss_risk > 0 or impact.security_auth_risk > 0 or impact.user_reachability > 0)
        if impact.cosmetic_only > 0 and not has_functional_vectors:
            discount = impact.cosmetic_only * 2.0
            base_score = max(0.0, base_score - discount)
            contributors.append(f"Pure Cosmetic Discount: -{discount:.2f}")

        # 4. Multiplicative Risk Interaction Engine (Amplification)
        interaction_multiplier = 1.0
        if impact.workflow_blocking > 0.4 and impact.security_auth_risk > 0.4:
            interaction_multiplier *= 1.5
            contributors.append("Multiplicative Interaction: Auth x Workflow (1.5x)")

        if impact.workflow_blocking > 0.4 and impact.data_loss_risk > 0.4:
            interaction_multiplier *= 1.4
            contributors.append("Multiplicative Interaction: Workflow x Data Loss (1.4x)")

        if impact.data_loss_risk > 0.4 and impact.security_auth_risk > 0.4:
            interaction_multiplier *= 1.6
            contributors.append("Multiplicative Interaction: Data Loss x Security (1.6x)")

        amplified_score = base_score * interaction_multiplier

        # 5. Time / Frequency Dimension Scaling (Impact x Likelihood)
        final_risk = min(10.0, max(0.0, round(amplified_score * impact.frequency_likelihood, 2)))
        if impact.frequency_likelihood < 1.0:
            contributors.append(f"Frequency Likelihood Scale: x{impact.frequency_likelihood}")

        # Calculate Confidence Score (0.0 - 1.0)
        confidence = 0.95 if len(evidence) > 1 and "playwright_visual" in str(evidence).lower() else (0.85 if len(evidence) > 0 else 0.70)

        # 6. Policy Mapping & Decision Execution against Configurable Thresholds
        if final_risk >= threshold_hard_block:
            policy = TierEnforcement.HARD_BLOCK
            decision = "REJECT_RELEASE"
            rationale = f"Risk Score {final_risk}/10 >= {threshold_hard_block} (Hard Block Threshold). Defect must be resolved before release."
        elif final_risk >= threshold_soft_warn:
            policy = TierEnforcement.SOFT_WARN
            decision = "ALLOW_WITH_WARN"
            rationale = f"Risk Score {final_risk}/10 in [{threshold_soft_warn}, {threshold_hard_block}). Moderate risk defect allowed with logged advisory and UX debt tracking."
        else:
            policy = TierEnforcement.SOFT_PASS
            decision = "ALLOW_RELEASE"
            rationale = f"Risk Score {final_risk}/10 < {threshold_soft_warn} (Soft Warn Threshold). Low risk / cosmetic defect allowed silently."

        return DefectEvaluationVerdict(
            defect_description=defect_description,
            impact=impact,
            risk_score=final_risk,
            confidence=confidence,
            policy_enforcement=policy,
            decision=decision,
            top_contributors=contributors,
            evidence=evidence,
            invariant_triggered=False,
            rationale=rationale,
        )


@dataclass
class ExecutionStrategy:
    goal: str
    risk_level: RiskLevel
    urgency: Urgency
    project_scale: ProjectScale
    parallelism_worthwhile: bool
    clarification_required: bool
    recommended_profile: WorkflowProfile
    detected_domains: List[str] = field(default_factory=list)
    review_depth: ReviewDepth = ReviewDepth.STANDARD
    debate_panel: List[str] = field(default_factory=list)
    required_evidence: Dict[str, List[str]] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "risk_level": self.risk_level.value,
            "urgency": self.urgency.value,
            "project_scale": self.project_scale.value,
            "parallelism_worthwhile": self.parallelism_worthwhile,
            "clarification_required": self.clarification_required,
            "recommended_profile": self.recommended_profile.value,
            "detected_domains": self.detected_domains,
            "review_depth": self.review_depth.value,
            "debate_panel": self.debate_panel,
            "required_evidence": self.required_evidence,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionStrategy":
        return cls(
            goal=data["goal"],
            risk_level=RiskLevel(data.get("risk_level", "medium")),
            urgency=Urgency(data.get("urgency", "medium")),
            project_scale=ProjectScale(data.get("project_scale", "medium")),
            parallelism_worthwhile=data.get("parallelism_worthwhile", False),
            clarification_required=data.get("clarification_required", False),
            recommended_profile=WorkflowProfile(data.get("recommended_profile", "full")),
            detected_domains=data.get("detected_domains", []),
            review_depth=ReviewDepth(data.get("review_depth", "standard")),
            debate_panel=data.get("debate_panel", []),
            required_evidence=data.get("required_evidence", {}),
            rationale=data.get("rationale", ""),
        )


# Default evidence requirements per state
DEFAULT_EVIDENCE_CONTRACTS: Dict[str, List[str]] = {
    "TRIAGE": ["config_file", "state_file"],
    "ANALYSIS": ["context_loaded"],
    "CLARIFICATION": ["intent_contract"],
    "DESIGN": ["decision_log"],
    "DEBATE": ["consensus_score"],
    "TASK_COMPILATION": ["task_queue"],
    "CODING": ["modified_files"],
    "TASK_VERIFICATION": ["task_verification_receipt"],
    "MERGE": ["merged_sandbox"],
    "INTEGRATION": ["build_check"],
    "QA": ["test_receipt"],
    "RECOVERY": ["patch_plan"],
    "RELEASE": ["release_verification"],
}


DOMAIN_INTERACTION_GRAPH: Dict[str, List[str]] = {
    "database": ["backend", "security"],   # Changing DB automatically triggers Backend & Security review
    "backend": ["frontend", "security"],   # Changing Backend triggers Frontend API & Security review
    "frontend": ["ui"],                     # Changing Frontend triggers UI review
    "security": ["backend", "database"],    # Changing Security triggers Backend & Database review
    "ui": []
}


class StrategyEngine:
    """Infers engineering strategy, domain interaction graph, review depth, and capability-matched debate panel."""

    @staticmethod
    def detect_domains(goal: str) -> List[str]:
        """Detects active software engineering domains and propagates relationships via Domain Interaction Graph."""
        goal_lower = goal.lower()
        base_domains = set()

        # UI / UX Domain
        if any(kw in goal_lower for kw in ["ui", "ux", "css", "style", "layout", "color", "alignment", "design", "navbar", "theme"]):
            base_domains.add("ui")

        # Frontend Domain
        if any(kw in goal_lower for kw in ["frontend", "react", "nextjs", "dom", "component", "button", "page", "view"]):
            base_domains.add("frontend")

        # Backend & API Domain
        if any(kw in goal_lower for kw in ["backend", "api", "dto", "endpoint", "controller", "server", "express", "nestjs", "fastapi", "route", "stripe", "billing", "payment", "auth", "jwt"]):
            base_domains.add("backend")

        # Database Domain
        if any(kw in goal_lower for kw in ["database", "sql", "orm", "schema", "migration", "table", "column", "postgres", "sqlite", "model", "billing", "subscription", "store"]):
            base_domains.add("database")

        # Security & Auth Domain
        if any(kw in goal_lower for kw in ["security", "auth", "crypto", "token", "jwt", "rbac", "secret", "stripe", "billing", "payment", "login"]):
            base_domains.add("security")

        if not base_domains:
            base_domains.add("frontend")
            base_domains.add("backend")

        # Propagate domain interaction graph relationships
        final_domains = set(base_domains)
        for dom in base_domains:
            for related in DOMAIN_INTERACTION_GRAPH.get(dom, []):
                final_domains.add(related)

        return sorted(list(final_domains))

    @staticmethod
    def infer_review_depth(risk_level: RiskLevel, urgency: Urgency) -> ReviewDepth:
        """Determines review depth based on risk level and urgency."""
        if urgency == Urgency.EMERGENCY or risk_level == RiskLevel.LOW:
            return ReviewDepth.LIGHT
        elif risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return ReviewDepth.DEEP
        else:
            return ReviewDepth.STANDARD

    @staticmethod
    def resolve_debate_squad(domains: List[str], review_depth: ReviewDepth) -> List[str]:
        """Dynamically matches debate panel agents based on capability taxonomy and review depth."""
        squad = set()

        # Always include Lead & Governor for architecture review
        squad.add("dss_governor")

        # Map detected domains to capabilities
        if "ui" in domains:
            squad.add("dss_ui_ux")
        if "frontend" in domains:
            squad.add("dss_frontend_dev")
        if "backend" in domains:
            squad.add("dss_backend_dev")
        if "database" in domains:
            squad.add("dss_db_architect")
        if "security" in domains:
            squad.add("dss_cso_v2")

        # Add auditors based on review depth
        if review_depth in [ReviewDepth.STANDARD, ReviewDepth.DEEP]:
            squad.add("dss_reviewer_v2")
        if review_depth == ReviewDepth.DEEP:
            squad.add("dss_user_alias_v2")

        # Fallback to governor & reviewer if squad too small
        if len(squad) < 2:
            squad.add("dss_reviewer_v2")

        return sorted(list(squad))

    @staticmethod
    def infer_strategy(goal: str, codebase_meta: Optional[Dict[str, Any]] = None) -> ExecutionStrategy:
        goal_lower = goal.lower()
        meta = codebase_meta or {}

        # 1. Infer Urgency
        if any(kw in goal_lower for kw in ["emergency", "hotfix", "production down", "critical bug", "crash"]):
            urgency = Urgency.EMERGENCY
        elif any(kw in goal_lower for kw in ["urgent", "asap", "blocking", "high priority"]):
            urgency = Urgency.HIGH
        elif any(kw in goal_lower for kw in ["minor", "tweak", "doc", "comment", "style", "typo"]):
            urgency = Urgency.LOW
        else:
            urgency = Urgency.MEDIUM

        # 2. Infer Risk Level
        if any(kw in goal_lower for kw in ["auth", "security", "crypto", "billing", "payment", "database migration", "schema change"]):
            risk = RiskLevel.CRITICAL if urgency == Urgency.EMERGENCY else RiskLevel.HIGH
        elif any(kw in goal_lower for kw in ["refactor", "architecture", "upgrade", "api change"]):
            risk = RiskLevel.HIGH
        elif any(kw in goal_lower for kw in ["bug", "fix", "typo", "ui alignment", "color", "navbar"]):
            risk = RiskLevel.LOW
        else:
            risk = RiskLevel.MEDIUM

        # 3. Detect Active Domains & Review Depth
        detected_domains = StrategyEngine.detect_domains(goal)
        review_depth = StrategyEngine.infer_review_depth(risk, urgency)

        # 4. Resolve Context-Aware Adaptive Debate Squad (Capability Match)
        debate_squad = StrategyEngine.resolve_debate_squad(detected_domains, review_depth)

        # 5. Infer Project Scale
        file_count = meta.get("file_count", 0)
        if file_count > 500:
            scale = ProjectScale.ENTERPRISE
        elif file_count > 100:
            scale = ProjectScale.LARGE
        elif file_count > 30:
            scale = ProjectScale.MEDIUM
        elif file_count > 5:
            scale = ProjectScale.SMALL
        else:
            scale = ProjectScale.MICRO

        # 6. Infer Parallelism & Clarification
        parallelism = scale in [ProjectScale.MEDIUM, ProjectScale.LARGE, ProjectScale.ENTERPRISE] and risk in [RiskLevel.MEDIUM, RiskLevel.HIGH]
        clarification = risk in [RiskLevel.HIGH, RiskLevel.CRITICAL] and not any(kw in goal_lower for kw in ["exact", "specifically", "do not change", "fix line"])

        # 7. Resolve Profile
        if urgency == Urgency.EMERGENCY:
            profile = WorkflowProfile.HOTFIX
        elif risk == RiskLevel.LOW and any(kw in goal_lower for kw in ["fix", "bug", "error", "align", "color"]):
            profile = WorkflowProfile.BUG_FIX
        elif any(kw in goal_lower for kw in ["audit", "research", "investigate", "explain"]):
            profile = WorkflowProfile.RESEARCH
        elif any(kw in goal_lower for kw in ["refactor", "clean"]):
            profile = WorkflowProfile.REFACTOR
        else:
            profile = WorkflowProfile.FULL

        # Construct Rationale
        rationale = (
            f"Strategy Inferred: Domains={detected_domains}, ReviewDepth={review_depth.value.upper()}, "
            f"Risk={risk.value.upper()}, DebateSquad={debate_squad}, Profile => {profile.value.upper()}"
        )

        return ExecutionStrategy(
            goal=goal,
            risk_level=risk,
            urgency=urgency,
            project_scale=scale,
            parallelism_worthwhile=parallelism,
            clarification_required=clarification,
            recommended_profile=profile,
            detected_domains=detected_domains,
            review_depth=review_depth,
            debate_panel=debate_squad,
            required_evidence=DEFAULT_EVIDENCE_CONTRACTS,
            rationale=rationale,
        )
