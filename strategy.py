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


class ProjectScale(Enum):
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


@dataclass
class ExecutionStrategy:
    goal: str
    risk_level: RiskLevel
    urgency: Urgency
    project_scale: ProjectScale
    parallelism_worthwhile: bool
    clarification_required: bool
    recommended_profile: WorkflowProfile
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
    "INTEGRATION": ["build_check"],
    "QA": ["test_receipt"],
    "RECOVERY": ["patch_plan"],
    "RELEASE": ["release_verification"],
}


class StrategyEngine:
    """Infers engineering strategy and evidence requirements from goal and project context."""

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
        elif any(kw in goal_lower for kw in ["bug", "fix", "typo", "ui alignment"]):
            risk = RiskLevel.LOW
        else:
            risk = RiskLevel.MEDIUM

        # 3. Infer Project Scale
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

        # 4. Infer Parallelism Worthwhile
        parallelism = scale in [ProjectScale.MEDIUM, ProjectScale.LARGE, ProjectScale.ENTERPRISE] and risk in [RiskLevel.MEDIUM, RiskLevel.HIGH]

        # 5. Infer Clarification Necessity
        # Needs clarification if high ambiguity terms or high risk without explicit criteria
        clarification = risk in [RiskLevel.HIGH, RiskLevel.CRITICAL] and not any(kw in goal_lower for kw in ["exact", "specifically", "do not change", "fix line"])

        # 6. Resolve Profile
        if urgency == Urgency.EMERGENCY:
            profile = WorkflowProfile.HOTFIX
        elif risk == RiskLevel.LOW and any(kw in goal_lower for kw in ["fix", "bug", "error"]):
            profile = WorkflowProfile.BUG_FIX
        elif any(kw in goal_lower for kw in ["audit", "research", "investigate", "explain"]):
            profile = WorkflowProfile.RESEARCH
        elif any(kw in goal_lower for kw in ["refactor", "clean"]):
            profile = WorkflowProfile.REFACTOR
        else:
            profile = WorkflowProfile.FULL

        # Construct Rationale
        rationale = (
            f"Strategy Inferred: Urgency={urgency.value.upper()}, Risk={risk.value.upper()}, "
            f"Scale={scale.value.upper()}, Parallelism={'YES' if parallelism else 'NO'}, "
            f"ClarificationNeeded={'YES' if clarification else 'NO'}. Profile => {profile.value.upper()}"
        )

        return ExecutionStrategy(
            goal=goal,
            risk_level=risk,
            urgency=urgency,
            project_scale=scale,
            parallelism_worthwhile=parallelism,
            clarification_required=clarification,
            recommended_profile=profile,
            required_evidence=DEFAULT_EVIDENCE_CONTRACTS,
            rationale=rationale,
        )
