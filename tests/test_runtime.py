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

def test_reset_to_triage(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace, goal="Original feature request")
    runtime.dispatch_event("triage_done", workspace)
    runtime.dispatch_event("context_loaded", workspace)
    assert runtime.get_state(workspace).currentPhase in ["SPECIFICATION_SYNTHESIS", "DESIGN", "CODING"]
    
    # User modifies requirement mid-flight -> reset_to_triage
    runtime.reset_to_triage(workspace, new_goal="Emergency hotfix for auth server")
    state = runtime.get_state(workspace)
    assert state.currentPhase == "TRIAGE"
    assert state.workflowProfile == "hotfix"
    assert state.activeEvent == "cancellation_requested"

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
        
    # Attempting initialization should recover stale lock file successfully and leave persistent lock file
    runtime.initialize_state(workspace)
    assert os.path.exists(lock_file)  # Persistent lock file remains intact after block exit

def test_memory_manager(tmp_path):
    workspace = str(tmp_path)
    
    # Test learn fix
    runtime.MemoryManager.learn_fix(
        pattern="Turbopack CSS syntax error",
        fix_description="Remove rogue closing brace in globals.css",
        file_path="frontend/app/globals.css",
        solution_code=".counterfactual-panel { padding: 10px; }",
        workspace_dir=workspace
    )
    
    # Verify fix retrieval
    retrieved = runtime.MemoryManager.get_fix("Build failed due to Turbopack CSS syntax error in globals.css", workspace)
    assert retrieved is not None
    assert retrieved["filePath"] == "frontend/app/globals.css"
    assert retrieved["fixDescription"] == "Remove rogue closing brace in globals.css"
    assert retrieved["solutionCode"] == ".counterfactual-panel { padding: 10px; }"
    
    # Non-matching pattern returns None
    assert runtime.MemoryManager.get_fix("Some other unrelated database lock error", workspace) is None

def test_workspace_config_wizard(tmp_path):
    workspace = str(tmp_path)
    
    # Simulate a full-stack web project directory structure
    frontend_dir = os.path.join(workspace, "frontend")
    os.makedirs(frontend_dir, exist_ok=True)
    with open(os.path.join(frontend_dir, "package.json"), "w", encoding="utf-8") as f:
        f.write('{"name": "test-frontend"}')
        
    backend_dir = os.path.join(workspace, "backend")
    os.makedirs(backend_dir, exist_ok=True)
    with open(os.path.join(backend_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write("# FastAPI entry point")
        
    os.makedirs(os.path.join(backend_dir, "prisma"), exist_ok=True)
    
    # Run wizard
    config = runtime.initialize_workspace_wizard(workspace)
    
    # Assertions
    assert config["projectType"] == "full-stack-web"
    assert config["commands"]["devServer"] == "cd frontend && npm run dev"
    assert config["commands"]["apiServer"] == "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
    assert config["commands"]["test"] == "cd frontend && npm test"
    assert config["commands"]["dbMigration"] == "npx prisma db push"

