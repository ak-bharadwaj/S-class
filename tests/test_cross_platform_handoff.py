"""
Unit tests for S-Class V12 Cross-Platform Context Projection & Session Handoff
(tests/test_cross_platform_handoff.py)
"""

import os
import json
import tempfile
import pytest
from codebase_graph_db import CodebaseGraphDB
from rule_generator import PlatformRuleGenerator
from staleness_cascade import StalenessCascadeEngine
from session_handoff import SessionHandoffEngine


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        # Seed orchestration_state.json
        state_path = os.path.join(state_dir, "orchestration_state.json")
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({
                "currentPhase": "CODING",
                "goal": "Build Distributed Event Store",
                "tasks": [{"id": "task-01", "status": "in_progress", "acceptanceCriteria": "Implement event publisher"}],
            }, f)
        yield tmpdir


def test_rule_generator_projections(temp_workspace):
    tmpdir = temp_workspace
    gen = PlatformRuleGenerator(workspace_dir=tmpdir)
    res = gen.generate_all_projections()

    assert os.path.exists(res["cursor"])
    assert res["cursor"].endswith("sclass-governance.mdc")
    with open(res["cursor"], "r", encoding="utf-8") as f:
        c_text = f.read()
        assert "S-Class V12 Epistemic Governance" in c_text
        assert "CODING" in c_text

    assert os.path.exists(res["claude"])
    with open(res["claude"], "r", encoding="utf-8") as f:
        cl_text = f.read()
        assert "CLAUDE.md" in cl_text
        assert "python -m pytest tests/" in cl_text

    assert os.path.exists(res["codex"])
    with open(res["codex"], "r", encoding="utf-8") as f:
        assert "AGENTS.md" in f.read()

    assert os.path.exists(res["gemini"])
    with open(res["gemini"], "r", encoding="utf-8") as f:
        assert "GEMINI.md" in f.read()


def test_staleness_cascade_invalidation(temp_workspace):
    tmpdir = temp_workspace
    db = CodebaseGraphDB(workspace_dir=tmpdir)
    db.upsert_node("file::api/events.py", "events.py", "FILE", "api/events.py")
    db.upsert_node("func::api/events.py:publish", "publish", "FUNCTION", "api/events.py")
    db.upsert_edge("file::api/events.py", "func::api/events.py:publish", "DEFINES")

    cascade = StalenessCascadeEngine(workspace_dir=tmpdir, graph_db=db)
    # Register verified claim
    cascade.register_claim("CLM-PUB-01", "Event publisher verified under load", ["func::api/events.py:publish"])

    claims_before = cascade.load_claims()
    assert claims_before["claims"]["CLM-PUB-01"]["status"] == "VERIFIED"

    # Invalidate file
    report = cascade.invalidate_for_file("api/events.py")
    assert report["stale_claims_count"] == 1
    assert "CLM-PUB-01" in report["stale_claim_ids"]

    claims_after = cascade.load_claims()
    assert claims_after["claims"]["CLM-PUB-01"]["status"] == "STALE"


def test_session_handoff_and_continue_here(temp_workspace):
    tmpdir = temp_workspace
    handoff = SessionHandoffEngine(workspace_dir=tmpdir)
    manifest = handoff.create_handoff_manifest()

    assert manifest["schema_version"] == "schema.session-handoff.v1"
    assert manifest["fsm_phase"] == "CODING"
    assert manifest["active_task"]["id"] == "task-01"

    handoff_file = os.path.join(tmpdir, ".agents", "session_handoff.json")
    assert os.path.exists(handoff_file)

    continue_file = os.path.join(tmpdir, "CONTINUE_HERE.md")
    assert os.path.exists(continue_file)
    with open(continue_file, "r", encoding="utf-8") as f:
        c_text = f.read()
        assert "CONTINUE_HERE.md" in c_text
        assert "Build Distributed Event Store" in c_text
        assert "task-01" in c_text
