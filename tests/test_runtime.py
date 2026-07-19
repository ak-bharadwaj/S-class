import os
import sys
import json
import pytest
from datetime import datetime, timezone

# Add parent directory to sys.path to import runtime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runtime

def test_initialize_state(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace)
    
    config_file = os.path.join(workspace, "sclass.config.json")
    state_file = os.path.join(workspace, ".agents", "orchestration_state.json")
    
    assert os.path.exists(config_file)
    assert os.path.exists(state_file)
    
    state = runtime.get_state(workspace)
    assert state.currentPhase == "TRIAGE"
    assert state.currentSpecVersion == 1
    assert len(state.decisionLog) == 1

def test_recursive_schema_validation(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace)
    state = runtime.get_state(workspace)
    
    # Insert invalid task format (dependsOn must be array of strings)
    invalid_task = {
        "id": "T1",
        "owner": "dss_builder_v2",
        "targets": ["auth.py"],
        "dependsOn": 12345,  # Invalid: integer instead of array
        "acceptanceCriteria": "Tests pass",
        "priority": "HIGH",
        "status": "PENDING"
    }
    
    state_dict = runtime.asdict(state)
    state_dict["tasks"].append(invalid_task)
    
    with pytest.raises(TypeError) as excinfo:
        runtime.validate_state_types(state_dict)
    assert "Type validation failed" in str(excinfo.value)

def test_dispatch_event_valid(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace)
    
    # TRIAGE -> triage_done -> ANALYSIS
    runtime.dispatch_event("triage_done", workspace)
    state = runtime.get_state(workspace)
    assert state.currentPhase == "ANALYSIS"
    assert state.activeEvent == "triage_done"

def test_dispatch_event_invalid(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace)
    
    # TRIAGE cannot transition via design_drafted
    with pytest.raises(ValueError) as excinfo:
        runtime.dispatch_event("design_drafted", workspace)
    assert "Transition" in str(excinfo.value)

def test_update_task_status(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace)
    state = runtime.get_state(workspace)
    
    # Add dependency tasks
    t1 = runtime.Task(
        id="T1", owner="dss_builder_v2", targets=["auth.py"],
        dependsOn=[], acceptanceCriteria="Done", priority="HIGH", status="PENDING"
    )
    t2 = runtime.Task(
        id="T2", owner="dss_builder_v2", targets=["router.py"],
        dependsOn=["T1"], acceptanceCriteria="Done", priority="HIGH", status="PENDING"
    )
    state.tasks = [t1, t2]
    runtime.save_state(state, workspace)
    
    # Update T1 to COMPLETED
    runtime.update_task("T1", "COMPLETED", workspace)
    state = runtime.get_state(workspace)
    assert state.tasks[0].status == "COMPLETED"

def test_stale_lock_recovery(tmp_path):
    workspace = str(tmp_path)
    state_dir = os.path.join(workspace, ".agents")
    os.makedirs(state_dir, exist_ok=True)
    lock_file = os.path.join(state_dir, "state.lock")
    
    # Write a dead PID to simulate a crashed holder
    dead_pid = 999999  # Highly unlikely to be running
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(str(dead_pid))
        
    # Attempting initialization should recover stale lock file successfully
    runtime.initialize_state(workspace)
    assert not os.path.exists(lock_file)  # Lock file is cleaned up after block exit
