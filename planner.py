"""
Meta-Planner Layer for S-Class V7.0

Dynamically inspects incoming user goals and classifies them into tailored workflow profiles.
Rather than forcing every task through the full 11-state pipeline, the Meta-Planner selects
the shortest safe FSM path based on task intent and complexity.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import copy


class WorkflowProfile(Enum):
    FULL = "full"            # Full 11-state pipeline (New features, complex architecture)
    BUG_FIX = "bug_fix"      # Fast-track repair (TRIAGE -> ANALYSIS -> CODING -> INTEGRATION -> QA -> RELEASE -> DONE)
    RESEARCH = "research"    # Read-only audit (TRIAGE -> ANALYSIS -> DEBATE -> DONE)
    REFACTOR = "refactor"    # Structuring (TRIAGE -> ANALYSIS -> DESIGN -> CODING -> INTEGRATION -> QA -> RELEASE -> DONE)
    HOTFIX = "hotfix"        # Emergency patch (TRIAGE -> CODING -> QA -> RELEASE -> DONE)


@dataclass
class WorkflowPlan:
    profile: WorkflowProfile
    state_sequence: List[str]
    allowed_transitions: Dict[str, Dict[str, str]]
    rationale: str
    estimated_steps: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile.value,
            "state_sequence": self.state_sequence,
            "allowed_transitions": self.allowed_transitions,
            "rationale": self.rationale,
            "estimated_steps": self.estimated_steps,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowPlan":
        return cls(
            profile=WorkflowProfile(data["profile"]),
            state_sequence=data["state_sequence"],
            allowed_transitions=data.get("allowed_transitions", {}),
            rationale=data.get("rationale", ""),
            estimated_steps=data.get("estimated_steps", len(data.get("state_sequence", []))),
        )


# Profile Definitions
PROFILE_SEQUENCES: Dict[WorkflowProfile, List[str]] = {
    WorkflowProfile.FULL: [
        "TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS", "DESIGN", "DEBATE",
        "DESIGN_REVISION", "TASK_COMPILATION", "CODING", "TASK_VERIFICATION",
        "MERGE", "INTEGRATION", "QA", "RELEASE", "MONITORING", "DONE"
    ],
    WorkflowProfile.BUG_FIX: [
        "TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS", "CODING",
        "TASK_VERIFICATION", "MERGE", "INTEGRATION", "QA", "RELEASE", "MONITORING", "DONE"
    ],
    WorkflowProfile.RESEARCH: [
        "TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS", "DESIGN", "DEBATE", "DONE"
    ],
    WorkflowProfile.REFACTOR: [
        "TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS", "DESIGN", "CODING",
        "TASK_VERIFICATION", "MERGE", "INTEGRATION", "QA", "RELEASE", "MONITORING", "DONE"
    ],
    WorkflowProfile.HOTFIX: [
        "TRIAGE", "CODING", "TASK_VERIFICATION", "MERGE", "INTEGRATION",
        "QA", "RELEASE", "MONITORING", "DONE"
    ]
}

# Transition overrides per profile (overrides default transitions from workflow.json)
PROFILE_TRANSITIONS: Dict[WorkflowProfile, Dict[str, Dict[str, str]]] = {
    WorkflowProfile.BUG_FIX: {
        "SPECIFICATION_SYNTHESIS": {
            "spec_synthesized": "CODING",     # Bypass DESIGN, DEBATE, DESIGN_REVISION, TASK_COMPILATION
            "spec_conflict_detected": "CLARIFICATION"
        }
    },
    WorkflowProfile.RESEARCH: {
        "DEBATE": {
            "spec_approved": "DONE",          # No coding/build execution needed for research audit
        }
    },
    WorkflowProfile.REFACTOR: {
        "DESIGN": {
            "design_drafted": "CODING",       # Bypass DEBATE, DESIGN_REVISION & TASK_COMPILATION
        }
    },
    WorkflowProfile.HOTFIX: {
        "TRIAGE": {
            "triage_done": "CODING",          # Direct emergency patch jump from TRIAGE to CODING
        }
    }
}


class MetaPlanner:
    """Classifies user goals and resolves dynamic workflow plans."""

    @staticmethod
    def classify_goal(goal_text: str, override_profile: Optional[str] = None) -> WorkflowPlan:
        """Classifies a goal string into a WorkflowPlan."""
        if override_profile:
            try:
                profile = WorkflowProfile(override_profile.lower())
                rationale = f"User explicitly specified workflow profile: {profile.value}"
            except ValueError:
                profile = WorkflowProfile.FULL
                rationale = f"Unknown profile '{override_profile}', defaulting to FULL"
        else:
            goal_lower = goal_text.lower()

            def _match_keywords(keywords: List[str]) -> bool:
                import re
                for kw in keywords:
                    if " " in kw or "-" in kw:
                        if kw in goal_lower:
                            return True
                    else:
                        if re.search(r"\b" + re.escape(kw) + r"\b", goal_lower):
                            return True
                return False

            if _match_keywords(["hotfix", "urgent patch", "emergency", "crash fix"]):
                profile = WorkflowProfile.HOTFIX
                rationale = "Goal indicates an emergency hotfix requiring immediate patch execution."
            elif _match_keywords(["refactor", "clean up", "restructure", "optimize", "rename", "format"]):
                profile = WorkflowProfile.REFACTOR
                rationale = "Goal indicates internal code refactoring. Bypassing multi-agent spec debate."
            elif _match_keywords(["bug", "fix", "error", "exception", "failed", "broken", "issue", "typo"]):
                profile = WorkflowProfile.BUG_FIX
                rationale = "Goal indicates a targeted bug fix. Bypassing spec debate and heavy design phase."
            elif _match_keywords(["research", "investigate", "audit", "survey", "explain", "analyze", "compare"]):
                profile = WorkflowProfile.RESEARCH
                rationale = "Goal indicates a research/audit request. Bypassing build and release execution."
            else:
                profile = WorkflowProfile.FULL
                rationale = "Goal requires comprehensive feature development through full 11-state pipeline."

        seq = PROFILE_SEQUENCES[profile]
        overrides = PROFILE_TRANSITIONS.get(profile, {})

        return WorkflowPlan(
            profile=profile,
            state_sequence=seq,
            allowed_transitions=overrides,
            rationale=rationale,
            estimated_steps=len(seq)
        )

    @staticmethod
    def get_effective_workflow(workflow_dict: Dict[str, Any], profile: WorkflowProfile) -> Dict[str, Any]:
        """Returns a copy of workflow_dict with profile-specific transition overrides applied."""
        effective = copy.deepcopy(workflow_dict)
        states = effective.get("states", {})
        overrides = PROFILE_TRANSITIONS.get(profile, {})

        for state_name, trans_map in overrides.items():
            if state_name in states:
                states[state_name].setdefault("transitions", {}).update(trans_map)

        return effective
