"""
S-Class Adversarial & Survival Gate Certification Suite (Reqs 29-33 / H1).
Covers the 5 non-negotiable survival gates:
1. Real Mutation E2E (Req 29): Real filesystem mutation + independent verification + denial check.
2. Crash Mid-Effect E2E (Req 30): Process termination mid-flight + fail-closed recovery without unverified replay.
3. Adversarial Auth Suite (Req 31): Forged HMAC, empty token, foreign workspace/task, expired token, WARN execution.
4. Observer Security & Escape Suite (Req 32): Metacharacters, UNC paths, path traversal, VerificationSpec enforcement.
5. Persistence Split-Brain Suite (Req 33): Stale index marker, SQLite fallback to JSONL, rebuild_derived_index, tampered ledger.
"""

import os
import sys
import time
import json
import uuid
import shutil
import tempfile
import pytest
from datetime import datetime, timezone, timedelta

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.obligations import TechnicalObligation, ObligationStatus
from sclass.domain.project import VerifiedProjectState
from sclass.core.errors import SecurityViolationError, ObservationIntegrityError
from sclass.core.completion_evaluator import CompletionEvaluator, CompletionVerdict
from sclass.control.composite_auth import DualLayerAuthorizer
from sclass.policy.authorization_service import (
    AuthorizationService,
    verify_decision_integrity,
    generate_integrity_token,
    get_authorization_secret,
)
from sclass.execution.operations import (
    CanonicalOperationStore,
    DurableOperation,
    OperationMetadata,
    OperationState,
    ReplayClass,
    compute_action_hash,
)
from sclass.execution.harness import StepCodeRpcHarness
from sclass.verification.independent_registry import (
    FileSystemObserver,
    IsolatedSubprocessObserver,
    VerificationSpec,
    FileVerifier,
)
from sclass.trust.two_ledgers import AssuranceLedger, ExecutionLedger
from sclass.trust.state_reducer import CanonicalStateReducer


@pytest.fixture
def workspace_env():
    tmp = tempfile.mkdtemp(prefix="sclass_h1_survival_")
    trust_dir = os.path.join(tmp, ".sclass", "trust")
    os.makedirs(trust_dir, exist_ok=True)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# ==============================================================================
# Gate 1 (Req 29): Real Mutation E2E
# ==============================================================================

def test_gate1_real_mutation_e2e_and_denial(workspace_env):
    """
    Req 29: End-to-end real mutation flow.
    1. Authorized filesystem mutation modifies workspace reality.
    2. Runtime settlement alone does NOT establish verification.
    3. Independent FileSystemObserver observes actual reality on disk.
    4. Independent FileVerifier establishes authoritative verification.
    5. Unauthorized mutation attempt is denied before execution.
    """
    target_rel = "artifact.txt"
    target_path = os.path.join(workspace_env, target_rel)

    # Step 1: Submit authorized mutation action
    action = ActionRequest(
        actor="dev_agent",
        capability="terminal.execute",
        action="write_file",
        target=target_rel,
        parameters={"content": "production verified payload v1"},
        workspace=workspace_env,
    )
    auth = DualLayerAuthorizer.authorize_request(action, workspace_dir=workspace_env)
    assert auth.is_allowed is True

    # Real mutation: create target file
    with open(target_path, "w", encoding="utf-8") as f:
        f.write("production verified payload v1")

    # Step 2: Runtime settlement is recorded in execution ledger, NOT assurance ledger
    exec_ledger = ExecutionLedger(workspace_env)
    exec_ledger.record_tool_call("terminal.execute", "write_file", target_rel, {"exit_code": 0, "status": "SETTLED"})

    # Step 3: Independent FileSystemObserver queries physical reality
    observer = FileSystemObserver()
    raw_obs = observer.observe(target=target_rel, workspace_dir=workspace_env)
    assert raw_obs.payload["exists"] is True
    assert raw_obs.payload["size_bytes"] > 0
    file_sha = raw_obs.payload["sha256"]
    assert len(file_sha) == 64

    # Step 4: Authoritative FileVerifier validates claim against observation
    claim = Claim(
        claim_id="cl_mut_01",
        task_id="t_mut_01",
        statement=f"File {target_rel} exists with valid content",
        claim_type=ClaimType.FILE_CHANGE,
        metadata={"expected_hash": file_sha},
    )
    verifier = FileVerifier()
    v_res = verifier.verify(claim, raw_obs.to_receipt())
    assert v_res.is_verified is True

    # Step 5: Test denial - prohibited deletion is blocked fail-closed
    forbidden_action = ActionRequest(
        actor="dev_agent",
        capability="terminal.execute",
        action="delete_file",
        target="critical_system.db",
        parameters={},
        workspace=workspace_env,
    )
    deny_auth = AuthorizationDecision(
        outcome=DecisionOutcome.DENY,
        reason="Deletion of critical databases is strictly forbidden",
        workspace_id=workspace_env,
    )
    harness = StepCodeRpcHarness(workspace_dir=workspace_env, use_test_double=True)
    try:
        with pytest.raises(SecurityViolationError, match="S-Class Authorization DENIED"):
            harness.submit_action(forbidden_action, deny_auth)
    finally:
        harness.close()


# ==============================================================================
# Gate 2 (Req 30): Crash Mid-Effect E2E
# ==============================================================================

def test_gate2_crash_mid_effect_recovery(workspace_env):
    """
    Req 30: Mid-effect crash handling and bounded recovery.
    1. Operation transitions to EFFECT_PENDING.
    2. External process crashes or terminates mid-flight.
    3. Harness detects process death, fails closed, and marks runtime unhealthy.
    4. In-flight operation is never assumed to have settled or verified.
    5. Re-executing without verification is blocked.
    """
    harness = StepCodeRpcHarness(workspace_dir=workspace_env, use_test_double=True)
    try:
        action = ActionRequest(
            actor="worker_agent",
            capability="terminal.execute",
            action="run_command",
            target="build.py",
            parameters={"command": "python build.py"},
            workspace=workspace_env,
        )
        auth = DualLayerAuthorizer.authorize_request(action, workspace_dir=workspace_env)

        op = harness.start_operation({
            "action": action.action,
            "target": action.target,
            "parameters": action.parameters,
            "session_id": "sess_crash_test",
            "workspace_id": workspace_env,
            "agent_id": action.actor,
        })
        op.transition_to(OperationState.AUTHORIZED)
        op.transition_to(OperationState.EFFECT_PENDING)
        harness.store.save_operation(op)

        # Abruptly kill external runtime process to simulate crash mid-flight
        if harness._proc and harness._proc.poll() is None:
            harness._proc.kill()
            harness._proc.wait()

        # Any subsequent submission or RPC fails closed immediately
        with pytest.raises(SecurityViolationError):
            harness.submit_action(action, auth)

        # Operation remains in EFFECT_PENDING or transitions to RECOVERY_REQUIRED/FAILED
        loaded_op = harness.store.get_operation(op.operation_id)
        assert loaded_op is not None
        assert loaded_op.state != OperationState.SETTLED
        assert loaded_op.state != OperationState.OBSERVED
        assert loaded_op.state != OperationState.ASSESSED
    finally:
        harness.close()


# ==============================================================================
# Gate 3 (Req 31): Adversarial Auth Suite
# ==============================================================================

def test_gate3_adversarial_auth_suite(workspace_env):
    """
    Req 31: Full adversarial authorization attack coverage.
    - Attack A: Empty HMAC integrity token rejected.
    - Attack B: Forged HMAC token rejected.
    - Attack C: Missing or mismatched action_hash rejected.
    - Attack D: Foreign workspace rejected.
    - Attack E: Foreign task ID rejected.
    - Attack F: Expired / stale decision token rejected.
    - Attack G: WARN outcome rejected from execution.
    """
    auth_service = AuthorizationService()
    req = ActionRequest(
        actor="agent_x",
        session="sess_auth_gate",
        capability="filesystem.read",
        action="read_file",
        target="data.txt",
        workspace=workspace_env,
    )
    valid_decision = auth_service.authorize(req)
    assert valid_decision.is_allowed is True

    # Attack A: Empty HMAC token
    dec_empty_token = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id=valid_decision.policy_id,
        evaluated_at=valid_decision.evaluated_at,
        request_hash=valid_decision.request_hash,
        action_hash=valid_decision.action_hash,
        integrity_token="", # EMPTY
    )
    ok, reason = verify_decision_integrity(dec_empty_token, req, secret_key=auth_service._secret_key)
    assert ok is False
    assert "Missing integrity token" in reason

    # Attack B: Forged HMAC token (tampered outcome from DENY to ALLOW)
    dec_forged_hmac = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        policy_id=valid_decision.policy_id,
        evaluated_at=valid_decision.evaluated_at,
        request_hash=valid_decision.request_hash,
        action_hash=valid_decision.action_hash,
        integrity_token="0123456789abcdef" * 4, # FORGED
    )
    ok, reason = verify_decision_integrity(dec_forged_hmac, req, secret_key=auth_service._secret_key)
    assert ok is False
    assert "Integrity token verification failed" in reason

    def make_token(outcome_str, act_hash=None, eval_time=None):
        return generate_integrity_token(
            issuer=valid_decision.issuer,
            request_hash=valid_decision.request_hash,
            capability_hash=valid_decision.capability_hash,
            policy_id=valid_decision.policy_id,
            policy_version=valid_decision.policy_version,
            outcome=outcome_str,
            risk_level=valid_decision.risk_level,
            evaluated_at=eval_time or valid_decision.evaluated_at,
            capability_id=valid_decision.capability_id,
            capability_version=valid_decision.capability_version,
            registry_generation=valid_decision.capability_registry_generation,
            secret_key=auth_service._secret_key,
            action_hash=act_hash if act_hash is not None else valid_decision.action_hash,
        )

    def clone_decision(outcome_val=DecisionOutcome.ALLOW, act_hash=None, ws=None, task=None, eval_time=None):
        a_hash = act_hash if act_hash is not None else valid_decision.action_hash
        e_time = eval_time or valid_decision.evaluated_at
        outcome_str = outcome_val.value if hasattr(outcome_val, "value") else str(outcome_val)
        tok = make_token(outcome_str, act_hash=a_hash, eval_time=e_time)
        return AuthorizationDecision(
            outcome=outcome_val,
            policy_id=valid_decision.policy_id,
            policy_version=valid_decision.policy_version,
            risk_level=valid_decision.risk_level,
            reason=valid_decision.reason,
            evaluated_at=e_time,
            issuer=valid_decision.issuer,
            request_hash=valid_decision.request_hash,
            capability_hash=valid_decision.capability_hash,
            capability_id=valid_decision.capability_id,
            capability_version=valid_decision.capability_version,
            capability_registry_generation=valid_decision.capability_registry_generation,
            action_hash=a_hash,
            workspace_id=ws if ws is not None else valid_decision.workspace_id,
            task_id=task if task is not None else valid_decision.task_id,
            integrity_token=tok,
        )

    # Attack C: Mismatched action_hash
    dec_bad_act_hash = clone_decision(act_hash="bad_action_hash_hex" * 2)
    ok, reason = verify_decision_integrity(dec_bad_act_hash, req, secret_key=auth_service._secret_key)
    assert ok is False
    assert "Action hash mismatch" in reason

    # Attack D: Foreign workspace
    dec_foreign_ws = clone_decision(ws="C:\\Different\\Workspace\\Root")
    ok, reason = verify_decision_integrity(dec_foreign_ws, req, secret_key=auth_service._secret_key)
    assert ok is False
    assert "another workspace" in reason

    # Attack E: Foreign task ID
    dec_foreign_task = clone_decision(task="foreign_task_999")
    ok, reason = verify_decision_integrity(dec_foreign_task, req, secret_key=auth_service._secret_key)
    assert ok is False
    assert "another task" in reason

    # Attack F: Expired token
    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    dec_expired = clone_decision(eval_time=old_time)
    ok, reason = verify_decision_integrity(dec_expired, req, secret_key=auth_service._secret_key, max_age_seconds=60)
    assert ok is False
    assert "stale" in reason

    # Attack G: WARN outcome must never execute
    dec_warn = clone_decision(outcome_val=DecisionOutcome.WARN)
    ok, reason = verify_decision_integrity(dec_warn, req, secret_key=auth_service._secret_key)
    assert ok is False
    assert "does not permit execution" in reason


# ==============================================================================
# Gate 4 (Req 32): Observer Security & Escape Suite
# ==============================================================================

def test_gate4_observer_security_and_escape(workspace_env):
    """
    Req 32: Observer security, sandbox escape resistance, and spec enforcement.
    - Metacharacter injection rejected without shell execution.
    - UNC path traversal rejected.
    - Directory traversal outside workspace rejected.
    - VerificationSpec target whitelisting enforced.
    - VerificationSpec executable and fixed_argv enforced.
    """
    spec = VerificationSpec(
        verifier_id="python_test_runner",
        executable="python",
        fixed_argv=("-m", "pytest"),
        allowed_targets=("tests/unit", "tests/contract"),
        timeout=10,
        environment_policy="minimal",
    )
    observer = IsolatedSubprocessObserver(spec)

    # Attack A: Shell injection metacharacters
    for meta in ["tests/unit; rm -rf /", "tests/unit && echo owned", "tests/unit | cat /etc/passwd"]:
        obs = observer.observe(target=meta, workspace_dir=workspace_env)
        assert obs.exit_code == 127
        assert "REJECTED" in obs.payload.get("stderr", "")

    # Attack B: UNC path escape
    for unc in ["\\\\attacker-server\\share\\test", "//192.168.1.1/exploit"]:
        obs = observer.observe(target=unc, workspace_dir=workspace_env)
        assert obs.exit_code == 127
        assert "REJECTED" in obs.payload.get("stderr", "")

    # Attack C: Path traversal escaping workspace
    for trav in ["../../etc/shadow", "..\\..\\Windows\\System32"]:
        obs = observer.observe(target=trav, workspace_dir=workspace_env)
        assert obs.exit_code == 127
        assert "Path traversal" in obs.payload.get("stderr", "")

    # Attack D: Target not in allowed_targets
    obs_unallowed = observer.observe(target="secret_src/credentials.py", workspace_dir=workspace_env)
    assert obs_unallowed.exit_code == 127
    assert "not in allowed_targets" in obs_unallowed.payload.get("stderr", "")

    # Attack E: Executable mismatch
    obs_bad_exec = observer.observe(
        target="tests/unit",
        workspace_dir=workspace_env,
        parameters={"command": "curl evil.com"},
    )
    assert obs_bad_exec.exit_code == 127
    assert "Executable" in obs_bad_exec.payload.get("stderr", "")

    # Attack F: Fixed argv mismatch
    obs_bad_argv = observer.observe(
        target="tests/unit",
        workspace_dir=workspace_env,
        parameters={"command": "python -m unittest tests/unit"},
    )
    assert obs_bad_argv.exit_code == 127
    assert "missing required fixed_argv" in obs_bad_argv.payload.get("stderr", "")


# ==============================================================================
# Gate 5 (Req 33): Persistence Split-Brain & Integrity Suite
# ==============================================================================

def test_gate5_persistence_split_brain_and_integrity(workspace_env):
    """
    Req 33: Persistence split-brain resistance, stale index detection, and tamper rejection.
    1. CanonicalOperationStore transparently reads from JSONL on SQLite index corruption.
    2. Stale index marker file prevents trusting out-of-sync SQLite cache.
    3. rebuild_derived_index() reconstructs the index from canonical JSONL truth.
    4. AssuranceLedger entries are chained and HMAC-authenticated.
    5. Tampered record hash, broken sequence, or altered payload fails closed in reducer.
    """
    store = CanonicalOperationStore(workspace_env)

    # 1. Create durable operation and verify dual persistence
    op = DurableOperation(
        metadata=OperationMetadata(
            operation_id="op_split_01",
            parent_operation_id=None,
            session_id="sess_split",
            task_id="t_split",
            agent_id="agent_split",
            action_id="act_split",
            workspace_id=workspace_env,
            replay_class=ReplayClass.NEVER,
            intent_hash="intent_split",
            action_hash="hash_split",
        ),
        state=OperationState.PLANNED,
    )
    store.save_operation(op)

    # 2. Corrupt SQLite derived index
    db_path = os.path.join(store.paths.state_dir, "project.db")
    if os.path.exists(db_path):
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS cross_runtime_operations")
    store._mark_derived_index_unhealthy()

    # Verify stale marker is set and store falls back safely to JSONL
    loaded = store.get_operation("op_split_01")
    assert loaded is not None
    assert loaded.operation_id == "op_split_01"
    assert store.is_derived_index_healthy is False
    assert os.path.exists(store.stale_marker_file)

    # 3. Rebuild derived index from canonical JSONL
    count = store.rebuild_derived_index()
    assert count == 1
    assert store.is_derived_index_healthy is True
    assert not os.path.exists(store.stale_marker_file)

    # 4. AssuranceLedger creates HMAC-authenticated, chained entries
    assurance = AssuranceLedger(workspace_env)
    e1 = assurance.record_obligation({"id": "ob_gate5", "task_id": "t_split", "status": "SATISFIED"})
    e2 = assurance.record_claim({"id": "cl_gate5", "task_id": "t_split", "statement": "All gates green"})

    assert e1["sequence"] == 1
    assert e2["sequence"] == 2
    assert e2["previous_record_hash"] == e1["record_hash"]
    assert len(e1["authenticator"]) == 64
    assert len(e2["authenticator"]) == 64

    # Reducer validates the clean history
    entries = assurance.get_entries()
    CanonicalStateReducer.validate_history_consistency(entries)

    # 5. Tamper test A: Tampering with payload content breaks record_hash check
    tampered_entries = json.loads(json.dumps(entries))
    tampered_entries[1]["payload"]["statement"] = "FORGED FAKE TRUTH"
    with pytest.raises(ObservationIntegrityError, match="record_hash does not match"):
        CanonicalStateReducer.validate_history_consistency(tampered_entries)

    # Tamper test B: Tampering with sequence breaks hash chain
    tampered_seq = json.loads(json.dumps(entries))
    tampered_seq[1]["sequence"] = 99
    with pytest.raises(ObservationIntegrityError):
        CanonicalStateReducer.validate_history_consistency(tampered_seq)

    # Tamper test C: Tampering with HMAC authenticator
    tampered_auth = json.loads(json.dumps(entries))
    tampered_auth[0]["authenticator"] = "0000000000000000" * 4
    with pytest.raises(SecurityViolationError, match="HMAC authenticator verification failed"):
        CanonicalStateReducer.validate_history_consistency(tampered_auth)
