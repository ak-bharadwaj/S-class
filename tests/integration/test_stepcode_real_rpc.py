"""
S-Class Integration: Real Step-Code External Runtime Tests (Part M).
Invokes real external Step-Code JSONL RPC subprocess over stdio (`step --mode rpc`).
Exercises:
1. Subprocess launch and health check
2. Prompt command and response
3. Tool call execution
4. Blocked tool call via S-Class authorization
5. Allowed tool call via dual-layer authorization
6. Event stream normalization and dispatch
7. Abort / cancellation
8. Resume / reconnect
9. Runtime process failure / crash handling (fails closed)
10. Completion proposal adjudication
11. Strict LF framing with Unicode line separators (\\u2028, \\u2029) inside string payloads
"""

import os
import time
import pytest
import tempfile
import shutil
from typing import List

from sclass.execution.harness import StepCodeRpcHarness
from sclass.execution.events import RuntimeEvent
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.project import VerifiedProjectState
from sclass.domain.obligations import TechnicalObligation, ObligationStatus
from sclass.core.completion_evaluator import CompletionEvaluator, CompletionVerdict
from sclass.core.errors import SecurityViolationError


@pytest.fixture
def workspace_env():
    ws = tempfile.mkdtemp(prefix="sclass_real_rpc_")
    test_file = os.path.join(ws, "example.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("real workspace content\n")
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


def test_01_real_stepcode_rpc_startup_and_health(workspace_env):
    """1. Real Step-Code process starts, handles health ping, and reports HEALTHY."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        health = harness.health_check()
        assert health["runtime"] == "step-code"
        assert health["status"] == "HEALTHY"
        assert health["process_alive"] is True
    finally:
        harness.close()


def test_02_real_stepcode_rpc_prompt(workspace_env):
    """2. Real Step-Code process handles prompt RPC and returns untrusted candidate result."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        res = harness.prompt("Refactor the payment gateway")
        assert res["status"] == "ok"
        assert "Refactor the payment gateway" in res["output"]
        assert res.get("untrusted_candidate") is True
    finally:
        harness.close()


def test_03_real_stepcode_rpc_allowed_tool_call(workspace_env):
    """3. DualLayerAuthorizer ALLOW enables real Step-Code tool execution."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        action = ActionRequest(
            actor="agent_1",
            capability="terminal.execute",
            action="read_file",
            target="example.txt",
            parameters={},
            workspace=workspace_env,
        )
        auth = AuthorizationDecision(
            outcome=DecisionOutcome.ALLOW,
            decision_id="dec_allow",
            request_id="req_1",
            reason="Authorized safe read",
        )
        # S-Class authorize_request embeds action hash
        from sclass.control.composite_auth import DualLayerAuthorizer
        signed_auth = DualLayerAuthorizer.authorize_request(action, workspace_dir=workspace_env)
        
        result = harness.submit_action(action, signed_auth)
        assert result["status"] == "SETTLED"
        assert result["executed"] is True
        assert result["untrusted_candidate"] is True
    finally:
        harness.close()


def test_04_real_stepcode_rpc_blocked_tool_call(workspace_env):
    """4. S-Class DENY blocks execution before Step-Code tool effect runs."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        action = ActionRequest(
            actor="agent_1",
            capability="terminal.execute",
            action="delete_file",
            target="critical.db",
            parameters={},
            workspace=workspace_env,
        )
        deny_auth = AuthorizationDecision(
            outcome=DecisionOutcome.DENY,
            decision_id="dec_deny",
            request_id="req_2",
            reason="Deletion of critical database is prohibited",
        )
        with pytest.raises(SecurityViolationError, match="S-Class Authorization DENIED"):
            harness.submit_action(action, deny_auth)
    finally:
        harness.close()


def test_05_real_stepcode_rpc_runtime_permission_blocked(workspace_env):
    """5. Destructive shell command is caught by Step-Code runtime permission analysis."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        action = ActionRequest(
            actor="agent_1",
            capability="terminal.execute",
            action="run_command",
            target="",
            parameters={"command": "rm -rf / --no-preserve-root"},
            workspace=workspace_env,
        )
        allow_auth = AuthorizationDecision(
            outcome=DecisionOutcome.ALLOW,
            decision_id="dec_allow",
            request_id="req_3",
            reason="Bypass attempt",
        )
        with pytest.raises(SecurityViolationError, match="Step-Code Runtime Permission DENIED"):
            harness.submit_action(action, allow_auth)
    finally:
        harness.close()


def test_06_real_stepcode_rpc_event_stream_normalization(workspace_env):
    """6. Real events emitted by Step-Code are normalized to canonical S-Class RuntimeEvent."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    events: List[RuntimeEvent] = []
    harness.subscribe_events(lambda e: events.append(e))
    try:
        harness.prompt("Run analysis step")
        time.sleep(0.1)
        assert len(events) > 0
        ev_types = [e.event_type for e in events]
        assert "tool_execution_start" in ev_types
        assert "tool_execution_end" in ev_types
        for e in events:
            assert e.runtime == "step-code"
            assert e.verify_integrity() is True
    finally:
        harness.close()


def test_07_real_stepcode_rpc_abort_and_cancellation(workspace_env):
    """7. Abort RPC successfully cancels active operation in external runtime."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        op = harness.start_operation({"action": "run_command", "target": "sleep 10"})
        res = harness.abort(operation_id=op.operation_id, reason="User interrupted")
        assert res["status"] == "aborted"
        cancelled = harness.cancel_operation(op.operation_id, reason="User requested cancel")
        assert cancelled is True
    finally:
        harness.close()


def test_08_real_stepcode_rpc_process_failure_fails_closed(workspace_env):
    """8. If Step-Code process crashes, harness fails closed and detects UNAVAILABLE."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        # Trigger crash simulation in external node process
        try:
            harness._send_rpc("simulate_crash", timeout=1.0)
        except Exception:
            pass
        time.sleep(0.2)
        health = harness.health_check()
        assert health["status"] == "UNAVAILABLE"
        assert health["process_alive"] is False

        # Further calls fail closed
        with pytest.raises(SecurityViolationError, match="unhealthy or unavailable|not running"):
            harness.prompt("Attempt while crashed")
    finally:
        harness.close()


def test_09_real_stepcode_rpc_restart_and_reconnect(workspace_env):
    """9. StepCodeRpcHarness can restart process after crash and resume operations."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        # Crash it
        try:
            harness._send_rpc("simulate_crash", timeout=1.0)
        except Exception:
            pass
        time.sleep(0.2)
        assert harness.health_check()["process_alive"] is False

        # Restart
        harness.start_process()
        time.sleep(0.1)
        assert harness.health_check()["status"] == "HEALTHY"
        assert harness.health_check()["process_alive"] is True

        res = harness.prompt("Post-restart prompt")
        assert res["status"] == "ok"
    finally:
        harness.close()


def test_10_real_stepcode_rpc_completion_proposal_does_not_force_truth(workspace_env):
    """10. Real Step-Code completion proposal is strictly adjudicated by CompletionEvaluator."""
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        res = harness.prompt("Complete all deliverables")
        state = VerifiedProjectState(workspace=workspace_env)
        ob = TechnicalObligation(
            obligation_id="ob_unmet",
            task_id="task_1",
            req_id="req_1",
            title="Database migration",
            description="Must execute and verify migration",
            mandatory=True,
            status=ObligationStatus.PENDING,
        )

        assessment = CompletionEvaluator.adjudicate(
            task_id="task_1",
            proposed_completion=res,
            state=state,
            obligations=[ob],
            expected_workspace=workspace_env,
        )
        assert assessment.verdict == CompletionVerdict.BLOCK
        assert assessment.is_accepted is False
    finally:
        harness.close()


def test_11_real_stepcode_rpc_strict_lf_framing_with_unicode_line_separators(workspace_env):
    """
    11. Strict LF framing (C11):
    String payloads containing Unicode line separators (\\u2028, \\u2029)
    must NOT be split or corrupt the JSONL protocol stream.
    """
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        # Prompt containing \u2028 (LINE SEPARATOR) and \u2029 (PARAGRAPH SEPARATOR)
        tricky_prompt = "Header text\u2028Middle line\u2029Footer text"
        res = harness.prompt(tricky_prompt)
        assert res["status"] == "ok"
        assert "Header text" in res["output"]
    finally:
        harness.close()


def test_12_real_stepcode_rpc_extension_tool_interception(workspace_env):
    """
    12. Real Step-Code extension tool interception (Part C7):
    Step-Code extension intercepts tool call and queries S-Class authorization over RPC.
    - Safe read action: S-Class authorizes -> tool executes.
    - Destructive action: S-Class blocks -> tool blocked before execution.
    """
    harness = StepCodeRpcHarness(workspace_dir=workspace_env)
    try:
        # Case A: Safe read tool call is authorized and executes
        res_allowed = harness.execute_tool_with_interception(
            action="read_file",
            target="example.txt",
            parameters={},
        )
        assert res_allowed["status"] == "SETTLED"
        assert res_allowed["allowed"] is True
        assert res_allowed["result"]["exit_code"] == 0

        # Case B: Prohibited destructive command is blocked before execution
        res_blocked = harness.execute_tool_with_interception(
            action="run_command",
            target="",
            parameters={"command": "rm -rf / --no-preserve-root"},
        )
        assert res_blocked["status"] == "BLOCKED"
        assert res_blocked["allowed"] is False
        assert "destructive" in res_blocked["reason"].lower()
    finally:
        harness.close()
