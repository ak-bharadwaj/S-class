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
    WorkflowProfile.FULL: {
        "SPECIFICATION_SYNTHESIS": {
            "spec_synthesized": "DESIGN",
            "spec_conflict_detected": "CLARIFICATION",
            "spec_scope_decision_needed": "CLARIFICATION"
        }
    },
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
            "design_drafted": "TASK_COMPILATION",       # Bypass DEBATE, DESIGN_REVISION
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

        has_question_mark = ("?" in goal or "？" in goal) or any(
            goal_lower.startswith(q) for q in [
                "what ", "why ", "how ", "where ", "who ", "which ", "can you explain ", "explain ", "tell me "
            ]
        )

        action_verbs = [
            "build", "create", "implement", "deploy", "migrate", "develop",
            "setup", "generate", "write code"
        ]
        has_imperative_action = any(
            re.search(r"\b" + re.escape(v) + r"\b", goal_lower) for v in action_verbs
        )
        if "?" in goal_lower or "？" in goal_lower:
            match = re.search(r"(\w+)\s*[\?？]$", goal_lower)
            if match and match.group(1) not in action_verbs:
                has_imperative_action = False

        destructive_patterns = [
            r"\brm\s+-(?:r|f|rf|fr)\b",
            r"\brmdir\b",
            r"\bdrop\s+(?:the\s+)?(?:production\s+)?(?:database|table|schema|collection|db)\b",
            r"\bdelete\s+(?:from\s+\w+|all\s+tests|tests\b)",
            r"\bremove\s+(?:all\s+)?tests\b",
            r"\btruncate\s+(?:table\b)?",
            r"\bwipe\s+(?:database|disk|tests|drive)\b",
            r"\bformat\s+[a-z]:",
        ]
        is_destructive = any(re.search(p, goal_lower) for p in destructive_patterns)

        feature_indicators = [
            "add", "create", "build", "implement", "design",
            "integrate", "setup", "deploy", "migrate", "portal",
            "dashboard", "platform", "system", "attendance",
            "management", "full", "complete"
        ]
        complexity_count = sum(1 for k in feature_indicators if re.search(r"\b" + re.escape(k) + r"\b", goal_lower))

        goal_intent = re.sub(r'\b[\w-]+\.[a-z]{2,4}\b', '', goal_lower)

        auth_keywords = ["auth", "oauth", "jwt", "rbac", "permission", "security", "credential"]
        ui_login_contexts = ["login button", "login btn", "login ui", "login screen", "login page", "login form", "login icon", "login text", "login css"]
        is_ui_login = any(kw in goal_lower for kw in ui_login_contexts)
        
        token_exclude_contexts = ["csrf token", "pagination token", "budget token"]
        is_safe_token = any(kw in goal_lower for kw in token_exclude_contexts)

        mentions_auth_security = (
            any(k in goal_intent for k in auth_keywords) or
            ("login" in goal_intent and not is_ui_login) or
            ("token" in goal_intent and not is_safe_token)
        )

        mentions_database = any(k in goal_lower for k in ["database", "schema", "migration", "prisma", "postgres", "sqlite", "table", "column"])
        has_serious_bug = any(k in goal_lower for k in ["crash", "null pointer", "segfault", "exception", "deadlock", "regression", "broken build"])

        micro_keywords = [
            "typo", "spelling", "copyright", "text in", "button text", "label",
            "rename", "comment", "readme", "documentation", "docstring", "unused import"
        ]
        is_micro = (
            not is_destructive
            and not mentions_database
            and not mentions_auth_security
            and not has_serious_bug
            and (
                any(k in goal_lower for k in micro_keywords)
                or (
                    word_count <= 6
                    and not complexity_count
                    and any(k in goal_lower for k in ["update", "change", "set", "fix", "replace", "remove"])
                    and any(k in goal_lower for k in ["year", "version", "title", "text", "string", "name", "tag", "icon"])
                )
            )
        )

        small_fix_keywords = [
            "small fix", "small feature", "css change", "css tweak", "styling change",
            "padding", "margin", "background to", "font size", "header background",
            "toggle", "dark mode", "light mode", "color to", "border", "align",
            "color", "colour", "button color", "background color", "button style",
            "csrf token", "pagination token", "budget token",
            "update dependencies", "bump dependencies", "update node.js dependencies",
            "update packages", "bump packages", "npm update", "npm install", "yarn upgrade",
            "yarn add", "npm i", "package.json", "pip install", "poetry add", "requirements.txt"
        ]
        is_small_fix = (
            not is_destructive
            and not mentions_database
            and not mentions_auth_security
            and not has_serious_bug
            and any(k in goal_lower for k in small_fix_keywords)
        )

        bug_indicators = ["bug", "fix", "error", "exception", "fail", "failed", "failing", "broken", "issue", "crash", "patch", "rogue"]
        has_bug_word = any(re.search(r"\b" + re.escape(k) + r"\b", goal_lower) for k in bug_indicators)

        score = min(100, (word_count * 2) + (complexity_count * 15))

        return {
            "goal": goal,
            "word_count": word_count,
            "has_question_mark": has_question_mark,
            "has_imperative_action": has_imperative_action,
            "is_destructive": is_destructive,
            "complexity_count": complexity_count,
            "complexity_score": score,
            "is_micro": is_micro,
            "is_small_fix": is_small_fix,
            "has_bug_word": has_bug_word,
            "mentions_auth_security": mentions_auth_security,
            "mentions_database": mentions_database,
            "has_serious_bug": has_serious_bug,
            "mentions_multiple_features": complexity_count >= 3,
        }

    @staticmethod
    def select_profile(signals: Dict[str, Any]) -> Optional[WorkflowProfile]:
        score = signals["complexity_score"]

        if signals.get("is_destructive"):
            return WorkflowProfile.FULL

        if signals["word_count"] == 0:
            return WorkflowProfile.QUESTION

        # Questions don't need FSM at all, UNLESS they contain imperative build actions
        if signals["has_question_mark"] and not signals["has_imperative_action"]:
            if score < 30 or not signals["mentions_multiple_features"]:
                return WorkflowProfile.QUESTION

        # Micro: explicit typo / spelling / simple rename / 1-line text/value change
        if signals["is_micro"] and not signals["mentions_auth_security"] and not signals["has_serious_bug"] and not signals["mentions_database"]:
            return WorkflowProfile.MICRO

        # Small fix: CSS / colors / small UI / simple tweaks (when not fixing a functional bug)
        if signals["is_small_fix"] and not signals["has_bug_word"] and not signals["mentions_auth_security"] and not signals["has_serious_bug"] and not signals["mentions_database"]:
            return WorkflowProfile.SMALL_FIX

        return None


PROFILE_SEVERITY_ORDER: Dict[WorkflowProfile, int] = {
    WorkflowProfile.QUESTION: 0,
    WorkflowProfile.MICRO: 1,
    WorkflowProfile.SMALL_FIX: 2,
    WorkflowProfile.RESEARCH: 3,
    WorkflowProfile.FAST: 4,
    WorkflowProfile.HOTFIX: 5,
    WorkflowProfile.CORE: 6,
    WorkflowProfile.BUG_FIX: 7,
    WorkflowProfile.REFACTOR: 8,
    WorkflowProfile.FULL: 9,
}


class MetaPlanner:
    """Classifies user goals and resolves dynamic workflow plans."""

    @classmethod
    def _classify_single_clause(cls, goal_text: str) -> WorkflowPlan:
        goal_lower = goal_text.lower()
        signals = TaskSignals.analyze(goal_text)
        auto_profile = TaskSignals.select_profile(signals)

        if not goal_text.strip():
            profile = WorkflowProfile.QUESTION
            rationale = "Empty goal string provided. Bypasses FSM execution pipeline."
        elif auto_profile == WorkflowProfile.QUESTION:
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

            if signals.get("is_destructive"):
                profile = WorkflowProfile.FULL
                rationale = "Destructive operational intent detected (drop database / rm -rf / delete tests). Escalating to FULL profile for mandatory verification gates."
            elif _match_keywords(["update dependencies", "upgrade", "bump", "npm", "yarn", "pip", "package.json"]):
                profile = WorkflowProfile.SMALL_FIX
                rationale = "Goal indicates a dependency update or minor upgrade. Using SMALL_FIX profile."
            elif _match_keywords(["hotfix", "urgent patch", "emergency", "crash fix"]):
                profile = WorkflowProfile.HOTFIX
                rationale = "Goal indicates an emergency hotfix requiring immediate patch execution."
            elif _match_keywords(["fast", "boost", "accelerate", "quick", "speed", "deploy", "release", "publish", "ship"]):
                profile = WorkflowProfile.FAST
                rationale = "Goal indicates high-velocity execution or deployment. Using accelerated FAST profile."
            elif signals.get("mentions_auth_security", False) or signals.get("mentions_database", False) or _match_keywords(["encryption", "database migration"]):
                profile = WorkflowProfile.FULL
                rationale = "High-risk domain detected (auth/security/db). Escalating to FULL profile for mandatory DEBATE & verification gates."
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

    @classmethod
    def classify_goal(cls, goal_text: str, override_profile: Optional[str] = None) -> WorkflowPlan:
        """Classifies a goal string into a WorkflowPlan, taking max severity across clauses."""
        if override_profile:
            try:
                profile = WorkflowProfile(override_profile.lower())
                rationale = f"User explicitly specified workflow profile: {profile.value}"
            except ValueError:
                profile = WorkflowProfile.FULL
                rationale = f"Unknown profile '{override_profile}', defaulting to FULL"
            seq = PROFILE_SEQUENCES[profile]
            overrides = PROFILE_TRANSITIONS.get(profile, {})
            return WorkflowPlan(
                profile=profile,
                state_sequence=seq,
                allowed_transitions=overrides,
                rationale=rationale,
                estimated_steps=len(seq)
            )

        # 1. Global destructive pattern check across raw goal string
        destructive_patterns = [
            r"\brm\s+-(?:r|f|rf|fr)\b",
            r"\brmdir\b",
            r"\bdrop\s+(?:the\s+)?(?:production\s+)?(?:database|table|schema|collection|db)\b",
            r"\bdelete\s+(?:from\s+\w+|all\s+tests|tests\b)",
            r"\bremove\s+(?:all\s+)?tests\b",
            r"\btruncate\s+(?:table\b)?",
            r"\bwipe\s+(?:database|disk|tests|drive)\b",
            r"\bformat\s+[a-z]:",
        ]
        if any(re.search(p, goal_text.lower()) for p in destructive_patterns):
            seq = PROFILE_SEQUENCES[WorkflowProfile.FULL]
            return WorkflowPlan(
                profile=WorkflowProfile.FULL,
                state_sequence=seq,
                allowed_transitions=PROFILE_TRANSITIONS.get(WorkflowProfile.FULL, {}),
                rationale="Destructive or high-risk operational intent detected (drop database / rm -rf / delete tests). Escalating to FULL profile for mandatory verification gates.",
                estimated_steps=len(seq)
            )

        # 2. Multi-clause analysis: split by conjunctions or separators and take maximum severity profile
        clauses = [c.strip() for c in re.split(r'\b(?:and\s+also|and\s+then|and|also|then|afterwards|after|before|plus|but|however|\&|\|\||\&\&)\b|[;,\n]', goal_text, flags=re.IGNORECASE) if c.strip()]
        if len(clauses) > 1:
            plans = [cls._classify_single_clause(c) for c in clauses]
            # Take plan with highest profile severity
            best_plan = max(plans, key=lambda p: PROFILE_SEVERITY_ORDER.get(p.profile, 0))
            return best_plan

        return cls._classify_single_clause(goal_text)

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
