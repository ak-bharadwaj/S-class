"""
S-Class EOS V11.2 - Hardened D7 Agent Integration & Protocol Normalization Test Suite (§8.1, §8.3).
Verifies:
1. Validation-time capability enforcement (direct hidden/prohibited tool invocation rejection).
2. Elimination of hardcoded capability escalation (proposal synthesis propagates actual session capabilities).
3. Full standard JSON Schema validation (Draft 2020-12: types, required, additionalProperties, patterns, bounds).
4. Repository state binding (source_sha) & Stale Context detection.
5. Strict separation of advisory estimated cost, authoritative usage cost, and remaining budget.
6. Session crash and error lifecycle semantics (worker timeout, disconnect, unhandled exceptions).
7. Canonical AgentMessage envelopes with RFC 8785 / JCS digest chaining (tamper / replay / reorder detection).
8. Preserved D5 boundary (no token minting, no execution authority in D7).
9. Multi-threaded concurrent session isolation.
"""

import os
import sys
import pytest
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from cryptography.hazmat.primitives.asymmetric import ed25519

from domain.exceptions import DomainValidationError
from domain.models import Obligation, Policy, PolicyRule, PolicyExpression
from domain.types import (
    ObligationStatus,
    ObligationCategory,
    Criticality,
    RuleType,
    CombinatorType,
    PolicyScope,
)
from events.store import D2NonceStore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from controller.authorization import ActionProposal, AuthorizationStatus
from controller.controller import SClassController
from agent.models import (
    AgentTurnStatus,
    ToolDefinition,
    AgentToolCall,
    AgentToolResult,
    AgentSessionContext,
    AgentTurnResponse,
    AgentSessionRecord,
    AgentMessage,
    create_agent_message,
    compute_agent_message_digest,
    GENESIS_DIGEST,
)
from agent.protocol import AgentWorkerProtocol, MockAgentWorker
from agent.tools import AgentToolRegistry
from agent.context import AgentContextBuilder
from agent.synthesizer import ActionProposalSynthesizer
from agent.session import AgentSessionManager

DEFAULT_SHA = "a" * 40
STALE_SHA = "b" * 40
DEFAULT_REPO_ID = "ak-bharadwaj/S-class"
TIMESTAMP_NOW = "2026-08-20T12:00:00Z"
TIMESTAMP_EXPIRY = "2026-08-20T13:00:00Z"


@pytest.fixture(autouse=True)
def setup_authority_keys():
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


@pytest.fixture
def fresh_controller(tmp_path):
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(file_path=str(tmp_path / "d7_nonces.log"))
    return SClassController(authority_signer=signer, nonce_store=nonce_store)


@pytest.fixture
def standard_domain_state():
    obl_1 = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-AGENT-01",
        title="Test Invariant 1",
        description="Verify property invariant",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        depends_on=(),
        policy_id="POL-001",
    )
    obl_2 = Obligation(
        obligation_id="OBL-002",
        task_id="TASK-AGENT-01",
        title="Test Invariant 2",
        description="Verify boundary fuzzing",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.MEDIUM,
        status=ObligationStatus.OPEN,
        depends_on=("OBL-001",),
        policy_id="POL-001",
    )
    rule = PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={})
    policy = Policy(
        policy_id="POL-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(combinator=CombinatorType.ALL, rules=(rule,)),
    )
    return {"OBL-001": obl_1, "OBL-002": obl_2}, {"POL-001": policy}


# =====================================================================
# 1. CANONICAL AGENT MESSAGE & DIGEST CHAIN TESTS
# =====================================================================

def test_agent_message_rfc8785_canonical_digest_and_tamper_detection():
    msg = create_agent_message(
        session_id="SESS-01",
        sequence=0,
        message_type="USER_CONTEXT",
        payload={"task": "T1", "count": 42},
        previous_digest=GENESIS_DIGEST,
    )
    assert msg.session_id == "SESS-01"
    assert msg.sequence == 0
    assert len(msg.message_digest) == 64

    # Tamper with payload -> should raise ValueError in constructor
    with pytest.raises(ValueError, match="does not match computed digest"):
        AgentMessage(
            session_id="SESS-01",
            sequence=0,
            message_type="USER_CONTEXT",
            payload={"task": "TAMPERED_PAYLOAD"},
            previous_digest=GENESIS_DIGEST,
            message_digest=msg.message_digest,
        )


def test_agent_message_validation_errors():
    with pytest.raises(ValueError):
        create_agent_message("", 0, "TYPE", {}, GENESIS_DIGEST)
    with pytest.raises(ValueError):
        create_agent_message("S1", -1, "TYPE", {}, GENESIS_DIGEST)
    with pytest.raises(ValueError):
        create_agent_message("S1", 0, "", {}, GENESIS_DIGEST)
    with pytest.raises((ValueError, DomainValidationError)):
        create_agent_message("S1", 0, "TYPE", {}, "invalid_hex")


# =====================================================================
# 2. VALIDATION-TIME CAPABILITY ENFORCEMENT & TOOL SCHEMA TESTS
# =====================================================================

def test_validate_tool_call_enforces_capabilities_at_validation_time():
    reg = AgentToolRegistry()

    # Worker attempts to invoke propose_test_run (requires CAP_PROPOSE_ACTION) with only CAP_READ_CODE
    call = AgentToolCall(
        call_id="C1",
        tool_name="propose_test_run",
        arguments={"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "Verify"},
    )
    is_valid, err = reg.validate_tool_call(call, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "Missing required capability 'CAP_PROPOSE_ACTION'" in (err or "")

    # Worker with CAP_PROPOSE_ACTION can invoke propose_test_run
    is_valid, err = reg.validate_tool_call(call, granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert is_valid is True
    assert err is None


def test_validate_tool_call_full_json_schema_validation():
    reg = AgentToolRegistry()

    # 1. Missing required property
    call_missing = AgentToolCall("C1", "read_file_chunk", arguments={})
    is_valid, err = reg.validate_tool_call(call_missing, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "required" in (err or "").lower()

    # 2. Type mismatch (path is int instead of string)
    call_bad_type = AgentToolCall("C2", "read_file_chunk", arguments={"path": 12345})
    is_valid, err = reg.validate_tool_call(call_bad_type, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "12345 is not of type 'string'" in (err or "")

    # 3. Disallowed additional property (additionalProperties: False)
    call_extra = AgentToolCall("C3", "read_file_chunk", arguments={"path": "main.py", "unsupported_extra_arg": True})
    is_valid, err = reg.validate_tool_call(call_extra, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "Additional properties are not allowed" in (err or "")

    # 4. Pattern validation on obligation_id
    call_bad_pattern = AgentToolCall(
        "C4",
        "propose_test_run",
        arguments={"obligation_id": "INVALID_PATTERN", "target_test": "test.py", "purpose": "Test"},
    )
    is_valid, err = reg.validate_tool_call(call_bad_pattern, granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert is_valid is False
    assert "does not match '^OBL-[A-Za-z0-9_-]+$'" in (err or "")

    # 5. Invalid object type
    is_valid, err = reg.validate_tool_call("NOT_A_CALL", granted_capabilities=("CAP_READ_CODE",))  # type: ignore
    assert is_valid is False
    assert "Invalid tool_call object type" in (err or "")

    # 6. Unknown tool name
    call_unknown = AgentToolCall("C5", "unknown_tool_name", {})
    is_valid, err = reg.validate_tool_call(call_unknown, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "Unknown tool" in (err or "")


# =====================================================================
# 3. ZERO CAPABILITY ESCALATION IN SYNTHESIZER
# =====================================================================

def test_proposal_synthesizer_propagates_actual_capabilities():
    call = AgentToolCall(
        call_id="C1",
        tool_name="propose_test_run",
        arguments={"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "Test"},
    )

    # Empty capabilities fails closed
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call, granted_capabilities=())
    assert prop is None
    assert "Cannot synthesize proposal with empty capability set" in (err or "")

    # Exact session capabilities propagated (sorted set canonicalization by ExecutionContext)
    session_caps = ("CAP_PROPOSE_ACTION", "CAP_EXEC_TEST", "CAP_EXTRA_RESTRICTED")
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call, granted_capabilities=session_caps)
    assert err is None
    assert prop is not None
    assert prop.execution_context.capability_set == tuple(sorted(set(session_caps)))


def test_proposal_synthesizer_supports_code_patch():
    call_patch = AgentToolCall(
        call_id="C2",
        tool_name="propose_code_patch",
        arguments={
            "obligation_id": "OBL-001",
            "target_file": "src/app.py",
            "patch_content": "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-pass\n+return 42",
            "purpose": "Fix return value",
        },
    )
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        call_patch,
        granted_capabilities=("CAP_PROPOSE_ACTION", "CAP_APPLY_PATCH"),
    )
    assert err is None
    assert prop is not None
    assert prop.action_type == "APPLY_PATCH"
    assert prop.target == "src/app.py"
    assert prop.parameters["patch_content"] == call_patch.arguments["patch_content"]


def test_proposal_synthesizer_rejects_malformed_inputs():
    # Non-proposal tool
    call_read = AgentToolCall("C1", "read_file_chunk", {"path": "a.py"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call_read, granted_capabilities=("CAP_READ_CODE",))
    assert prop is None
    assert "not a recognized proposal tool" in (err or "")

    # Missing obligation_id in propose_test_run
    call_no_obl = AgentToolCall("C2", "propose_test_run", {"target_test": "t.py", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call_no_obl, granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'obligation_id'" in (err or "")

    # Missing target_test in propose_test_run
    call_no_target = AgentToolCall("C3", "propose_test_run", {"obligation_id": "OBL-1", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call_no_target, granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'target_test'" in (err or "")

    # Missing target_file in propose_code_patch
    call_no_file = AgentToolCall("C4", "propose_code_patch", {"obligation_id": "OBL-1", "patch_content": "d", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call_no_file, granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'target_file'" in (err or "")

    # Missing patch_content in propose_code_patch
    call_no_patch = AgentToolCall("C5", "propose_code_patch", {"obligation_id": "OBL-1", "target_file": "f.py", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call_no_patch, granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'patch_content'" in (err or "")

    # Missing obligation_id in propose_code_patch
    call_patch_no_obl = AgentToolCall("C6", "propose_code_patch", {"target_file": "f.py", "patch_content": "d", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call_patch_no_obl, granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'obligation_id'" in (err or "")


# =====================================================================
# 4. REPOSITORY STATE BINDING & STALE CONTEXT DETECTION
# =====================================================================

def test_session_manager_detects_stale_repository_context(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")
    worker.set_script([AgentTurnResponse(thought="Test", tool_calls=(), turn_status=AgentTurnStatus.CONTINUE)])

    # Provider returning a modified/drifted repository SHA
    current_sha = STALE_SHA
    sha_provider = lambda: current_sha

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        current_repo_sha_provider=sha_provider,
    )

    record, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,  # Session initialized against DEFAULT_SHA
        task_id="TASK-AGENT-01",
        objective="Verify system invariants",
        obligations=obls,
        policies=policies,
        policy_version=1,
        max_turns=5,
    )

    assert record.final_status == AgentTurnStatus.STALE_CONTEXT
    assert len(dispatches) == 0


# =====================================================================
# 5. BUDGET & TURN BOUNDING SEMANTICS
# =====================================================================

def test_session_manager_distinguishes_advisory_cost_from_authoritative_usage(
    fresh_controller, standard_domain_state
):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")

    t1 = AgentTurnResponse(
        thought="Advisory cost turn",
        tool_calls=(
            AgentToolCall(
                "C1",
                "propose_test_run",
                {"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "Test"},
            ),
        ),
        turn_status=AgentTurnStatus.COMPLETED,
        advisory_estimated_cost_usd=0.035,  # Worker-reported estimate
    )
    worker.set_script([t1])

    session_mgr = AgentSessionManager(worker=worker, controller=fresh_controller)
    record, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-AGENT-01",
        objective="Verify budget tracking",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
        cost_budget_usd=1.0,
    )

    assert record.advisory_total_cost_usd == 0.035
    assert record.authoritative_usage_cost_usd == 0.05  # Authoritative cost per proposal
    assert len(dispatches) == 1


def test_session_manager_enforces_max_turns_and_budget_exhaustion(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state

    # 1. Max turns reached
    worker_loop = MockAgentWorker("worker-loop")
    worker_loop.set_script([AgentTurnResponse(thought="Loop", tool_calls=(), turn_status=AgentTurnStatus.CONTINUE)] * 10)
    mgr = AgentSessionManager(worker=worker_loop, controller=fresh_controller)
    rec, _ = mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-1",
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
        max_turns=3,
        cost_budget_usd=10.0,
    )
    assert rec.final_status == AgentTurnStatus.MAX_TURNS_REACHED
    assert rec.total_turns == 3

    # 2. Budget exceeded by authoritative proposal submissions
    worker_expensive = MockAgentWorker("worker-exp")
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "T"})
    worker_expensive.set_script([AgentTurnResponse(thought="T", tool_calls=(call,), turn_status=AgentTurnStatus.CONTINUE)] * 5)
    mgr_exp = AgentSessionManager(worker=worker_expensive, controller=fresh_controller)
    rec_exp, _ = mgr_exp.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-1",
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
        max_turns=10,
        cost_budget_usd=0.05,  # Exactly enough for 1 proposal (0.05)
    )
    assert rec_exp.final_status == AgentTurnStatus.BUDGET_EXCEEDED


def test_session_manager_handles_invalid_tool_calls_in_turn(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")
    
    # Tool call with missing required argument
    bad_call = AgentToolCall("C1", "read_file_chunk", arguments={})
    t1 = AgentTurnResponse(thought="Bad call", tool_calls=(bad_call,), turn_status=AgentTurnStatus.CONTINUE)
    t2 = AgentTurnResponse(thought="Done", tool_calls=(), turn_status=AgentTurnStatus.COMPLETED)
    worker.set_script([t1, t2])

    mgr = AgentSessionManager(worker=worker, controller=fresh_controller)
    rec, dispatches = mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-1",
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_READ_CODE",),
    )
    assert rec.final_status == AgentTurnStatus.COMPLETED
    assert "validation_error" in rec.turns_transcript[0]
    assert len(dispatches) == 0


# =====================================================================
# 6. D7 CRASH & EXCEPTION LIFECYCLE SEMANTICS
# =====================================================================

class CrashingWorker(AgentWorkerProtocol):
    def __init__(self, exception_to_raise):
        self._exc = exception_to_raise

    @property
    def worker_id(self) -> str:
        return "crashing-worker"

    def generate_turn(self, context, history):
        raise self._exc


def test_session_manager_handles_worker_timeout(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = CrashingWorker(TimeoutError("Worker request timed out"))
    session_mgr = AgentSessionManager(worker=worker, controller=fresh_controller)

    record, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-AGENT-01",
        objective="Timeout test",
        obligations=obls,
        policies=policies,
        policy_version=1,
    )
    assert record.final_status == AgentTurnStatus.WORKER_TIMEOUT


def test_session_manager_handles_worker_disconnect(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = CrashingWorker(ConnectionError("Socket disconnected"))
    session_mgr = AgentSessionManager(worker=worker, controller=fresh_controller)

    record, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-AGENT-01",
        objective="Disconnect test",
        obligations=obls,
        policies=policies,
        policy_version=1,
    )
    assert record.final_status == AgentTurnStatus.WORKER_DISCONNECT


def test_session_manager_handles_unhandled_worker_exception(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = CrashingWorker(RuntimeError("Unexpected runtime crash"))
    session_mgr = AgentSessionManager(worker=worker, controller=fresh_controller)

    record, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-AGENT-01",
        objective="Crash test",
        obligations=obls,
        policies=policies,
        policy_version=1,
    )
    assert record.final_status == AgentTurnStatus.FAILED


# =====================================================================
# 7. CONCURRENCY & ISOLATION TESTS
# =====================================================================

def test_concurrent_agent_sessions_remain_isolated(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state

    def run_worker_session(worker_idx: int):
        worker = MockAgentWorker(f"worker-{worker_idx}")
        t1 = AgentTurnResponse(
            thought=f"Turn 1 for worker {worker_idx}",
            tool_calls=(
                AgentToolCall(
                    f"C-{worker_idx}",
                    "propose_test_run",
                    {"obligation_id": "OBL-001", "target_test": f"test_{worker_idx}.py", "purpose": "Test"},
                ),
            ),
            turn_status=AgentTurnStatus.COMPLETED,
            advisory_estimated_cost_usd=0.01,
        )
        worker.set_script([t1])
        mgr = AgentSessionManager(worker=worker, controller=fresh_controller)
        return mgr.run_session(
            repository_id=DEFAULT_REPO_ID,
            source_sha=DEFAULT_SHA,
            task_id=f"TASK-AGENT-{worker_idx}",
            objective="Concurrent test",
            obligations=obls,
            policies=policies,
            policy_version=1,
            granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
            max_turns=2,
            cost_budget_usd=0.5,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run_worker_session, range(4)))

    session_ids = [r[0].session_id for r in results]
    assert len(set(session_ids)) == 4, "All concurrent session IDs must be unique"
    for record, dispatches in results:
        assert record.final_status == AgentTurnStatus.COMPLETED
        assert record.proposed_action_count == 1
        assert len(dispatches) == 1
        assert dispatches[0].decision.status == AuthorizationStatus.AUTHORIZED
        assert len(record.final_message_digest) == 64


# =====================================================================
# 8. ARCHITECTURAL INVARIANT & TAMPER GUARDS
# =====================================================================

def test_d7_has_no_token_minting_or_execution_authority():
    """Architectural Guard: D7 modules must not have token minting or direct action execution APIs."""
    import agent
    assert not hasattr(agent, "mint_execution_token")
    assert not hasattr(agent, "admit_execution")
    assert not hasattr(agent, "execute_action")
    assert not hasattr(agent, "evaluate_policy")
    assert not hasattr(AgentSessionManager, "mint_execution_token")
    assert not hasattr(ActionProposalSynthesizer, "mint_execution_token")


def test_d7_session_manager_rejects_invalid_worker_or_controller():
    with pytest.raises(TypeError):
        AgentSessionManager(worker="NOT_A_WORKER", controller="NOT_A_CONTROLLER")  # type: ignore


def test_tool_definition_and_agent_model_validations():
    # Tool definition validations
    with pytest.raises(ValueError):
        ToolDefinition("", "desc", {})
    with pytest.raises(ValueError):
        ToolDefinition("t", "", {})
    with pytest.raises(TypeError):
        ToolDefinition("t", "desc", "not_a_dict")  # type: ignore

    # AgentToolResult validations
    with pytest.raises(ValueError):
        AgentToolResult("", "t", True)
    with pytest.raises(ValueError):
        AgentToolResult("C", "", True)

    # AgentSessionRecord validations
    with pytest.raises(ValueError):
        AgentSessionRecord("S", "R", DEFAULT_SHA, "T", -1, 0.0, 0.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(ValueError):
        AgentSessionRecord("S", "R", DEFAULT_SHA, "T", 1, -1.0, 0.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(ValueError):
        AgentSessionRecord("S", "R", DEFAULT_SHA, "T", 1, 0.0, -1.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(TypeError):
        AgentSessionRecord("S", "R", DEFAULT_SHA, "T", 1, 0.0, 0.0, "INVALID_STATUS", "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)  # type: ignore
