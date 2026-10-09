import json

from adapters.state_sync import StateSyncManager
from adapters.antigravity import AntigravityAdapter
from adapters.cursor import CursorAdapter
from adapters.copilot import CopilotAdapter


def test_state_sync_uninitialized(tmp_path):
    assert StateSyncManager.get_authoritative_state(str(tmp_path)) is None
    assert StateSyncManager.get_authoritative_phase(str(tmp_path)) == "UNINITIALIZED"

    is_desynced, msg = StateSyncManager.check_desync("TRIAGE", workspace_dir=str(tmp_path))
    assert not is_desynced
    assert "not yet initialized" in msg

    reconciled = StateSyncManager.reconcile(str(tmp_path))
    assert reconciled["status"] == "uninitialized"


def test_state_sync_synchronized(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True)
    state_file = agents_dir / "orchestration_state.json"
    state_data = {
        "currentPhase": "CODING",
        "taskId": "task-abc-123",
        "workflowProfile": "core",
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")

    assert StateSyncManager.get_authoritative_phase(str(tmp_path)) == "CODING"

    is_desynced, msg = StateSyncManager.check_desync("CODING", str(tmp_path), local_task_id="task-abc-123")
    assert not is_desynced
    assert "synchronized" in msg.lower()

    reconciled = StateSyncManager.reconcile(str(tmp_path))
    assert reconciled["status"] == "reconciled"
    assert reconciled["phase"] == "CODING"
    assert reconciled["taskId"] == "task-abc-123"


def test_state_sync_phase_desync(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True)
    state_file = agents_dir / "orchestration_state.json"
    state_data = {
        "currentPhase": "RELEASE",
        "taskId": "task-abc-123",
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")

    # IDE thinks it is in CODING, but kernel is in RELEASE
    is_desynced, msg = StateSyncManager.check_desync("CODING", str(tmp_path))
    assert is_desynced
    assert "desynchronization" in msg.lower()
    assert "RELEASE" in msg


def test_state_sync_task_id_desync(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True)
    state_file = agents_dir / "orchestration_state.json"
    state_data = {
        "currentPhase": "CODING",
        "taskId": "task-kernel-999",
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")

    is_desynced, msg = StateSyncManager.check_desync("CODING", str(tmp_path), local_task_id="task-ide-111")
    assert is_desynced
    assert "mismatch" in msg.lower()


def test_adapters_wire_state_sync(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir(parents=True)
    state_file = agents_dir / "orchestration_state.json"
    state_data = {
        "currentPhase": "QA",
        "taskId": "task-expo-42",
        "workflowProfile": "full",
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")

    # Antigravity adapter
    ag = AntigravityAdapter(str(tmp_path))
    desynced, _ = ag.check_desync("QA", "task-expo-42")
    assert not desynced
    rec = ag.sync_state("QA")
    assert rec["phase"] == "QA"

    # Cursor adapter
    cur = CursorAdapter(str(tmp_path))
    desynced, _ = cur.check_desync("QA", "task-expo-42")
    assert not desynced
    rec = cur.sync_state("QA")
    assert rec["phase"] == "QA"

    # Copilot adapter
    cop = CopilotAdapter(str(tmp_path))
    desynced, _ = cop.check_desync("QA", "task-expo-42")
    assert not desynced
    rec = cop.sync_state("QA")
    assert rec["phase"] == "QA"
