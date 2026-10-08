"""
Integration Test: Event Sourcing Crash Recovery & Replay Continuity

Simulates hard process crashes (kill -9 / power failure) mid-task where
orchestration_state.json is corrupted or wiped, and verifies that the ReplayEngine
and SClassKernel can deterministically reconstruct the state from the append-only
event_store.jsonl log and safely resume workflow execution without corruption.
"""

import os
import json
import pytest
from pathlib import Path
import runtime
from replay import ReplayEngine, TransitionRecord
from sclass_kernel import SClassKernel, EventStore


def test_crash_recovery_from_event_log_after_hard_kill(tmp_path: Path):
    ws = str(tmp_path)
    state_dir = os.path.join(ws, ".agents")
    state_file = os.path.join(state_dir, "orchestration_state.json")
    event_store_file = os.path.join(state_dir, "event_store.jsonl")

    # Step 1: Initialize FSM state with a multi-step profile
    runtime.initialize_state(ws, goal="Build secure auth service", profile="full")
    assert os.path.exists(state_file), "Initial orchestration_state.json must exist"

    # Step 2: Progress through multiple deterministic state transitions
    kernel = SClassKernel()
    res1 = kernel.request_transition(event_name="triage_done", workspace_dir=ws)
    assert res1.get("status") == "APPROVED"
    assert res1.get("currentPhase") == "ANALYSIS"

    res2 = kernel.request_transition(event_name="context_loaded", workspace_dir=ws)
    assert res2.get("status") == "APPROVED"
    assert res2.get("currentPhase") == "SPECIFICATION_SYNTHESIS"

    # Verify event_store.jsonl has recorded append-only events
    assert os.path.exists(event_store_file), "Append-only event store must be written"
    events = EventStore.read_all_events(ws)
    assert len(events) >= 2, "Event store must contain multiple transition events"

    # Read state right before crash
    pre_crash_state = runtime.get_state(ws)
    assert pre_crash_state.currentPhase == "SPECIFICATION_SYNTHESIS"
    pre_crash_steps = len(pre_crash_state.transitionHistory)

    # Step 3: Simulate Hard Crash (kill -9 / abrupt disk loss)
    # Corrupt or wipe orchestration_state.json completely
    os.remove(state_file)
    assert not os.path.exists(state_file)

    # Also simulate a stale lock file left behind by the crashed process
    stale_lock = os.path.join(state_dir, "state.lock")
    with open(stale_lock, "w", encoding="utf-8") as f:
        f.write("99999999")  # Non-existent dead PID

    # Step 4: Execute Event Sourcing State Reconstruction
    recovery_result = ReplayEngine.reconstruct_state_from_event_log(ws)
    assert recovery_result["recovered"] is True, "State reconstruction must succeed"
    assert recovery_result["currentPhase"] == "SPECIFICATION_SYNTHESIS"
    assert recovery_result["workflowProfile"] == "full"

    # Step 5: Verify Reconstructed State On Disk
    assert os.path.exists(state_file), "Reconstructed state file must be restored to disk"
    reconstructed_state = runtime.get_state(ws)
    assert reconstructed_state.currentPhase == "SPECIFICATION_SYNTHESIS"
    assert reconstructed_state.workflowProfile == "full"
    assert len(reconstructed_state.transitionHistory) == pre_crash_steps

    # Step 6: Verify Replay Trajectory Continuity
    replay_report = ReplayEngine.audit_replay(ws)
    assert replay_report.valid_sequence is True, f"Replay sequence must be unbroken: {replay_report.errors}"
    assert replay_report.unbroken_trajectory is True

    # Step 7: Verify Workflow Resumption After Recovery
    # Advance to the next valid state (DESIGN)
    res3 = kernel.request_transition(event_name="spec_synthesized", workspace_dir=ws)
    assert res3.get("status") == "APPROVED"
    assert res3.get("currentPhase") == "DESIGN"

    resumed_state = runtime.get_state(ws)
    assert resumed_state.currentPhase == "DESIGN"
    assert len(resumed_state.transitionHistory) == pre_crash_steps + 1
