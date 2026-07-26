import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runtime
from sclass_kernel import DeterministicKernel, KernelEventBus, kernel_instance


def test_kernel_event_bus_and_transition(tmp_path):
    workspace = str(tmp_path)
    
    # Initialize state
    runtime.initialize_state(workspace_dir=workspace, goal="Test microkernel architecture")
    
    # Emit event via Kernel EventBus
    bus = kernel_instance.event_bus
    res = bus.emit("triage_done", workspace_dir=workspace, payload={"enforce_evidence": False})
    
    assert res["status"] == "APPROVED"
    assert res["previousPhase"] == "TRIAGE"
    assert res["currentPhase"] == "ANALYSIS"
    assert res["stepIndex"] == 1


def test_kernel_invalid_transition_rejection(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace_dir=workspace)
    
    # Try invalid jump from TRIAGE -> CODING via Kernel
    bus = kernel_instance.event_bus
    with pytest.raises(ValueError) as excinfo:
        bus.emit("code_written", workspace_dir=workspace)
    
    assert "Invalid transition" in str(excinfo.value)


def test_kernel_reset_workflow(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace_dir=workspace)
    
    kernel_instance.event_bus.emit("triage_done", workspace_dir=workspace)
    
    res = kernel_instance.reset_workflow(workspace_dir=workspace, new_goal="Reset goal via microkernel")
    assert res["status"] == "RESET_APPROVED"
    assert res["currentPhase"] == "TRIAGE"
