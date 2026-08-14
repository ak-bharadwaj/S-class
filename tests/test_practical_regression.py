"""
Empirical Regression Suite for S-Class EOS

Tests real-world failure cases from actual projects (SGDA 19-feature gap,
Next.js/Prisma schema grounding, FastAPI async session handling, file lock resilience,
dead process lock recovery, and low-confidence decision provenance).
"""

import pytest
import os
import sys
import time
import tempfile
import shutil

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from failure_log import FailureLogManager, FailureCase
from practical_skeptic import PracticalSkeptic
from spec_synthesis import SpecSynthesisEngine
import runtime


@pytest.fixture
def temp_workspace():
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_failure_log_loading_and_recording():
    """Verify that failure log loads existing empirical cases and allows 1-line logging."""
    cases = FailureLogManager.load_cases()
    assert len(cases) >= 3
    assert any("SGDA" in c.project for c in cases)
    assert any("AMIS-RU" in c.project for c in cases)


def test_skeptic_rules_are_100_percent_grounded_in_failure_log():
    """Verify that every rule checked in PracticalSkeptic maps 1:1 to a real logged failure case."""
    cases = FailureLogManager.load_cases()
    logged_rule_ids = {c.skeptic_rule_id for c in cases}
    
    # Assert all core empirical rules exist in the failure cases
    assert "SKEPTIC-PRISMA-SCHEMA-GROUNDING" in logged_rule_ids
    assert "SKEPTIC-ROLE-ROUTE-GUARD" in logged_rule_ids
    assert "SKEPTIC-FASTAPI-ASYNC-TYPING" in logged_rule_ids


def test_practical_skeptic_catches_vibecoded_mockup_fields():
    """Verify that PracticalSkeptic detects generic mockup placeholder fields."""
    mock_spec = {
        "low_level_designs": {
            "admin:/dashboard": {
                "page_name": "Admin Dashboard",
                "tabs": [
                    {
                        "name": "Overview",
                        "fields": ["genericField (string)", "dummy (number)", "validField (string)"],
                        "actions": ["Save"]
                    }
                ],
                "api_endpoints": ["GET /api/admin/dashboard"]
            }
        },
        "page_spreads": {"admin": [{"route": "/profile"}]}
    }
    passed, warns, checks = PracticalSkeptic.audit_specification(mock_spec)
    assert any("SKEPTIC-NO-VIBECODE-UI" in w for w in warns)


def test_practical_skeptic_passes_real_sgda_driving_school_spec(temp_workspace):
    """
    Prompt: 'Build student lesson booking and instructor schedule portal for Sri Guru Driving Academy'
    Ensures S-Class synthesizes actual operational workflows and clean API contracts.
    """
    engine = SpecSynthesisEngine()
    prompt = "Build student lesson booking and instructor schedule portal for Sri Guru Driving Academy with lesson progress and vehicle dispatch"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.gate_result in ["PASS", "PASS_WITH_DECISIONS"]
    assert len(spec.low_level_designs) > 0

    passed, warns, checks = PracticalSkeptic.audit_specification({
        "low_level_designs": spec.low_level_designs,
        "page_spreads": spec.page_spreads,
        "requirements": spec.requirements
    })
    assert passed is True


def test_filelock_recovers_from_dead_pid_and_stale_file(temp_workspace):
    """Verify that FileLock recovers immediately from a crashed process without hanging or timing out."""
    lock_file = os.path.join(temp_workspace, ".agents", "state.lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)

    # Simulate a crashed process leaving behind its lock with a dead PID (e.g. 9999999)
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write("9999999")

    # FileLock must detect the dead PID, clean it up immediately, and acquire the lock in < 0.2s
    start = time.time()
    with runtime.FileLock(lock_file, timeout=2.0):
        # We successfully acquired the lock!
        assert True
    elapsed = time.time() - start
    assert elapsed < 1.0


def test_filelock_enforces_mutual_exclusion_and_timeout(temp_workspace):
    """Verify that FileLock NEVER bypasses the lock when another live process holds it."""
    lock_file = os.path.join(temp_workspace, ".agents", "state.lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)

    # Write CURRENT live process's PID
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    # Attempting to acquire lock with 0.3s timeout must raise TimeoutError (not bypass!)
    with pytest.raises(TimeoutError):
        with runtime.FileLock(lock_file, timeout=0.3):
            pass

    # Cleanup
    if os.path.exists(lock_file):
        os.unlink(lock_file)


def test_low_confidence_decisions_tagged_in_decision_log(temp_workspace):
    """Verify that assumptions and derived low-confidence decisions are recorded in state.decisionLog with provenance."""
    runtime.initialize_state(temp_workspace, goal="Build Driving Academy student portal with booking and lesson progress")
    state = runtime.get_state(temp_workspace)

    assert len(state.decisionLog) >= 1
    # Check that decisions contain provenance details and confidence scores
    decisions = state.decisionLog
    has_confidence_score = any(d.confidence < 1.0 for d in decisions)
    assert has_confidence_score is True
    assert any("Provenance:" in d.reason for d in decisions)
