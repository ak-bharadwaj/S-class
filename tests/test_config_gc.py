import os
import json
import time
from datetime import datetime, timezone, timedelta
from config_gc import run_gc

def test_run_gc_stale_lock(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    
    lock_file = agents_dir / "state.lock"
    lock_file.write_text(json.dumps({"pid": 99999999}))
    
    report = run_gc(str(tmp_path))
    assert report.stale_locks_removed == 1
    assert lock_file.exists()
    data = json.loads(lock_file.read_text())
    assert data.get("status") in ["released", "idle"]

def test_run_gc_expired_state(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    
    state_file = agents_dir / "orchestration_state.json"
    state_file.write_text("{}")
    
    old_time = time.time() - (8 * 86400) # 8 days
    os.utime(state_file, (old_time, old_time))
    
    report = run_gc(str(tmp_path), state_max_age_days=7)
    assert report.expired_states_removed == 1
    assert not state_file.exists()

def test_run_gc_memory_pruning(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    
    memory_file = agents_dir / "learning_memory.json"
    old_date = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    new_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    
    data = [
        {"timestamp": old_date, "data": "old"},
        {"timestamp": new_date, "data": "new"}
    ]
    memory_file.write_text(json.dumps(data))
    
    report = run_gc(str(tmp_path), memory_max_age_days=30)
    assert report.expired_memory_entries_pruned == 1
    
    new_data = json.loads(memory_file.read_text())
    assert len(new_data) == 1
    assert new_data[0]["data"] == "new"

def test_run_gc_orphaned_screenshots(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    screenshots_dir = agents_dir / "qa_screenshots"
    screenshots_dir.mkdir()
    
    img = screenshots_dir / "test.png"
    img.write_text("fake image")
    
    old_time = time.time() - (8 * 86400)
    os.utime(img, (old_time, old_time))
    
    report = run_gc(str(tmp_path), state_max_age_days=7)
    assert report.orphaned_screenshots_removed == 1
    assert not img.exists()
