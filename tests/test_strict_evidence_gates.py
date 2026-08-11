import os
import json
import pytest
from verifier import EvidenceVerifier

def setup_dummy_state(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(exist_ok=True)
    state_file = agents_dir / "orchestration_state.json"
    state_file.write_text(json.dumps({
        "taskId": "test-task",
        "currentPhase": "TRIAGE",
        "tasks": [],
        "decisionLog": []
    }))
    return str(tmp_path)

def test_merge_rejects_on_git_conflict_markers(tmp_path):
    cwd = setup_dummy_state(tmp_path)
    bad_code = tmp_path / "app.py"
    bad_code.write_text("<<<<<<< HEAD\nprint('a')\n=======\nprint('b')\n>>>>>>> feature\n")
    
    res = EvidenceVerifier.verify_phase("MERGE", workspace_dir=cwd, allow_soft=False)
    assert not res.passed
    assert any("git conflict markers" in err for err in res.errors)

def test_issue_detection_requires_anomaly_evaluation(tmp_path):
    cwd = setup_dummy_state(tmp_path)
    
    res = EvidenceVerifier.verify_phase("ISSUE_DETECTION", workspace_dir=cwd, allow_soft=False)
    assert not res.passed
    assert any("ISSUE_DETECTION verification failed" in err for err in res.errors)
    
    # Create anomaly evaluation report -> Should pass
    (tmp_path / ".agents" / "anomaly_evaluation.json").write_text("{}")
    res_pass = EvidenceVerifier.verify_phase("ISSUE_DETECTION", workspace_dir=cwd, allow_soft=False)
    assert res_pass.passed

def test_recovery_requires_failure_report_not_just_state_file(tmp_path):
    cwd = setup_dummy_state(tmp_path)
    
    # State file exists, but failure_report.json is missing -> Must fail
    res = EvidenceVerifier.verify_phase("RECOVERY", workspace_dir=cwd, allow_soft=False)
    assert not res.passed
    assert any("RECOVERY verification failed" in err for err in res.errors)

    # Create failure report -> Should pass
    (tmp_path / ".agents" / "failure_report.json").write_text("{}")
    res_pass = EvidenceVerifier.verify_phase("RECOVERY", workspace_dir=cwd, allow_soft=False)
    assert res_pass.passed

def test_monitoring_requires_telemetry_file(tmp_path):
    cwd = setup_dummy_state(tmp_path)
    
    # State file exists, but monitoring telemetry is missing -> Must fail
    res = EvidenceVerifier.verify_phase("MONITORING", workspace_dir=cwd, allow_soft=False)
    assert not res.passed
    assert any("MONITORING verification failed" in err for err in res.errors)

    # Create monitoring heartbeat -> Should pass
    (tmp_path / ".agents" / "monitoring_heartbeat.json").write_text("{}")
    res_pass = EvidenceVerifier.verify_phase("MONITORING", workspace_dir=cwd, allow_soft=False)
    assert res_pass.passed

def test_feedback_requires_feedback_file(tmp_path):
    cwd = setup_dummy_state(tmp_path)
    
    # State file exists, but user feedback log is missing -> Must fail
    res = EvidenceVerifier.verify_phase("FEEDBACK", workspace_dir=cwd, allow_soft=False)
    assert not res.passed
    assert any("FEEDBACK verification failed" in err for err in res.errors)

    # Create user feedback log -> Should pass
    (tmp_path / ".agents" / "user_feedback.json").write_text("{}")
    res_pass = EvidenceVerifier.verify_phase("FEEDBACK", workspace_dir=cwd, allow_soft=False)
    assert res_pass.passed
