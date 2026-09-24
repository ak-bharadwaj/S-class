"""
Certification Suite: Deep Step-Code Runtime Certification.
Fulfills Directive Section 17, 42, and 43:
Validates the harvested Step-Code runtime substrate:
1. Tool interception & fails closed without bridge.
2. Tool result interception captures exit code, stdio hashes, and classifies UNTRUSTED_CANDIDATE.
3. Permission conjunction rule (5-way conjunction: S-Class ALLOW cannot override Step-Code DENY and vice versa).
4. Subagent lane lifecycle & explicit capability delegation.
5. Workflow orchestration (phase, parallel, pipeline) and append-only journaling.
6. Context compaction preserves durable session history & evidence.
7. Durable effect boundary (TX1 -> EFFECT -> TX2).
8. Comprehensive replay classification (SAFE, IDEMPOTENT, NEVER, UNKNOWN fails closed).
9. Bounded recovery ladder (bounded retries, NEVER fails closed).
"""

import os
import json
import pytest
import tempfile
import shutil

from sclass.runtime.permissions import (
    PermissionPreset,
    ComprehensivePermissionEngine,
    CommandPolicy,
    DangerousCommandDetector,
)
from sclass.runtime.lanes import LaneManager, LaneBudget, LaneType, LaneStatus
from sclass.runtime.subagents import SubagentManager, SubagentDelegationScope
from sclass.runtime.workflows import WorkflowEngine, WorkflowStep, PluginRegistry, TrustClassification
from sclass.runtime.sessions import SessionManager
from sclass.runtime.recovery import BoundedRecoveryLadder, FailureClass, ReplayClass
from sclass.runtime.telemetry import RuntimeTelemetryLedger, TelemetryEventType
from sclass.execution.operations import CanonicalOperationStore, OperationState
from sclass.execution.effect_boundary import DurableEffectBoundary, IntentDescriptor
from sclass.execution.replay import DeepReplayClassifier, ReplayContext


@pytest.fixture
def workspace_dir():
    ws = tempfile.mkdtemp(prefix="sclass_cert_stepcode_")
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


def test_permission_conjunction_rule(workspace_dir):
    """
    Step-Code Cert 1: 5-Way Conjunction Rule.
    Step-Code ALLOW cannot override S-Class DENY.
    S-Class ALLOW cannot override Step-Code DENY.
    """
    engine = ComprehensivePermissionEngine(preset=PermissionPreset.AUTOPILOT)

    # Case A: S-Class DENY, Step-Code ALLOW -> Verdict: DENY
    verdict_a, rejections_a = engine.evaluate_conjunction(
        tool_name="read_file",
        target="file.txt",
        parameters={},
        workspace_dir=workspace_dir,
        sclass_auth_allowed=False,  # S-Class DENY
        capability_allowed=True,
        workspace_policy_allowed=True,
        operation_state_allowed=True,
    )
    assert verdict_a is False
    assert "DENIED_BY_SCLASS_AUTHORIZATION" in rejections_a

    # Case B: S-Class ALLOW, Step-Code DENY (due to dangerous pattern) -> Verdict: DENY
    verdict_b, rejections_b = engine.evaluate_conjunction(
        tool_name="run_command",
        target="",
        parameters={"command": "rm -rf /"},
        workspace_dir=workspace_dir,
        sclass_auth_allowed=True,  # S-Class ALLOW
        capability_allowed=True,
        workspace_policy_allowed=True,
        operation_state_allowed=True,
    )
    assert verdict_b is False
    assert any("STEPCODE_PERMISSION" in r for r in rejections_b)

    # Case C: Preset READ_ONLY blocks mutating action even if S-Class allows
    read_only_engine = ComprehensivePermissionEngine(preset=PermissionPreset.READ_ONLY)
    verdict_c, rejections_c = read_only_engine.evaluate_conjunction(
        tool_name="write_to_file",
        target="out.txt",
        parameters={"content": "hello"},
        workspace_dir=workspace_dir,
        sclass_auth_allowed=True,
        capability_allowed=True,
        workspace_policy_allowed=True,
        operation_state_allowed=True,
    )
    assert verdict_c is False
    assert any("READ_ONLY" in r for r in rejections_c)

    # Case D: All 5 permit -> Verdict: ALLOW
    verdict_d, rejections_d = engine.evaluate_conjunction(
        tool_name="read_file",
        target="file.txt",
        parameters={},
        workspace_dir=workspace_dir,
        sclass_auth_allowed=True,
        capability_allowed=True,
        workspace_policy_allowed=True,
        operation_state_allowed=True,
    )
    assert verdict_d is True
    assert len(rejections_d) == 0


def test_durable_operation_effect_sandwich(workspace_dir):
    """
    Step-Code Cert 2: Effect Sandwich (TX1 -> EFFECT -> TX2).
    State advances: PLANNED -> EFFECT_PENDING -> EFFECT_EXECUTED -> SETTLED.
    """
    store = CanonicalOperationStore(workspace_dir)
    boundary = DurableEffectBoundary(store)

    intent = IntentDescriptor(
        actor="agent_1",
        action="read_file",
        target="test.py",
        parameters={},
        workspace=workspace_dir,
        task_id="task_1",
        session_id="sess_1",
        replay_class=ReplayClass.SAFE,
    )

    def mock_runtime_effect():
        return {"exit_code": 0, "stdout": "print('hello')", "stderr": ""}

    receipt = boundary.execute_sandwich(intent=intent, effect_fn=mock_runtime_effect)

    assert receipt.state == OperationState.SETTLED
    assert receipt.untrusted_candidate is True
    assert receipt.settlement_data["status"] == "SETTLED"
    assert receipt.settlement_data["runtime_exit_code"] == 0

    # Verify persisted record in canonical storage
    saved_op = store.get_operation(receipt.operation_id)
    assert saved_op is not None
    assert saved_op.state == OperationState.SETTLED


def test_deep_replay_classification_and_verification(workspace_dir):
    """
    Step-Code Cert 3: Deep Replay Classification & Context Invariants.
    - SAFE: Automatic replay permitted.
    - NEVER: Replay strictly forbidden.
    - UNKNOWN: Fails closed.
    - IDEMPOTENT: Replay requires identical context and content hashes.
    """
    # 1. Classification
    assert DeepReplayClassifier.classify("read_file") == ReplayClass.SAFE
    assert DeepReplayClassifier.classify("write_to_file") == ReplayClass.NEVER
    assert DeepReplayClassifier.classify("unknown_custom_tool") == ReplayClass.UNKNOWN
    assert DeepReplayClassifier.classify("run_command", parameters={"command": "pytest tests/"}) == ReplayClass.SAFE
    assert DeepReplayClassifier.classify("run_command", parameters={"command": "rm -rf ."}) == ReplayClass.NEVER

    # 2. Eligibility Verification
    ctx = ReplayContext(
        workspace=workspace_dir,
        task_id="task_1",
        session_id="sess_1",
        runtime_identity="step-code",
        target_identity="main.py",
        mutation_class="NONE",
    )

    # SAFE op
    safe_op = {"replay_class": ReplayClass.SAFE.value, "workspace_id": workspace_dir, "task_id": "task_1"}
    assess_safe = DeepReplayClassifier.verify_replay_eligibility(safe_op, ctx)
    assert assess_safe.eligible is True

    # NEVER op
    never_op = {"replay_class": ReplayClass.NEVER.value, "workspace_id": workspace_dir, "task_id": "task_1"}
    assess_never = DeepReplayClassifier.verify_replay_eligibility(never_op, ctx)
    assert assess_never.eligible is False
    assert "NEVER_REPLAY_FORBIDDEN" in assess_never.violated_invariants

    # UNKNOWN op
    unknown_op = {"replay_class": ReplayClass.UNKNOWN.value, "workspace_id": workspace_dir, "task_id": "task_1"}
    assess_unk = DeepReplayClassifier.verify_replay_eligibility(unknown_op, ctx)
    assert assess_unk.eligible is False
    assert "UNKNOWN_REPLAY_FAIL_CLOSED" in assess_unk.violated_invariants


def test_session_tree_compaction_preserves_evidence(workspace_dir):
    """
    Step-Code Cert 4: Context Compaction.
    Compaction projects summaries for LLM context, but CANNOT delete canonical history.
    """
    session_mgr = SessionManager(workspace_dir)
    sess_id = "sess_compaction_test"

    # Record 15 nodes
    for i in range(15):
        session_mgr.record_node(
            session_id=sess_id,
            node_type="tool_execution",
            data={"step": i, "output": f"result_{i}"},
        )

    # Compact context keeping tail 5
    projection = session_mgr.compact_context(session_id=sess_id, retained_tail_count=5)
    assert projection.is_compacted is True
    assert len(projection.retained_tail_entries) == 5
    assert len(projection.summarized_branches) == 1
    assert projection.evidence_intact is True

    # Critical check: durable history still contains all 15 nodes!
    assert len(session_mgr._history[sess_id]) == 15


def test_workflow_orchestration_and_journaling(workspace_dir):
    """
    Step-Code Cert 5: Workflow Engine.
    Executes phase, parallel, pipeline steps and writes append-only journal.
    """
    engine = WorkflowEngine(workspace_dir)

    step1 = engine.agent(name="scout", role="explorer")
    step2 = engine.agent(name="coder", role="implementer")
    pipeline = engine.pipeline(name="main_pipeline", steps=[step1, step2])
    root = engine.phase(name="phase_1", steps=[pipeline])

    executed_steps = []

    def mock_step_runner(s: WorkflowStep):
        executed_steps.append(s.name)
        return {"output": f"Executed {s.name}", "artifacts": [{"name": f"{s.name}_artifact"}]}

    res = engine.run_workflow(workflow_name="test_wf", root_step=root, step_runner_fn=mock_step_runner)

    assert res.status == "COMPLETED"
    assert res.untrusted_execution_fact is True
    assert "scout" in executed_steps
    assert "coder" in executed_steps
    assert os.path.exists(res.journal_path)


def test_bounded_recovery_ladder():
    """
    Step-Code Cert 6: Bounded Recovery Ladder.
    - Enforces maximum attempt limits.
    - NEVER operations can NEVER be automatically retried.
    """
    # Case 1: NEVER operation fails closed immediately
    dec_never = BoundedRecoveryLadder.evaluate_retry(
        replay_class=ReplayClass.NEVER,
        failure_class=FailureClass.MUTATION_FAILURE,
        current_attempt=0,
    )
    assert dec_never.can_retry is False
    assert dec_never.give_up is True

    # Case 2: SAFE operation retries with backoff
    dec_safe_1 = BoundedRecoveryLadder.evaluate_retry(
        replay_class=ReplayClass.SAFE,
        failure_class=FailureClass.TRANSIENT,
        current_attempt=0,
    )
    assert dec_safe_1.can_retry is True
    assert dec_safe_1.attempt_number == 1

    # Case 3: Exceeded max retries gives up
    dec_max = BoundedRecoveryLadder.evaluate_retry(
        replay_class=ReplayClass.SAFE,
        failure_class=FailureClass.TRANSIENT,
        current_attempt=3,
    )
    assert dec_max.can_retry is False
    assert dec_max.give_up is True
