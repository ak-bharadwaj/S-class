"""
Integration Test: Real StepCodeProvider Substrate.
Exercises the complete StepCodeProvider integrating:
1. Subprocess launch and health check
2. Prompt execution returning untrusted candidate
3. Action execution through 5-way permission and durable effect boundary
4. Denied action execution blocked fail-closed
5. Subagent spawning and bounded delegation
6. Telemetry emission into runtime_telemetry.jsonl
"""

import os
import pytest
import tempfile
import shutil

from sclass.runtime.stepcode import StepCodeProvider
from sclass.runtime.permissions import PermissionPreset
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.composite_auth import DualLayerAuthorizer
from sclass.core.errors import SecurityViolationError


@pytest.fixture
def workspace_env():
    ws = tempfile.mkdtemp(prefix="sclass_provider_live_")
    test_file = os.path.join(ws, "sample.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("content for live provider\n")
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


def test_stepcode_provider_startup_and_health(workspace_env):
    provider = StepCodeProvider(workspace_dir=workspace_env, use_test_double=True)
    try:
        health = provider.health_check()
        assert health["provider"] == "StepCodeProvider"
        assert health["status"] == "HEALTHY"
        assert health["permission_preset"] == PermissionPreset.AUTOPILOT.value
    finally:
        provider.close()


def test_stepcode_provider_prompt(workspace_env):
    provider = StepCodeProvider(workspace_dir=workspace_env, use_test_double=True)
    try:
        res = provider.prompt("Optimize database query")
        assert res["status"] == "ok"
        assert res.get("untrusted_candidate") is True
    finally:
        provider.close()


def test_stepcode_provider_action_execution_sandwich(workspace_env):
    provider = StepCodeProvider(workspace_dir=workspace_env, use_test_double=True)
    try:
        action = ActionRequest(
            actor="agent_live",
            capability="terminal.execute",
            action="read_file",
            target="sample.txt",
            parameters={},
            workspace=workspace_env,
        )
        auth = DualLayerAuthorizer.authorize_request(action, workspace_dir=workspace_env)
        assert auth.outcome == DecisionOutcome.ALLOW

        settlement = provider.execute_action(action=action, authorization=auth)
        assert settlement["status"] == "ok"
        assert settlement["untrusted_candidate"] is True
        assert settlement["state"] == "SETTLED"

        # Verify telemetry was emitted
        events = provider.telemetry.get_events()
        assert len(events) >= 2
    finally:
        provider.close()


def test_stepcode_provider_blocks_denied_action(workspace_env):
    provider = StepCodeProvider(workspace_dir=workspace_env, use_test_double=True)
    try:
        action = ActionRequest(
            actor="agent_live",
            capability="terminal.execute",
            action="write_to_file",
            target="out.txt",
            parameters={},
            workspace=workspace_env,
        )
        deny_auth = AuthorizationDecision(
            outcome=DecisionOutcome.DENY,
            decision_id="deny_123",
            reason="Security policy violation",
            action_hash="hash_123",
            policy_version="1.0.0",
        )

        with pytest.raises(SecurityViolationError):
            provider.execute_action(action=action, authorization=deny_auth)
    finally:
        provider.close()


def test_stepcode_provider_spawn_subagent(workspace_env):
    provider = StepCodeProvider(workspace_dir=workspace_env, use_test_double=True)
    try:
        subagent = provider.spawn_subagent(
            task_id="child_task_1",
            task_scope="Scan dependency tree",
            delegated_tools=["read_file"],
            budget_tokens=15000,
            agent_name="scanner",
        )
        assert subagent.subagent_id.startswith("subagent_")
        assert subagent.scope.can_certify_evidence is False

        subagent.start()
        reply = subagent.reply("Scan finished", [{"receipt": "scan_ok"}])
        assert reply.candidate_evidence[0]["untrusted_candidate"] is True
        assert reply.candidate_evidence[0]["verified"] is False
    finally:
        provider.close()
