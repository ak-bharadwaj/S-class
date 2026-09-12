import os
import pytest
from rule_projector import RuleProjector


def test_rule_projector_sync_and_drift_check(tmp_path):
    projector = RuleProjector(workspace_dir=str(tmp_path))
    
    # Initially target files are missing -> drift should be True
    has_drift, statuses = projector.check_drift()
    assert has_drift is True
    assert statuses["CLAUDE.md"] == "MISSING"
    assert statuses[".cursorrules"] == "MISSING"

    # Run sync
    synced = projector.sync()
    assert len(synced) == 4
    assert os.path.exists(tmp_path / "CLAUDE.md")
    assert os.path.exists(tmp_path / ".cursorrules")
    assert os.path.exists(tmp_path / ".windsurfrules")
    assert os.path.exists(tmp_path / ".github" / "copilot-instructions.md")

    # Now check drift -> should be in sync!
    has_drift, statuses = projector.check_drift()
    assert has_drift is False
    assert statuses["CLAUDE.md"] == "IN_SYNC"
    assert statuses[".cursorrules"] == "IN_SYNC"

    # Mutate one file directly -> should detect drift!
    claude_file = tmp_path / "CLAUDE.md"
    claude_file.write_text("Unauthorized manual modification", encoding="utf-8")
    
    has_drift, statuses = projector.check_drift()
    assert has_drift is True
    assert statuses["CLAUDE.md"] == "DRIFTED"
    assert statuses[".cursorrules"] == "IN_SYNC"

    # Re-sync heals the drift
    projector.sync()
    has_drift, statuses = projector.check_drift()
    assert has_drift is False
    assert statuses["CLAUDE.md"] == "IN_SYNC"


def test_rule_projector_detects_missing_canonical_agents_md(tmp_path):
    projector = RuleProjector(workspace_dir=str(tmp_path))
    # Initially AGENTS.md does not exist
    has_drift, statuses = projector.check_drift()
    assert has_drift is True
    assert statuses.get("AGENTS.md") == "MISSING"

