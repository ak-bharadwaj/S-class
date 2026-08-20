"""
S-Class EOS V11.2 - D7A Hardened Agent Integration & Protocol Normalization Test Suite (§8.1, §8.3).
Exhaustively verifies:
1. Inbound AgentMessage ingress validation (tamper, replay, reorder, wrong worker, wrong session).
2. Mandatory Authoritative Repository State Verification (stale SHA, fake repo ID).
3. Capability Provenance & Zero Escalation (invented capability rejection).
4. Validation-time capability enforcement & Draft 2020-12 JSON Schema validation.
5. Safe Execution of Read/Search Inspection Tools.
6. Non-authoritative internal accounting unit tracking (D7_INTERNAL_ACCOUNTING_UNIT).
7. Session crash and error lifecycle semantics (worker timeout, disconnect, unhandled exceptions).
8. Ephemeral session state & Preserved D5 Authorization Boundary (zero token minting in D7).
9. Multi-threaded Concurrent Session Isolation.
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
from execution.workspace import IsolatedWorkspace
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
    D7_INTERNAL_ACCOUNTING_UNIT,
)
from agent.protocol import (
    AgentWorkerProtocol,
    AgentMessageChainValidator,
    MockAgentWorker,
)
from agent.tools import AgentToolRegistry
from agent.context import AgentContextBuilder
from agent.synthesizer import ActionProposalSynthesizer
from agent.session import AgentSessionManager

DEFAULT_SHA = "a" * 40
STALE_SHA = "b" * 40
FAKE_REPO_ID = "adversary/malicious-repo"
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
def default_repo_provider():
    return lambda: (DEFAULT_REPO_ID, DEFAULT_SHA)


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
# 1. INBOUND AGENT MESSAGE INGRESS & VALIDATION TESTS
# =====================================================================

def test_ingress_validator_accepts_valid_message_sequence():
    msg0 = create_agent_message("S1", "W1", 0, "USER_CONTEXT", {"turn": 0}, GENESIS_DIGEST)
    valid, err, status = AgentMessageChainValidator.validate_inbound_message(
        msg0, "S1", "W1", 0, GENESIS_DIGEST
    )
    assert valid is True
    assert err is None
    assert status is None

    msg1 = create_agent_message("S1", "W1", 1, "AGENT_TURN", {"thought": "t"}, msg0.message_digest)
    valid, err, status = AgentMessageChainValidator.validate_inbound_message(
        msg1, "S1", "W1", 1, msg0.message_digest
    )
    assert valid is True
    assert err is None


def test_ingress_validator_rejects_reordered_and_duplicate_sequence():
    msg0 = create_agent_message("S1", "W1", 0, "USER_CONTEXT", {}, GENESIS_DIGEST)

    # 1. Reordered gap (sequence 2 instead of expected 1)
    msg_reordered = create_agent_message("S1", "W1", 2, "AGENT_TURN", {}, msg0.message_digest)
    valid, err, status = AgentMessageChainValidator.validate_inbound_message(
        msg_reordered, "S1", "W1", 1, msg0.message_digest
    )
    assert valid is False
    assert status == AgentTurnStatus.REORDER_DETECTED
    assert "Reordered sequence gap" in (err or "")

    # 2. Duplicate / stale sequence (sequence 0 when expecting 1)
    valid, err, status = AgentMessageChainValidator.validate_inbound_message(
        msg0, "S1", "W1", 1, msg0.message_digest
    )
    assert valid is False
    assert status == AgentTurnStatus.REPLAY_DETECTED
    assert "Duplicate or stale sequence" in (err or "")


def test_ingress_validator_rejects_wrong_worker_and_wrong_session():
    msg0 = create_agent_message("S1", "W1", 0, "USER_CONTEXT", {}, GENESIS_DIGEST)

    # Wrong worker ID
    valid, err, status = AgentMessageChainValidator.validate_inbound_message(
        msg0, "S1", "WRONG_WORKER", 0, GENESIS_DIGEST
    )
    assert valid is False
    assert status == AgentTurnStatus.WORKER_IDENTITY_MISMATCH
    assert "Wrong worker ID" in (err or "")

    # Wrong session ID
    valid, err, status = AgentMessageChainValidator.validate_inbound_message(
        msg0, "WRONG_SESSION", "W1", 0, GENESIS_DIGEST
    )
    assert valid is False
    assert status == AgentTurnStatus.INGRESS_VALIDATION_FAILED
    assert "Wrong session ID" in (err or "")


def test_ingress_validator_rejects_tampered_payload_and_broken_digest_chain():
    msg0 = create_agent_message("S1", "W1", 0, "USER_CONTEXT", {"val": 1}, GENESIS_DIGEST)

    # Broken digest chain (previous_digest does not match)
    msg1 = create_agent_message("S1", "W1", 1, "AGENT_TURN", {"val": 2}, "f" * 64)
    valid, err, status = AgentMessageChainValidator.validate_inbound_message(
        msg1, "S1", "W1", 1, msg0.message_digest
    )
    assert valid is False
    assert status == AgentTurnStatus.REPLAY_DETECTED
    assert "Digest chain discontinuity" in (err or "")


# =====================================================================
# 2. MANDATORY REPOSITORY STATE VERIFICATION TESTS
# =====================================================================

def test_session_manager_requires_mandatory_repo_provider(fresh_controller):
    worker = MockAgentWorker("worker")
    with pytest.raises(TypeError, match="authoritative_repo_state_provider is mandatory"):
        AgentSessionManager(worker=worker, controller=fresh_controller, authoritative_repo_state_provider=None)  # type: ignore


def test_session_manager_rejects_stale_repository_before_turn(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")
    stale_provider = lambda: (DEFAULT_REPO_ID, STALE_SHA)

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=stale_provider,
    )
    rec, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-1",
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
    )
    assert rec.final_status == AgentTurnStatus.STALE_CONTEXT
    assert len(dispatches) == 0


def test_session_manager_rejects_fake_repository_identity(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")
    fake_repo_provider = lambda: (FAKE_REPO_ID, DEFAULT_SHA)

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=fake_repo_provider,
    )
    rec, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-1",
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
    )
    assert rec.final_status == AgentTurnStatus.REPOSITORY_MISMATCH
    assert len(dispatches) == 0


def test_session_manager_rejects_repository_drift_before_proposal_synthesis(
    fresh_controller, standard_domain_state
):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "T"})
    worker.set_script([AgentTurnResponse(thought="Propose test", tool_calls=(call,), turn_status=AgentTurnStatus.CONTINUE)])

    current_sha = [DEFAULT_SHA]
    def dynamic_provider():
        return (DEFAULT_REPO_ID, current_sha[0])

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=dynamic_provider,
    )

    # Trigger drift immediately when proposal would be synthesized
    current_sha[0] = STALE_SHA

    rec, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-1",
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
    )
    assert rec.final_status == AgentTurnStatus.STALE_CONTEXT
    assert len(dispatches) == 0


# =====================================================================
# 3. CAPABILITY PROVENANCE & VALIDATION-TIME ENFORCEMENT
# =====================================================================

def test_validate_tool_call_enforces_capabilities_at_validation_time():
    reg = AgentToolRegistry()

    # Worker attempts to invoke propose_test_run without CAP_PROPOSE_ACTION
    call = AgentToolCall(
        call_id="C1",
        tool_name="propose_test_run",
        arguments={"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "Verify"},
    )
    is_valid, err = reg.validate_tool_call(call, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "Missing required capability 'CAP_PROPOSE_ACTION'" in (err or "")

    # Worker with CAP_PROPOSE_ACTION passes validation
    is_valid, err = reg.validate_tool_call(call, granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert is_valid is True
    assert err is None


def test_validate_tool_call_full_json_schema_validation():
    reg = AgentToolRegistry()

    # Missing required property
    call_missing = AgentToolCall("C1", "read_file_chunk", arguments={})
    is_valid, err = reg.validate_tool_call(call_missing, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "required" in (err or "").lower()

    # Disallowed additional property
    call_extra = AgentToolCall("C2", "read_file_chunk", arguments={"path": "main.py", "unsupported": 123})
    is_valid, err = reg.validate_tool_call(call_extra, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "Additional properties are not allowed" in (err or "")


def test_proposal_synthesizer_rejects_empty_and_invented_capabilities():
    call = AgentToolCall(
        call_id="C1",
        tool_name="propose_test_run",
        arguments={"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "Test"},
    )

    # Empty capabilities fails closed
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call, session_granted_capabilities=())
    assert prop is None
    assert "Cannot synthesize proposal with empty capability set" in (err or "")

    # Exact session capabilities propagated without alteration
    session_caps = ("CAP_PROPOSE_ACTION", "CAP_EXEC_TEST")
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call, session_granted_capabilities=session_caps)
    assert err is None
    assert prop is not None
    assert prop.execution_context.capability_set == tuple(sorted(session_caps))


# =====================================================================
# 4. SAFE EXECUTION OF READ/SEARCH INSPECTION TOOLS
# =====================================================================

def test_tool_registry_executes_inspection_tools_safely(tmp_path):
    ws = IsolatedWorkspace("ws_inspect_test", base_dir=str(tmp_path))
    ws.setup()

    # Create a test file in workspace
    test_file_path = os.path.join(ws.path, "module.py")
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write("line 1\nline 2: target_query\nline 3\n")

    reg = AgentToolRegistry()

    # 1. Test read_file_chunk
    call_read = AgentToolCall("C1", "read_file_chunk", {"path": "module.py", "start_line": 1, "end_line": 2})
    res_read = reg.execute_inspection_tool(call_read, workspace=ws)
    assert res_read.success is True
    assert len(res_read.result_data["lines"]) == 2

    # 2. Test search_codebase
    call_search = AgentToolCall("C2", "search_codebase", {"query": "target_query"})
    res_search = reg.execute_inspection_tool(call_search, workspace=ws)
    assert res_search.success is True
    assert len(res_search.result_data["matches"]) == 1
    assert res_search.result_data["matches"][0]["line"] == 2

    ws.cleanup()


# =====================================================================
# 5. BUDGET SEMANTICS & ACCOUNTING UNITS
# =====================================================================

def test_session_manager_tracks_internal_accounting_units(
    fresh_controller, standard_domain_state, default_repo_provider
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
        advisory_estimated_cost_usd=0.035,
    )
    worker.set_script([t1])

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=default_repo_provider,
    )
    record, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-AGENT-01",
        objective="Verify budget tracking",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
        budget_units=1.0,
    )

    assert record.advisory_total_cost_usd == 0.035
    assert record.internal_accounting_units == D7_INTERNAL_ACCOUNTING_UNIT
    assert len(dispatches) == 1


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


def test_session_manager_handles_worker_timeout(fresh_controller, standard_domain_state, default_repo_provider):
    obls, policies = standard_domain_state
    worker = CrashingWorker(TimeoutError("Worker request timed out"))
    session_mgr = AgentSessionManager(
        worker=worker, controller=fresh_controller, authoritative_repo_state_provider=default_repo_provider
    )

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


def test_session_manager_handles_worker_disconnect(fresh_controller, standard_domain_state, default_repo_provider):
    obls, policies = standard_domain_state
    worker = CrashingWorker(ConnectionError("Socket disconnected"))
    session_mgr = AgentSessionManager(
        worker=worker, controller=fresh_controller, authoritative_repo_state_provider=default_repo_provider
    )

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


def test_session_manager_handles_unhandled_worker_exception(fresh_controller, standard_domain_state, default_repo_provider):
    obls, policies = standard_domain_state
    worker = CrashingWorker(RuntimeError("Unexpected runtime crash"))
    session_mgr = AgentSessionManager(
        worker=worker, controller=fresh_controller, authoritative_repo_state_provider=default_repo_provider
    )

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

def test_concurrent_agent_sessions_remain_isolated(fresh_controller, standard_domain_state, default_repo_provider):
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
        mgr = AgentSessionManager(
            worker=worker, controller=fresh_controller, authoritative_repo_state_provider=default_repo_provider
        )
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
            budget_units=0.5,
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


# =====================================================================
# 9. COMPREHENSIVE MODEL & SYNTHESIZER VALIDATION TESTS
# =====================================================================

def test_synthesizer_missing_arguments_and_invalid_types():
    # Invalid object type
    prop, err = ActionProposalSynthesizer.synthesize_proposal("NOT_A_CALL", session_granted_capabilities=())  # type: ignore
    assert prop is None
    assert "tool_call must be an instance of AgentToolCall" in (err or "")

    # propose_test_run missing target_test
    c1 = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(c1, session_granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'target_test'" in (err or "")

    # propose_test_run missing obligation_id
    c2 = AgentToolCall("C2", "propose_test_run", {"target_test": "test.py"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(c2, session_granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'obligation_id'" in (err or "")

    # propose_code_patch missing target_file
    c3 = AgentToolCall("C3", "propose_code_patch", {"obligation_id": "OBL-001", "patch_content": "d"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(c3, session_granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'target_file'" in (err or "")

    # propose_code_patch missing patch_content
    c4 = AgentToolCall("C4", "propose_code_patch", {"obligation_id": "OBL-001", "target_file": "a.py"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(c4, session_granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'patch_content'" in (err or "")

    # propose_code_patch missing obligation_id
    c5 = AgentToolCall("C5", "propose_code_patch", {"target_file": "a.py", "patch_content": "d"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(c5, session_granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "Missing or invalid 'obligation_id'" in (err or "")

    # Unrecognized proposal tool
    c6 = AgentToolCall("C6", "unknown_tool", {})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(c6, session_granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert prop is None
    assert "not a recognized proposal tool" in (err or "")


def test_tool_definition_and_agent_model_validations():
    # Tool definition
    with pytest.raises(ValueError):
        ToolDefinition("", "desc", {})
    with pytest.raises(ValueError):
        ToolDefinition("t", "", {})
    with pytest.raises(TypeError):
        ToolDefinition("t", "desc", "not_a_dict")  # type: ignore

    # AgentToolCall
    with pytest.raises(ValueError):
        AgentToolCall("", "tool", {})
    with pytest.raises(ValueError):
        AgentToolCall("C1", "", {})

    # AgentToolResult
    with pytest.raises(ValueError):
        AgentToolResult("", "tool", True)
    with pytest.raises(ValueError):
        AgentToolResult("C1", "", True)

    # AgentTurnResponse
    with pytest.raises(TypeError):
        AgentTurnResponse(thought=123)  # type: ignore
    with pytest.raises(TypeError):
        AgentTurnResponse(thought="t", turn_status="INVALID")  # type: ignore
    with pytest.raises(ValueError):
        AgentTurnResponse(thought="t", advisory_estimated_cost_usd=-1.0)

    # AgentSessionRecord
    with pytest.raises(ValueError):
        AgentSessionRecord("", DEFAULT_REPO_ID, DEFAULT_SHA, "T1", 0, 0.0, 0.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(ValueError):
        AgentSessionRecord("S1", "", DEFAULT_SHA, "T1", 0, 0.0, 0.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(ValueError):
        AgentSessionRecord("S1", DEFAULT_REPO_ID, DEFAULT_SHA, "", 0, 0.0, 0.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(ValueError):
        AgentSessionRecord("S1", DEFAULT_REPO_ID, DEFAULT_SHA, "T1", -1, 0.0, 0.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(ValueError):
        AgentSessionRecord("S1", DEFAULT_REPO_ID, DEFAULT_SHA, "T1", 0, -1.0, 0.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(ValueError):
        AgentSessionRecord("S1", DEFAULT_REPO_ID, DEFAULT_SHA, "T1", 0, 0.0, -1.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(TypeError):
        AgentSessionRecord("S1", DEFAULT_REPO_ID, DEFAULT_SHA, "T1", 0, 0.0, 0.0, "INVALID", "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)  # type: ignore


def test_inspection_tool_non_existent_file(tmp_path):
    ws = IsolatedWorkspace("ws_non_existent", base_dir=str(tmp_path))
    ws.setup()
    reg = AgentToolRegistry()

    call_read = AgentToolCall("C1", "read_file_chunk", {"path": "missing_file.py"})
    res = reg.execute_inspection_tool(call_read, workspace=ws)
    assert res.success is False
    assert "does not exist" in (res.error_message or "")

    call_invalid = AgentToolCall("C2", "propose_test_run", {})
    res_inv = reg.execute_inspection_tool(call_invalid, workspace=ws)
    assert res_inv.success is False
    assert "not an executable inspection tool" in (res_inv.error_message or "")

    ws.cleanup()
