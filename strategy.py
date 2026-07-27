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


VERIFICATION_PRIORITY_HIERARCHY = {
    "TIER_1_LOGIC": ["working_flow", "business_logic", "backend_routing", "db_schema", "rbac_security"],
    "TIER_2_DATA_VISUAL": ["data_rendering_fidelity", "no_prop_leaks", "input_output_form_flow"],
    "TIER_3_UI": ["layout_structure", "grid_alignment", "component_hierarchy"],
    "TIER_4_UX": ["ergonomics", "micro_animations", "toast_feedback", "hover_states"]
}


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
