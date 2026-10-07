import pytest
from planner import WorkflowProfile
from token_budget import TOKEN_BUDGETS, get_token_budget, can_fast_path

def test_token_budgets_structure():
    for profile in WorkflowProfile:
        budget = get_token_budget(profile)
        assert "instructions" in budget
        assert "context" in budget
        assert "max_subagents" in budget
        assert budget["instructions"] >= 0
        assert budget["context"] >= 0
        assert budget["max_subagents"] >= 0

def test_token_budgets_string_resolution():
    assert get_token_budget("micro") == TOKEN_BUDGETS[WorkflowProfile.MICRO]
    assert get_token_budget("full") == TOKEN_BUDGETS[WorkflowProfile.FULL]
    assert get_token_budget("invalid_profile") == TOKEN_BUDGETS[WorkflowProfile.FULL]

def test_fast_path_eligibility():
    # Single file typo fix -> eligible
    assert can_fast_path("Fix typo in header", ["header.tsx"]) is True
    assert can_fast_path("Update button color", ["button.css"]) is True

    # Multi-file -> ineligible
    assert can_fast_path("Fix typo in header", ["header.tsx", "footer.tsx"]) is False

    # High-risk keywords -> ineligible
    assert can_fast_path("Update database schema", ["db.py"]) is False
    assert can_fast_path("Update auth token handler", ["auth.py"]) is False
    assert can_fast_path("Fix login issue", ["login.tsx"]) is False
