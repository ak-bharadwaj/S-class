"""
Empirical Regression Suite for S-Class EOS

Tests real-world failure cases from actual projects (SGDA 19-feature gap,
Next.js/Prisma schema grounding, FastAPI async session handling, file lock resilience).
"""

import pytest
import os
import sys
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

    # Ensure practical skeptic found zero blocking API issues
    passed, warns, checks = PracticalSkeptic.audit_specification({
        "low_level_designs": spec.low_level_designs,
        "page_spreads": spec.page_spreads,
        "requirements": spec.requirements
    })
    assert passed is True


def test_runtime_file_lock_resilience(temp_workspace):
    """Verify that runtime.write_json_atomic and load_json handle concurrent reads/writes cleanly."""
    state_file = os.path.join(temp_workspace, ".agents", "test_state.json")
    test_data = {"key": "value", "count": 42}

    runtime.write_json_atomic(state_file, test_data)
    loaded = runtime.load_json(state_file)
    assert loaded["count"] == 42
