"""
S-Class v6 Speed Engine: Token Budget & Execution Optimization (token_budget.py)

Enforces profile-based token budgets and manages high-velocity bypass execution paths.
"""

from typing import Dict, Any, Optional
from planner import WorkflowProfile
from context_budget import ContextBudgetMonitor


TOKEN_BUDGETS: Dict[WorkflowProfile, Dict[str, int]] = {
    WorkflowProfile.QUESTION: {
        "instructions": 0,        # No FSM instructions
        "context": 500,           # Minimal project context
        "max_subagents": 0,
    },
    WorkflowProfile.MICRO: {
        "instructions": 500,      # ~10 lines
        "context": 1000,          # Relevant file only
        "max_subagents": 0,
    },
    WorkflowProfile.SMALL_FIX: {
        "instructions": 1500,     # ~30 lines
        "context": 3000,          # Relevant files + patterns
        "max_subagents": 0,
    },
    WorkflowProfile.BUG_FIX: {
        "instructions": 2000,     # Phase-specific rules
        "context": 5000,          # Error context + related files
        "max_subagents": 2,
    },
    WorkflowProfile.CORE: {
        "instructions": 2000,
        "context": 5000,
        "max_subagents": 2,
    },
    WorkflowProfile.HOTFIX: {
        "instructions": 2000,
        "context": 4000,
        "max_subagents": 2,
    },
    WorkflowProfile.FAST: {
        "instructions": 3000,
        "context": 6000,
        "max_subagents": 3,
    },
    WorkflowProfile.REFACTOR: {
        "instructions": 3000,
        "context": 6000,
        "max_subagents": 3,
    },
    WorkflowProfile.FULL: {
        "instructions": 4000,     # Full phase rules
        "context": 8000,          # Comprehensive project context
        "max_subagents": 5,
    },
}

PARALLEL_SAFE_PHASES = {
    ("CODING_BACKEND", "CODING_FRONTEND"): True,
    ("TASK_VERIFICATION", "LINT_CHECK"): True,
}


def get_token_budget(profile: Any) -> Dict[str, int]:
    """Retrieves token limits and subagent limits for a given profile."""
    if isinstance(profile, str):
        try:
            profile = WorkflowProfile(profile.lower())
        except ValueError:
            return TOKEN_BUDGETS[WorkflowProfile.FULL]
    return TOKEN_BUDGETS.get(profile, TOKEN_BUDGETS[WorkflowProfile.FULL])


def count_tokens(text: str) -> int:
    """Counts BPE tokens using ContextBudgetMonitor."""
    return ContextBudgetMonitor.count_tokens(text)


def can_fast_path(goal: str, files_touched: Optional[list] = None) -> bool:
    """
    Checks if a task qualifies for direct fast-path execution (no FSM state overhead).
    1-3 line changes: typo fixes, renames, simple values, color tweaks, single-label updates.
    """
    if files_touched and len(files_touched) > 1:
        return False
    goal_lower = goal.lower()
    # High-risk or complex architecture tasks strictly disqualify fast-path
    if any(k in goal_lower for k in [
        "portal", "dashboard", "database", "schema", "migration", "auth",
        "login", "security", "rbac", "api route", "service", "system", "architecture"
    ]):
        return False

    fast_path_indicators = [
        "typo", "rename", "color", "styling", "css tweak", "css change",
        "fix typo", "spelling", "copyright", "text in", "button text",
        "label", "font", "padding", "margin", "comment", "readme",
        "unused import", "version bump"
    ]
    if any(k in goal_lower for k in fast_path_indicators):
        return True

    words = goal_lower.split()
    if len(words) <= 6 and any(k in goal_lower for k in ["change", "update", "set", "fix", "replace", "remove"]):
        return True

    return False
