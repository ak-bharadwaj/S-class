import pytest
from sdk_interface import SClassSDK
from planner import MetaPlanner

def test_expo_e2e_micro(tmp_path):
    sdk = SClassSDK(workspace_dir=str(tmp_path))
    goal = "Fix typo in README.md"
    plan = MetaPlanner.classify_goal(goal)
    sdk.initialize_workspace(goal, profile=plan.profile.name)
    state = sdk.get_fsm_state()
    assert state.get("workflowProfile") == "micro"

def test_expo_e2e_small_fix(tmp_path):
    sdk = SClassSDK(workspace_dir=str(tmp_path))
    goal = "Add CSRF token to forms"
    plan = MetaPlanner.classify_goal(goal)
    sdk.initialize_workspace(goal, profile=plan.profile.name)
    state = sdk.get_fsm_state()
    assert state.get("workflowProfile") == "small_fix"

def test_expo_e2e_full(tmp_path):
    sdk = SClassSDK(workspace_dir=str(tmp_path))
    goal = "Refactor auth system"
    plan = MetaPlanner.classify_goal(goal)
    sdk.initialize_workspace(goal, profile=plan.profile.name)
    state = sdk.get_fsm_state()
    assert state.get("workflowProfile") == "full"
