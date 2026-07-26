import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runtime
from replay import ReplayEngine, TransitionRecord


def test_transition_record_serialization():
    rec = TransitionRecord(
        stepIndex=1,
        fromState="TRIAGE",
        toState="ANALYSIS",
        eventFired="triage_done",
        workflowProfile="full",
        evidenceVerified=[{"artifact_type": "config_file", "verified": True}],
        decision={"decision": "Transition State to ANALYSIS"},
        timestamp="2026-07-26T19:41:00Z"
    )
    d = rec.to_dict()
    rec2 = TransitionRecord.from_dict(d)
    assert rec2.stepIndex == 1
    assert rec2.fromState == "TRIAGE"
    assert rec2.toState == "ANALYSIS"
    assert rec2.eventFired == "triage_done"
    assert len(rec2.evidenceVerified) == 1


def test_replay_engine_audit(tmp_path):
    workspace = str(tmp_path)
    
    # Initialize state and dispatch events
    runtime.initialize_state(workspace_dir=workspace, goal="Fix rogue closing brace in globals.css")
    runtime.dispatch_event("triage_done", workspace_dir=workspace)
    runtime.dispatch_event("context_loaded", workspace_dir=workspace)
    
    # Audit replay
    report = ReplayEngine.audit_replay(workspace)
    assert report.valid_sequence is True
    assert report.unbroken_trajectory is True
    assert report.total_steps == 2
    assert report.profile_used == "bug_fix"
    assert report.evidence_verified_count > 0


def test_replay_markdown_export(tmp_path):
    workspace = str(tmp_path)
    
    runtime.initialize_state(workspace_dir=workspace, goal="Audit security policies")
    runtime.dispatch_event("triage_done", workspace_dir=workspace)
    
    md = ReplayEngine.export_audit_trail_markdown(workspace)
    assert "# S-Class EOS Execution Audit Trail" in md
    assert "TRIAGE" in md
    assert "triage_done" in md
    assert "| 1 |" in md
