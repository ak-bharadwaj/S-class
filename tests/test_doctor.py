import os
import json
from doctor import run_doctor

def test_doctor_healthy(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    (agents_dir / "screenshots").mkdir()
    (agents_dir / "screenshots" / "test.png").write_text("dummy")
    
    (agents_dir / "orchestration_state.json").write_text(json.dumps({"decisionLog": [{"agent": "dss_ui_ux"}]}))
    (agents_dir / "learning_memory.json").write_text("[]")
    (tmp_path / "sclass.config.json").write_text("{}")

    # Create root markdown files required for 100% HEALTHY score
    for md in ["PROJECT.md", "SYSTEM_ARCHITECTURE.md", "DATABASE_SCHEMA.md", "FRONTEND_DESIGN_SYSTEM.md", "ROLE_INTERACTION_MATRIX.md"]:
        (tmp_path / md).write_text("# Root Spec Header\n" + "x" * 150)
    
    report = run_doctor(str(tmp_path))
    assert report.overall_status == "HEALTHY"

def test_doctor_missing_files(tmp_path):
    report = run_doctor(str(tmp_path))
    assert report.overall_status == "DEGRADED"

def test_doctor_corrupt_files(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    
    (agents_dir / "orchestration_state.json").write_text("{bad json")
    
    report = run_doctor(str(tmp_path))
    assert report.overall_status == "BROKEN"
    
def test_doctor_stale_lock(tmp_path):
    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    (agents_dir / "orchestration_state.json").write_text("{}")
    (agents_dir / "learning_memory.json").write_text("[]")
    (tmp_path / "sclass.config.json").write_text("{}")
    
    (agents_dir / "state.lock").write_text(json.dumps({"pid": 99999999}))
    
    report = run_doctor(str(tmp_path))
    assert report.overall_status == "DEGRADED"
