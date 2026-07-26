import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runtime
from planner import MetaPlanner, WorkflowProfile, WorkflowPlan


def test_classify_bug_fix():
    plan = MetaPlanner.classify_goal("Fix the null pointer crash in user authentication")
    assert plan.profile == WorkflowProfile.BUG_FIX
    assert "CODING" in plan.state_sequence
    assert "DESIGN" not in plan.state_sequence
    assert "spec_approved" not in str(plan.state_sequence)


def test_classify_research():
    plan = MetaPlanner.classify_goal("Investigate and audit security policies in execution_governance")
    assert plan.profile == WorkflowProfile.RESEARCH
    assert plan.state_sequence == ["TRIAGE", "ANALYSIS", "DEBATE", "DONE"]


def test_classify_refactor():
    plan = MetaPlanner.classify_goal("Refactor the memory search logic to use cleaner functions")
    assert plan.profile == WorkflowProfile.REFACTOR
    assert "DESIGN" in plan.state_sequence


def test_classify_hotfix():
    plan = MetaPlanner.classify_goal("Urgent patch for broken production build")
    assert plan.profile == WorkflowProfile.HOTFIX
    assert plan.state_sequence == ["TRIAGE", "CODING", "QA", "RECOVERY", "RELEASE", "DONE"]


def test_classify_full_default():
    plan = MetaPlanner.classify_goal("Build a comprehensive real-time dashboard with multi-tenant RBAC")
    assert plan.profile == WorkflowProfile.FULL
    assert len(plan.state_sequence) == 12


def test_override_profile():
    plan = MetaPlanner.classify_goal("Do something", override_profile="bug_fix")
    assert plan.profile == WorkflowProfile.BUG_FIX


def test_runtime_integration_bug_fix_shortcut(tmp_path):
    workspace = str(tmp_path)
    
    # Initialize state with a bug fix goal
    runtime.initialize_state(workspace_dir=workspace, goal="Fix rogue closing brace in globals.css")
    state = runtime.get_state(workspace)
    assert state.workflowProfile == "bug_fix"
    assert "bug fix" in state.planRationale.lower()
    
    # TRIAGE -> ANALYSIS
    runtime.dispatch_event("triage_done", workspace_dir=workspace)
    assert runtime.get_state(workspace).currentPhase == "ANALYSIS"
    
    # Under BUG_FIX profile, context_loaded shortcuts ANALYSIS directly to CODING!
    runtime.dispatch_event("context_loaded", workspace_dir=workspace)
    assert runtime.get_state(workspace).currentPhase == "CODING"


def test_runtime_integration_hotfix_shortcut(tmp_path):
    workspace = str(tmp_path)
    
    # Initialize state with hotfix profile
    runtime.initialize_state(workspace_dir=workspace, goal="Emergency hotfix for server crash", profile="hotfix")
    assert runtime.get_state(workspace).workflowProfile == "hotfix"
    
    # Under HOTFIX profile, triage_done jumps directly from TRIAGE to CODING!
    runtime.dispatch_event("triage_done", workspace_dir=workspace)
    assert runtime.get_state(workspace).currentPhase == "CODING"
