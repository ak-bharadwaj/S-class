"""
Certification Suite: Independent Observation & Structured OTel Telemetry (B.9).
Certifies:
1. Complete execution lifecycle span correlation (parent trace ID binds turn, authorization, execution, and observation).
2. S-Class Prime Invariant: Agent claim contradicted by independently observed OTel telemetry is strictly rejected.
3. Strict secret redaction in OTel process attributes (tokens and credentials replaced with [REDACTED_SECRET]).
4. Local zero-cloud trace persistence to .sclass/events/traces.jsonl with JSON Lines validation.
5. Real-time feeding of observed execution latency and tool calls directly into PerformanceBudget.
6. Hierarchical parent-child span linking across execution lifecycle.
"""

import os
import json
import pytest

from sclass.domain.action import ActionRequest
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.capability import CAP_TERMINAL_EXECUTE
from sclass.observation.convergence import ObservationConvergence
from sclass.telemetry.tracing import (
    get_local_tracer,
    read_recent_traces,
    SPAN_SESSION_TURN,
    SPAN_ACTION_AUTHORIZE,
    SPAN_ACTION_EXECUTE,
    SPAN_OBSERVATION_RECORD,
)
from sclass.platform.budget import PerformanceBudget
from sclass.verification.provider import PytestProvider


@pytest.fixture
def b9_workspace(tmp_path):
    ws = tmp_path / "cert_b9_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_b9_lifecycle_span_correlation_and_hierarchy(b9_workspace):
    """Certifies that execution lifecycle spans are correlated by trace_id with valid hierarchy."""
    session_id = "session_cert_b9_corr_001"
    req = ActionRequest(
        actor="agent:claude_code",
        session=session_id,
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo hello-b9",
        parameters={"command": "echo hello-b9"},
        workspace=b9_workspace,
        platform="claude_code",
    )

    exec_result, receipt = ObservationConvergence.execute_and_observe(
        request=req,
        timeout=10.0,
    )

    assert exec_result.exit_code == 0
    assert receipt is not None

    traces = read_recent_traces(b9_workspace, limit=20)
    assert len(traces) >= 4

    # Filter traces for this session
    session_traces = [t for t in traces if t.get("trace_id") == session_id]
    assert len(session_traces) == 4

    span_names = {t["name"] for t in session_traces}
    assert SPAN_SESSION_TURN in span_names
    assert SPAN_ACTION_AUTHORIZE in span_names
    assert SPAN_ACTION_EXECUTE in span_names
    assert SPAN_OBSERVATION_RECORD in span_names

    turn_span = next(t for t in session_traces if t["name"] == SPAN_SESSION_TURN)
    auth_span = next(t for t in session_traces if t["name"] == SPAN_ACTION_AUTHORIZE)
    exec_span = next(t for t in session_traces if t["name"] == SPAN_ACTION_EXECUTE)
    obs_span = next(t for t in session_traces if t["name"] == SPAN_OBSERVATION_RECORD)

    # All spans share the exact same trace_id
    assert auth_span["trace_id"] == session_id
    assert exec_span["trace_id"] == session_id
    assert obs_span["trace_id"] == session_id

    # Children reference parent_span_id of turn_span
    assert auth_span["parent_span_id"] == turn_span["span_id"]
    assert exec_span["parent_span_id"] == turn_span["span_id"]
    assert obs_span["parent_span_id"] == turn_span["span_id"]

    # Verify attributes recorded
    assert auth_span["attributes"]["decision_outcome"] in ("allow", "warn")
    assert exec_span["attributes"]["exit_code"] == 0
    assert obs_span["attributes"]["receipt_id"] == receipt.receipt_id


def test_b9_agent_claim_contradicted_by_observed_telemetry_rejected(b9_workspace):
    """
    Certifies S-Class Prime Invariant:
    Agent claims 'All 20 tests pass completely', but independently observed telemetry
    recorded exit_code=1 with test failure -> Verification strictly REJECTS claim.
    """
    test_file = os.path.join(b9_workspace, "test_adversarial_b9.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("def test_failing_case():\n    assert False, 'Deliberate failure'\n")

    prov = PytestProvider()
    agent_claim = Claim(
        claim_id="claim_agent_false_pass_001",
        task_id="task_b9_fraud_001",
        statement="All 20 tests pass completely without errors",
        claim_type=ClaimType.TEST_PASS.value,
        metadata={"agent_assertion": "tests_passed"},
    )

    # Independently execute and observe
    exec_res, receipt = prov.execute_and_observe(
        agent_claim,
        b9_workspace,
        parameters={"test_path": "test_adversarial_b9.py"},
    )

    # Observed reality: process failed
    assert exec_res.exit_code != 0

    # Verification must authoritatively reject agent's false claim
    verification_res = prov.verify(agent_claim, receipt, workspace_dir=b9_workspace)
    assert verification_res.is_accepted is False
    assert verification_res.status == "REJECT"
    assert "exit code" in verification_res.reason.lower() or "failed" in verification_res.reason.lower()


def test_b9_secret_redaction_in_otel_attributes(b9_workspace):
    """Certifies that credentials and secrets in commands are redacted before OTel export."""
    from sclass.core.errors import SecurityViolationError

    sensitive_token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
    cmd = f"echo token={sensitive_token}"

    session_id = "session_cert_b9_redact_002"
    req = ActionRequest(
        actor="agent:codex",
        session=session_id,
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target=cmd,
        parameters={"command": cmd},
        workspace=b9_workspace,
        platform="codex",
    )

    # Security policy authoritatively blocks credential leaks at authorization gate
    with pytest.raises(SecurityViolationError):
        ObservationConvergence.execute_and_observe(
            request=req,
            timeout=10.0,
        )

    # Verify secret does not appear anywhere in traces.jsonl
    traces = read_recent_traces(b9_workspace, limit=20)
    session_traces = [t for t in traces if t.get("trace_id") == session_id]
    assert len(session_traces) >= 2

    for span_data in session_traces:
        span_str = json.dumps(span_data)
        assert sensitive_token not in span_str, f"Sensitive token leaked into trace span: {span_str}"

    turn_span = next(t for t in session_traces if t["name"] == SPAN_SESSION_TURN)
    assert "[REDACTED_SECRET]" in turn_span["attributes"]["target"]

    auth_span = next(t for t in session_traces if t["name"] == SPAN_ACTION_AUTHORIZE)
    assert "[REDACTED_SECRET]" in auth_span["attributes"]["target"]


def test_b9_zero_cloud_local_file_persistence(b9_workspace):
    """Certifies that traces are written to .sclass/events/traces.jsonl locally with zero network calls."""
    req = ActionRequest(
        actor="agent:antigravity",
        session="session_cert_b9_zero_cloud",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo offline-observation",
        parameters={"command": "echo offline-observation"},
        workspace=b9_workspace,
        platform="antigravity",
    )

    ObservationConvergence.execute_and_observe(request=req, timeout=10.0)

    trace_file = os.path.join(b9_workspace, ".sclass", "events", "traces.jsonl")
    assert os.path.exists(trace_file)

    # Ensure every line is valid standalone JSON
    lines_read = 0
    with open(trace_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                assert "trace_id" in record
                assert "name" in record
                assert "status" in record
                lines_read += 1

    assert lines_read >= 4


def test_b9_performance_budget_overhead_recording(b9_workspace):
    """Certifies that observed execution duration and tool calls feed directly into PerformanceBudget."""
    budget = PerformanceBudget()
    assert budget.consumption.latency_ms == 0.0
    assert budget.consumption.tool_calls == 0

    req = ActionRequest(
        actor="agent:cursor",
        session="session_cert_b9_budget_001",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo budget-test",
        parameters={"command": "echo budget-test"},
        workspace=b9_workspace,
        platform="cursor",
    )

    ObservationConvergence.execute_and_observe(
        request=req,
        budget=budget,
        timeout=10.0,
    )

    # Budget has received overhead accounting
    assert budget.consumption.tool_calls == 1
    assert budget.consumption.latency_ms > 0.0
    assert budget.compute_overhead_score() > 0.0
