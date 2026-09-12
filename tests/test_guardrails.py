"""
Unit tests for S-Class V12 Guardrails, Resilience, and Observability
(tests/test_guardrails.py)
"""

import os
import tempfile
import pytest
from package_verifier import PackageVerifier
from secret_scanner import SecretScanner
from context_budget import ContextBudgetMonitor
from steering import SteeringEngine
from promise_protocol import PromiseProtocol
from resilience import ActionResilienceEngine, CircuitBreakerOpenException
from observability import LocalAuditLogger


def test_package_verifier():
    # Known packages return valid
    pypi_res = PackageVerifier.verify_pypi_package("fastapi")
    assert pypi_res["valid"] is True

    npm_res = PackageVerifier.verify_npm_package("react")
    assert npm_res["valid"] is True


def test_secret_scanner():
    clean_code = "def add(a, b): return a + b"
    res_clean = SecretScanner.scan_text(clean_code)
    assert res_clean["clean"] is True

    leaky_code = """
AWS_KEY = "AKIA1234567890ABCDEF"
GITHUB_TOKEN = "ghp_123456789012345678901234567890123456"
"""
    res_leaks = SecretScanner.scan_text(leaky_code)
    assert res_leaks["clean"] is False
    assert res_leaks["leaks_found"] >= 2
    types = [f["type"] for f in res_leaks["findings"]]
    assert "AWS Access Key" in types
    assert "GitHub Token" in types


def test_context_budget_monitor():
    sample_prompt = "Implement an ERP ledger with atomic transactions and role-based access control."
    count = ContextBudgetMonitor.count_tokens(sample_prompt)
    assert count > 0

    eval_norm = ContextBudgetMonitor.evaluate_budget(used_tokens=50000, context_window=128000)
    assert eval_norm["alert_level"] == "NOMINAL"

    eval_warn = ContextBudgetMonitor.evaluate_budget(used_tokens=100000, context_window=128000)
    assert eval_warn["alert_level"] == "WARNING"

    eval_crit = ContextBudgetMonitor.evaluate_budget(used_tokens=120000, context_window=128000)
    assert eval_crit["alert_level"] == "CRITICAL"


def test_steering_engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write directive
        path = SteeringEngine.write_steering_directive(
            instruction="Focus on backend auth endpoints first.",
            workspace_dir=tmpdir,
            command="PRIORITIZE:AUTH",
            priority="HIGH",
        )
        assert os.path.exists(path)

        # Read directive
        directive = SteeringEngine.read_steering_directive(workspace_dir=tmpdir)
        assert directive is not None
        assert directive["command"] == "PRIORITIZE:AUTH"
        assert "Focus on backend auth endpoints" in directive["instruction"]

        # Clear directive
        cleared = SteeringEngine.clear_steering_directive(workspace_dir=tmpdir)
        assert cleared is True
        assert SteeringEngine.read_steering_directive(workspace_dir=tmpdir) is None


def test_promise_protocol():
    sample_output = """
Everything is completed and all unit tests are green.
<promise>TASK-102:DONE</promise>
<promise>TASK-103:BLOCKED:Need database password</promise>
"""
    promises = PromiseProtocol.parse_promise_tags(sample_output)
    assert len(promises) == 2
    assert promises[0]["task_id"] == "TASK-102"
    assert promises[0]["status"] == "DONE"
    assert promises[1]["task_id"] == "TASK-103"
    assert promises[1]["status"] == "BLOCKED"
    assert promises[1]["payload"] == "Need database password"

    receipt = PromiseProtocol.sign_promise_receipt("TASK-102")
    assert receipt.startswith("RECEIPT:TASK-102:")


def test_action_resilience_loop_guard():
    engine = ActionResilienceEngine(loop_threshold=3)

    # 1st time
    res1 = engine.record_action("edit_file", {"path": "auth.py", "content": "pass"})
    assert res1["loop_detected"] is False

    # 2nd time
    res2 = engine.record_action("edit_file", {"path": "auth.py", "content": "pass"})
    assert res2["loop_detected"] is False

    # 3rd identical time -> loop triggered
    res3 = engine.record_action("edit_file", {"path": "auth.py", "content": "pass"})
    assert res3["loop_detected"] is True
    assert res3["circuit_state"] == "OPEN"

    # Subsequent call raises circuit breaker exception
    with pytest.raises(CircuitBreakerOpenException):
        engine.record_action("edit_file", {"path": "auth.py", "content": "pass"})

    engine.reset()
    assert engine.circuit_state == "CLOSED"


def test_local_audit_logger():
    with tempfile.TemporaryDirectory() as tmpdir:
        LocalAuditLogger.log_event(
            event_type="TASK_STARTED",
            message="Agent began working on TASK-01",
            payload={"task_id": "TASK-01", "agent": "coder"},
            workspace_dir=tmpdir,
        )
        LocalAuditLogger.log_event(
            event_type="TEST_PASSED",
            message="Unit tests passed 100%",
            payload={"passed": 12, "failed": 0},
            workspace_dir=tmpdir,
        )

        traces = LocalAuditLogger.get_recent_traces(limit=10, workspace_dir=tmpdir)
        assert len(traces) == 2
        assert traces[0]["event_type"] == "TASK_STARTED"
        assert traces[1]["event_type"] == "TEST_PASSED"
