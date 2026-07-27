import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runtime
from sclass_kernel import MinimalDeterministicKernel, EventStore, kernel_instance
from sclass_planner import ExecutionPlanner, IntentExtractor, RiskAnalyzer, WorkflowSelector
from knowledge_base import KnowledgeBaseManager


def test_kernel_formal_api_and_event_sourcing(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace_dir=workspace, goal="Test minimal microkernel")
    
    # 1. Test request_transition Kernel API
    res = kernel_instance.request_transition("TRIAGE", "triage_done", workspace_dir=workspace)
    assert res["status"] == "APPROVED"
    assert res["previousPhase"] == "TRIAGE"
    assert res["currentPhase"] == "ANALYSIS"
    
    # 2. Test Event Store (Event Sourcing)
    events = EventStore.read_all_events(workspace)
    assert len(events) == 1
    assert events[0]["event_name"] == "triage_done"
    
    # 3. Test State Reconstruction
    recon = kernel_instance.reconstruct_state_from_event_store(workspace)
    assert recon["reconstructed"] is True
    assert recon["total_events"] == 1


def test_design_revision_and_post_release_monitoring(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace_dir=workspace)
    
    # Design -> Debate -> Design Revision -> Task Compilation
    state = runtime.get_state(workspace)
    state.currentPhase = "DEBATE"
    runtime.save_state(state, workspace)
    
    res_rev = kernel_instance.request_transition("DEBATE", "spec_approved", workspace_dir=workspace)
    assert res_rev["currentPhase"] == "DESIGN_REVISION"
    
    res_comp = kernel_instance.request_transition("DESIGN_REVISION", "revision_approved", workspace_dir=workspace)
    assert res_comp["currentPhase"] == "TASK_COMPILATION"

    # Release -> Monitoring -> Feedback -> Issue Detection -> Recovery Loop
    state.currentPhase = "RELEASE"
    runtime.save_state(state, workspace)
    
    res_mon = kernel_instance.request_transition("RELEASE", "release_complete", workspace_dir=workspace)
    assert res_mon["currentPhase"] == "MONITORING"
    
    res_fb = kernel_instance.request_transition("MONITORING", "issue_detected", workspace_dir=workspace)
    assert res_fb["currentPhase"] == "FEEDBACK"


def test_decoupled_planner_pipeline_and_knowledge_base(tmp_path):
    workspace = str(tmp_path)
    goal = "Implement Stripe billing with PostgreSQL database"
    
    # 1. Intent Extractor
    intent = IntentExtractor.extract_intent(goal)
    assert "security" in intent.target_domains
    assert "database" in intent.target_domains
    
    # 2. Risk Analyzer & Knowledge Base
    risk = RiskAnalyzer.analyze_risk(intent, workspace_dir=workspace)
    assert risk.risk_level.value in ["high", "critical"]
    assert "coding_standards" in risk.knowledge_context
    
    # 3. Workflow Selector
    plan = WorkflowSelector.select_profile(intent, risk)
    assert plan.profile.value == "full"
    
    # 4. Execution Planner
    strat = ExecutionPlanner.create_plan(goal, workspace_dir=workspace)
    assert "dss_cso_v2" in strat.debate_panel
