import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runtime
from sclass_kernel import MinimalDeterministicKernel, EventStore, kernel_instance
from sclass_planner import PlanningEngine


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


def test_kernel_formal_api_recovery(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace_dir=workspace)
    
    # Transition to RECOVERY phase simulation
    state = runtime.get_state(workspace)
    state.currentPhase = "RECOVERY"
    runtime.save_state(state, workspace)
    
    # Request Recovery Kernel API
    res = kernel_instance.request_recovery("SyntaxError: Unexpected token", workspace_dir=workspace)
    assert res["status"] == "APPROVED"
    assert res["currentPhase"] == "CODING"


def test_planner_engine_and_capability_discovery():
    plan = PlanningEngine.create_execution_plan("Implement Stripe billing with Postgres database")
    assert "security" in plan.detected_domains
    assert "database" in plan.detected_domains
    
    plugins = PlanningEngine.discover_capability_plugins()
    assert "dss_builder_react" in plugins
    assert "dss_builder_sql" in plugins
