"""
Meta-Planner Layer for S-Class v6

Dynamically inspects incoming user goals and classifies them into tailored workflow profiles.
Rather than forcing every task through the full 15-state pipeline, the Meta-Planner selects
the shortest safe FSM path based on task intent and complexity.
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import copy
import re


class WorkflowProfile(Enum):
    FULL = "full"            # Full 15-state pipeline (New features, complex architecture)
    BUG_FIX = "bug_fix"      # Fast-track repair (TRIAGE -> ANALYSIS -> CODING -> INTEGRATION -> QA -> RELEASE -> DONE)
    RESEARCH = "research"    # Read-only audit (TRIAGE -> ANALYSIS -> DEBATE -> DONE)
    REFACTOR = "refactor"    # Structuring (TRIAGE -> ANALYSIS -> DESIGN -> CODING -> INTEGRATION -> QA -> RELEASE -> DONE)
    HOTFIX = "hotfix"        # Emergency patch (TRIAGE -> CODING -> QA -> RELEASE -> DONE)
    FAST = "fast"            # High-velocity accelerated pipeline (/boost workflow)
    CORE = "core"            # Minimal build path for algorithm/library/CLI tasks (7 states)
    MICRO = "micro"          # 3 states - Typo, rename, 1-line fix (TRIAGE -> CODING -> DONE)
    SMALL_FIX = "small_fix"  # 5 states - Small feature, CSS change (TRIAGE -> ANALYSIS -> CODING -> TASK_VERIFICATION -> DONE)
    QUESTION = "question"    # 1 state  - User asked a question (DONE - no FSM needed)


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
    ],
    WorkflowProfile.FAST: [
        "TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS", "CODING",
        "TASK_VERIFICATION", "MERGE", "INTEGRATION", "QA", "RELEASE", "MONITORING", "DONE"
    ],
    WorkflowProfile.CORE: [
        "TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS",
        "CODING", "TASK_VERIFICATION", "QA", "DONE"
    ],
    WorkflowProfile.MICRO: [
        "TRIAGE", "CODING", "DONE"
    ],
    WorkflowProfile.SMALL_FIX: [
        "TRIAGE", "ANALYSIS", "CODING", "TASK_VERIFICATION", "DONE"
    ],
    WorkflowProfile.QUESTION: [
        "DONE"
    ],
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
    },
    WorkflowProfile.FAST: {
        "SPECIFICATION_SYNTHESIS": {
            "spec_synthesized": "CODING",     # Accelerated bypass: DESIGN, DEBATE, DESIGN_REVISION, TASK_COMPILATION
            "spec_conflict_detected": "CLARIFICATION"
        }
    },
    WorkflowProfile.CORE: {
        "SPECIFICATION_SYNTHESIS": {
            "spec_synthesized": "CODING",      # Skip DESIGN → DEBATE → REVISION → COMPILATION
            "spec_conflict_detected": "CLARIFICATION"
        },
        "TASK_VERIFICATION": {
            "task_verified": "QA",             # Skip MERGE → INTEGRATION
            "task_verification_failed": "CODING"
        },
        "QA": {
            "qa_passed": "DONE",               # Skip RELEASE → MONITORING
            "qa_failed": "CODING"              # Recovery goes straight back to CODING
        }
    },
    WorkflowProfile.MICRO: {
        "TRIAGE": {
            "triage_done": "CODING"
        },
        "CODING": {
            "code_written": "DONE",
            "coding_completed": "DONE"
        }
    },
    WorkflowProfile.SMALL_FIX: {
        "TRIAGE": {
            "triage_done": "ANALYSIS"
        },
        "ANALYSIS": {
            "context_loaded": "CODING",
            "analysis_done": "CODING"
        },
        "CODING": {
            "code_written": "TASK_VERIFICATION",
            "coding_completed": "TASK_VERIFICATION"
        },
        "TASK_VERIFICATION": {
            "task_verified": "DONE",
            "task_verification_failed": "CODING"
        }
    },
    WorkflowProfile.QUESTION: {}
}


class TaskSignals:
    """Multi-signal task classifier for adaptive workflow selection."""

    @staticmethod
    def analyze(goal: str, workspace_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Returns scored signals for profile selection."""
        goal_lower = goal.lower().strip()
        words = goal_lower.split()
        word_count = len(words)

        has_question_mark = "?" in goal or any(
            goal_lower.startswith(q) for q in [
                "what ", "why ", "how ", "where ", "who ", "can you explain ", "explain "
            ]
        )

        feature_indicators = [
            "add", "create", "build", "implement", "design",
            "integrate", "setup", "deploy", "migrate", "portal",
            "dashboard", "platform", "system", "service", "attendance",
            "management", "full", "complete"
        ]
        complexity_count = sum(1 for k in feature_indicators if k in goal_lower)

        # Micro: typo, rename, spelling
        is_micro = "typo" in goal_lower or "spelling" in goal_lower or ("rename" in goal_lower and word_count <= 6)

        # Small fix: explicit small fix or CSS change
        is_small_fix = (
            "small fix" in goal_lower
            or "small feature" in goal_lower
            or "css change" in goal_lower
            or "color change" in goal_lower
            or "styling change" in goal_lower
        )

        # Bug indicators
        bug_indicators = ["bug", "fix", "error", "exception", "failed", "broken", "issue", "crash", "patch"]
        has_bug_word = any(k in goal_lower for k in bug_indicators)

        score = min(100, (word_count * 2) + (complexity_count * 15))

        return {
            "goal": goal,
            "word_count": word_count,
            "has_question_mark": has_question_mark,
            "complexity_count": complexity_count,
            "complexity_score": score,
            "is_micro": is_micro,
            "is_small_fix": is_small_fix,
            "has_bug_word": has_bug_word,
            "mentions_multiple_features": complexity_count >= 3,
        }

    @staticmethod
    def select_profile(signals: Dict[str, Any]) -> Optional[WorkflowProfile]:
        score = signals["complexity_score"]

        # Questions don't need FSM at all
        if signals["has_question_mark"] and score < 25 and signals["complexity_count"] == 0:
            return WorkflowProfile.QUESTION

        # Micro: explicit typo / spelling / simple rename
        if signals["is_micro"]:
            return WorkflowProfile.MICRO

        # Small fix
        if signals["is_small_fix"]:
            return WorkflowProfile.SMALL_FIX

        return None


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
            signals = TaskSignals.analyze(goal_text)
            auto_profile = TaskSignals.select_profile(signals)

            if auto_profile == WorkflowProfile.QUESTION:
                profile = WorkflowProfile.QUESTION
                rationale = "Goal is an informational query or question. Bypasses FSM execution pipeline."
            elif auto_profile == WorkflowProfile.MICRO:
                profile = WorkflowProfile.MICRO
                rationale = "Goal indicates a micro task (e.g. typo/rename/1-line fix). Using minimal 3-state MICRO profile (TRIAGE -> CODING -> DONE)."
            elif auto_profile == WorkflowProfile.SMALL_FIX:
                profile = WorkflowProfile.SMALL_FIX
                rationale = "Goal indicates a targeted small change. Using 5-state SMALL_FIX profile (TRIAGE -> ANALYSIS -> CODING -> TASK_VERIFICATION -> DONE)."
            else:
                def _match_keywords(keywords: List[str]) -> bool:
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
                elif _match_keywords(["fast", "boost", "accelerate", "quick", "speed"]):
                    profile = WorkflowProfile.FAST
                    rationale = "Goal indicates high-velocity execution. Using accelerated FAST profile."
                elif _match_keywords(["refactor", "clean up", "restructure", "optimize", "rename", "format"]):
                    profile = WorkflowProfile.REFACTOR
                    rationale = "Goal indicates internal code refactoring. Bypassing multi-agent spec debate."
                elif _match_keywords(["bug", "fix", "error", "exception", "failed", "broken", "issue"]):
                    profile = WorkflowProfile.BUG_FIX
                    rationale = "Goal indicates a targeted bug fix. Bypassing spec debate and heavy design phase."
                elif _match_keywords(["research", "investigate", "audit", "survey", "explain", "analyze", "compare"]):
                    profile = WorkflowProfile.RESEARCH
                    rationale = "Goal indicates a research/audit request. Bypassing build and release execution."
                elif _match_keywords(["algorithm", "data structure", "sorting", "binary search", "sliding window",
                                      "linked list", "tree traversal", "graph algorithm", "dynamic programming",
                                      "implement a", "write a function", "cli tool", "command line",
                                      "library", "sdk", "package", "module", "utility"]):
                    profile = WorkflowProfile.CORE
                    rationale = "Goal indicates algorithm/library/CLI task. Using minimal CORE profile (7 states, no debate/deploy)."
                else:
                    profile = WorkflowProfile.FULL
                    rationale = "Goal requires comprehensive feature development through full 15-state pipeline."

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
            else:
                states[state_name] = {"transitions": copy.deepcopy(trans_map)}

        return effective
