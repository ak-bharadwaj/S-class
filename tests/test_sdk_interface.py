"""
Unit tests for S-Class V12 Unified SDK Interface
(tests/test_sdk_interface.py)
"""

import os
import tempfile
import pytest
from sdk_interface import SClassSDK


def test_sdk_full_surface():
    with tempfile.TemporaryDirectory() as tmpdir:
        sdk = SClassSDK(workspace_dir=tmpdir)

        # 1. Initialize FSM
        state = sdk.initialize_workspace(goal="Test ERP Core", profile="full")
        assert state["currentPhase"] == "TRIAGE"
        assert state["goal"] == "Test ERP Core"

        # 2. Advance FSM
        adv = sdk.advance_phase()
        assert adv["status"] == "ADVANCED"
        assert adv["current_phase"] == "ANALYSIS"

        # 3. Rule Projection
        projections = sdk.project_rules()
        assert "cursor" in projections
        assert os.path.exists(projections["cursor"])
        assert os.path.exists(projections["claude"])

        # 4. Session Handoff
        handoff = sdk.create_session_handoff()
        assert handoff["schema_version"] == "schema.session-handoff.v1"
        assert os.path.exists(os.path.join(tmpdir, "CONTINUE_HERE.md"))

        # 5. DOM verification
        dom_res = sdk.verify_dom("<!DOCTYPE html><html><head><title>OK</title></head><body><p>App running successfully.</p></body></html>")
        assert dom_res["passed"] is True

        # 6. Secret scan
        secret_res = sdk.scan_secrets("clean code without tokens")
        assert secret_res["clean"] is True

        # 7. Token budget
        budget_res = sdk.evaluate_token_budget(used_tokens=20000)
        assert budget_res["alert_level"] == "NOMINAL"

        # 8. Promise parse
        promises = sdk.parse_promise("Task finished <promise>TASK-1:DONE</promise>")
        assert len(promises) == 1
        assert promises[0]["task_id"] == "TASK-1"
        assert promises[0]["status"] == "DONE"

        # 9. Audit trace
        entry = sdk.log_audit("TEST_RUN", "SDK test completed successfully")
        assert entry["event_type"] == "TEST_RUN"
        assert os.path.exists(os.path.join(tmpdir, ".agents", "audit_trace.jsonl"))
